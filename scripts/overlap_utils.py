import os
import datetime
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, select, text
from sqlalchemy.orm import declarative_base, Session
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

# Constants
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///scoring_weights.db")
SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "False") == "True"

Base = declarative_base()

class ScoringWeight(Base):
    __tablename__ = 'scoring_weights'
    parameter = Column(String, primary_key=True)
    section = Column(String, primary_key=True)  # 'opportunity' or 'partner'
    weight = Column(Float)  # as decimal, e.g., 0.25

class InternalTeam(Base):
    __tablename__ = 'internal_team'
    name = Column(String, primary_key=True)
    designation = Column(String)
    hierarchy = Column(Float)
    channel_id = Column(String)
    webhook_url = Column(String)
    max_message = Column(Float)

class OverlapStatus(Base):
    __tablename__ = 'overlap_status'
    record_id = Column(String, primary_key=True)
    resolved = Column(Boolean, default=False)
    completed = Column(Boolean, default=False)
    resolved_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class CrossbeamRecord(Base):
    __tablename__ = 'crossbeam_records'
    id = Column(String, primary_key=True)
    opportunity_name = Column(String)
    opportunity_website = Column(String)
    opportunity_size_label = Column(String)
    opportunity_size_score = Column(Float)
    relationship_status_label = Column(String)
    relationship_status_score = Column(Float)
    engagement_score_label = Column(String)
    engagement_score_score = Column(Float)
    opportunity_stage_label = Column(String)
    opportunity_stage_score = Column(Float)
    winnability_label = Column(String)
    winnability_score = Column(Float)
    logo_potential = Column(Boolean)
    partner_name = Column(String)
    partner_website = Column(String)
    partner_size_label = Column(String)
    partner_size_score = Column(Float)
    stickiness_label = Column(String)
    stickiness_score = Column(Float)
    relationship_strength_label = Column(String)
    relationship_strength_score = Column(Float)
    recent_deal_support_label = Column(String)
    recent_deal_support_score = Column(Float)
    partner_champion_flagged = Column(Boolean)

engine = create_engine(DATABASE_URL, echo=SQLALCHEMY_ECHO)
Base.metadata.create_all(engine)

WEIGHTS_CACHE = {"opportunity": None, "partner": None}

def get_weights(section: str) -> Dict[str, float]:
    """Always retrieve weights from DB (no caching)."""
    with Session(engine) as session:
        rows = session.execute(
            select(ScoringWeight.parameter, ScoringWeight.weight)
            .where(ScoringWeight.section == section)
        ).all()
        return {row[0]: row[1] / 100.0 for row in rows}

def load_crossbeam_data() -> List[Dict]:
    """Load Crossbeam records from the database."""
    try:
        with Session(engine) as session:
            result = session.execute(select(CrossbeamRecord)).all()
            records = [dict(row[0].__dict__) for row in result]
            print(f"Loaded {len(records)} crossbeam records from database.")
            return records
    except Exception as e:
        print(f"Error loading crossbeam records from database: {e}")
        return []

def opportunity_score(record: Dict) -> float:
    """Calculate opportunity score based on weighted criteria."""
    weights = get_weights('opportunity')
    total = (
        record.get('opportunity_size_score', 0) * weights.get('opportunity_size', 0) +
        record.get('relationship_status_score', 0) * weights.get('relationship_status', 0) +
        record.get('engagement_score_score', 0) * weights.get('engagement_score', 0) +
        record.get('opportunity_stage_score', 0) * weights.get('opportunity_stage', 0) +
        record.get('winnability_score', 0) * weights.get('winnability', 0)
    )
    return total

def partner_score(record: Dict) -> float:
    """Calculate partner score based on weighted criteria."""
    weights = get_weights('partner')
    total = (
        record.get('relationship_strength_score', 0) * weights.get('relationship_strength_score', 0) +
        record.get('recent_deal_support_score', 0) * weights.get('recent_deal_support', 0) +
        record.get('stickiness_score', 0) * weights.get('stickiness_score', 0)
    )
    return total

def get_logo_potential(record: Dict) -> bool:
    """Check if the opportunity has logo potential."""
    return record.get('logo_potential', False)

def get_partner_champion_flag(record: Dict) -> bool:
    """Check if the partner has a champion flag."""
    return record.get('partner_champion_flagged', False)

def get_overlap_status_db(record_id: str) -> Optional[Dict]:
    """Retrieve overlap status from the database."""
    with Session(engine) as session:
        row = session.query(OverlapStatus).filter_by(record_id=record_id).first()
        return dict(row.__dict__) if row else None

def set_overlap_status_db(record_id: str, resolved: bool, resolved_by: Optional[str] = None):
    """Update overlap status in the database."""
    with Session(engine) as session:
        row = session.query(OverlapStatus).filter_by(record_id=record_id).first()
        now = datetime.datetime.utcnow()
        if row:
            row.resolved = resolved
            row.resolved_by = resolved_by
            row.resolved_at = now if resolved else None
        else:
            row = OverlapStatus(
                record_id=record_id,
                resolved=resolved,
                resolved_by=resolved_by,
                created_at=now,
                resolved_at=now if resolved else None
            )
            session.add(row)
        session.commit()

def ensure_overlap_status_exists(record_id: str):
    """Ensure an overlap status record exists."""
    with Session(engine) as session:
        row = session.query(OverlapStatus).filter_by(record_id=record_id).first()
        if not row:
            now = datetime.datetime.utcnow()
            row = OverlapStatus(record_id=record_id, resolved=False, resolved_by=None, created_at=now, resolved_at=None)
            session.add(row)
            session.commit()

def migrate_prospect_to_opportunity_in_weights(db_path: str = 'scoring_weights.db'):
    """Update scoring_weights from 'prospect' to 'opportunity'."""
    engine = create_engine(f'sqlite:///{db_path}')
    with engine.connect() as conn:
        print("Updating scoring_weights: setting section='opportunity' where section='prospect'...")
        conn.execute(text("UPDATE scoring_weights SET section = 'opportunity' WHERE section = 'prospect';"))
        conn.commit()
        print("Migration complete.")

def migrate_add_completed_to_overlap_status(db_path: str = 'scoring_weights.db'):
    """Add 'completed' column to overlap_status if it does not exist."""
    engine = create_engine(f'sqlite:///{db_path}')
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(overlap_status);"))
        columns = [row[1] for row in result]
        if 'completed' not in columns:
            print("Adding 'completed' column to overlap_status table...")
            conn.execute(text("ALTER TABLE overlap_status ADD COLUMN completed BOOLEAN DEFAULT 0;"))
            print("Migration complete: 'completed' column added.")
        else:
            print("'completed' column already exists in overlap_status table.")

class OverlapQualifier:
    def __init__(self):
        self.crossbeam_data = load_crossbeam_data()
        self.crossbeam_lookup = {record["id"]: record for record in self.crossbeam_data}

    def calculate_priority_score(self, record: Dict) -> Tuple[float, Dict]:
        """Calculate the priority score and context for an overlap record."""
        logo_potential = get_logo_potential(record)
        has_champion = get_partner_champion_flag(record)
        o_score = opportunity_score(record)
        pa_score = partner_score(record)
        if logo_potential:
            final_score = 5
            priority_level = "LOGO POTENTIAL"
        else:
            final_score = (o_score + pa_score) / 2 if o_score and pa_score else max(o_score, pa_score, 0)
            priority_level = "SCORED"
        return final_score, {
            "logo_potential": logo_potential,
            "opportunity": {
                "name": record.get("opportunity_name", "Unknown"),
                "website": record.get("opportunity_website", ""),
            },
            "partner": {
                "name": record.get("partner_name", "Unknown"),
                "website": record.get("partner_website", ""),
                "industry": record.get("partner_size_label", "Unknown")  # Fallback for industry
            },
            "has_champion": has_champion,
            "priority_score": final_score,
            "priority_level": priority_level
        }

    def should_process_overlap(self, record: Dict) -> Tuple[bool, Dict]:
        """Determine if an overlap should be processed."""
        score, context = self.calculate_priority_score(record)
        should_process = score >= 1.0 or context.get("logo_potential", False)
        return should_process, context

    def get_enhanced_record(self, record_id: str) -> Optional[Dict]:
        """Retrieve a record by ID."""
        return self.crossbeam_lookup.get(record_id)