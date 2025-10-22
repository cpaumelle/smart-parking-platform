"""
Optimized database queries with JOINs to prevent N+1 problems

This module contains reusable query functions that fetch related data
in a single query using JOINs instead of making multiple queries.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime


# ============================================================================
# Spaces Queries (with eager loading)
# ============================================================================

async def get_spaces_with_devices(
    db_pool,
    tenant_id: UUID,
    filters: Optional[Dict[str, Any]] = None,
    include_deleted: bool = False
) -> List[Dict[str, Any]]:
    """
    Fetch spaces with sensor/display info in single query (N+1 prevention)

    Args:
        db_pool: Database connection pool
        tenant_id: Tenant ID for filtering
        filters: Optional dict with building, floor, zone, state, site_id
        include_deleted: Whether to include soft-deleted spaces

    Returns:
        List of space dicts with embedded device information

    Performance: Single query with LEFT JOINs instead of N+1 pattern
    """
    conditions = ["s.tenant_id = $1"]
    params = [tenant_id]
    param_count = 2

    if filters:
        if filters.get("building"):
            conditions.append(f"s.building = ${param_count}")
            params.append(filters["building"])
            param_count += 1

        if filters.get("floor"):
            conditions.append(f"s.floor = ${param_count}")
            params.append(filters["floor"])
            param_count += 1

        if filters.get("zone"):
            conditions.append(f"s.zone = ${param_count}")
            params.append(filters["zone"])
            param_count += 1

        if filters.get("state"):
            conditions.append(f"s.state = ${param_count}")
            params.append(filters["state"])
            param_count += 1

        if filters.get("site_id"):
            conditions.append(f"s.site_id = ${param_count}")
            params.append(filters["site_id"])
            param_count += 1

    if not include_deleted:
        conditions.append("s.deleted_at IS NULL")

    where_clause = "WHERE " + " AND ".join(conditions)

    # Optimized query with all related data fetched in single query
    query = f"""
        SELECT
            s.id,
            s.name,
            s.code,
            s.building,
            s.floor,
            s.zone,
            s.state,
            s.site_id,
            s.tenant_id,
            s.sensor_eui,
            s.display_eui,
            s.gps_latitude,
            s.gps_longitude,
            s.metadata,
            s.created_at,
            s.updated_at,
            s.deleted_at,
            -- Site details (LEFT JOIN)
            sites.name AS site_name,
            sites.timezone AS site_timezone,
            -- Last sensor reading (using LATERAL JOIN for efficiency)
            last_reading.timestamp AS last_reading_timestamp,
            last_reading.occupied AS last_reading_occupied
        FROM spaces s
        LEFT JOIN sites ON s.site_id = sites.id
        LEFT JOIN LATERAL (
            SELECT timestamp, occupied
            FROM sensor_readings
            WHERE space_id = s.id
            ORDER BY timestamp DESC
            LIMIT 1
        ) last_reading ON true
        {where_clause}
        ORDER BY s.code, s.name
    """

    results = await db_pool.fetch(query, *params)

    spaces = []
    for row in results:
        space = {
            "id": str(row["id"]),
            "name": row["name"],
            "code": row["code"],
            "building": row["building"],
            "floor": row["floor"],
            "zone": row["zone"],
            "state": row["state"],
            "site_id": str(row["site_id"]) if row["site_id"] else None,
            "tenant_id": str(row["tenant_id"]),
            "sensor_eui": row["sensor_eui"],
            "display_eui": row["display_eui"],
            "gps_latitude": float(row["gps_latitude"]) if row["gps_latitude"] else None,
            "gps_longitude": float(row["gps_longitude"]) if row["gps_longitude"] else None,
            "metadata": row["metadata"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            "deleted_at": row["deleted_at"].isoformat() if row["deleted_at"] else None,
            # Embedded site details (no additional query needed)
            "site": {
                "name": row["site_name"],
                "timezone": row["site_timezone"]
            } if row["site_name"] else None,
            # Last sensor reading (no additional query needed)
            "last_reading": {
                "timestamp": row["last_reading_timestamp"].isoformat() if row["last_reading_timestamp"] else None,
                "occupied": row["last_reading_occupied"]
            } if row["last_reading_timestamp"] else None
        }
        spaces.append(space)

    return spaces


# ============================================================================
# Reservations Queries (with space details)
# ============================================================================

async def get_reservations_with_space(
    db_pool,
    tenant_id: UUID,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetch reservations with space details in single query (N+1 prevention)

    Args:
        db_pool: Database connection pool
        tenant_id: Tenant ID for filtering
        date_from: Optional start date filter
        date_to: Optional end date filter
        status_filter: Optional status filter

    Returns:
        List of reservation dicts with embedded space information

    Performance: Single query with JOIN instead of N+1 pattern
    """
    conditions = ["r.tenant_id = $1"]
    params = [tenant_id]
    param_count = 2

    if date_from:
        conditions.append(f"r.start_time >= ${param_count}")
        params.append(date_from)
        param_count += 1

    if date_to:
        conditions.append(f"r.end_time <= ${param_count}")
        params.append(date_to)
        param_count += 1

    if status_filter:
        conditions.append(f"r.status = ${param_count}")
        params.append(status_filter)
        param_count += 1

    where_clause = "WHERE " + " AND ".join(conditions)

    # Optimized query with space details in single query
    query = f"""
        SELECT
            r.id as reservation_id,
            r.space_id,
            r.start_time,
            r.end_time,
            r.status,
            r.user_email,
            r.user_phone,
            r.external_booking_id,
            r.external_system,
            r.metadata,
            r.created_at,
            r.updated_at,
            -- Space details (JOIN)
            s.code as space_code,
            s.name as space_name,
            s.building,
            s.floor,
            s.zone,
            s.state as space_state,
            -- Site details (additional JOIN)
            sites.name as site_name
        FROM reservations r
        JOIN spaces s ON r.space_id = s.id
        LEFT JOIN sites ON s.site_id = sites.id
        {where_clause}
        ORDER BY r.start_time DESC
    """

    results = await db_pool.fetch(query, *params)

    reservations = []
    for row in results:
        reservation = {
            "reservation_id": str(row["reservation_id"]),
            "space_id": str(row["space_id"]),
            "start_time": row["start_time"].isoformat(),
            "end_time": row["end_time"].isoformat(),
            "status": row["status"],
            "user_email": row["user_email"],
            "user_phone": row["user_phone"],
            "external_booking_id": row["external_booking_id"],
            "external_system": row["external_system"],
            "metadata": row["metadata"] if row["metadata"] else {},
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            # Embedded space details (no additional query needed)
            "space": {
                "code": row["space_code"],
                "name": row["space_name"],
                "building": row["building"],
                "floor": row["floor"],
                "zone": row["zone"],
                "state": row["space_state"],
                "site_name": row["site_name"]
            }
        }
        reservations.append(reservation)

    return reservations


# ============================================================================
# Sites Queries (with aggregates)
# ============================================================================

async def get_sites_with_stats(
    db_pool,
    tenant_id: UUID,
    include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """
    Fetch sites with space counts and state aggregations

    Args:
        db_pool: Database connection pool
        tenant_id: Tenant ID for filtering
        include_inactive: Whether to include inactive sites

    Returns:
        List of site dicts with aggregated space statistics

    Performance: Single query with GROUP BY instead of multiple queries
    """
    active_filter = "" if include_inactive else "AND s.is_active = true"

    # Optimized query with aggregations in single query
    query = f"""
        SELECT
            s.id,
            s.tenant_id,
            s.name,
            s.timezone,
            s.location,
            s.metadata,
            s.is_active,
            s.created_at,
            s.updated_at,
            -- Aggregate space counts by state
            COUNT(sp.id) FILTER (WHERE sp.deleted_at IS NULL) AS total_spaces,
            COUNT(sp.id) FILTER (WHERE sp.deleted_at IS NULL AND sp.state = 'FREE') AS free_spaces,
            COUNT(sp.id) FILTER (WHERE sp.deleted_at IS NULL AND sp.state = 'OCCUPIED') AS occupied_spaces,
            COUNT(sp.id) FILTER (WHERE sp.deleted_at IS NULL AND sp.state = 'RESERVED') AS reserved_spaces
        FROM sites s
        LEFT JOIN spaces sp ON s.id = sp.site_id
        WHERE s.tenant_id = $1 {active_filter}
        GROUP BY s.id
        ORDER BY s.name ASC
    """

    results = await db_pool.fetch(query, tenant_id)

    sites = []
    for row in results:
        site = {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "name": row["name"],
            "timezone": row["timezone"],
            "location": row["location"] if isinstance(row["location"], dict) else None,
            "metadata": row["metadata"] if isinstance(row["metadata"], dict) else {},
            "is_active": row["is_active"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            # Space statistics (no additional queries needed)
            "spaces_count": row["total_spaces"] or 0,
            "spaces_by_state": {
                "FREE": row["free_spaces"] or 0,
                "OCCUPIED": row["occupied_spaces"] or 0,
                "RESERVED": row["reserved_spaces"] or 0
            }
        }
        sites.append(site)

    return sites


# ============================================================================
# Query Performance Helpers
# ============================================================================

async def explain_query(db_pool, query: str, params: List[Any]) -> str:
    """
    Run EXPLAIN ANALYZE on a query to check performance

    Args:
        db_pool: Database connection pool
        query: SQL query to analyze
        params: Query parameters

    Returns:
        EXPLAIN ANALYZE output as string

    Usage:
        explain = await explain_query(db_pool, query, params)
        logger.info(f"Query plan:\n{explain}")
    """
    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {query}"
    result = await db_pool.fetch(explain_query, *params)
    return "\n".join([row[0] for row in result])
