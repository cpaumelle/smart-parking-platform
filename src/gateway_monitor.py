"""
Gateway Health Monitoring for ChirpStack
Tracks gateway online/offline status and provides failover support for Class C downlinks
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncpg

logger = logging.getLogger(__name__)


class GatewayMonitor:
    """
    Monitor ChirpStack gateway health and provide failover recommendations
    """

    def __init__(self, chirpstack_dsn: str, offline_threshold_minutes: int = 5):
        """
        Initialize gateway monitor

        Args:
            chirpstack_dsn: ChirpStack database connection string
            offline_threshold_minutes: Minutes since last_seen to consider gateway offline
        """
        self.chirpstack_dsn = chirpstack_dsn
        self.offline_threshold = timedelta(minutes=offline_threshold_minutes)
        self.pool: Optional[asyncpg.Pool] = None
        self._gateway_cache: Dict[str, Dict] = {}
        self._cache_updated: Optional[datetime] = None
        self._cache_ttl = timedelta(seconds=30)

    async def connect(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.chirpstack_dsn,
                min_size=1,
                max_size=3,
                command_timeout=10
            )
            logger.info("Gateway monitor connected to ChirpStack database")
        except Exception as e:
            logger.error(f"Failed to connect gateway monitor: {e}")

    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Gateway monitor disconnected")

    async def get_all_gateways(self, refresh: bool = False) -> List[Dict]:
        """
        Get all gateways with their status

        Args:
            refresh: Force cache refresh

        Returns:
            List of gateway dictionaries with status info
        """
        if not self.pool:
            logger.warning("Gateway monitor not connected")
            return []

        # Check cache
        now = datetime.utcnow()
        if not refresh and self._cache_updated and (now - self._cache_updated) < self._cache_ttl:
            return list(self._gateway_cache.values())

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        encode(gateway_id, 'hex') as gateway_id,
                        name,
                        description,
                        last_seen_at,
                        properties
                    FROM gateway
                    ORDER BY last_seen_at DESC NULLS LAST
                """)

                gateways = []
                for row in rows:
                    gateway_id = row['gateway_id']
                    last_seen = row['last_seen_at']

                    # Determine online status
                    is_online = False
                    minutes_offline = None
                    if last_seen:
                        time_since_seen = now - last_seen.replace(tzinfo=None)
                        is_online = time_since_seen < self.offline_threshold
                        if not is_online:
                            minutes_offline = int(time_since_seen.total_seconds() / 60)

                    gateway_info = {
                        'gateway_id': gateway_id,
                        'name': row['name'],
                        'description': row['description'],
                        'last_seen_at': last_seen.isoformat() if last_seen else None,
                        'is_online': is_online,
                        'minutes_offline': minutes_offline,
                        'properties': row['properties']
                    }

                    gateways.append(gateway_info)
                    self._gateway_cache[gateway_id] = gateway_info

                self._cache_updated = now
                logger.debug(f"Refreshed gateway cache: {len(gateways)} gateways")
                return gateways

        except Exception as e:
            logger.error(f"Failed to get gateways: {e}")
            return []

    async def get_online_gateways(self) -> List[Dict]:
        """Get list of currently online gateways"""
        all_gateways = await self.get_all_gateways()
        return [gw for gw in all_gateways if gw['is_online']]

    async def get_offline_gateways(self) -> List[Dict]:
        """Get list of currently offline gateways"""
        all_gateways = await self.get_all_gateways()
        return [gw for gw in all_gateways if not gw['is_online']]

    async def is_gateway_online(self, gateway_id: str) -> bool:
        """
        Check if specific gateway is online

        Args:
            gateway_id: Gateway EUI as hex string

        Returns:
            True if online, False if offline or not found
        """
        gateways = await self.get_all_gateways()
        for gw in gateways:
            if gw['gateway_id'] == gateway_id:
                return gw['is_online']
        return False

    async def get_device_last_gateway(self, dev_eui: str) -> Optional[str]:
        """
        Get the gateway that last received uplink from device

        Args:
            dev_eui: Device EUI as hex string

        Returns:
            Gateway ID or None if not found
        """
        if not self.pool:
            return None

        try:
            # Note: ChirpStack doesn't store last gateway in device table
            # This would require querying device_uplink_frame or similar
            # For now, we return None and rely on ChirpStack's internal routing
            logger.debug(f"Device last gateway lookup not implemented for {dev_eui}")
            return None
        except Exception as e:
            logger.error(f"Failed to get device last gateway: {e}")
            return None

    async def get_health_summary(self) -> Dict:
        """
        Get overall gateway health summary

        Returns:
            Dictionary with health metrics
        """
        all_gateways = await self.get_all_gateways(refresh=True)
        online_gateways = [gw for gw in all_gateways if gw['is_online']]
        offline_gateways = [gw for gw in all_gateways if not gw['is_online']]

        return {
            'total_gateways': len(all_gateways),
            'online_count': len(online_gateways),
            'offline_count': len(offline_gateways),
            'online_gateways': [gw['gateway_id'] for gw in online_gateways],
            'offline_gateways': [
                {
                    'gateway_id': gw['gateway_id'],
                    'name': gw['name'],
                    'minutes_offline': gw['minutes_offline']
                }
                for gw in offline_gateways
            ],
            'health_status': 'healthy' if len(online_gateways) > 0 else 'critical',
            'checked_at': datetime.utcnow().isoformat()
        }
