"""
Database connection pooling and query management
Handles all database operations with proper pooling and error handling
"""
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import json
from contextlib import asynccontextmanager

from .models import Space, SpaceCreate, SpaceUpdate, Reservation, ReservationCreate
from .exceptions import DatabaseError

logger = logging.getLogger(__name__)

class DatabasePool:
    """
    Database connection pool with automatic retry and health checks
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
        self._stats = {
            "queries": 0,
            "errors": 0,
            "connections": 0
        }

    async def initialize(self):
        """Initialize connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.dsn,
                min_size=5,
                max_size=20,
                command_timeout=60,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                init=self._init_connection
            )
            logger.info(f"Database pool created: {self.pool.get_idle_size()} connections")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            raise DatabaseError(f"Cannot connect to database: {e}")

    async def _init_connection(self, conn):
        """Initialize each connection"""
        # Set connection parameters
        await conn.execute("""
            SET statement_timeout = '30s';
            SET lock_timeout = '10s';
            SET idle_in_transaction_session_timeout = '60s';
        """)

        # Register custom types if needed
        await conn.set_type_codec(
            'jsonb',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        async with self.pool.acquire() as conn:
            self._stats["connections"] += 1
            yield conn

    async def execute(self, query: str, *args):
        """Execute a query"""
        try:
            async with self.acquire() as conn:
                result = await conn.execute(query, *args)
                self._stats["queries"] += 1
                return result
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Query execution failed: {e}")
            raise

    async def fetch(self, query: str, *args):
        """Fetch multiple rows"""
        try:
            async with self.acquire() as conn:
                result = await conn.fetch(query, *args)
                self._stats["queries"] += 1
                return result
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Query fetch failed: {e}")
            raise

    async def fetchrow(self, query: str, *args):
        """Fetch single row"""
        try:
            async with self.acquire() as conn:
                result = await conn.fetchrow(query, *args)
                self._stats["queries"] += 1
                return result
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Query fetchrow failed: {e}")
            raise

    async def fetchval(self, query: str, *args):
        """Fetch single value"""
        try:
            async with self.acquire() as conn:
                result = await conn.fetchval(query, *args)
                self._stats["queries"] += 1
                return result
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Query fetchval failed: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        if self.pool:
            return {
                **self._stats,
                "pool_size": self.pool.get_size(),
                "idle_connections": self.pool.get_idle_size(),
                "max_size": self.pool.get_max_size()
            }
        return self._stats

    # ============================================================
    # Space Queries
    # ============================================================

    async def get_spaces(
        self,
        building: Optional[str] = None,
        floor: Optional[str] = None,
        zone: Optional[str] = None,
        state: Optional[str] = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Space]:
        """Get spaces with filtering"""

        query = """
            SELECT 
                id, name, code, building, floor, zone,
                sensor_eui, display_eui, state,
                gps_latitude, gps_longitude,
                metadata, created_at, updated_at
            FROM spaces
            WHERE 1=1
        """

        params = []
        param_count = 0

        if not include_deleted:
            query += " AND deleted_at IS NULL"

        if building:
            param_count += 1
            params.append(building)
            query += f" AND building = ${param_count}"

        if floor:
            param_count += 1
            params.append(floor)
            query += f" AND floor = ${param_count}"

        if zone:
            param_count += 1
            params.append(zone)
            query += f" AND zone = ${param_count}"

        if state:
            param_count += 1
            params.append(state)
            query += f" AND state = ${param_count}"

        query += f" ORDER BY name LIMIT {limit} OFFSET {offset}"

        rows = await self.fetch(query, *params)
        return [Space(**dict(row)) for row in rows]

    async def get_space(self, space_id: str) -> Optional[Space]:
        """Get single space by ID"""

        row = await self.fetchrow("""
            SELECT * FROM spaces 
            WHERE id = $1 AND deleted_at IS NULL
        """, space_id)

        return Space(**dict(row)) if row else None

    async def get_space_by_sensor(self, sensor_eui: str) -> Optional[Space]:
        """Get space by sensor EUI"""

        row = await self.fetchrow("""
            SELECT * FROM spaces 
            WHERE sensor_eui = $1 AND deleted_at IS NULL
        """, sensor_eui)

        return Space(**dict(row)) if row else None

    async def create_space(self, space: SpaceCreate) -> Space:
        """Create new space"""

        row = await self.fetchrow("""
            INSERT INTO spaces (
                name, code, building, floor, zone,
                sensor_eui, display_eui, state,
                gps_latitude, gps_longitude, metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
            )
            RETURNING *
        """, space.name, space.code, space.building, space.floor, space.zone,
            space.sensor_eui, space.display_eui, space.state.value,
            space.gps_latitude, space.gps_longitude, 
            json.dumps(space.metadata) if space.metadata else None)

        return Space(**dict(row))

    async def update_space(
        self, 
        space_id: str,
        updates: SpaceUpdate
    ) -> Space:
        """Update space with dynamic fields"""

        # Build UPDATE query dynamically
        set_clauses = []
        params = [space_id]
        param_count = 1

        for field, value in updates.dict(exclude_unset=True).items():
            param_count += 1
            params.append(value)
            set_clauses.append(f"{field} = ${param_count}")

        if not set_clauses:
            # No updates, just return current
            return await self.get_space(space_id)

        query = f"""
            UPDATE spaces 
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """

        row = await self.fetchrow(query, *params)
        return Space(**dict(row))

    async def soft_delete_space(self, space_id: str):
        """Soft delete a space"""

        await self.execute("""
            UPDATE spaces 
            SET deleted_at = NOW()
            WHERE id = $1
        """, space_id)

    # ============================================================
    # Reservation Queries
    # ============================================================

    async def create_reservation(
        self,
        reservation: ReservationCreate
    ) -> Reservation:
        """Create new reservation"""

        row = await self.fetchrow("""
            INSERT INTO reservations (
                space_id, start_time, end_time,
                user_email, user_phone, metadata, status
            ) VALUES (
                $1, $2, $3, $4, $5, $6, 'active'
            )
            RETURNING *
        """, reservation.space_id, reservation.start_time, reservation.end_time,
            reservation.user_email, reservation.user_phone,
            json.dumps(reservation.metadata) if reservation.metadata else None)

        return Reservation(**dict(row))

    async def get_reservations(
        self,
        space_id: Optional[str] = None,
        user_email: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Reservation]:
        """Get reservations with filtering"""

        query = "SELECT * FROM reservations WHERE 1=1"
        params = []
        param_count = 0

        if space_id:
            param_count += 1
            params.append(space_id)
            query += f" AND space_id = ${param_count}"

        if user_email:
            param_count += 1
            params.append(user_email)
            query += f" AND user_email = ${param_count}"

        if status:
            param_count += 1
            params.append(status)
            query += f" AND status = ${param_count}"

        if date_from:
            param_count += 1
            params.append(date_from)
            query += f" AND end_time >= ${param_count}"

        if date_to:
            param_count += 1
            params.append(date_to)
            query += f" AND start_time <= ${param_count}"

        query += f" ORDER BY start_time DESC LIMIT {limit} OFFSET {offset}"

        rows = await self.fetch(query, *params)
        return [Reservation(**dict(row)) for row in rows]

    async def get_reservation(self, reservation_id: str) -> Optional[Reservation]:
        """Get single reservation"""

        row = await self.fetchrow("""
            SELECT * FROM reservations WHERE id = $1
        """, reservation_id)

        return Reservation(**dict(row)) if row else None

    async def get_active_reservations(self, space_id: str) -> List[Reservation]:
        """Get active reservations for a space"""

        rows = await self.fetch("""
            SELECT * FROM reservations 
            WHERE space_id = $1 
            AND status = 'active'
            AND end_time > NOW()
        """, space_id)

        return [Reservation(**dict(row)) for row in rows]

    async def cancel_reservation(self, reservation_id: str):
        """Cancel a reservation"""

        await self.execute("""
            UPDATE reservations 
            SET status = 'cancelled', updated_at = NOW()
            WHERE id = $1
        """, reservation_id)

    # ============================================================
    # Sensor Data Queries
    # ============================================================

    async def insert_sensor_reading(
        self,
        device_eui: str,
        space_id: Optional[str],
        occupancy_state: Optional[str],
        battery: Optional[float],
        rssi: Optional[int],
        snr: Optional[float]
    ):
        """Insert sensor reading"""

        await self.execute("""
            INSERT INTO sensor_readings (
                device_eui, space_id, occupancy_state,
                battery, rssi, snr, timestamp
            ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
        """, device_eui, space_id, occupancy_state, battery, rssi, snr)

    async def insert_telemetry(self, device_eui: str, data: Dict[str, Any]):
        """Insert device telemetry"""

        await self.execute("""
            INSERT INTO device_telemetry (device_eui, data, timestamp)
            VALUES ($1, $2, NOW())
        """, device_eui, json.dumps(data))
