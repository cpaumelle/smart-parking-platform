"""
ChirpStack Database Client
Direct PostgreSQL database access to ChirpStack (same pattern as v4)
ChirpStack 4 stores all data in PostgreSQL, so we query it directly

This approach is more reliable than using ChirpStack's gRPC API and
provides better performance for read-heavy operations.
"""
import asyncpg
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from functools import wraps

from .exceptions import ChirpStackError, DeviceNotFoundError
from .config import settings

logger = logging.getLogger(__name__)

# Import ChirpStack gRPC modules at module level to avoid repeated initialization
# The chirpstack_api package has broken __init__.py files, so we need workarounds
try:
    # Try normal import first (works if package is properly installed)
    from chirpstack_api.api import device_pb2, device_pb2_grpc
    logger.debug("ChirpStack API imports successful (normal path)")
except Exception as e:
    logger.warning(f"Normal chirpstack_api import failed: {e}, trying workaround...")
    # Workaround for broken package: import the compiled protobuf modules directly
    import sys
    import types

    # Create dummy parent module to avoid __init__.py execution
    if 'chirpstack_api' not in sys.modules:
        sys.modules['chirpstack_api'] = types.ModuleType('chirpstack_api')
    if 'chirpstack_api.api' not in sys.modules:
        sys.modules['chirpstack_api.api'] = types.ModuleType('chirpstack_api.api')

    # Now import the actual modules
    import chirpstack_api.api.device_pb2 as device_pb2
    import chirpstack_api.api.device_pb2_grpc as device_pb2_grpc
    logger.debug("ChirpStack API imports successful (workaround path)")

# Extract the classes we need
DeviceQueueItem = device_pb2.DeviceQueueItem
EnqueueDeviceQueueItemRequest = device_pb2.EnqueueDeviceQueueItemRequest
DeviceServiceStub = device_pb2_grpc.DeviceServiceStub

# Retry decorator for transient failures
def with_retry(max_attempts=3, delay=1.0):
    """Retry decorator for database operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(self, *args, **kwargs)
                except (asyncpg.PostgresError, asyncpg.InterfaceError) as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}), "
                            f"retrying in {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
            raise ChirpStackError(f"Failed after {max_attempts} attempts: {last_error}")
        return wrapper
    return decorator

class ChirpStackClient:
    """
    ChirpStack client using direct PostgreSQL database access
    This is more reliable than trying to use ChirpStack 4's gRPC API
    """

    def __init__(self, host: str, port: int, api_key: str):
        self.host = host  # Database host (postgres container)
        self.db_port = 5432  # PostgreSQL port, not ChirpStack port
        self.api_key = api_key  # Not used for DB access, kept for compatibility

        # Build ChirpStack database URL
        # Using same credentials as main database but different database name
        db_parts = settings.database_url.split('/')
        base_url = '/'.join(db_parts[:-1])
        self.chirpstack_dsn = f"{base_url}/chirpstack"

        self.pool: Optional[asyncpg.Pool] = None
        self._connected = False

    async def connect(self):
        """Initialize database connection pool with retry logic"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                logger.info(f"Creating ChirpStack database pool (attempt {attempt + 1}/{max_attempts})...")

                self.pool = await asyncpg.create_pool(
                    self.chirpstack_dsn,
                    min_size=2,
                    max_size=10,
                    max_queries=10000,
                    max_inactive_connection_lifetime=300,
                    command_timeout=30,
                    server_settings={
                        'application_name': 'parking_v5_chirpstack',
                        'jit': 'off'
                    }
                )

                # Test connection and verify schema
                async with self.pool.acquire() as conn:
                    # Test basic connectivity
                    await conn.fetchval("SELECT 1")

                    # Verify device table exists
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'device'
                        )
                    """)

                    if not table_exists:
                        raise ChirpStackError("ChirpStack database schema not found (device table missing)")

                self._connected = True
                logger.info(f"✅ Connected to ChirpStack database successfully")
                return

            except Exception as e:
                logger.warning(f"ChirpStack database connection failed (attempt {attempt + 1}/{max_attempts}): {e}")
                self._connected = False

                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    # Don't fail startup if ChirpStack DB isn't ready
                    logger.error(f"❌ ChirpStack database connection failed after {max_attempts} attempts. Some features will be unavailable.")
                    self._connected = False

    async def disconnect(self):
        """Close database connection pool gracefully"""
        if self.pool:
            try:
                # Close pool with timeout
                await asyncio.wait_for(self.pool.close(), timeout=5.0)
                logger.info("ChirpStack database pool closed")
            except asyncio.TimeoutError:
                logger.warning("ChirpStack database pool close timed out")
            except Exception as e:
                logger.error(f"Error closing ChirpStack database pool: {e}")
        self._connected = False

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for ChirpStack connection"""
        if not self.pool or not self._connected:
            return {
                "status": "disconnected",
                "error": "Not connected to ChirpStack database"
            }

        try:
            async with self.pool.acquire() as conn:
                # Test query with timeout
                device_count = await asyncio.wait_for(
                    conn.fetchval("SELECT COUNT(*) FROM device"),
                    timeout=5.0
                )

                # Get pool stats
                pool_size = self.pool.get_size()
                pool_free = self.pool.get_idle_size()

                return {
                    "status": "healthy",
                    "version": "4.x",
                    "device_count": device_count,
                    "pool_size": pool_size,
                    "pool_free": pool_free,
                    "pool_max": self.pool.get_max_size()
                }
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": "Health check query timed out"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def get_version(self) -> Dict[str, str]:
        """Test ChirpStack database connectivity (simplified health check)"""
        health = await self.health_check()
        if health["status"] != "healthy":
            raise ChirpStackError(f"ChirpStack unhealthy: {health.get('error', 'Unknown error')}")
        return {
            "status": "connected",
            "version": health["version"],
            "device_count": health["device_count"]
        }

    @with_retry(max_attempts=3, delay=0.5)
    async def get_device(self, dev_eui: str) -> Optional[Dict[str, Any]]:
        """Get device information from database with retry logic"""
        if not self.pool or not self._connected:
            logger.warning("Cannot get device: not connected to ChirpStack database")
            return None

        try:
            # Convert hex string to bytes
            dev_eui_bytes = bytes.fromhex(dev_eui)

            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT
                        dev_eui,
                        name,
                        description,
                        application_id,
                        device_profile_id,
                        enabled_class,
                        is_disabled,
                        battery_level,
                        last_seen_at,
                        created_at,
                        updated_at
                    FROM device
                    WHERE dev_eui = $1
                """, dev_eui_bytes)

                if not row:
                    return None

                # Convert to dict with hex-encoded dev_eui
                return {
                    "dev_eui": row['dev_eui'].hex(),
                    "name": row['name'],
                    "description": row['description'],
                    "application_id": str(row['application_id']),
                    "device_profile_id": str(row['device_profile_id']),
                    "enabled_class": row['enabled_class'],
                    "is_disabled": row['is_disabled'],
                    "battery_level": float(row['battery_level']) if row['battery_level'] else None,
                    "last_seen_at": row['last_seen_at'].isoformat() if row['last_seen_at'] else None,
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None,
                }
        except Exception as e:
            logger.error(f"Failed to get device {dev_eui}: {e}")
            raise ChirpStackError(f"Failed to get device: {e}")

    @with_retry(max_attempts=3, delay=0.5)
    async def get_device_count(self) -> int:
        """Get total device count from database with retry logic"""
        if not self.pool or not self._connected:
            logger.warning("Cannot get device count: not connected to ChirpStack database")
            return 0

        try:
            async with self.pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM device WHERE is_disabled = false")
                return count or 0
        except Exception as e:
            logger.error(f"Failed to get device count: {e}")
            return 0

    @with_retry(max_attempts=3, delay=0.5)
    async def get_devices(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List devices from database with retry logic"""
        if not self.pool or not self._connected:
            logger.warning("Cannot list devices: not connected to ChirpStack database")
            return []

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        dev_eui,
                        name,
                        description,
                        application_id,
                        last_seen_at,
                        is_disabled,
                        battery_level
                    FROM device
                    ORDER BY last_seen_at DESC NULLS LAST
                    LIMIT $1 OFFSET $2
                """, limit, offset)

                devices = []
                for row in rows:
                    devices.append({
                        "dev_eui": row['dev_eui'].hex(),
                        "name": row['name'],
                        "description": row['description'],
                        "application_id": str(row['application_id']),
                        "last_seen_at": row['last_seen_at'].isoformat() if row['last_seen_at'] else None,
                        "is_disabled": row['is_disabled'],
                        "battery_level": float(row['battery_level']) if row['battery_level'] else None,
                    })

                return devices
        except Exception as e:
            logger.error(f"Failed to list devices: {e}")
            return []

    async def queue_downlink(
        self,
        device_eui: str,
        payload: bytes,
        fport: int = 1,
        confirmed: bool = False
    ) -> Dict[str, Any]:
        """
        Queue a downlink message using ChirpStack gRPC API (same as V4)

        This triggers immediate Class C transmission via the gRPC Enqueue method.
        """
        # Use pre-imported gRPC modules (imported at module level)
        import base64
        import grpc

        try:
            if isinstance(payload, str):
                payload_bytes = bytes.fromhex(payload)
            else:
                payload_bytes = payload

            # Create gRPC channel (same as V4)
            channel = grpc.insecure_channel(f"{self.host}:8080")
            client = DeviceServiceStub(channel)

            # Create auth metadata
            auth_token = [("authorization", f"Bearer {self.api_key}")]

            # Create queue item (same structure as V4)
            queue_item = DeviceQueueItem(
                dev_eui=device_eui,
                confirmed=confirmed,
                f_port=fport,
                data=payload_bytes,
            )

            # Enqueue via gRPC (same as V4)
            req = EnqueueDeviceQueueItemRequest(queue_item=queue_item)
            response = client.Enqueue(req, metadata=auth_token)

            # Response has 'id' field (queue item ID), not f_cnt
            queue_id = response.id if hasattr(response, 'id') else 'unknown'
            logger.info(f"Queued downlink for {device_eui}: fport={fport}, payload={payload_bytes.hex()}, queue_id={queue_id}")

            return {
                "id": str(queue_id),
                "dev_eui": device_eui,
                "f_port": fport,
                "confirmed": confirmed,
                "data": base64.b64encode(payload_bytes).decode()
            }

        except grpc.RpcError as e:
            logger.error(f"gRPC error queueing downlink for {device_eui}: {e.code()} - {e.details()}")
            raise ChirpStackError(f"gRPC error: {e.details()}")
        except Exception as e:
            logger.error(f"Failed to queue downlink for {device_eui}: {e}")
            raise ChirpStackError(f"Failed to queue downlink: {e}")

    async def get_device_queue(self, device_eui: str) -> List[Dict[str, Any]]:
        """Get device downlink queue from database"""
        try:
            dev_eui_bytes = bytes.fromhex(device_eui)

            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, f_port, confirmed, data, is_pending, created_at
                    FROM device_queue_item
                    WHERE dev_eui = $1 AND is_pending = true
                    ORDER BY created_at ASC
                """, dev_eui_bytes)

                import base64
                queue = []
                for row in rows:
                    queue.append({
                        "id": str(row['id']),
                        "f_port": row['f_port'],
                        "confirmed": row['confirmed'],
                        "data": base64.b64encode(row['data']).decode(),
                        "is_pending": row['is_pending'],
                        "created_at": row['created_at'].isoformat()
                    })

                return queue
        except Exception as e:
            logger.error(f"Failed to get device queue for {device_eui}: {e}")
            return []

    async def flush_device_queue(self, device_eui: str):
        """Flush device downlink queue"""
        try:
            dev_eui_bytes = bytes.fromhex(device_eui)

            async with self.pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM device_queue_item
                    WHERE dev_eui = $1 AND is_pending = true
                """, dev_eui_bytes)

            logger.info(f"Flushed queue for device {device_eui}")
        except Exception as e:
            logger.error(f"Failed to flush device queue for {device_eui}: {e}")
            raise ChirpStackError(f"Failed to flush device queue: {e}")
