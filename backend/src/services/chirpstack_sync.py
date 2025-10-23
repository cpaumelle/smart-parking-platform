# src/services/chirpstack_sync.py

import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ChirpStackSyncService:
    """Service to synchronize devices and gateways with ChirpStack"""

    def __init__(self, chirpstack_url: str, api_token: str, db):
        self.chirpstack_url = chirpstack_url
        self.api_token = api_token
        self.db = db

    async def sync_all_tenants(self):
        """Background job to sync all tenant devices with ChirpStack"""
        while True:
            try:
                await self._perform_sync()
                await asyncio.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"ChirpStack sync failed: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute

    async def _perform_sync(self):
        """Perform actual synchronization"""
        # Get all pending sync items
        pending_syncs = await self.db.fetch("""
            SELECT * FROM chirpstack_sync
            WHERE sync_status IN ('pending', 'error')
            AND (next_sync_at IS NULL OR next_sync_at <= NOW())
            ORDER BY created_at
            LIMIT 100
        """)

        for sync_item in pending_syncs:
            await self._sync_entity(sync_item)

    async def _sync_entity(self, sync_item: Dict[str, Any]):
        """Sync a single entity with ChirpStack"""
        try:
            if sync_item['entity_type'] == 'device':
                await self._sync_device(sync_item)
            elif sync_item['entity_type'] == 'gateway':
                await self._sync_gateway(sync_item)

            # Update sync status
            await self._update_sync_status(
                sync_item['id'],
                'synced',
                datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Sync error for {sync_item['entity_type']} {sync_item['entity_id']}: {e}")
            # Log error and mark for retry
            await self._update_sync_status(
                sync_item['id'],
                'error',
                None,
                datetime.utcnow() + timedelta(minutes=15),
                str(e)
            )

    async def _sync_device(self, sync_item: Dict[str, Any]):
        """Sync device with ChirpStack"""
        # Get device from our database
        device = await self.db.fetchrow("""
            SELECT * FROM sensor_devices
            WHERE id = $1
        """, sync_item['entity_id'])

        if not device:
            raise ValueError(f"Device {sync_item['entity_id']} not found")

        # TODO: Implement actual ChirpStack gRPC calls
        # This would use chirpstack_api.api module to:
        # 1. Check if device exists in ChirpStack
        # 2. Create or update device
        # 3. Sync device profile and application

        logger.info(f"Would sync device {device['dev_eui']} with ChirpStack")

    async def _sync_gateway(self, sync_item: Dict[str, Any]):
        """Sync gateway with ChirpStack"""
        # Get gateway from our database
        gateway = await self.db.fetchrow("""
            SELECT * FROM gateways
            WHERE id = $1
        """, sync_item['entity_id'])

        if not gateway:
            raise ValueError(f"Gateway {sync_item['entity_id']} not found")

        # TODO: Implement actual ChirpStack gRPC calls
        logger.info(f"Would sync gateway {gateway['gateway_id']} with ChirpStack")

    async def import_from_chirpstack(self, tenant_id):
        """Import all devices from ChirpStack for a tenant"""
        # TODO: Implement ChirpStack import
        # This would:
        # 1. List all devices from ChirpStack
        # 2. Check which ones don't exist in our DB
        # 3. Import new devices with tenant_id

        logger.info(f"Would import devices from ChirpStack for tenant {tenant_id}")
        return 0

    async def _update_sync_status(
        self,
        sync_id,
        status: str,
        last_sync_at=None,
        next_sync_at=None,
        error_msg=None
    ):
        """Update sync status in database"""
        error_json = f'["{error_msg}"]' if error_msg else '[]'

        await self.db.execute("""
            UPDATE chirpstack_sync
            SET sync_status = $1,
                last_sync_at = COALESCE($2, last_sync_at),
                next_sync_at = $3,
                sync_errors = $4::jsonb,
                updated_at = NOW()
            WHERE id = $5
        """, status, last_sync_at, next_sync_at, error_json, sync_id)

    async def queue_sync(self, entity_type: str, entity_id, chirpstack_id: str, tenant_id):
        """Queue an entity for synchronization"""
        await self.db.execute("""
            INSERT INTO chirpstack_sync (
                tenant_id, entity_type, entity_id, chirpstack_id,
                sync_status, sync_direction
            ) VALUES ($1, $2, $3, $4, 'pending', 'push')
            ON CONFLICT (entity_type, entity_id)
            DO UPDATE SET
                sync_status = 'pending',
                next_sync_at = NOW(),
                updated_at = NOW()
        """, tenant_id, entity_type, entity_id, chirpstack_id)
