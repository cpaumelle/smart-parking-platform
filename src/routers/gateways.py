# src/routers/gateways.py
# Gateways API Router for V5 Smart Parking Platform
# Queries ChirpStack database for gateway information

from fastapi import APIRouter, Request, Query, HTTPException, status
from typing import Optional, Dict, Any, List
from datetime import datetime

router = APIRouter(prefix="/api/v1/gateways", tags=["gateways"])

@router.get("/", response_model=List[Dict[str, Any]])
async def list_gateways(
    request: Request,
    includeArchived: Optional[bool] = Query(False, description="Include archived gateways")
):
    """
    List all gateways from ChirpStack database

    Returns gateway information including EUI, name, location, and last seen time
    """
    try:
        # Access ChirpStack database pool
        chirpstack_pool = request.app.state.chirpstack_client.pool

        query = """
            SELECT
                encode(gateway_id, 'hex') as gw_eui,
                name as gateway_name,
                description,
                latitude,
                longitude,
                altitude,
                last_seen_at,
                created_at,
                updated_at,
                tags,
                properties
            FROM gateway
            ORDER BY name
        """

        results = await chirpstack_pool.fetch(query)

        gateways = []
        for row in results:
            gateway = {
                "gw_eui": row["gw_eui"],
                "gateway_name": row["gateway_name"],
                "description": row["description"] if row["description"] else "",
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "altitude": row["altitude"],
                "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "tags": row["tags"] if row["tags"] else {},
                "properties": row["properties"] if row["properties"] else {},
                "is_online": bool(row["last_seen_at"]) if row["last_seen_at"] else False
            }
            gateways.append(gateway)

        return gateways

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch gateways from ChirpStack: {str(e)}"
        )

@router.get("/{gw_eui}", response_model=Dict[str, Any])
async def get_gateway(
    request: Request,
    gw_eui: str
):
    """
    Get details of a specific gateway by EUI

    Args:
        gw_eui: Gateway EUI in hex format (e.g., "7276ff002e062e5e")
    """
    try:
        chirpstack_pool = request.app.state.chirpstack_client.pool

        # Convert hex EUI to bytea for query
        query = """
            SELECT
                encode(gateway_id, 'hex') as gw_eui,
                name as gateway_name,
                description,
                latitude,
                longitude,
                altitude,
                last_seen_at,
                created_at,
                updated_at,
                stats_interval_secs,
                tags,
                properties
            FROM gateway
            WHERE encode(gateway_id, 'hex') = $1
        """

        result = await chirpstack_pool.fetchrow(query, gw_eui.lower())

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Gateway with EUI {gw_eui} not found"
            )

        gateway = {
            "gw_eui": result["gw_eui"],
            "gateway_name": result["gateway_name"],
            "description": result["description"] if result["description"] else "",
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "altitude": result["altitude"],
            "last_seen_at": result["last_seen_at"].isoformat() if result["last_seen_at"] else None,
            "created_at": result["created_at"].isoformat() if result["created_at"] else None,
            "updated_at": result["updated_at"].isoformat() if result["updated_at"] else None,
            "stats_interval_secs": result["stats_interval_secs"],
            "tags": result["tags"] if result["tags"] else {},
            "properties": result["properties"] if result["properties"] else {},
            "is_online": bool(result["last_seen_at"]) if result["last_seen_at"] else False
        }

        return gateway

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch gateway: {str(e)}"
        )

@router.get("/stats/summary", response_model=Dict[str, Any])
async def get_gateway_stats(request: Request):
    """
    Get summary statistics about gateways

    Returns:
        - total: Total number of gateways
        - online: Number of gateways seen in last 5 minutes
        - offline: Number of gateways not seen recently
    """
    try:
        chirpstack_pool = request.app.state.chirpstack_client.pool

        query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE last_seen_at > NOW() - INTERVAL '5 minutes') as online,
                COUNT(*) FILTER (WHERE last_seen_at IS NULL OR last_seen_at <= NOW() - INTERVAL '5 minutes') as offline
            FROM gateway
        """

        result = await chirpstack_pool.fetchrow(query)

        return {
            "total": result["total"],
            "online": result["online"],
            "offline": result["offline"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch gateway statistics: {str(e)}"
        )
