"""
Database connection pool and query functions
This is the heart of data operations
"""
import asyncpg
from typing import Optional, List, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import json
from uuid import UUID

from .config import settings
from .models import (
    Space, SpaceCreate, SpaceUpdate,
    Reservation, ReservationCreate,
    SpaceState, ReservationStatus
)
from .exceptions import (
    DatabaseError,
    SpaceNotFoundError,
    ReservationNotFoundError,
    DuplicateResourceError
)
from .utils import utcnow

logger = logging.getLogger(__name__)

class DatabasePool:
    """
    Async PostgreSQL connection pool
    Simplified but production-ready
    """

    def __init__(self, dsn: str = None):
        self.dsn = dsn or settings.database_url
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def initialize(self):
        """Create connection pool"""
        if self._initialized:
            return

        try:
            logger.info(f"Creating database pool...")

            self.pool = await asyncpg.create_pool(
                self.dsn,
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                command_timeout=60,
                server_settings={
                    'application_name': 'parking_v5',
                    'jit': 'off'
                }
            )

            # Test connection
            async with self.pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                logger.info(f"Connected to PostgreSQL: {version[:30]}...")

            self._initialized = True
            logger.info(f"Database pool ready: {self.get_stats()}")

        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise DatabaseError(f"Cannot connect to database: {e}")

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("Database pool closed")

    @asynccontextmanager
    async def acquire(self, tenant_id: Optional[UUID] = None) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Acquire connection from pool with optional tenant context for RLS

        Args:
            tenant_id: Optional tenant ID to set for Row-Level Security isolation
                      If provided, sets app.current_tenant for this connection
        """
        if not self.pool:
            raise DatabaseError("Database pool not initialized")

        async with self.pool.acquire() as conn:
            # Set tenant context for Row-Level Security if provided
            if tenant_id:
                await conn.execute(f"SET LOCAL app.current_tenant = '{tenant_id}'")
            yield conn

    @asynccontextmanager
    async def transaction(self, tenant_id: Optional[UUID] = None) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Execute in transaction with optional tenant context for RLS

        Args:
            tenant_id: Optional tenant ID to set for Row-Level Security isolation
        """
        async with self.acquire(tenant_id=tenant_id) as conn:
            async with conn.transaction():
                yield conn

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        if not self.pool:
            return {"status": "not_initialized"}

        return {
            "size": self.pool.get_size(),
            "min_size": self.pool.get_min_size(),
            "max_size": self.pool.get_max_size(),
            "free_connections": self.pool.get_idle_size(),
        }

    # ============================================================
    # Space Operations
    # ============================================================

    async def get_spaces(
        self,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        zone: Optional[str] = None,
        state: Optional[SpaceState] = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Space]:
        """Get spaces with filters"""

        query = """
            SELECT
                id, name, code, building, floor, zone,
                sensor_eui, display_eui, state,
                gps_latitude, gps_longitude,
                metadata, created_at, updated_at, deleted_at
            FROM spaces
            WHERE 1=1
        """

        params = []
        conditions = []

        if not include_deleted:
            conditions.append("deleted_at IS NULL")

        if building:
            params.append(building)
            conditions.append(f"building = ${len(params)}")

        if floor:
            params.append(floor)
            conditions.append(f"floor = ${len(params)}")

        if zone:
            params.append(zone)
            conditions.append(f"zone = ${len(params)}")

        if state:
            params.append(state.value if hasattr(state, 'value') else state)
            conditions.append(f"state = ${len(params)}")

        if conditions:
            query += " AND " + " AND ".join(conditions)

        query += f" ORDER BY name LIMIT {limit} OFFSET {offset}"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)

        spaces = []
        for row in rows:
            row_dict = dict(row)
            # Parse metadata JSON string to dict
            if row_dict.get('metadata') and isinstance(row_dict['metadata'], str):
                row_dict['metadata'] = json.loads(row_dict['metadata'])
            spaces.append(Space(**row_dict))

        return spaces

    async def get_space(self, space_id: str) -> Optional[Space]:
        """Get single space by ID"""

        query = """
            SELECT * FROM spaces
            WHERE id = $1 AND deleted_at IS NULL
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query, space_id)

        if not row:
            return None

        row_dict = dict(row)
        # Parse metadata JSON string to dict
        if row_dict.get('metadata') and isinstance(row_dict['metadata'], str):
            row_dict['metadata'] = json.loads(row_dict['metadata'])

        return Space(**row_dict)

    async def get_space_by_sensor(self, sensor_eui: str) -> Optional[Space]:
        """Get space by sensor DevEUI (EUI normalized at ingestion)"""

        query = """
            SELECT * FROM spaces
            WHERE sensor_eui = $1 AND deleted_at IS NULL
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query, sensor_eui)

        if not row:
            return None

        row_dict = dict(row)
        # Parse metadata JSON string to dict
        if row_dict.get('metadata') and isinstance(row_dict['metadata'], str):
            row_dict['metadata'] = json.loads(row_dict['metadata'])

        return Space(**row_dict)

    async def create_space(self, space: SpaceCreate) -> Space:
        """Create new space"""

        query = """
            INSERT INTO spaces (
                name, code, building, floor, zone,
                sensor_eui, display_eui, state,
                gps_latitude, gps_longitude, metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
            )
            RETURNING *
        """

        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    space.name, space.code, space.building, space.floor, space.zone,
                    space.sensor_eui.upper() if space.sensor_eui else None,
                    space.display_eui.upper() if space.display_eui else None,
                    space.state.value,
                    space.gps_latitude, space.gps_longitude,
                    json.dumps(space.metadata) if space.metadata else None
                )

            return Space(**dict(row))

        except asyncpg.UniqueViolationError as e:
            if "sensor_eui" in str(e):
                raise DuplicateResourceError("Sensor", space.sensor_eui)
            elif "code" in str(e):
                raise DuplicateResourceError("Space code", space.code)
            raise DatabaseError(f"Unique constraint violation: {e}")

    async def update_space(
        self,
        space_id: str,
        updates: SpaceUpdate
    ) -> Space:
        """Update space with partial updates"""

        # Build dynamic UPDATE query
        set_clauses = []
        params = [space_id]

        update_dict = updates.dict(exclude_unset=True)

        for field, value in update_dict.items():
            params.append(value)

            # Handle special fields
            if field in ["sensor_eui", "display_eui"] and value:
                set_clauses.append(f"{field} = LOWER(${len(params)})")
            elif field == "metadata":
                set_clauses.append(f"{field} = ${len(params)}::jsonb")
            elif field == "state" and hasattr(value, 'value'):
                params[-1] = value.value  # Get enum value
                set_clauses.append(f"{field} = ${len(params)}")
            else:
                set_clauses.append(f"{field} = ${len(params)}")

        if not set_clauses:
            # No updates, return existing
            space = await self.get_space(space_id)
            if not space:
                raise SpaceNotFoundError(space_id)
            return space

        query = f"""
            UPDATE spaces
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING *
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            raise SpaceNotFoundError(space_id)

        return Space(**dict(row))

    async def soft_delete_space(self, space_id: str):
        """Soft delete space"""

        query = """
            UPDATE spaces
            SET deleted_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id
        """

        async with self.acquire() as conn:
            result = await conn.fetchval(query, space_id)

        if not result:
            raise SpaceNotFoundError(space_id)

    async def update_space_state(
        self,
        space_id: str,
        new_state: SpaceState,
        source: str = "system"
    ) -> tuple[Optional[str], str]:
        """
        Update space state and return (old_state, new_state)
        Also records state change in audit table
        """

        async with self.transaction() as conn:
            # Get current state with lock
            old_state = await conn.fetchval("""
                SELECT state FROM spaces
                WHERE id = $1 AND deleted_at IS NULL
                FOR UPDATE
            """, space_id)

            if old_state is None:
                raise SpaceNotFoundError(space_id)

            # Update state
            await conn.execute("""
                UPDATE spaces
                SET state = $1, updated_at = NOW()
                WHERE id = $2
            """, new_state.value, space_id)

            # Record state change
            await conn.execute("""
                INSERT INTO state_changes (
                    space_id, previous_state, new_state, source
                ) VALUES ($1, $2, $3, $4)
            """, space_id, old_state, new_state.value, source)

            return old_state, new_state.value

    # ============================================================
    # Reservation Operations
    # ============================================================

    async def get_reservations(
        self,
        space_id: Optional[str] = None,
        user_email: Optional[str] = None,
        status: Optional[ReservationStatus] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Reservation]:
        """Get reservations with filters"""

        query = "SELECT * FROM reservations WHERE 1=1"
        params = []

        if space_id:
            params.append(space_id)
            query += f" AND space_id = ${len(params)}"

        if user_email:
            params.append(user_email)
            query += f" AND user_email = ${len(params)}"

        if status:
            params.append(status.value if hasattr(status, 'value') else status)
            query += f" AND status = ${len(params)}"

        if date_from:
            params.append(date_from)
            query += f" AND end_time >= ${len(params)}"

        if date_to:
            params.append(date_to)
            query += f" AND start_time <= ${len(params)}"

        query += f" ORDER BY start_time DESC LIMIT {limit} OFFSET {offset}"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [Reservation(**dict(row)) for row in rows]

    async def get_reservation(self, reservation_id: str) -> Optional[Reservation]:
        """Get single reservation"""

        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM reservations WHERE id = $1",
                reservation_id
            )

        if not row:
            return None

        return Reservation(**dict(row))

    async def create_reservation(
        self,
        reservation: ReservationCreate
    ) -> Reservation:
        """Create new reservation"""

        # Check for conflicts in a transaction
        async with self.transaction() as conn:
            # Check space exists
            space_exists = await conn.fetchval(
                "SELECT id FROM spaces WHERE id = $1 AND deleted_at IS NULL",
                str(reservation.space_id)
            )

            if not space_exists:
                raise SpaceNotFoundError(str(reservation.space_id))

            # Check for overlapping reservations
            overlap = await conn.fetchval("""
                SELECT COUNT(*) FROM reservations
                WHERE space_id = $1
                AND status = 'active'
                AND (
                    (start_time, end_time) OVERLAPS ($2, $3)
                )
            """, str(reservation.space_id), reservation.start_time, reservation.end_time)

            if overlap > 0:
                raise DuplicateResourceError(
                    "Reservation",
                    f"Overlapping reservation for space {reservation.space_id}"
                )

            # Create reservation
            row = await conn.fetchrow("""
                INSERT INTO reservations (
                    space_id, start_time, end_time,
                    user_email, user_phone, metadata
                ) VALUES (
                    $1, $2, $3, $4, $5, $6
                )
                RETURNING *
            """,
                str(reservation.space_id),
                reservation.start_time,
                reservation.end_time,
                reservation.user_email,
                reservation.user_phone,
                json.dumps(reservation.metadata) if reservation.metadata else None
            )

        return Reservation(**dict(row))

    async def cancel_reservation(self, reservation_id: str) -> bool:
        """Cancel reservation"""

        query = """
            UPDATE reservations
            SET status = 'cancelled', updated_at = NOW()
            WHERE id = $1 AND status = 'active'
            RETURNING id
        """

        async with self.acquire() as conn:
            result = await conn.fetchval(query, reservation_id)

        if not result:
            raise ReservationNotFoundError(reservation_id)

        return True

    async def get_active_reservations_for_space(
        self,
        space_id: str
    ) -> List[Reservation]:
        """Get all active reservations for a space"""

        query = """
            SELECT * FROM reservations
            WHERE space_id = $1
            AND status = 'active'
            AND end_time > NOW()
            ORDER BY start_time
        """

        async with self.acquire() as conn:
            rows = await conn.fetch(query, space_id)

        return [Reservation(**dict(row)) for row in rows]

    # ============================================================
    # Device Discovery & Management (ORPHAN Pattern)
    # ============================================================

    async def get_or_create_device_type_by_profile(
        self,
        chirpstack_profile_name: str,
        sample_payload: Optional[Dict[str, Any]] = None,
        category: str = 'sensor'
    ) -> Dict[str, Any]:
        """
        Get device type by ChirpStack profile name, or create ORPHAN type if not found.
        Returns: device_type row with id, type_code, status, handler_class, etc.
        """
        # Check if device type exists for this profile
        query_check = """
            SELECT id, type_code, status, handler_class, capabilities, category
            FROM device_types
            WHERE chirpstack_profile_name = $1
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query_check, chirpstack_profile_name)

            if row:
                return dict(row)

            # Device type not found - create ORPHAN type
            type_code = f"orphan_{chirpstack_profile_name.lower().replace(' ', '_').replace('-', '_')}"

            # Auto-detect capabilities from sample payload
            capabilities = self._auto_detect_capabilities(sample_payload) if sample_payload else {}

            query_insert = """
                INSERT INTO device_types (
                    type_code,
                    category,
                    name,
                    status,
                    chirpstack_profile_name,
                    sample_payload,
                    capabilities
                ) VALUES ($1, $2, $3, 'orphan', $4, $5, $6)
                RETURNING id, type_code, status, handler_class, capabilities, category
            """

            row = await conn.fetchrow(
                query_insert,
                type_code,
                category,
                f"ORPHAN: {chirpstack_profile_name}",
                chirpstack_profile_name,
                json.dumps(sample_payload) if sample_payload else None,
                json.dumps(capabilities)
            )

            logger.info(f"Created ORPHAN device_type: {type_code} for profile '{chirpstack_profile_name}'")
            return dict(row)

    def _auto_detect_capabilities(self, payload: Dict[str, Any]) -> Dict[str, bool]:
        """Auto-detect device capabilities from sample payload keys"""
        key_mapping = {
            'occupancy': 'occupancy',
            'occupied': 'occupancy',
            'temperature': 'temperature',
            'temp': 'temperature',
            'humidity': 'humidity',
            'battery': 'battery',
            'batteryLevel': 'battery',
            'battery_level': 'battery',
            'co2': 'co2',
            'rssi': 'rssi',
            'snr': 'snr',
            'door_open': 'door_state',
            'motion': 'motion'
        }

        capabilities = {}
        for key, capability in key_mapping.items():
            if key in payload:
                capabilities[capability] = True

        return capabilities

    async def get_or_create_sensor_device(
        self,
        dev_eui: str,
        device_type_id: str,
        device_name: Optional[str] = None,
        device_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get sensor device by DevEUI, or create ORPHAN device if not found.
        Returns: sensor_device row with id, dev_eui, status, device_type_id, etc.
        """
        # Check if device exists (EUI normalized to UPPERCASE at ingestion point)
        query_check = """
            SELECT id, dev_eui, device_type_id, status, device_model, enabled, last_seen_at
            FROM sensor_devices
            WHERE dev_eui = $1
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query_check, dev_eui)

            if row:
                # Update last_seen_at
                await conn.execute(
                    "UPDATE sensor_devices SET last_seen_at = NOW() WHERE id = $1",
                    row['id']
                )
                return dict(row)

            # Device not found - create ORPHAN device
            query_insert = """
                INSERT INTO sensor_devices (
                    dev_eui,
                    device_type,
                    device_type_id,
                    device_model,
                    status,
                    enabled,
                    last_seen_at
                ) VALUES ($1, 'orphan', $2, $3, 'orphan', true, NOW())
                ON CONFLICT (dev_eui) DO UPDATE
                SET last_seen_at = NOW()
                RETURNING id, dev_eui, device_type_id, status, device_model, enabled, last_seen_at
            """

            row = await conn.fetchrow(
                query_insert,
                dev_eui,
                device_type_id,
                device_model or device_name or f"Device {dev_eui[:8]}"
            )

            logger.info(f"Created ORPHAN sensor_device: {dev_eui} with type_id={device_type_id}")
            return dict(row)

    async def get_sensor_device_by_deveui(self, dev_eui: str) -> Optional[Dict[str, Any]]:
        """Get sensor device by DevEUI"""
        query = """
            SELECT
                sd.id,
                sd.dev_eui,
                sd.device_type,
                sd.device_type_id,
                sd.device_model,
                sd.status,
                sd.enabled,
                sd.last_seen_at,
                dt.handler_class,
                dt.capabilities,
                dt.status as type_status
            FROM sensor_devices sd
            LEFT JOIN device_types dt ON sd.device_type_id = dt.id
            WHERE sd.dev_eui = $1
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query, dev_eui)
            return dict(row) if row else None

    async def check_device_assigned_to_space(self, device_id: str) -> bool:
        """Check if sensor device is assigned to any space"""
        query = """
            SELECT EXISTS (
                SELECT 1 FROM spaces
                WHERE sensor_device_id = $1
                  AND deleted_at IS NULL
            )
        """

        async with self.acquire() as conn:
            return await conn.fetchval(query, device_id)

    # ============================================================
    # Sensor Data Operations
    # ============================================================

    async def insert_sensor_reading(
        self,
        device_eui: str,
        space_id: Optional[str],
        occupancy_state: Optional[str],
        battery: Optional[float],
        rssi: Optional[int],
        snr: Optional[float],
        timestamp: Optional[datetime] = None,
        fcnt: Optional[int] = None,
        tenant_id: Optional[str] = None
    ):
        """
        Insert sensor reading with idempotency via fcnt

        Args:
            fcnt: LoRaWAN frame counter for deduplication
            tenant_id: Tenant ID for multi-tenant deduplication

        Note:
            If fcnt and tenant_id are provided, duplicate uplinks (same dev_eui + fcnt)
            will be silently ignored via ON CONFLICT clause.
        """

        query = """
            INSERT INTO sensor_readings (
                device_eui, space_id, occupancy_state,
                battery, temperature, rssi, snr, timestamp, fcnt, tenant_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (tenant_id, device_eui, fcnt) WHERE fcnt IS NOT NULL
            DO NOTHING
        """

        async with self.acquire() as conn:
            result = await conn.execute(
                query,
                device_eui.upper(),
                space_id,
                occupancy_state,
                battery,
                None,  # temperature
                rssi,
                snr,
                timestamp or utcnow(),
                fcnt,
                tenant_id
            )

    async def insert_telemetry(self, device_eui: str, data: Any):
        """
        Insert raw telemetry data for unknown devices
        Useful for debugging and future device support
        """
        # Convert data to dict if it's a model
        if hasattr(data, 'dict'):
            data_dict = data.dict()
        elif isinstance(data, dict):
            data_dict = data
        else:
            data_dict = {}

        # Extract occupancy state value if it's an enum
        occupancy_state = data_dict.get('occupancy_state')
        if occupancy_state and hasattr(occupancy_state, 'value'):
            occupancy_state = occupancy_state.value

        query = """
            INSERT INTO sensor_readings (
                device_eui,
                occupancy_state,
                battery,
                rssi,
                snr,
                timestamp
            ) VALUES ($1, $2, $3, $4, $5, NOW())
        """

        async with self.acquire() as conn:
            await conn.execute(
                query,
                device_eui.upper(),
                occupancy_state,
                data_dict.get('battery'),
                data_dict.get('rssi'),
                data_dict.get('snr')
            )

    async def get_latest_sensor_reading(
        self,
        device_eui: str
    ) -> Optional[Dict[str, Any]]:
        """Get latest reading from a sensor (case-insensitive)"""

        query = """
            SELECT * FROM sensor_readings
            WHERE LOWER(device_eui) = LOWER($1)
            ORDER BY timestamp DESC
            LIMIT 1
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query, device_eui)

        return dict(row) if row else None

    # ============================================================
    # Utility Operations
    # ============================================================

    async def execute(self, query: str, *args):
        """Execute raw query"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Fetch multiple rows"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        """Fetch single row"""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch single value"""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)

# Global instance (singleton pattern)
_db_pool: Optional[DatabasePool] = None

async def get_db_pool() -> DatabasePool:
    """Get or create database pool"""
    global _db_pool

    if _db_pool is None:
        _db_pool = DatabasePool()
        await _db_pool.initialize()

    return _db_pool

async def close_db_pool():
    """Close database pool"""
    global _db_pool

    if _db_pool:
        await _db_pool.close()
        _db_pool = None

async def get_db() -> DatabasePool:
    """
    FastAPI dependency to get database pool

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: Pool = Depends(get_db)):
            result = await db.fetchrow("SELECT ...")
    """
    pool = await get_db_pool()
    return pool

@asynccontextmanager
async def get_db_with_tenant(request, tenant_id: Optional[UUID] = None) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI dependency to get database connection with tenant context for RLS

    This function automatically sets the tenant context (app.current_tenant) for
    Row-Level Security enforcement.

    Args:
        request: FastAPI request object (contains request.state.tenant_id from middleware)
        tenant_id: Optional tenant_id override (defaults to request.state.tenant_id)

    Usage:
        from fastapi import Request, Depends

        @app.get("/spaces")
        async def get_spaces(
            request: Request,
            db: asyncpg.Connection = Depends(get_db_with_tenant)
        ):
            # This query is automatically filtered by tenant_id via RLS
            rows = await db.fetch("SELECT * FROM spaces")
            return rows

    Note:
        If tenant_id is not available (e.g., public endpoints), the connection
        will work normally but RLS policies will not filter data. Make sure
        all tenant-scoped endpoints require authentication.
    """
    pool = await get_db_pool()

    # Extract tenant_id from request state (set by middleware)
    if tenant_id is None and hasattr(request, 'state') and hasattr(request.state, 'tenant_id'):
        tenant_id = request.state.tenant_id

    async with pool.acquire(tenant_id=tenant_id) as conn:
        yield conn
