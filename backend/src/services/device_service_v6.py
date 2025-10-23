# src/services/device_service_v6.py

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class DeviceServiceV6:
    """Device service with proper tenant scoping"""

    def __init__(self, db, tenant_context):
        self.db = db
        self.tenant = tenant_context

    async def list_devices(
        self,
        status: Optional[str] = None,
        include_stats: bool = False
    ) -> dict:
        """List devices with v6 tenant scoping"""

        # Build base query
        query = """
            SELECT
                id, dev_eui, name, tenant_id, status,
                lifecycle_state, assigned_space_id, assigned_at,
                last_seen_at, created_at, updated_at
            FROM sensor_devices
            WHERE 1=1
        """
        params = []

        # Apply tenant filter (RLS will also enforce this)
        if not (self.tenant.is_platform_admin and self.tenant.is_viewing_platform_tenant):
            query += " AND tenant_id = $1"
            params.append(self.tenant.tenant_id)

        # Apply status filter
        if status:
            param_num = len(params) + 1
            query += f" AND status = ${param_num}"
            params.append(status)

        query += " ORDER BY created_at DESC"

        # Execute query
        devices = await self.db.fetch(query, *params)

        # Build response
        response = {
            "devices": [self._device_to_dict(d) for d in devices],
            "count": len(devices),
            "tenant_scope": str(self.tenant.tenant_id),
            "is_cross_tenant": self.tenant.is_platform_admin and self.tenant.is_viewing_platform_tenant
        }

        # Add statistics if requested
        if include_stats:
            response["stats"] = await self._get_device_stats()

        return response

    async def assign_device_to_space(
        self,
        device_id: UUID,
        space_id: UUID,
        reason: str = "Manual assignment"
    ) -> dict:
        """Assign device to space with v6 validation"""

        # Get device
        device = await self.db.fetchrow(
            "SELECT * FROM sensor_devices WHERE id = $1",
            device_id
        )

        if not device:
            raise ValueError(f"Device {device_id} not found")

        # Verify tenant access
        if not self.tenant.can_access_tenant(device['tenant_id']):
            raise PermissionError("Cannot access device from another tenant")

        # Get space
        space = await self.db.fetchrow(
            "SELECT * FROM spaces WHERE id = $1",
            space_id
        )

        if not space:
            raise ValueError(f"Space {space_id} not found")

        # Verify same tenant
        if device['tenant_id'] != space['tenant_id']:
            raise ValueError("Device and space must belong to same tenant")

        # Check if already assigned
        if device['status'] == 'assigned' and device['assigned_space_id']:
            raise ValueError(f"Device already assigned to space {device['assigned_space_id']}")

        # Update device
        await self.db.execute("""
            UPDATE sensor_devices
            SET status = 'assigned',
                assigned_space_id = $1,
                assigned_at = $2,
                lifecycle_state = 'operational',
                updated_at = $2
            WHERE id = $3
        """, space_id, datetime.utcnow(), device_id)

        # Update space
        await self.db.execute("""
            UPDATE spaces
            SET sensor_device_id = $1,
                updated_at = $2
            WHERE id = $3
        """, device_id, datetime.utcnow(), space_id)

        # Create assignment history
        await self.db.execute("""
            INSERT INTO device_assignments (
                tenant_id, device_type, device_id, dev_eui,
                space_id, assigned_by, assignment_reason
            ) VALUES ($1, 'sensor', $2, $3, $4, $5, $6)
        """, device['tenant_id'], device_id, device['dev_eui'],
            space_id, self.tenant.user_id, reason)

        return {
            "success": True,
            "device_id": str(device_id),
            "space_id": str(space_id),
            "message": f"Device {device['dev_eui']} assigned to space {space['code']}"
        }

    async def unassign_device(
        self,
        device_id: UUID,
        reason: str = "Manual unassignment"
    ) -> dict:
        """Unassign device from its current space"""

        # Get device
        device = await self.db.fetchrow(
            "SELECT * FROM sensor_devices WHERE id = $1",
            device_id
        )

        if not device:
            raise ValueError(f"Device {device_id} not found")

        # Verify tenant access
        if not self.tenant.can_access_tenant(device['tenant_id']):
            raise PermissionError("Cannot access device from another tenant")

        if device['status'] != 'assigned' or not device['assigned_space_id']:
            raise ValueError("Device is not currently assigned")

        space_id = device['assigned_space_id']

        # Update device
        await self.db.execute("""
            UPDATE sensor_devices
            SET status = 'unassigned',
                assigned_space_id = NULL,
                lifecycle_state = 'provisioned',
                updated_at = $1
            WHERE id = $2
        """, datetime.utcnow(), device_id)

        # Update space
        await self.db.execute("""
            UPDATE spaces
            SET sensor_device_id = NULL,
                updated_at = $1
            WHERE id = $2
        """, datetime.utcnow(), space_id)

        # Update assignment history
        await self.db.execute("""
            UPDATE device_assignments
            SET unassigned_at = $1,
                unassigned_by = $2,
                unassignment_reason = $3
            WHERE device_id = $4
            AND unassigned_at IS NULL
        """, datetime.utcnow(), self.tenant.user_id, reason, device_id)

        return {
            "success": True,
            "device_id": str(device_id),
            "message": f"Device {device['dev_eui']} unassigned"
        }

    async def get_device_pool_stats(self) -> dict:
        """Get device pool statistics (platform admin only)"""
        if not self.tenant.is_platform_admin:
            raise PermissionError("Only platform admins can view pool statistics")

        # Get statistics across all tenants
        stats = await self.db.fetch("""
            SELECT
                t.name as tenant_name,
                COUNT(sd.id) as device_count,
                COUNT(sd.id) FILTER (WHERE sd.status = 'assigned') as assigned_count,
                COUNT(sd.id) FILTER (WHERE sd.status = 'unassigned') as unassigned_count
            FROM tenants t
            LEFT JOIN sensor_devices sd ON sd.tenant_id = t.id
            GROUP BY t.id, t.name
            ORDER BY t.name
        """)

        return {
            "tenants": [
                {
                    "name": s['tenant_name'],
                    "total": s['device_count'],
                    "assigned": s['assigned_count'],
                    "unassigned": s['unassigned_count']
                }
                for s in stats
            ],
            "total_devices": sum(s['device_count'] for s in stats),
            "total_assigned": sum(s['assigned_count'] for s in stats),
            "total_unassigned": sum(s['unassigned_count'] for s in stats)
        }

    async def _get_device_stats(self) -> dict:
        """Get device statistics for current tenant"""
        stats = await self.db.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'assigned') as assigned,
                COUNT(*) FILTER (WHERE status = 'unassigned') as unassigned,
                COUNT(*) FILTER (WHERE status = 'active') as active,
                COUNT(*) FILTER (WHERE status = 'inactive') as inactive
            FROM sensor_devices
            WHERE tenant_id = $1
        """, self.tenant.tenant_id)

        return dict(stats) if stats else {}

    def _device_to_dict(self, device) -> dict:
        """Convert device row to dictionary"""
        return {
            "id": str(device['id']),
            "dev_eui": device['dev_eui'],
            "name": device['name'],
            "tenant_id": str(device['tenant_id']),
            "status": device['status'],
            "lifecycle_state": device['lifecycle_state'],
            "assigned_space_id": str(device['assigned_space_id']) if device['assigned_space_id'] else None,
            "assigned_at": device['assigned_at'].isoformat() if device['assigned_at'] else None,
            "last_seen_at": device['last_seen_at'].isoformat() if device['last_seen_at'] else None
        }
