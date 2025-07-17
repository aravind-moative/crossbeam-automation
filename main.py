import requests
import json
import time
import threading
from fastapi import FastAPI, Request, Form
from typing import Dict
from contextlib import asynccontextmanager
from scripts.llm_utils import GeminiMessageGenerator
from scripts.overlap_utils import (
    load_crossbeam_data,
    prospect_score,
    partner_score,
    get_logo_potential,
    get_partner_champion_flag,
    OverlapQualifier
)
from fastapi.responses import JSONResponse
import os

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

app = FastAPI()

# Load internal team config
with open("data/we.json", "r") as f:
    INTERNAL_TEAM = json.load(f)

# Initialize overlap tracking by record_id
resolved_state: Dict[str, bool] = {}
state_lock = threading.Lock()
message_count: Dict[str, int] = {}
escalation_state: Dict[str, int] = {}
gemini_generator = GeminiMessageGenerator()
mail_crafting_in_progress: Dict[str, bool] = {}

# Add a new dictionary to track who resolved each overlap
resolved_by: Dict[str, str] = {}

# Initialize the qualifier
overlap_qualifier = OverlapQualifier()

def send_slack_message(webhook_url, channel_id, text, username="Moat", icon_emoji=":ghost:"):
    payload = {
        "channel": channel_id,
        "username": username,
        "text": text,
        "icon_emoji": icon_emoji
    }
    response = requests.post(webhook_url, json=payload)
    if response.status_code != 200:
        print(f"Request to Slack returned error {response.status_code}, the response is:\n{response.text}")
    else:
        print("Message sent successfully!")

def send_slack_message_with_button(webhook_url, channel_id, text, action_url, record_id, username="Moat", icon_emoji=":ghost:"):
    payload = {
        "channel": channel_id,
        "username": username,
        "icon_emoji": icon_emoji,
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "RESOLVE"},
                        "action_id": "resolve_overlap",
                        "value": record_id
                    }
                ]
            }
        ]
    }
    response = requests.post(webhook_url, json=payload)
    if response.status_code != 200:
        print(f"Request to Slack returned error {response.status_code}, the response is:\n{response.text}")
    else:
        print("Message with button sent successfully!")

def get_hierarchy_designations(internal_team):
    # Build a mapping of hierarchy level (as str) to designation from the internal team config
    designations = {}
    for member in internal_team.values():
        if isinstance(member, dict):
            level = str(member.get("hierarchy"))
            designation = member.get("designation")
            if level and designation and level not in designations:
                designations[level] = designation
    return designations

def send_messages_with_gap(record_id: str, overlap_context: dict):
    # Find the relevant overlap record by record_id from synthetic data
    overlap_record = overlap_qualifier.get_enhanced_record(record_id)
    if not overlap_record:
        print(f"No overlap record found for record_id '{record_id}'.")
        return
    
    record_name = overlap_record.get("record_name", "Unknown Account")
    partner_record_name = overlap_record.get("partner_record_name", "Unknown Partner")
    partner_company_type = overlap_record.get("partner_record_company_type", "Unknown")
    
    # Action URL for the OKAY button
    action_url = f"https://65371c2620e0.ngrok-free.app/resolve_overlap"

    # HIERARCHY 1: Send 3 messages (Main + 2 follow-ups)
    print(f"🎯 Starting HIERARCHY 1 for {record_id} ({record_name} ↔ {partner_record_name})")
    
    # Send main message to Hierarchy 1
    send_message_to_hierarchy(record_id, record_name, partner_record_name, partner_company_type, 
                             overlap_context, 1, "main", action_url)
    time.sleep(10)
    
    # Check if resolved
    if resolved_state.get(record_id):
        print(f"✅ Overlap resolved for {record_id} at Hierarchy 1")
        return
    
    # Send follow-up 1 to Hierarchy 1
    send_message_to_hierarchy(record_id, record_name, partner_record_name, partner_company_type, 
                             overlap_context, 1, "followup1", action_url)
    time.sleep(10)
    
    # Check if resolved
    if resolved_state.get(record_id):
        print(f"✅ Overlap resolved for {record_id} at Hierarchy 1")
        return
    
    # Send follow-up 2 to Hierarchy 1
    send_message_to_hierarchy(record_id, record_name, partner_record_name, partner_company_type, 
                             overlap_context, 1, "followup2", action_url)
    time.sleep(10)
    
    # Check if resolved
    if resolved_state.get(record_id):
        print(f"✅ Overlap resolved for {record_id} at Hierarchy 1")
        return
    
    # HIERARCHY 2: Send 2 messages (Main + 1 follow-up)
    print(f"🔄 Escalating to HIERARCHY 2 for {record_id}")
    
    # Send main message to Hierarchy 2
    send_message_to_hierarchy(record_id, record_name, partner_record_name, partner_company_type, 
                             overlap_context, 2, "main", action_url)
    time.sleep(10)
    
    # Check if resolved
    if resolved_state.get(record_id):
        print(f"✅ Overlap resolved for {record_id} at Hierarchy 2")
        return
    
    # Send follow-up to Hierarchy 2
    send_message_to_hierarchy(record_id, record_name, partner_record_name, partner_company_type, 
                             overlap_context, 2, "followup1", action_url)
    time.sleep(10)
    
    # Check if resolved
    if resolved_state.get(record_id):
        print(f"✅ Overlap resolved for {record_id} at Hierarchy 2")
        return
    
    # HIERARCHY 3: Send 1 message (Main only)
    print(f"🔄 Escalating to HIERARCHY 3 for {record_id}")
    
    # Send main message to Hierarchy 3
    send_message_to_hierarchy(record_id, record_name, partner_record_name, partner_company_type, 
                             overlap_context, 3, "main", action_url)
    
    print(f"🏁 Completed all messages for {record_id} (6 total messages sent)")

def send_message_to_hierarchy(record_id: str, record_name: str, partner_record_name: str, 
                             partner_company_type: str, overlap_context: dict, hierarchy_level: int, 
                             message_type: str, action_url: str):
    """Send a specific message to a specific hierarchy level"""
    # Find the appropriate internal team member(s) for this hierarchy
    internal_members = []
    for member_name, member_info in INTERNAL_TEAM.items():
        if isinstance(member_info, dict) and member_info.get("hierarchy") == hierarchy_level:
            internal_members.append(member_info)
    if not internal_members:
        print(f"❌ No Hierarchy {hierarchy_level} member found in internal team.")
        return
    # Build dynamic hierarchy designations mapping
    hierarchy_designations = get_hierarchy_designations(INTERNAL_TEAM)
    # Find the Account Executive (AE) name from INTERNAL_TEAM
    ae_name = None
    for member in INTERNAL_TEAM.values():
        if isinstance(member, dict) and member.get("hierarchy") == 1:
            ae_name = member.get("name")
            break
    # Send message to all members at this hierarchy level
    for internal_member in internal_members:
        webhook_url = internal_member["webhook_url"]
        channel_id = internal_member["channel_id"]
        member_name = internal_member["name"]
        # Get company name from we.json
        company_name = INTERNAL_TEAM.get("company")
        if not company_name:
            company_name = "Moative"
        # Find the internal team member/channel name and designation for personalization
        channel_name = None
        designation = None
        for member in INTERNAL_TEAM.values():
            if isinstance(member, dict) and member.get("channel_id") == channel_id:
                channel_name = member.get("name")
                designation = member.get("designation")
                break
        # Call the message generator with dynamic designations and AE name
        message = gemini_generator.generate_overlap_message(
            record_name=record_name,
            overlap_type="overlap",  # or pass actual type if available
            internal_name=member_name,
            partner_record_name=partner_record_name,
            partner_company_type=partner_company_type,
            count=1 if message_type == "main" else (2 if message_type == "followup1" else 3),
            hierarchy_level=hierarchy_level,
            overlap_context=overlap_context,
            hierarchy_designations=hierarchy_designations,
            ae_name=ae_name
        )
        send_slack_message_with_button(webhook_url, channel_id, message, action_url, record_id)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting overlap analysis and selection...")
    all_overlaps = []
    for record in overlap_qualifier.crossbeam_data:
        record_id = record.get("record_id")
        record_name = record.get("record_name")
        partner_record_name = record.get("partner_record_name")
        should_process, context = overlap_qualifier.should_process_overlap(record)
        if should_process:
            priority_score = context.get("priority_score", 0)
            print(f"📊 ANALYZED: {record_name} with {partner_record_name} (ID: {record_id})")
            print(f"   Priority Score: {priority_score}")
            print(f"   LOGO Potential: {context.get('logo_potential', False)}")
            print(f"   Partner Champion: {context.get('has_champion', False)}")
            all_overlaps.append({
                "record_id": record_id,
                "record_name": record_name,
                "partner_record_name": partner_record_name,
                "context": context
            })
        else:
            print(f"❌ SKIPPED: {record_name} with {partner_record_name} (ID: {record_id})")
    if not all_overlaps:
        print("❌ No overlaps found to analyze.")
        yield
        return

    best_overlap = max(all_overlaps, key=lambda x: x["context"].get("priority_score", 0))
    record_id = best_overlap["record_id"]
    record_name = best_overlap["record_name"]
    partner_record_name = best_overlap["partner_record_name"]
    context = best_overlap["context"]
    priority_score = context.get("priority_score", 0)
    print(f"\n🏆 SELECTED BEST OVERLAP FROM ALL AVAILABLE:")
    print(f"   {record_name} ↔ {partner_record_name} (ID: {record_id})")
    print(f"   Priority Score: {priority_score}")
    print(f"   LOGO Potential: {context.get('logo_potential', False)}")
    print(f"   Partner Champion: {context.get('has_champion', False)}")
    with state_lock:
        resolved_state[record_id] = False
    threading.Thread(target=send_messages_with_gap, args=(record_id, context), daemon=True).start()
    print(f"✅ Started processing for the best overlap: {record_id} (in background thread)")
    print("Overlap processing initialization complete.")
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/resolve_overlap")
async def resolve_overlap_slash(
    command: str = Form(...),
    text: str = Form(...),
    user_id: str = Form(...),
    channel_id: str = Form(...)
):
    # Find which internal team member's channel this is
    internal_member = None
    internal_designation = None
    for name, info in INTERNAL_TEAM.items():
        if info.get("channel_id") == channel_id:
            internal_member = name
            internal_designation = info.get("designation", "Team Member")
            break

    if not internal_member:
        return {"response_type": "ephemeral", "text": f"No internal team member found for channel {channel_id}."}

    # Find all unresolved overlaps
    unresolved_overlaps = []
    for record_id, is_resolved in resolved_state.items():
        if not is_resolved:  # Only unresolved overlaps
            unresolved_overlaps.append(record_id)
        
    # If all overlaps are already resolved, say who resolved it
    if not unresolved_overlaps:
        # Try to find who resolved the last overlap
        last_resolver = None
        last_resolver_designation = None
        for record_id in resolved_state:
            if resolved_by.get(record_id):
                last_resolver = resolved_by[record_id]
                # Find designation from we.json
                for info in INTERNAL_TEAM.values():
                    if isinstance(info, dict) and info.get("designation") == last_resolver:
                        last_resolver_designation = info.get("designation")
                        break
        if last_resolver:
            return {"response_type": "ephemeral", "text": f"Overlap already resolved by {last_resolver}."}
        else:
            return {"response_type": "ephemeral", "text": "No active overlaps to resolve."}
        
    # If overlap is already resolved, say who resolved it
    already_resolved = True
    resolver_designation = None
    for record_id in unresolved_overlaps:
        if resolved_by.get(record_id):
            resolver_designation = resolved_by[record_id]
        if not resolved_state.get(record_id):
            already_resolved = False
            break
    if already_resolved and resolver_designation:
        return {"response_type": "ephemeral", "text": f"Overlap already resolved by {resolver_designation}."}

    # Resolve all active overlaps and record who resolved it
    with state_lock:
        for record_id in unresolved_overlaps:
            resolved_state[record_id] = True
            message_count[record_id] = 0  # Reset the count
            escalation_state[record_id] = 0  # Reset escalation state
            if internal_designation:
                resolved_by[record_id] = internal_designation

    return {"response_type": "in_channel", "text": f"Marked all active overlaps as resolved. Thank you, {internal_member}!"}

@app.post("/slack/actions")
async def slack_actions(request: Request):
    form = await request.form()
    payload = form.get("payload")
    if not payload:
        return JSONResponse(content={"text": "No payload received."})
    try:
        payload_data = json.loads(payload)
        action_id = payload_data["actions"][0]["action_id"]
        response_url = payload_data.get("response_url")
        record_id = payload_data["actions"][0].get("value")
        channel_id = payload_data["channel"]["id"]
        message_ts = payload_data["message"]["ts"]
    except Exception as e:
        return JSONResponse(content={"text": f"Error parsing payload: {e}"})
    if action_id == "resolve_overlap":
        with state_lock:
            resolved_state[record_id] = True
        # Find the webhook URL for the channel that resolved it
        webhook_url = None
        for member in INTERNAL_TEAM.values():
            if isinstance(member, dict) and member.get("channel_id") == channel_id:
                webhook_url = member.get("webhook_url")
                break
        # Remove the RESOLVE button by updating the original message
        if SLACK_BOT_TOKEN and channel_id and message_ts:
            # Get the original message text and blocks, but remove the actions block
            original_blocks = payload_data["message"].get("blocks", [])
            # Remove the actions block (usually the last block)
            new_blocks = [block for block in original_blocks if block.get("type") != "actions"]
            # Fallback: if all blocks are actions, just show the first section
            if not new_blocks and original_blocks:
                for block in original_blocks:
                    if block.get("type") == "section":
                        new_blocks.append(block)
                        break
            headers = {
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            }
            update_payload = {
                "channel": channel_id,
                "ts": message_ts,
                "blocks": new_blocks
            }
            requests.post("https://slack.com/api/chat.update", headers=headers, json=update_payload)
        if webhook_url:
            send_slack_message(webhook_url, channel_id, "Thanks for resolving the overlap!")
        return JSONResponse(content={"text": "Marked as resolved. Thank you!"})
    return JSONResponse(content={"text": "Unknown action."})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)