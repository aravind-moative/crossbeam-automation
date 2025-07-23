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
        logger.info("Successfully loaded internal team from DB")
        return team
    except sqlite3.Error as e:
        logger.error(f"Error loading internal team from DB: {e}")
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
        logger.info(f"Message sent successfully to {channel_id}")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Slack message to {channel_id}: {e}")
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
        logger.info(f"Message with button sent successfully to {channel_id} for record {record_id}")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to send Slack message with button to {channel_id}: {e}")
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
        logger.debug("No qualifying unprocessed overlaps found")
        return None
    # Sort overlaps: prioritize logo_potential, then priority_score (descending), then record_name (lexicographically)
    sorted_overlaps = sorted(
        all_overlaps,
        key=lambda x: (x["logo_potential"], x["priority_score"], x["record_name"]),
        reverse=True
    )
    best = sorted_overlaps[0]
    logger.debug(f"Selected best overlap: {best['record_id']}, score={best['priority_score']}, logo_potential={best['logo_potential']}")
    return best

def trigger_overlap_processing(exclude_id: Optional[str] = None):
    """Trigger processing of the best overlap if none is currently being processed."""
    global current_overlap_id
    with state_lock:
        if current_overlap_id:
            logger.info(f"Skipping overlap processing; {current_overlap_id} is being processed")
            return
        best_overlap = get_best_overlap(exclude_id)
        if best_overlap:
            best_id = best_overlap["record_id"]
            logger.info(f"New best overlap detected: {best_id}")
            resolved_state[best_id] = False
            processed_overlaps[best_id] = True
            current_overlap_id = best_id
            threading.Thread(
                target=send_messages_with_gap,
                args=(best_id, best_overlap["context"]),
                daemon=True
            ).start()
            logger.info(f"Started processing for overlap: {best_id} (in background thread)")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event handler for startup analysis."""
    global current_overlap_id
    logger.info("Starting overlap analysis and selection...")
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM scoring_weights"))
            weights = [dict(row) for row in result.mappings()]
        logger.debug(f"All scoring_weights from DB: {weights}")
    except Exception as e:
        logger.error(f"Error loading scoring weights: {e}")
        yield
        return

    best_overlap = get_best_overlap()
    if best_overlap:
        record_id = best_overlap["record_id"]
        record_name = best_overlap["record_name"]
        partner_record_name = best_overlap["partner_record_name"]
        context = best_overlap["context"]
        priority_score = context.get("priority_score", 0)
        logger.info(f"SELECTED BEST OVERLAP: {record_name} ↔ {partner_record_name} (ID: {record_id}), "
                    f"Priority Score: {priority_score}, LOGO Potential: {context.get('logo_potential', False)}, "
                    f"Partner Champion: {context.get('has_champion', False)}")
        with state_lock:
            resolved_state[record_id] = False
            processed_overlaps[record_id] = True
            current_overlap_id = record_id
        threading.Thread(target=send_messages_with_gap, args=(record_id, context), daemon=True).start()
        logger.info(f"Started processing for the best overlap: {record_id} (in background thread)")
    else:
        logger.info("No qualifying overlaps found at startup")
    yield
    with state_lock:
        current_overlap_id = None

def send_messages_with_gap(record_id: str, context: Dict):
    """Send Slack messages to team members one at a time, escalating through hierarchy levels."""
    global current_overlap_id
    designations = get_hierarchy_designations(INTERNAL_TEAM)
    print(designations, "DESIGNATIONS")
    max_hierarchy = max(
        (member.get("hierarchy") for member in INTERNAL_TEAM.values() if isinstance(member.get("hierarchy"), (int, float))),
        default=0
    )
    record = overlap_qualifier.get_enhanced_record(record_id)
    record_name = record.get("opportunity_name", "Unknown") if record else "Unknown"
    partner_record_name = record.get("partner_name", "Unknown") if record else "Unknown"
    partner_company_type = record.get("partner_size_label", "Unknown") if record else "Unknown"
    ae_name = record.get("ae_name", "Unknown") if record else "Unknown"

    # Log message plan
    logger.info(f"Message plan for overlap {record_id}:")
    for hierarchy_level in range(1, int(max_hierarchy) + 1):
        members = [m for m in INTERNAL_TEAM.values() if m.get("hierarchy") == hierarchy_level]
        for member in members:
            max_msgs = member.get("max_message", 0)
            logger.info(f"  Hierarchy {hierarchy_level}, {member['name']}: {max_msgs} message(s)")

    with messaging_lock:
        for hierarchy_level in range(1, int(max_hierarchy) + 1):
            internal_members = [
                member for member in INTERNAL_TEAM.values()
                if isinstance(member, dict) and member.get("hierarchy") == hierarchy_level
            ]
            if not internal_members:
                logger.warning(f"No Hierarchy {hierarchy_level} member found in internal team")
                continue

            for member in internal_members:
                max_message = member.get("max_message", 0)
                if max_message < 1:
                    logger.warning(f"No messages allowed for {member['name']} at Hierarchy {hierarchy_level}, skipping")
                    continue
                message_types = ["main"] + [f"followup{i}" for i in range(1, max_message)]
                webhook_url = member.get("webhook_url")
                channel_id = member.get("channel_id")
                member_name = member.get("name")
                if not webhook_url or not channel_id:
                    logger.warning(f"No webhook_url or channel_id for {member_name}, skipping")
                    continue

                for idx, message_type in enumerate(message_types):
                    with state_lock:
                        if resolved_state.get(record_id, False):
                            logger.info(f"Overlap resolved for {record_id} at Hierarchy {hierarchy_level}")
                            current_overlap_id = None
                            return

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
                                            ae_name=ae_name
                                        )
                                            
                    #message = f"ACCOUNT: {record_name} | PARTNER: {partner_record_name} | Hierarchy {hierarchy_level} | {message_type.capitalize()}"
                    success = send_slack_message_with_button(webhook_url, channel_id, message, RESOLVE_ACTION_URL, record_id)
                    if not success:
                        logger.error(f"Failed to send message to {member_name} at hierarchy {hierarchy_level}")
                    time.sleep(MESSAGE_DELAY_SECONDS)

        logger.info(f"Completed all messages for {record_id}")
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
    logger.info(f"Received request to resolve overlap: {await request.json()}")
    data = await request.json()
    record_id = data.get("record_id")
    if not record_id:
        logger.error("Missing record_id in resolve-overlap request")
        raise HTTPException(status_code=400, detail="Missing record_id")
    with state_lock:
        resolved_state[record_id] = True
        logger.info(f"Overlap {record_id} marked as resolved")
        if current_overlap_id == record_id:
            current_overlap_id = None
    return {"message": f"Overlap {record_id} resolved"}

@app.get("/api/crossbeam-records")
async def get_crossbeam_records():
    """Retrieve all crossbeam records from the database."""
    logger.info("Received GET request for /api/crossbeam-records")
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM crossbeam_records"))
            records = [dict(row) for row in result.mappings()]
        logger.info(f"Successfully retrieved {len(records)} crossbeam records")
        return records
    except Exception as e:
        logger.error(f"Error retrieving crossbeam records: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving crossbeam records: {e}")

@app.get("/api/pipeline-scores")
async def get_pipeline_scores():
    """Retrieve crossbeam records with computed opportunity and partner scores."""
    logger.info("Received GET request for /api/pipeline-scores")
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM crossbeam_records"))
            records = [dict(row) for row in result.mappings()]
    except Exception as e:
        logger.error(f"Error retrieving pipeline scores: {e}")
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
    logger.info(f"Successfully computed scores for {len(records)} records")
    return records

@app.get("/api/internal-team")
async def get_internal_team():
    """Retrieve all internal team members from the database."""
    logger.info("Received GET request for /api/internal-team")
    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, designation, hierarchy, channel_id, webhook_url, max_message FROM internal_team")
            team_members = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Successfully retrieved {len(team_members)} internal team members")
        return JSONResponse(content=team_members)
    except sqlite3.Error as e:
        logger.error(f"Error retrieving internal team: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving internal team: {e}")

@app.post("/api/internal-team")
async def add_internal_team_member(member: InternalTeamMember):
    """Add a new internal team member to the database and check for new best overlap."""
    logger.info(f"Received POST request for /api/internal-team: {member.dict()}")
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
        logger.info(f"Team member added successfully, ID: {new_id}")
        trigger_overlap_processing()  # Check for new best overlap
        return {"message": "Team member added successfully", "id": new_id}
    except sqlite3.Error as e:
        logger.error(f"Error adding team member: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding team member: {e}")

from fastapi import Path

@app.put("/api/internal-team/{member_id}")
async def update_internal_team_member(
    member_id: int = Path(..., description="ID of the internal team member to update"),
    member: InternalTeamMember = ...
):
    """Update an existing internal team member in the database and reload team data."""
    logger.info(f"Received PUT request for /api/internal-team/{member_id}: {member.dict()}")
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
                logger.warning(f"No team member found with ID: {member_id}")
                raise HTTPException(status_code=404, detail="Team member not found")
            conn.commit()

        global INTERNAL_TEAM
        INTERNAL_TEAM = load_internal_team_from_db()  # Reload internal team
        logger.info(f"Team member updated successfully, ID: {member_id}")
        return {"message": "Team member updated successfully", "id": member_id}

    except sqlite3.Error as e:
        logger.error(f"Error updating team member: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating team member: {e}")

@app.delete("/api/internal-team/{member_id}")
async def delete_internal_team_member(member_id: int):
    """Delete an internal team member by ID and check for new best overlap."""
    logger.info(f"Received DELETE request for /api/internal-team/{member_id}")
    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM internal_team WHERE id = ?", (member_id,))
            if not cursor.fetchone():
                logger.error(f"Team member with ID {member_id} not found")
                raise HTTPException(status_code=404, detail="Team member not found")
            cursor.execute("DELETE FROM internal_team WHERE id = ?", (member_id,))
            conn.commit()
        global INTERNAL_TEAM
        INTERNAL_TEAM = load_internal_team_from_db()  # Reload internal team
        logger.info(f"Team member with ID {member_id} deleted successfully")
        trigger_overlap_processing()  # Check for new best overlap
        return {"message": f"Team member with ID {member_id} deleted successfully"}
    except sqlite3.Error as e:
        logger.error(f"Error deleting team member: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting team member: {e}")

@app.get("/api/weights")
async def get_weights():
    """Retrieve all scoring weights from the database."""
    logger.info("Received GET request for /api/weights")
    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scoring_weights")
            weights = [{"name": row["parameter"], "type": row["section"], "weight": row["weight"]} for row in cursor.fetchall()]
        logger.info(f"Successfully retrieved {len(weights)} scoring weights")
        return JSONResponse(content=weights)
    except sqlite3.Error as e:
        logger.error(f"Error retrieving weights: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving weights: {e}")

@app.post("/api/weights")
async def save_weights(request: Request):
    """Update scoring weights in the database and check for new best overlap."""
    logger.info(f"Received POST request for /api/weights: {await request.json()}")
    data = await request.json()
    opportunity_weights = flatten_weights(data.get("opportunity", {}))
    partner_weights = flatten_weights(data.get("partner", {}))

    try:
        with sqlite3.connect(DATABASE_URL.replace("sqlite:///", "")) as conn:
            cursor = conn.cursor()
            for key, weight in opportunity_weights.items():
                logger.info(f"Updating opportunity weight → {key}: {weight}")
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO scoring_weights (parameter, section, weight)
                    VALUES (?, ?, ?)
                    """,
                    (key, "opportunity", weight)
                )
            for key, weight in partner_weights.items():
                logger.info(f"Updating partner weight → {key}: {weight}")
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO scoring_weights (parameter, section, weight)
                    VALUES (?, ?, ?)
                    """,
                    (key, "partner", weight)
                )
            conn.commit()
        logger.info("Weights updated successfully, triggering overlap processing")
        trigger_overlap_processing()  # Check for new best overlap
        return JSONResponse(content={"message": "Weights updated successfully"})
    except sqlite3.Error as e:
        logger.error(f"Error updating weights: {e}")
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