# enrichment_logger.py
# Purpose: Append a new row to enrichment_logs for tracking pipeline progress

from models import EnrichmentLog
from datetime import datetime

def log_step(db, uplink_uuid, step, status, detail=""):
    """
    Add an entry to enrichment_logs.

    Args:
        db: Active SQLAlchemy session
        uplink_uuid (UUID): ID of the uplink being logged
        step (str): Processing step (see constants.Step)
        status (str): Result of the step (see constants.Status)
        detail (str): Optional explanation or debug context
    """
    log = EnrichmentLog(
        uplink_uuid=uplink_uuid,
        step=step,
        status=status,
        detail=detail or "(no detail)",
        created_at=datetime.utcnow()
    )
    db.add(log)
