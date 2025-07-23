import os
import json
import time
import threading
from typing import Dict, List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
from sqlalchemy import create_engine, text
import sqlite3
from contextlib import asynccontextmanager
from scripts.llm_utils import GeminiMessageGenerator
from scripts.overlap_utils import (
    load_crossbeam_data,
    opportunity_score,
    partner_score,
    get_logo_potential,
    get_partner_champion_flag,
    OverlapQualifier
)
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///scoring_weights.db")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
RESOLVE_ACTION_URL = os.getenv("RESOLVE_ACTION_URL", "http://localhost:8000/api/resolve-overlap")
MESSAGE_DELAY_SECONDS = int(os.getenv("MESSAGE_DELAY_SECONDS", 2))
DEFAULT_COMPANY_NAME = os.getenv("DEFAULT_COMPANY_NAME", "Moative")
SLACK_USERNAME = os.getenv("SLACK_USERNAME", "Moat")
SLACK_ICON_EMOJI = os.getenv("SLACK_ICON_EMOJI", ":ghost:")

# Initialize global state
resolved_state: Dict[str, bool] = {}
processed_overlaps: Dict[str, bool] = {}  # Tracks all processed overlaps, not just those with logo potential
state_lock = threading.Lock()
messaging_lock = threading.Lock()
current_overlap_id: Optional[str] = None
overlap_qualifier = OverlapQualifier()
gemini_generator = GeminiMessageGenerator()

class InternalTeamMember(BaseModel):
    name: str
    designation: str
    hierarchy: int
    channel_id: str
    webhook_url: str
    max_message: int

def load_internal_team_from_db() -> Dict[str, dict]:
    """Load internal team data from the database."""
    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, designation, hierarchy, channel_id, webhook_url, max_message FROM internal_team")
            team = {row["name"]: dict(row) for row in cursor.fetchall()}
        return team
    except sqlite3.Error as e:
        return {}

INTERNAL_TEAM = load_internal_team_from_db()

def send_slack_message(webhook_url: str, channel_id: str, text: str) -> bool:
    """Send a Slack message to the specified channel."""
    payload = {
        "channel": channel_id,
        "username": SLACK_USERNAME,
        "text": text,
        "icon_emoji": SLACK_ICON_EMOJI
    }
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()

        return True
    except requests.RequestException as e:
        return False

def send_slack_message_with_button(webhook_url: str, channel_id: str, text: str, action_url: str, record_id: str) -> bool:
    """Send a Slack message with a 'RESOLVE' button."""
    payload = {
        "channel": channel_id,
        "username": SLACK_USERNAME,
        "icon_emoji": SLACK_ICON_EMOJI,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
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
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()

        return True
    except requests.RequestException as e:
        return False

def get_hierarchy_designations(internal_team: Dict[str, dict]) -> Dict[str, str]:
    """Map hierarchy levels to designations."""
    designations = {}
    for member in internal_team.values():
        level = str(member.get("hierarchy"))
        designation = member.get("designation")
        if level and designation and level not in designations:
            designations[level] = designation
    return designations

def get_best_overlap(exclude_id: Optional[str] = None) -> Optional[Dict]:
    """Find the best overlap, prioritizing logo_potential=1, then highest priority_score, then lexicographically by record_name."""
    all_overlaps = [
        {
            "record_id": record.get("id"),
            "record_name": record.get("opportunity_name", "Unknown"),
            "partner_record_name": record.get("partner_name", "Unknown"),
            "context": context,
            "priority_score": context.get("priority_score", 0),
            "logo_potential": record.get("logo_potential", False)
        }
        for record in overlap_qualifier.crossbeam_data
        if (should_process := overlap_qualifier.should_process_overlap(record)[0])
        for context in [overlap_qualifier.should_process_overlap(record)[1]]
        if record.get("id") != exclude_id and not resolved_state.get(record.get("id"), False)
        and not processed_overlaps.get(record.get("id"), False)
    ]
    if not all_overlaps:

        return None
    # Sort overlaps: prioritize logo_potential, then priority_score (descending), then record_name (lexicographically)
    sorted_overlaps = sorted(
        all_overlaps,
        key=lambda x: (x["logo_potential"], x["priority_score"], x["record_name"]),
        reverse=True
    )
    best = sorted_overlaps[0]

    return best

def trigger_overlap_processing(exclude_id: Optional[str] = None):
    """Trigger processing of the best overlap if none is currently being processed."""
    global current_overlap_id
    with state_lock:
        if current_overlap_id:
            return
        best_overlap = get_best_overlap(exclude_id)
        if best_overlap:
            best_id = best_overlap["record_id"]

            resolved_state[best_id] = False
            processed_overlaps[best_id] = True
            current_overlap_id = best_id
            threading.Thread(
                target=send_messages_with_gap,
                args=(best_id, best_overlap["context"]),
                daemon=True
            ).start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event handler for startup analysis."""
    global current_overlap_id
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM scoring_weights"))
            weights = [dict(row) for row in result.mappings()]
    except Exception as e:
        yield
        return

    best_overlap = get_best_overlap()
    if best_overlap:
        record_id = best_overlap["record_id"]
        record_name = best_overlap["record_name"]
        partner_record_name = best_overlap["partner_record_name"]
        context = best_overlap["context"]
        priority_score = context.get("priority_score", 0)
        with state_lock:
            resolved_state[record_id] = False
            processed_overlaps[record_id] = True
            current_overlap_id = record_id
        threading.Thread(target=send_messages_with_gap, args=(record_id, context), daemon=True).start()
    else:
        logger.info("No overlaps found to process at startup.")
    yield
    with state_lock:
        current_overlap_id = None

def send_messages_with_gap(record_id: str, context: Dict):
    """Send Slack messages to team members one at a time, escalating through hierarchy levels."""
    global current_overlap_id
    designations = get_hierarchy_designations(INTERNAL_TEAM)
    max_hierarchy = max(
        (member.get("hierarchy") for member in INTERNAL_TEAM.values() if isinstance(member.get("hierarchy"), (int, float))),
        default=0
    )
    record = overlap_qualifier.get_enhanced_record(record_id)
    record_name = record.get("opportunity_name", "Unknown") if record else "Unknown"
    partner_record_name = record.get("partner_name", "Unknown") if record else "Unknown"
    partner_company_type = record.get("partner_size_label", "Unknown") if record else "Unknown"
    
    # Retrieve ae_name based on hierarchy (e.g., lowest hierarchy level)
    internal_members = sorted(
        [member for member in INTERNAL_TEAM.values() if isinstance(member.get("hierarchy"), (int, float))],
        key=lambda x: x["hierarchy"]
    )
    ae_name = internal_members[0]["name"] if internal_members else "Unknown"

    # Log message plan
    for hierarchy_level in range(1, int(max_hierarchy) + 1):
        members = [m for m in INTERNAL_TEAM.values() if m.get("hierarchy") == hierarchy_level]
        for member in members:
            max_msgs = member.get("max_message", 0)

    with messaging_lock:
        for hierarchy_level in range(1, int(max_hierarchy) + 1):
            internal_members = [
                member for member in INTERNAL_TEAM.values()
                if isinstance(member, dict) and member.get("hierarchy") == hierarchy_level
            ]
            if not internal_members:
                continue

            for member in internal_members:
                max_message = member.get("max_message", 0)
                if max_message < 1:
                    continue
                message_types = ["main"] + [f"followup{i}" for i in range(1, max_message)]
                webhook_url = member.get("webhook_url")
                channel_id = member.get("channel_id")
                member_name = member.get("name")
                if not webhook_url or not channel_id:
                    continue

                for idx, message_type in enumerate(message_types):
                    with state_lock:
                        if resolved_state.get(record_id, False):

                            current_overlap_id = None
                            return
                    #message = f"ACCOUNT: {record_name} | PARTNER: {partner_record_name} | AE: {ae_name} | Hierarchy {hierarchy_level} | {message_type.capitalize()}"
                    message = gemini_generator.generate_overlap_message(
                        record_name=record_name,
                        overlap_type="overlap",
                        internal_name=member_name,
                        partner_record_name=partner_record_name,
                        partner_company_type=partner_company_type,
                        count=idx + 1,
                        hierarchy_level=hierarchy_level,
                        overlap_context=context,
                        hierarchy_designations=designations,
                        ae_name=ae_name  # Pass ae_name to the message generator if needed
                    )
                    success = send_slack_message_with_button(webhook_url, channel_id, message, RESOLVE_ACTION_URL, record_id)
                    if not success:
                        logger.error(f"Failed to send message to {member_name} in channel {channel_id}")
                    time.sleep(MESSAGE_DELAY_SECONDS)


        with state_lock:
            current_overlap_id = None

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/resolve-overlap")
async def resolve_overlap(request: Request):
    """Handle overlap resolution via Slack button."""

    data = await request.json()
    record_id = data.get("record_id")
    if not record_id:

        raise HTTPException(status_code=400, detail="Missing record_id")
    with state_lock:
        resolved_state[record_id] = True

        if current_overlap_id == record_id:
            current_overlap_id = None
    return {"message": f"Overlap {record_id} resolved"}

@app.get("http://127.0.0.1:8000/api/crossbeam-records")
async def get_crossbeam_records():
    """Retrieve all crossbeam records from the database."""

    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM crossbeam_records"))
            records = [dict(row) for row in result.mappings()]

        return records
    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Error retrieving crossbeam records: {e}")

@app.get("/api/pipeline-scores")
async def get_pipeline_scores():
    """Retrieve crossbeam records with computed opportunity and partner scores."""

    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM crossbeam_records"))
            records = [dict(row) for row in result.mappings()]
    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Error retrieving pipeline scores: {e}")

    for rec in records:
        o_score = opportunity_score(rec)
        p_score = partner_score(rec)
        combined = (o_score + p_score) / 2
        rec.update({
            "opportunity_score": o_score,
            "partner_score": p_score,
            "combined_score_percent": (combined / 5) * 100
        })

    return records

@app.get("/api/internal-team")
async def get_internal_team():
    """Retrieve all internal team members from the database."""

    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, designation, hierarchy, channel_id, webhook_url, max_message FROM internal_team")
            team_members = [dict(row) for row in cursor.fetchall()]

        return JSONResponse(content=team_members)
    except sqlite3.Error as e:

        raise HTTPException(status_code=500, detail=f"Error retrieving internal team: {e}")

@app.post("/api/internal-team")
async def add_internal_team_member(member: InternalTeamMember):
    """Add a new internal team member to the database and check for new best overlap."""

    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO internal_team (name, designation, hierarchy, channel_id, webhook_url, max_message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (member.name, member.designation, member.hierarchy, member.channel_id, member.webhook_url, member.max_message)
            )
            conn.commit()
            new_id = cursor.lastrowid
        global INTERNAL_TEAM
        INTERNAL_TEAM = load_internal_team_from_db()  # Reload internal team

        trigger_overlap_processing()  # Check for new best overlap
        return {"message": "Team member added successfully", "id": new_id}
    except sqlite3.Error as e:

        raise HTTPException(status_code=500, detail=f"Error adding team member: {e}")

from fastapi import Path

@app.put("/api/internal-team/{member_id}")
async def update_internal_team_member(
    member_id: int = Path(..., description="ID of the internal team member to update"),
    member: InternalTeamMember = ...
):
    """Update an existing internal team member in the database and reload team data."""

    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE internal_team
                SET name = ?, designation = ?, hierarchy = ?, channel_id = ?, webhook_url = ?, max_message = ?
                WHERE id = ?
                """,
                (member.name, member.designation, member.hierarchy, member.channel_id, member.webhook_url, member.max_message, member_id)
            )
            if cursor.rowcount == 0:

                raise HTTPException(status_code=404, detail="Team member not found")
            conn.commit()

        global INTERNAL_TEAM
        INTERNAL_TEAM = load_internal_team_from_db()  # Reload internal team

        return {"message": "Team member updated successfully", "id": member_id}

    except sqlite3.Error as e:

        raise HTTPException(status_code=500, detail=f"Error updating team member: {e}")

@app.delete("/api/internal-team/{member_id}")
async def delete_internal_team_member(member_id: int):
    """Delete an internal team member by ID and check for new best overlap."""

    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM internal_team WHERE id = ?", (member_id,))
            if not cursor.fetchone():

                raise HTTPException(status_code=404, detail="Team member not found")
            cursor.execute("DELETE FROM internal_team WHERE id = ?", (member_id,))
            conn.commit()
        global INTERNAL_TEAM
        INTERNAL_TEAM = load_internal_team_from_db()  # Reload internal team

        trigger_overlap_processing()  # Check for new best overlap
        return {"message": f"Team member with ID {member_id} deleted successfully"}
    except sqlite3.Error as e:

        raise HTTPException(status_code=500, detail=f"Error deleting team member: {e}")

@app.get("/api/weights")
async def get_weights():
    """Retrieve all scoring weights from the database."""

    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scoring_weights")
            weights = [{"name": row["parameter"], "type": row["section"], "weight": row["weight"]} for row in cursor.fetchall()]

        return JSONResponse(content=weights)
    except sqlite3.Error as e:

        raise HTTPException(status_code=500, detail=f"Error retrieving weights: {e}")

@app.post("/api/weights")
async def save_weights(request: Request):
    """Update scoring weights in the database and check for new best overlap."""

    data = await request.json()
    opportunity_weights = flatten_weights(data.get("opportunity", {}))
    partner_weights = flatten_weights(data.get("partner", {}))

    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            cursor = conn.cursor()
            for key, weight in opportunity_weights.items():

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO scoring_weights (parameter, section, weight)
                    VALUES (?, ?, ?)
                    """,
                    (key, "opportunity", weight)
                )
            for key, weight in partner_weights.items():

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO scoring_weights (parameter, section, weight)
                    VALUES (?, ?, ?)
                    """,
                    (key, "partner", weight)
                )
            conn.commit()

        trigger_overlap_processing()  # Check for new best overlap
        return JSONResponse(content={"message": "Weights updated successfully"})
    except sqlite3.Error as e:

        raise HTTPException(status_code=500, detail=f"Error updating weights: {e}")

def flatten_weights(weights: Dict) -> Dict[str, float]:
    """Flatten nested weight dictionary into a simple key-value map."""
    result = {}
    for key, value in weights.items():
        if isinstance(value, dict) and "weight" in value:
            result[key] = float(value["weight"])
        else:
            result[key] = float(value)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENV", "development") == "development"
    )