# query_latest_logs.py
# Purpose: Select uplinks whose most recent log matches a given (step, status) pair.

from sqlalchemy.orm import Session
from sqlalchemy import func
from models import IngestUplink, EnrichmentLog

def find_uplinks_by_latest_log(db: Session, target_step: str, target_status: str, limit=100):
    """
    Return uplinks whose latest log is exactly (target_step, target_status).

    Args:
        db (Session): SQLAlchemy session
        target_step (str): e.g. 'enrichment'
        target_status (str): e.g. 'pending'
        limit (int): Max rows to return

    Returns:
        List of IngestUplink rows
    """
    subq = (
        db.query(
            EnrichmentLog.uplink_uuid,
            func.max(EnrichmentLog.created_at).label("latest_time")
        )
        .group_by(EnrichmentLog.uplink_uuid)
        .subquery()
    )

    matching = (
        db.query(EnrichmentLog.uplink_uuid)
        .join(subq, (EnrichmentLog.uplink_uuid == subq.c.uplink_uuid) & (EnrichmentLog.created_at == subq.c.latest_time))
        .filter(EnrichmentLog.step == target_step)
        .filter(EnrichmentLog.status == target_status)
        .subquery()
    )

    return (
        db.query(IngestUplink)
        .join(matching, IngestUplink.uplink_uuid == matching.c.uplink_uuid)
        .order_by(IngestUplink.inserted_at.asc())
        .limit(limit)
        .all()
    )
