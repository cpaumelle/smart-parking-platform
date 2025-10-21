"""
Orphan Device Handling
Tracks uplinks from devices not yet assigned to spaces
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


async def handle_orphan_device(
    db,
    device_eui: str,
    payload: Optional[bytes] = None,
    rssi: Optional[int] = None,
    snr: Optional[float] = None
) -> Dict[str, Any]:
    """
    Handle uplink from a device not assigned to any space

    This prevents webhook spam and aids in device provisioning by tracking
    unknown devices in the orphan_devices table.

    Args:
        db: Database connection pool
        device_eui: Device EUI (16 hex characters)
        payload: Raw payload bytes (optional)
        rssi: RSSI value (optional)
        snr: SNR value (optional)

    Returns:
        Dictionary with orphan device info
    """
    try:
        # Insert or update orphan device record
        result = await db.fetchrow("""
            INSERT INTO orphan_devices (dev_eui, last_payload, last_rssi, last_snr, first_seen, last_seen, uplink_count)
            VALUES ($1, $2, $3, $4, NOW(), NOW(), 1)
            ON CONFLICT (dev_eui) DO UPDATE SET
                last_seen = NOW(),
                uplink_count = orphan_devices.uplink_count + 1,
                last_payload = EXCLUDED.last_payload,
                last_rssi = EXCLUDED.last_rssi,
                last_snr = EXCLUDED.last_snr
            RETURNING id, dev_eui, uplink_count, first_seen, last_seen, assigned_to_space_id
        """, device_eui, payload, rssi, snr)

        if result['uplink_count'] == 1:
            logger.info(f"New orphan device discovered: {device_eui}")
        elif result['uplink_count'] % 10 == 0:
            # Log every 10th uplink to track active orphans
            logger.warning(
                f"Orphan device {device_eui} has sent {result['uplink_count']} uplinks "
                f"(first seen: {result['first_seen']}, assigned: {result['assigned_to_space_id']})"
            )

        return {
            "status": "orphan",
            "device_eui": device_eui,
            "uplink_count": result['uplink_count'],
            "first_seen": result['first_seen'].isoformat() if result['first_seen'] else None,
            "last_seen": result['last_seen'].isoformat() if result['last_seen'] else None,
            "assigned": result['assigned_to_space_id'] is not None
        }

    except Exception as e:
        logger.error(f"Error handling orphan device {device_eui}: {e}")
        # Don't fail the webhook - just log and return minimal info
        return {
            "status": "orphan_error",
            "device_eui": device_eui,
            "error": str(e)
        }


async def assign_orphan_device(
    db,
    device_eui: str,
    space_id: str
) -> bool:
    """
    Mark an orphan device as assigned to a space

    Args:
        db: Database connection pool
        device_eui: Device EUI
        space_id: Space UUID to assign to

    Returns:
        True if assignment succeeded

    Note:
        This doesn't actually update the spaces table - it just marks the
        orphan record as assigned for tracking purposes.
    """
    try:
        result = await db.execute("""
            UPDATE orphan_devices
            SET assigned_to_space_id = $1, assigned_at = NOW()
            WHERE dev_eui = $2
        """, space_id, device_eui)

        if result == "UPDATE 1":
            logger.info(f"Marked orphan device {device_eui} as assigned to space {space_id}")
            return True

        logger.warning(f"Failed to mark orphan device {device_eui} as assigned - device not found")
        return False

    except Exception as e:
        logger.error(f"Error assigning orphan device {device_eui}: {e}")
        return False


async def get_orphan_devices(
    db,
    include_assigned: bool = False,
    since_hours: Optional[int] = None
) -> list:
    """
    Get list of orphan devices for provisioning

    Args:
        db: Database connection pool
        include_assigned: Include devices already assigned to spaces
        since_hours: Only include devices seen in the last N hours

    Returns:
        List of orphan device records
    """
    try:
        conditions = []
        params = []

        if not include_assigned:
            conditions.append("assigned_to_space_id IS NULL")

        if since_hours:
            conditions.append(f"last_seen > NOW() - INTERVAL '{since_hours} hours'")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT
                id,
                dev_eui,
                first_seen,
                last_seen,
                uplink_count,
                last_rssi,
                last_snr,
                assigned_to_space_id,
                assigned_at
            FROM v_orphan_devices
            {where_clause}
            ORDER BY last_seen DESC
        """

        rows = await db.fetch(query, *params)

        return [
            {
                "id": str(row['id']),
                "dev_eui": row['dev_eui'],
                "first_seen": row['first_seen'].isoformat() if row['first_seen'] else None,
                "last_seen": row['last_seen'].isoformat() if row['last_seen'] else None,
                "uplink_count": row['uplink_count'],
                "last_rssi": row['last_rssi'],
                "last_snr": float(row['last_snr']) if row['last_snr'] else None,
                "assigned_to_space_id": str(row['assigned_to_space_id']) if row['assigned_to_space_id'] else None,
                "assigned_at": row['assigned_at'].isoformat() if row['assigned_at'] else None
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Error fetching orphan devices: {e}")
        return []


async def delete_orphan_device(db, device_eui: str) -> bool:
    """
    Delete an orphan device record from sensor_devices or display_devices

    Args:
        db: Database connection pool
        device_eui: Device EUI to delete

    Returns:
        True if deletion succeeded
    """
    try:
        # Try deleting from sensor_devices first
        result = await db.execute("""
            DELETE FROM sensor_devices WHERE dev_eui = $1 AND status = 'orphan'
        """, device_eui)

        if result == "DELETE 1":
            logger.info(f"Deleted orphan sensor device {device_eui}")
            return True

        # If not found in sensors, try displays
        result = await db.execute("""
            DELETE FROM display_devices WHERE dev_eui = $1 AND status = 'orphan'
        """, device_eui)

        if result == "DELETE 1":
            logger.info(f"Deleted orphan display device {device_eui}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error deleting orphan device {device_eui}: {e}")
        return False
