# routers/gateways.py
# Version: 0.3.1 - 2025-08-05 13:25 UTC
# Changelog:
# - Fixed GET /gateways/{gw_eui} to return archived gateways
# - Allows unarchiving from UI

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict
from database.connections import get_sync_db_session
from models import Gateway
from schemas.gateways import GatewayIn, GatewayOut, GatewayUpdate
from datetime import datetime

router = APIRouter(tags=["Gateways"])

@router.get("", response_model=List[GatewayOut])
@router.get("/", response_model=List[GatewayOut])
def list_gateways(includeArchived: bool = Query(False)):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        query = db.query(Gateway)
        if not includeArchived:
            query = query.filter(Gateway.archived_at == None)
        gateways = query.all()
        return gateways
    finally:
        db_gen.close()

@router.get("/{gw_eui}", response_model=GatewayOut)
def get_gateway(gw_eui: str):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        gateway = db.query(Gateway).filter_by(gw_eui=gw_eui).first()  # ✅ no archived filter
        if not gateway:
            raise HTTPException(status_code=404, detail="Gateway not found")
        return gateway
    finally:
        db_gen.close()

@router.post("/", response_model=GatewayOut)
def create_gateway(payload: GatewayIn):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        if db.query(Gateway).filter_by(gw_eui=payload.gw_eui, archived_at=None).first():
            raise HTTPException(status_code=400, detail="Gateway already exists")
        new_gateway = Gateway(**payload.dict())
        db.add(new_gateway)
        db.commit()
        db.refresh(new_gateway)
        return new_gateway
    finally:
        db_gen.close()

@router.put("/{gw_eui}", response_model=GatewayOut)
def update_gateway(gw_eui: str, update: GatewayUpdate):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        gateway = db.query(Gateway).filter_by(gw_eui=gw_eui).first()  # ✅ also include archived
        if not gateway:
            raise HTTPException(status_code=404, detail="Gateway not found")
        for key, value in update.dict(exclude_unset=True).items():
            setattr(gateway, key, value)
        db.commit()
        db.refresh(gateway)
        return gateway
    finally:
        db_gen.close()

@router.patch("/{gw_eui}/archive", response_model=Dict)
def archive_gateway(gw_eui: str, confirm: bool = Query(False)):
    """Soft-archive a gateway by setting `archived_at`"""
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        gateway = db.query(Gateway).filter_by(gw_eui=gw_eui, archived_at=None).first()
        if not gateway:
            raise HTTPException(status_code=404, detail="Gateway not found")

        if not confirm:
            return {
                "dry_run": True,
                "gw_eui": gateway.gw_eui,
                "confirm_url": f"/v1/gateways/{gw_eui}/archive?confirm=true"
            }

        gateway.archived_at = datetime.utcnow()
        db.commit()
        return {"archived": True, "gw_eui": gw_eui}
    finally:
        db_gen.close()
