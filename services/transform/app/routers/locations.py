# locations.py - Location API Router
# Version: 0.3.3
# Last Updated: 2025-08-05 17:25 UTC+2
# Changelog:
# - Loggind and defensive logic for nesting


from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Optional
from database.connections import get_sync_db_session
from models import Location
from datetime import datetime
from pydantic import BaseModel, Field

router = APIRouter()

# ─────────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────────
class LocationIn(BaseModel):
    name: str
    type: str = Field(..., pattern="^(site|floor|room|zone)$")
    parent_id: Optional[str] = None
    uplink_metadata: Optional[Dict] = {}

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    uplink_metadata: Optional[Dict] = None
    parent_id: Optional[str] = None

class LocationOut(BaseModel):
    location_id: str
    name: str
    type: str
    parent_id: Optional[str]
    uplink_metadata: Optional[Dict]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    archived_at: Optional[datetime]

# ─────────────────────────────────────────────────────────────
# UTILITY: Recursive Location Tree
# ─────────────────────────────────────────────────────────────
def get_descendant_location_ids(db: Session, root_id: str) -> List[str]:
    query = text("""
        WITH RECURSIVE descendants AS (
            SELECT location_id FROM transform.locations WHERE location_id = :root_id
            UNION ALL
            SELECT l.location_id
            FROM transform.locations l
            JOIN descendants d ON l.parent_id = d.location_id
        )
        SELECT location_id FROM descendants;
    """)
    result = db.execute(query, {"root_id": root_id})
    return [row[0] for row in result.fetchall()]

# ─────────────────────────────────────────────────────────────
# GET /locations/tree
# ─────────────────────────────────────────────────────────────

class LocationTreeOut(BaseModel):
    location_id: str
    name: str
    type: str
    parent_id: Optional[str]
    path_string: str
    level: int
    children: List["LocationTreeOut"] = Field(default_factory=list)

LocationTreeOut.update_forward_refs()

@router.get("/tree", response_model=List[LocationTreeOut])
def get_location_tree(archived: str = Query("false", pattern="^(true|false|all)$")):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        # Apply archive filter in WHERE clause
        archive_filter = ""
        if archived == "false":
            archive_filter = "archived_at IS NULL"
        elif archived == "true":
            archive_filter = "archived_at IS NOT NULL"
        else:
            archive_filter = "1=1"  # no filter

        sql = f"""
        WITH RECURSIVE location_tree AS (
            SELECT
                location_id,
                name,
                type,
                parent_id,
                ARRAY[name] AS path,
                0 AS level
            FROM transform.locations
            WHERE {archive_filter} AND parent_id IS NULL

            UNION ALL

            SELECT
                c.location_id,
                c.name,
                c.type,
                c.parent_id,
                p.path || c.name,
                p.level + 1
            FROM transform.locations c
            JOIN location_tree p ON p.location_id = c.parent_id
            WHERE {archive_filter}
        )
        SELECT
            location_id,
            name,
            type,
            parent_id,
            array_to_string(path, ' > ') AS path_string,
            level
        FROM location_tree
        ORDER BY level, name;
        """

        rows = db.execute(text(sql)).mappings().all()

        # Step 1: Build node map
        node_map = {}
        for r in rows:
            node_map[str(r["location_id"])] = {
                "location_id": str(r["location_id"]),
                "name": r["name"],
                "type": r["type"],
                "parent_id": str(r["parent_id"]) if r["parent_id"] else None,
                "path_string": r["path_string"],
                "level": r["level"],
                "children": []
            }

        # Step 2: Nest children into parents
        for node_id, node in node_map.items():
            pid = node["parent_id"]
            if pid and pid in node_map:
                node_map[pid]["children"].append(node)

        def build_tree(node):
            node["children"].sort(key=lambda c: c["name"].lower())
            for child in node["children"]:
                build_tree(child)
            return node

        # Final tree: only root nodes
        tree = []
        for node in node_map.values():
            if node["parent_id"] is None:
                tree.append(build_tree(node))

        tree.sort(key=lambda n: n["name"].lower())
        return tree

    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to process location tree")
    finally:
        db_gen.close()

# ─────────────────────────────────────────────────────────────
# GET /locations
# ─────────────────────────────────────────────────────────────
@router.get("", response_model=List[LocationOut])
def get_locations(
    type: Optional[str] = None,
    parent_id: Optional[str] = None,
    archived: str = Query("false", pattern="^(true|false|all)$")
):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        query = db.query(Location)

        if archived == "false":
            query = query.filter(Location.archived_at.is_(None))
        elif archived == "true":
            query = query.filter(Location.archived_at.is_not(None))
        # if "all", do not filter

        if type:
            query = query.filter(Location.type == type)
        if parent_id:
            query = query.filter(Location.parent_id == parent_id)

        return [loc.as_dict() for loc in query.all()]
    finally:
        db_gen.close()

# ─────────────────────────────────────────────────────────────
# GET /locations/{id}
# ─────────────────────────────────────────────────────────────
@router.get("/{location_id}", response_model=LocationOut)
def get_location_by_id(location_id: str):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        loc = db.query(Location).filter_by(location_id=location_id, archived_at=None).first()
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")
        return loc.as_dict()
    finally:
        db_gen.close()

# ─────────────────────────────────────────────────────────────
# POST /locations
# ─────────────────────────────────────────────────────────────
@router.post("", response_model=LocationOut)
def create_location(location_data: LocationIn):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        loc = Location(
            name=location_data.name,
            type=location_data.type,
            parent_id=location_data.parent_id,
            uplink_metadata=location_data.uplink_metadata or {},
            created_at=datetime.utcnow(),
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)
        return loc.as_dict()
    finally:
        db_gen.close()

# ─────────────────────────────────────────────────────────────
# PUT /locations/{id}
# ─────────────────────────────────────────────────────────────
@router.put("/{location_id}", response_model=LocationOut)
def update_location(location_id: str, location_data: LocationUpdate):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        loc = db.query(Location).filter_by(location_id=location_id, archived_at=None).first()
        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")

        if location_data.name:
            loc.name = location_data.name
        if location_data.uplink_metadata is not None:
            loc.uplink_metadata = location_data.uplink_metadata
        if location_data.parent_id is not None:
            loc.parent_id = location_data.parent_id

        loc.updated_at = datetime.utcnow()
        db.commit()
        return loc.as_dict()
    finally:
        db_gen.close()

# ─────────────────────────────────────────────────────────────
# PUT /locations/{id}/archive
# ─────────────────────────────────────────────────────────────
@router.put("/{location_id}/archive", response_model=Dict)
def archive_location(location_id: str, confirm: bool = Query(False)):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        all_ids = get_descendant_location_ids(db, location_id)
        locations = db.query(Location).filter(Location.location_id.in_(all_ids)).all()

        if not locations:
            raise HTTPException(status_code=404, detail="No locations found")

        if not confirm:
            return {
                "dry_run": True,
                "affected_count": len(locations),
                "affected_names": [l.name for l in locations],
                "confirm_url": f"/locations/{location_id}/archive?confirm=true"
            }

        for loc in locations:
            loc.archived_at = datetime.utcnow()
        db.commit()

        return {
            "archived_count": len(locations),
            "archived_ids": all_ids
        }
    finally:
        db_gen.close()

# ─────────────────────────────────────────────────────────────
# PUT /locations/{id}/unarchive
# ─────────────────────────────────────────────────────────────
@router.put("/{location_id}/unarchive", response_model=Dict)
def unarchive_location(location_id: str):
    db_gen = get_sync_db_session()
    db = next(db_gen)
    try:
        loc = db.query(Location).filter_by(location_id=location_id).first()

        if not loc:
            raise HTTPException(status_code=404, detail="Location not found")

        if loc.archived_at is None:
            return {"unarchived": False, "message": "Location is already active"}

        loc.archived_at = None
        loc.updated_at = datetime.utcnow()
        db.commit()

        return {"unarchived": True, "location_id": location_id}
    finally:
        db_gen.close()

