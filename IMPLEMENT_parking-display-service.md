# Smart Parking Implementation Plan

**Real-time Class A Sensor → Class C Display Actuation**

**Version**: 1.0  
**Date**: 2025-10-07  
**Target Platform**: VPS verdegris.eu

---

## Overview

Implement real-time parking display actuation where Class A occupancy sensors trigger immediate downlinks to Class C display devices, bypassing async polling delays for sub-second response times.

### Architecture Summary

```
Sensor → ChirpStack → Ingest (fast routing) → Parking Display → Downlink → Class C Display
                              ↓
                        Transform (existing analytics)
```

**Key Features:**

- ⚡ **Sub-second latency** for parking display updates
- 🔄 **Dual routing**: Parking sensors go to both Transform AND Parking Display
- 💾 **Dedicated database** for parking logic and device pairing
- 🎯 **State priority**: Reservations override sensor occupancy
- 📊 **Complete audit trail** of all actuations

---

## Phase 1: Database Schema Setup

### 1.1 Create Parking Database Schema

```sql
-- Connect to your existing parking_platform database
-- Add new schemas for parking display logic

-- Configuration schema for device registries
CREATE SCHEMA IF NOT EXISTS parking_config;

-- Spaces schema for parking space definitions  
CREATE SCHEMA IF NOT EXISTS parking_spaces;

-- Operations schema for logs and monitoring
CREATE SCHEMA IF NOT EXISTS parking_operations;

-- Grant permissions
GRANT USAGE ON SCHEMA parking_config TO parking_user;
GRANT USAGE ON SCHEMA parking_spaces TO parking_user;
GRANT USAGE ON SCHEMA parking_operations TO parking_user;

GRANT ALL ON ALL TABLES IN SCHEMA parking_config TO parking_user;
GRANT ALL ON ALL TABLES IN SCHEMA parking_spaces TO parking_user;
GRANT ALL ON ALL TABLES IN SCHEMA parking_operations TO parking_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA parking_config GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_spaces GRANT ALL ON TABLES TO parking_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA parking_operations GRANT ALL ON TABLES TO parking_user;
```

### 1.2 Device Registry Tables

```sql
-- Sensor device registry
CREATE TABLE parking_config.sensor_registry (
    sensor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dev_eui VARCHAR(16) NOT NULL UNIQUE,
    sensor_type VARCHAR(50) NOT NULL, -- 'occupancy', 'environment', 'door' 
    device_model VARCHAR(100),
    manufacturer VARCHAR(100),
    is_parking_related BOOLEAN DEFAULT FALSE, -- KEY: Ingest service filtering
    payload_decoder VARCHAR(100), -- Function name for payload decoding

    -- Metadata
    device_metadata JSONB DEFAULT '{}',
    commissioning_notes TEXT,

    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Display device registry
CREATE TABLE parking_config.display_registry (
    display_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dev_eui VARCHAR(16) NOT NULL UNIQUE,
    display_type VARCHAR(50) NOT NULL, -- 'led_matrix', 'e_paper', 'lcd'
    device_model VARCHAR(100),
    manufacturer VARCHAR(100),

    -- Display codes configuration
    display_codes JSONB DEFAULT '{
        "FREE": "01",
        "OCCUPIED": "02", 
        "RESERVED": "03",
        "OUT_OF_ORDER": "04",
        "MAINTENANCE": "05"
    }',

    -- Technical specs
    fport INTEGER DEFAULT 1,
    confirmed_downlinks BOOLEAN DEFAULT FALSE,
    max_payload_size INTEGER DEFAULT 51,

    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_sensor_registry_parking ON parking_config.sensor_registry(dev_eui, is_parking_related) 
WHERE is_parking_related = TRUE;

CREATE INDEX idx_display_registry_deveui ON parking_config.display_registry(dev_eui, enabled) 
WHERE enabled = TRUE;
```

### 1.3 Parking Spaces Core Table

```sql
-- Core parking spaces with sensor→display pairing
CREATE TABLE parking_spaces.spaces (
    space_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_name VARCHAR(100) NOT NULL UNIQUE,
    space_code VARCHAR(20), -- Short code like "A1-001"
    location_description TEXT,

    -- Geographic location
    building VARCHAR(100),
    floor VARCHAR(50),
    zone VARCHAR(50),
    gps_latitude DECIMAL(10,8),
    gps_longitude DECIMAL(11,8),

    -- DEVICE PAIRING - The core relationships
    occupancy_sensor_id UUID REFERENCES parking_config.sensor_registry(sensor_id),
    display_device_id UUID REFERENCES parking_config.display_registry(display_id),

    -- DevEUI copies for fast lookup (denormalized for performance)
    occupancy_sensor_deveui VARCHAR(16),
    display_device_deveui VARCHAR(16),

    -- Current state tracking
    current_state VARCHAR(20) DEFAULT 'FREE', -- FREE, OCCUPIED, RESERVED, OUT_OF_ORDER
    sensor_state VARCHAR(20) DEFAULT 'FREE',  -- Last known sensor reading
    display_state VARCHAR(20) DEFAULT 'FREE', -- Last state sent to display

    -- Timing information
    last_sensor_update TIMESTAMP,
    last_display_update TIMESTAMP,
    state_changed_at TIMESTAMP DEFAULT NOW(),

    -- Configuration
    auto_actuation BOOLEAN DEFAULT TRUE, -- Enable/disable automatic sensor→display
    reservation_priority BOOLEAN DEFAULT TRUE, -- Reservations override sensor

    -- Status
    enabled BOOLEAN DEFAULT TRUE,
    maintenance_mode BOOLEAN DEFAULT FALSE,

    -- Metadata
    space_metadata JSONB DEFAULT '{}',
    notes TEXT,

    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_states CHECK (current_state IN ('FREE', 'OCCUPIED', 'RESERVED', 'OUT_OF_ORDER', 'MAINTENANCE')),
    CONSTRAINT sensor_display_required CHECK (
        (occupancy_sensor_deveui IS NOT NULL OR maintenance_mode = TRUE) AND
        display_device_deveui IS NOT NULL
    )
);

-- Performance indexes
CREATE INDEX idx_spaces_sensor_lookup ON parking_spaces.spaces(occupancy_sensor_deveui, enabled) 
WHERE enabled = TRUE;

CREATE INDEX idx_spaces_display_lookup ON parking_spaces.spaces(display_device_deveui, enabled) 
WHERE enabled = TRUE;

CREATE INDEX idx_spaces_location ON parking_spaces.spaces(building, floor, zone);
CREATE INDEX idx_spaces_state ON parking_spaces.spaces(current_state, enabled);
```

### 1.4 Reservations and Operations Tables

```sql
-- Reservations table for API-driven state overrides
CREATE TABLE parking_spaces.reservations (
    reservation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL REFERENCES parking_spaces.spaces(space_id) ON DELETE CASCADE,

    -- Reservation time window
    reserved_from TIMESTAMP NOT NULL,
    reserved_until TIMESTAMP NOT NULL,

    -- External system integration
    external_booking_id VARCHAR(255),
    external_system VARCHAR(100) DEFAULT 'api',
    external_user_id VARCHAR(255),

    -- Reservation details
    booking_metadata JSONB DEFAULT '{}', -- Customer info, vehicle details, etc.
    reservation_type VARCHAR(50) DEFAULT 'standard', -- standard, vip, maintenance, event

    -- Status tracking
    status VARCHAR(20) DEFAULT 'active', -- active, cancelled, completed, expired, no_show

    -- Grace period for no-shows
    grace_period_minutes INTEGER DEFAULT 15,
    no_show_detected_at TIMESTAMP,

    -- Lifecycle timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    cancellation_reason TEXT,

    -- Constraints
    CONSTRAINT valid_time_range CHECK (reserved_until > reserved_from),
    CONSTRAINT valid_status CHECK (status IN ('active', 'cancelled', 'completed', 'expired', 'no_show'))
);

-- Actuation log for complete audit trail
CREATE TABLE parking_operations.actuations (
    actuation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL REFERENCES parking_spaces.spaces(space_id),

    -- Trigger information
    trigger_type VARCHAR(30) NOT NULL, -- sensor_uplink, api_reservation, manual_override, system_cleanup
    trigger_source VARCHAR(100), -- sensor DevEUI, API client ID, user ID, system process
    trigger_data JSONB, -- Raw trigger data for debugging

    -- State transition
    previous_state VARCHAR(20),
    new_state VARCHAR(20) NOT NULL,
    state_reason VARCHAR(100), -- Why this state was chosen

    -- Display actuation details
    display_deveui VARCHAR(16) NOT NULL,
    display_code VARCHAR(10) NOT NULL,
    fport INTEGER DEFAULT 1,
    confirmed BOOLEAN DEFAULT FALSE,

    -- Execution tracking
    downlink_sent BOOLEAN DEFAULT FALSE,
    downlink_confirmed BOOLEAN DEFAULT FALSE,
    response_time_ms INTEGER,

    -- Error handling
    downlink_error TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    confirmed_at TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_trigger_type CHECK (trigger_type IN (
        'sensor_uplink', 'api_reservation', 'manual_override', 'system_cleanup', 'reservation_expired'
    ))
);

-- Reservation indexes
CREATE INDEX idx_reservations_active ON parking_spaces.reservations(space_id, status, reserved_from, reserved_until) 
WHERE status = 'active';

CREATE INDEX idx_reservations_timerange ON parking_spaces.reservations(reserved_from, reserved_until);
CREATE INDEX idx_reservations_external ON parking_spaces.reservations(external_system, external_booking_id);

-- Actuation indexes
CREATE INDEX idx_actuations_space_time ON parking_operations.actuations(space_id, created_at DESC);
CREATE INDEX idx_actuations_trigger ON parking_operations.actuations(trigger_type, created_at DESC);
CREATE INDEX idx_actuations_errors ON parking_operations.actuations(downlink_sent, downlink_error) 
WHERE downlink_sent = FALSE OR downlink_error IS NOT NULL;
```

---

## Phase 2: Parking Display Service

### 2.1 Service Structure

```bash
# Create service directory
mkdir -p services/parking-display
cd services/parking-display

mkdir -p app/{routers,services,models,tasks}
touch app/{main.py,database.py,models.py}
touch app/routers/{__init__.py,spaces.py,actuations.py,reservations.py}
touch app/services/{__init__.py,state_engine.py,downlink_client.py}
touch app/tasks/{__init__.py,monitor.py}
touch {Dockerfile,requirements.txt}
```

### 2.2 Core Application Files

#### **requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.32.1
asyncpg==0.30.0
httpx==0.27.2
pydantic==2.10.3
pydantic-settings==2.6.1
python-json-logger==2.0.7
asyncio-mqtt==0.16.2
```

#### **app/database.py**

```python
import os
import asyncpg
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger("database")

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://parking_user:parking_password@postgres-primary:5432/parking_platform"
)

# Connection pool
_pool = None

async def init_db_pool():
    """Initialize database connection pool"""
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=20,
            command_timeout=30
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        raise

async def close_db_pool():
    """Close database connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")

@asynccontextmanager
async def get_db():
    """Get database connection from pool"""
    if not _pool:
        raise RuntimeError("Database pool not initialized")

    async with _pool.acquire() as connection:
        try:
            yield connection
        except Exception as e:
            logger.error(f"Database operation error: {e}")
            raise

async def get_db_dependency():
    """FastAPI dependency for database connection"""
    async with get_db() as db:
        yield db
```

#### **app/models.py**

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ParkingState(str, Enum):
    FREE = "FREE"
    OCCUPIED = "OCCUPIED" 
    RESERVED = "RESERVED"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    MAINTENANCE = "MAINTENANCE"

class TriggerType(str, Enum):
    SENSOR_UPLINK = "sensor_uplink"
    API_RESERVATION = "api_reservation"
    MANUAL_OVERRIDE = "manual_override"
    SYSTEM_CLEANUP = "system_cleanup"
    RESERVATION_EXPIRED = "reservation_expired"

# Request models
class SensorUplinkRequest(BaseModel):
    """Request from Ingest Service when parking sensor sends uplink"""
    sensor_deveui: str = Field(..., min_length=16, max_length=16, description="Sensor DevEUI")
    space_id: Optional[str] = Field(None, description="Space ID if known by ingest")
    occupancy_state: ParkingState = Field(..., description="Sensor occupancy reading")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_payload: Optional[str] = Field(None, description="Raw hex payload")
    payload_data: Dict[str, Any] = Field(default_factory=dict, description="Decoded payload data")
    rssi: Optional[float] = Field(None, description="Signal strength")
    snr: Optional[float] = Field(None, description="Signal to noise ratio")

    @validator('sensor_deveui')
    def validate_deveui(cls, v):
        if not v.replace('0123456789abcdefABCDEF', ''):
            raise ValueError('DevEUI must be hexadecimal')
        return v.lower()

class ReservationRequest(BaseModel):
    """Create new parking reservation"""
    space_id: str = Field(..., description="Parking space UUID")
    reserved_from: datetime = Field(..., description="Reservation start time")
    reserved_until: datetime = Field(..., description="Reservation end time")
    external_booking_id: Optional[str] = Field(None, description="External system booking ID")
    external_system: str = Field("api", description="External system name")
    external_user_id: Optional[str] = Field(None, description="External user identifier")
    booking_metadata: Dict[str, Any] = Field(default_factory=dict)
    reservation_type: str = Field("standard", description="Reservation type")
    grace_period_minutes: int = Field(15, ge=0, le=60, description="No-show grace period")

    @validator('reserved_until')
    def validate_time_range(cls, v, values):
        if 'reserved_from' in values and v <= values['reserved_from']:
            raise ValueError('reserved_until must be after reserved_from')
        return v

class ManualActuationRequest(BaseModel):
    """Manual override for parking space state"""
    space_id: str = Field(..., description="Parking space UUID")
    new_state: ParkingState = Field(..., description="Desired display state")
    reason: str = Field("manual_override", description="Reason for override")
    override_duration_minutes: Optional[int] = Field(None, ge=1, le=1440, description="Override duration (max 24h)")
    user_id: Optional[str] = Field(None, description="User performing override")

class CreateSpaceRequest(BaseModel):
    """Create new parking space"""
    space_name: str = Field(..., min_length=1, max_length=100)
    space_code: Optional[str] = Field(None, max_length=20)
    location_description: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    zone: Optional[str] = None
    occupancy_sensor_deveui: str = Field(..., min_length=16, max_length=16)
    display_device_deveui: str = Field(..., min_length=16, max_length=16)
    auto_actuation: bool = Field(True)
    reservation_priority: bool = Field(True)
    space_metadata: Dict[str, Any] = Field(default_factory=dict)

# Response models
class ActuationResponse(BaseModel):
    """Response from actuation request"""
    status: str = Field(..., description="Processing status")
    space_id: str
    space_name: Optional[str] = None
    previous_state: Optional[ParkingState] = None
    new_state: ParkingState
    reason: str = Field(..., description="Reason for state change")
    processing_time_ms: Optional[float] = None
    actuation_id: Optional[str] = None

class SpaceStatusResponse(BaseModel):
    """Current parking space status"""
    space_id: str
    space_name: str
    current_state: ParkingState
    sensor_state: Optional[ParkingState] = None
    last_sensor_update: Optional[datetime] = None
    last_display_update: Optional[datetime] = None
    active_reservation: Optional[Dict[str, Any]] = None
    enabled: bool

class HealthResponse(BaseModel):
    """Service health status"""
    status: str
    service: str
    version: str
    timestamp: datetime
    database_connected: bool
    parking_spaces_count: int
    active_reservations_count: int
    last_actuation: Optional[datetime] = None
```

#### **app/services/state_engine.py**

```python
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import logging
from ..models import ParkingState

logger = logging.getLogger("state-engine")

class ParkingStateEngine:
    """
    Core business logic for determining parking space display state

    State Priority Rules:
    1. Manual Override (highest priority)
    2. Maintenance Mode 
    3. Active Reservation
    4. Sensor State (lowest priority)
    """

    @staticmethod
    async def determine_display_state(
        space_id: str,
        sensor_state: Optional[ParkingState] = None,
        manual_override: Optional[ParkingState] = None,
        db_connection = None
    ) -> Dict[str, Any]:
        """
        Determine what state the Class C display should show

        Returns:
        {
            "display_state": ParkingState,
            "reason": str,
            "priority": int,
            "metadata": dict,
            "should_actuate": bool
        }
        """

        # Get space configuration and current state
        space_data = await ParkingStateEngine._get_space_data(space_id, db_connection)
        if not space_data:
            raise ValueError(f"Parking space {space_id} not found")

        current_state = space_data['current_state']

        # Priority 1: Manual Override
        if manual_override:
            return {
                "display_state": manual_override,
                "reason": "manual_override",
                "priority": 1,
                "metadata": {"override_value": manual_override},
                "should_actuate": current_state != manual_override
            }

        # Priority 2: Maintenance Mode
        if space_data['maintenance_mode']:
            return {
                "display_state": ParkingState.MAINTENANCE,
                "reason": "maintenance_mode",
                "priority": 2,
                "metadata": {"maintenance_enabled": True},
                "should_actuate": current_state != ParkingState.MAINTENANCE
            }

        # Priority 3: Active Reservation (if reservation_priority enabled)
        if space_data['reservation_priority']:
            active_reservation = await ParkingStateEngine._get_active_reservation(space_id, db_connection)
            if active_reservation:
                return {
                    "display_state": ParkingState.RESERVED,
                    "reason": "active_reservation",
                    "priority": 3,
                    "metadata": {
                        "reservation_id": str(active_reservation['reservation_id']),
                        "reserved_until": active_reservation['reserved_until'].isoformat(),
                        "external_booking_id": active_reservation.get('external_booking_id')
                    },
                    "should_actuate": current_state != ParkingState.RESERVED
                }

        # Priority 4: Sensor State (if auto_actuation enabled)
        if space_data['auto_actuation'] and sensor_state:
            return {
                "display_state": sensor_state,
                "reason": "sensor_state",
                "priority": 4,
                "metadata": {"sensor_value": sensor_state},
                "should_actuate": current_state != sensor_state
            }

        # Fallback: Keep current state
        return {
            "display_state": ParkingState(current_state),
            "reason": "no_change",
            "priority": 5,
            "metadata": {"fallback": True},
            "should_actuate": False
        }

    @staticmethod
    async def _get_space_data(space_id: str, db_connection) -> Optional[Dict]:
        """Get space configuration and current state"""
        query = """
            SELECT 
                space_id,
                space_name,
                current_state,
                display_device_deveui,
                auto_actuation,
                reservation_priority,
                maintenance_mode,
                enabled,
                display_codes
            FROM parking_spaces.spaces s
            LEFT JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
            WHERE s.space_id = $1 AND s.enabled = TRUE
        """

        result = await db_connection.fetchrow(query, space_id)
        return dict(result) if result else None

    @staticmethod
    async def _get_active_reservation(space_id: str, db_connection) -> Optional[Dict]:
        """Get active reservation for space"""
        query = """
            SELECT 
                reservation_id,
                reserved_from,
                reserved_until,
                external_booking_id,
                external_system,
                booking_metadata
            FROM parking_spaces.reservations
            WHERE space_id = $1
              AND status = 'active'
              AND reserved_from <= NOW()
              AND reserved_until >= NOW()
            ORDER BY reserved_from DESC
            LIMIT 1
        """

        result = await db_connection.fetchrow(query, space_id)
        return dict(result) if result else None

    @staticmethod
    def get_display_code(state: ParkingState, display_codes: Dict[str, str]) -> str:
        """Get hex code for display state"""
        return display_codes.get(state.value, display_codes.get("FREE", "01"))

    @staticmethod
    async def log_actuation(
        space_id: str,
        trigger_type: str,
        trigger_source: str,
        trigger_data: Dict,
        previous_state: str,
        new_state: ParkingState,
        display_deveui: str,
        display_code: str,
        db_connection
    ) -> str:
        """Log actuation attempt and return actuation_id"""

        query = """
            INSERT INTO parking_operations.actuations (
                space_id, trigger_type, trigger_source, trigger_data,
                previous_state, new_state, display_deveui, display_code
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING actuation_id
        """

        actuation_id = await db_connection.fetchval(
            query,
            space_id, trigger_type, trigger_source, trigger_data,
            previous_state, new_state.value, display_deveui, display_code
        )

        return str(actuation_id)
```

#### **app/services/downlink_client.py**

```python
import httpx
import logging
from typing import Dict, Any
import asyncio
import time

logger = logging.getLogger("downlink-client")

class DownlinkClient:
    """HTTP client for sending downlinks via existing Downlink Service"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or "http://parking-downlink-service:8000"
        self.timeout = 5.0
        self.max_retries = 2

    async def send_downlink(
        self, 
        dev_eui: str, 
        fport: int, 
        data: str, 
        confirmed: bool = False
    ) -> Dict[str, Any]:
        """
        Send downlink via existing Downlink Service

        Args:
            dev_eui: Device EUI of Class C display
            fport: LoRaWAN fPort (usually 1)
            data: Hex payload (e.g., "01" for FREE)
            confirmed: Request LoRaWAN confirmation

        Returns:
            {
                "success": bool,
                "error": str or None,
                "response_time_ms": float,
                "response": dict or None
            }
        """
        start_time = time.time()

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/downlink/send",
                        json={
                            "dev_eui": dev_eui,
                            "fport": fport,
                            "data": data,
                            "confirmed": confirmed
                        }
                    )

                    response_time = (time.time() - start_time) * 1000

                    if response.status_code == 200:
                        result = response.json()
                        logger.info(f"✅ Downlink sent to {dev_eui}: {data} ({response_time:.1f}ms)")
                        return {
                            "success": True,
                            "error": None,
                            "response_time_ms": response_time,
                            "response": result
                        }
                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text}"
                        if attempt < self.max_retries:
                            logger.warning(f"Downlink attempt {attempt + 1} failed to {dev_eui}: {error_msg}, retrying...")
                            await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            logger.error(f"❌ Downlink failed to {dev_eui} after {self.max_retries + 1} attempts: {error_msg}")
                            return {
                                "success": False,
                                "error": error_msg,
                                "response_time_ms": (time.time() - start_time) * 1000,
                                "response": None
                            }

            except asyncio.TimeoutError:
                error_msg = f"Timeout after {self.timeout}s"
                if attempt < self.max_retries:
                    logger.warning(f"Downlink timeout attempt {attempt + 1} to {dev_eui}, retrying...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"❌ Downlink timeout to {dev_eui} after {self.max_retries + 1} attempts")
                    return {
                        "success": False,
                        "error": error_msg,
                        "response_time_ms": (time.time() - start_time) * 1000,
                        "response": None
                    }
            except Exception as e:
                error_msg = f"Exception: {str(e)}"
                if attempt < self.max_retries:
                    logger.warning(f"Downlink exception attempt {attempt + 1} to {dev_eui}: {error_msg}, retrying...")
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    logger.error(f"❌ Downlink exception to {dev_eui} after {self.max_retries + 1} attempts: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "response_time_ms": (time.time() - start_time) * 1000,
                        "response": None
                    }

        # Should never reach here
        return {
            "success": False,
            "error": "Unknown error",
            "response_time_ms": (time.time() - start_time) * 1000,
            "response": None
        }

    async def health_check(self) -> bool:
        """Check if downlink service is reachable"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
```

### 2.3 API Routers

#### **app/routers/actuations.py**

```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional
import logging
import time
import asyncio

from ..database import get_db_dependency
from ..models import (
    SensorUplinkRequest, ManualActuationRequest, ActuationResponse,
    ParkingState, TriggerType
)
from ..services.state_engine import ParkingStateEngine
from ..services.downlink_client import DownlinkClient

router = APIRouter()
logger = logging.getLogger("actuations")

@router.post("/sensor-uplink", response_model=ActuationResponse)
async def handle_sensor_uplink(
    request: SensorUplinkRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db_dependency)
):
    """
    Handle Class A sensor uplink from Ingest Service

    This is the main entry point for real-time parking actuation.
    Optimized for <200ms response time.
    """
    start_time = time.time()

    try:
        # Find parking space by sensor DevEUI
        space_query = """
            SELECT 
                s.space_id,
                s.space_name,
                s.current_state,
                s.display_device_deveui,
                s.auto_actuation,
                s.reservation_priority,
                s.maintenance_mode,
                dr.display_codes
            FROM parking_spaces.spaces s
            JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
            WHERE s.occupancy_sensor_deveui = $1 
              AND s.enabled = TRUE
        """

        space = await db.fetchrow(space_query, request.sensor_deveui)

        if not space:
            logger.warning(f"No parking space found for sensor {request.sensor_deveui}")
            return ActuationResponse(
                status="ignored",
                space_id="unknown",
                new_state=request.occupancy_state,
                reason="sensor_not_mapped",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        space_id = str(space['space_id'])

        # Update sensor state in database (fire and forget)
        asyncio.create_task(update_sensor_state(
            space_id, request.occupancy_state, request.timestamp, db
        ))

        # Determine display state using state engine
        state_result = await ParkingStateEngine.determine_display_state(
            space_id=space_id,
            sensor_state=request.occupancy_state,
            db_connection=db
        )

        # Check if actuation needed
        if not state_result['should_actuate']:
            logger.info(f"No actuation needed for {space['space_name']} - state unchanged")
            return ActuationResponse(
                status="no_change",
                space_id=space_id,
                space_name=space['space_name'],
                new_state=ParkingState(space['current_state']),
                reason=state_result['reason'],
                processing_time_ms=(time.time() - start_time) * 1000
            )

        # Queue immediate actuation in background
        background_tasks.add_task(
            execute_immediate_actuation,
            space_id=space_id,
            space_name=space['space_name'],
            previous_state=space['current_state'],
            new_state=state_result['display_state'],
            display_deveui=space['display_device_deveui'],
            display_codes=dict(space['display_codes']),
            trigger_type=TriggerType.SENSOR_UPLINK,
            trigger_source=request.sensor_deveui,
            trigger_data=request.dict(),
            state_metadata=state_result
        )

        processing_time = (time.time() - start_time) * 1000

        # Log performance
        if processing_time > 100:
            logger.warning(f"Slow sensor processing: {processing_time:.1f}ms for {request.sensor_deveui}")

        return ActuationResponse(
            status="queued_immediate",
            space_id=space_id,
            space_name=space['space_name'],
            previous_state=ParkingState(space['current_state']),
            new_state=state_result['display_state'],
            reason=state_result['reason'],
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.error(f"Error handling sensor uplink from {request.sensor_deveui}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/manual", response_model=ActuationResponse)
async def manual_actuation(
    request: ManualActuationRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db_dependency)
):
    """
    Manual override - force display to specific state
    """
    try:
        # Validate space exists and get current state
        space_query = """
            SELECT 
                s.space_name,
                s.current_state,
                s.display_device_deveui,
                dr.display_codes
            FROM parking_spaces.spaces s
            JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
            WHERE s.space_id = $1 AND s.enabled = TRUE
        """

        space = await db.fetchrow(space_query, request.space_id)

        if not space:
            raise HTTPException(status_code=404, detail="Parking space not found or disabled")

        # Check if change needed
        if space['current_state'] == request.new_state.value:
            return ActuationResponse(
                status="no_change",
                space_id=request.space_id,
                space_name=space['space_name'],
                new_state=request.new_state,
                reason="already_in_target_state"
            )

        # Queue manual actuation
        background_tasks.add_task(
            execute_immediate_actuation,
            space_id=request.space_id,
            space_name=space['space_name'],
            previous_state=space['current_state'],
            new_state=request.new_state,
            display_deveui=space['display_device_deveui'],
            display_codes=dict(space['display_codes']),
            trigger_type=TriggerType.MANUAL_OVERRIDE,
            trigger_source=request.user_id or "api",
            trigger_data=request.dict(),
            state_metadata={"reason": "manual_override"}
        )

        return ActuationResponse(
            status="queued_immediate",
            space_id=request.space_id,
            space_name=space['space_name'],
            previous_state=ParkingState(space['current_state']),
            new_state=request.new_state,
            reason="manual_override"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in manual actuation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def execute_immediate_actuation(
    space_id: str,
    space_name: str,
    previous_state: str,
    new_state: ParkingState,
    display_deveui: str,
    display_codes: dict,
    trigger_type: TriggerType,
    trigger_source: str,
    trigger_data: dict,
    state_metadata: dict
):
    """
    Background task to execute display actuation immediately

    Priority: Send downlink first, update database after
    """
    actuation_start = time.time()

    async with get_db_dependency() as db:
        try:
            # 1. Log actuation attempt first
            actuation_id = await ParkingStateEngine.log_actuation(
                space_id=space_id,
                trigger_type=trigger_type.value,
                trigger_source=trigger_source,
                trigger_data=trigger_data,
                previous_state=previous_state,
                new_state=new_state,
                display_deveui=display_deveui,
                display_code=ParkingStateEngine.get_display_code(new_state, display_codes),
                db_connection=db
            )

            # 2. Send downlink immediately (highest priority)
            downlink_client = DownlinkClient()
            display_code = ParkingStateEngine.get_display_code(new_state, display_codes)

            downlink_result = await downlink_client.send_downlink(
                dev_eui=display_deveui,
                fport=1,
                data=display_code,
                confirmed=False  # Class C devices, no need for confirmation
            )

            # 3. Update actuation log with downlink result
            await db.execute("""
                UPDATE parking_operations.actuations
                SET downlink_sent = $1,
                    downlink_confirmed = $2,
                    response_time_ms = $3,
                    downlink_error = $4,
                    sent_at = NOW()
                WHERE actuation_id = $5
            """, 
                downlink_result['success'],
                False,  # Class C doesn't confirm
                downlink_result['response_time_ms'],
                downlink_result['error'],
                actuation_id
            )

            # 4. Update space state if downlink successful
            if downlink_result['success']:
                await db.execute("""
                    UPDATE parking_spaces.spaces
                    SET current_state = $1,
                        display_state = $1,
                        last_display_update = NOW(),
                        state_changed_at = NOW(),
                        updated_at = NOW()
                    WHERE space_id = $2
                """, new_state.value, space_id)

                total_time = (time.time() - actuation_start) * 1000
                logger.info(f"✅ {space_name}: {previous_state} → {new_state.value} ({total_time:.1f}ms)")
            else:
                logger.error(f"❌ Failed actuation {space_name}: {downlink_result['error']}")

        except Exception as e:
            logger.error(f"Error executing actuation for space {space_id}: {e}", exc_info=True)

async def update_sensor_state(space_id: str, sensor_state: ParkingState, timestamp, db):
    """Update sensor state tracking (non-blocking)"""
    try:
        await db.execute("""
            UPDATE parking_spaces.spaces
            SET sensor_state = $1,
                last_sensor_update = $2,
                updated_at = NOW()
            WHERE space_id = $3
        """, sensor_state.value, timestamp, space_id)
    except Exception as e:
        logger.error(f"Error updating sensor state for space {space_id}: {e}")

@router.get("/status/{space_id}")
async def get_space_status(space_id: str, db = Depends(get_db_dependency)):
    """Get current status of parking space"""
    try:
        query = """
            SELECT 
                s.space_id,
                s.space_name,
                s.current_state,
                s.sensor_state,
                s.last_sensor_update,
                s.last_display_update,
                s.enabled,
                s.maintenance_mode,
                r.reservation_id,
                r.reserved_until,
                r.external_booking_id
            FROM parking_spaces.spaces s
            LEFT JOIN parking_spaces.reservations r ON s.space_id = r.space_id
                AND r.status = 'active'
                AND r.reserved_from <= NOW()
                AND r.reserved_until >= NOW()
            WHERE s.space_id = $1
        """

        result = await db.fetchrow(query, space_id)

        if not result:
            raise HTTPException(status_code=404, detail="Parking space not found")

        active_reservation = None
        if result['reservation_id']:
            active_reservation = {
                "reservation_id": str(result['reservation_id']),
                "reserved_until": result['reserved_until'].isoformat(),
                "external_booking_id": result['external_booking_id']
            }

        return {
            "space_id": str(result['space_id']),
            "space_name": result['space_name'],
            "current_state": result['current_state'],
            "sensor_state": result['sensor_state'],
            "last_sensor_update": result['last_sensor_update'],
            "last_display_update": result['last_display_update'],
            "enabled": result['enabled'],
            "maintenance_mode": result['maintenance_mode'],
            "active_reservation": active_reservation
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting space status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

### 2.4 Main Application

#### **app/main.py**

```python
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import os

from .routers import actuations, spaces, reservations
from .database import init_db_pool, close_db_pool, get_db_dependency
from .tasks.monitor import start_monitoring_tasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("parking-display")

# Background tasks storage
background_tasks = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""

    # Startup
    logger.info("🅿️ Starting Parking Display Service v1.0.0")

    try:
        # Initialize database
        await init_db_pool()
        logger.info("✅ Database connection pool initialized")

        # Start background monitoring tasks
        monitor_task = asyncio.create_task(start_monitoring_tasks())
        background_tasks.append(monitor_task)
        logger.info("✅ Background monitoring tasks started")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down Parking Display Service")

    try:
        # Cancel background tasks
        for task in background_tasks:
            task.cancel()

        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
            logger.info("✅ Background tasks stopped")

        # Close database pool
        await close_db_pool()
        logger.info("✅ Database connections closed")

    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")

# Create FastAPI app
app = FastAPI(
    title="Parking Display Service",
    description="Smart parking state management and Class C display actuation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(actuations.router, prefix="/v1/actuations", tags=["actuations"])
app.include_router(spaces.router, prefix="/v1/spaces", tags=["spaces"])
app.include_router(reservations.router, prefix="/v1/reservations", tags=["reservations"])

@app.get("/")
async def root():
    """Service information"""
    return {
        "service": "parking-display",
        "version": "1.0.0",
        "status": "operational",
        "description": "Smart parking state management and Class C display actuation",
        "endpoints": {
            "actuations": "/v1/actuations",
            "spaces": "/v1/spaces", 
            "reservations": "/v1/reservations",
            "health": "/health",
            "docs": "/docs"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check(db = Depends(get_db_dependency)):
    """Comprehensive health check"""
    try:
        # Test database connection
        db_result = await db.fetchval("SELECT 1")
        database_connected = db_result == 1

        # Get basic stats
        stats_query = """
            SELECT 
                (SELECT COUNT(*) FROM parking_spaces.spaces WHERE enabled = TRUE) as spaces_count,
                (SELECT COUNT(*) FROM parking_spaces.reservations WHERE status = 'active') as active_reservations,
                (SELECT MAX(created_at) FROM parking_operations.actuations) as last_actuation
        """
        stats = await db.fetchrow(stats_query)

        return {
            "status": "healthy" if database_connected else "unhealthy",
            "service": "parking-display",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "database_connected": database_connected,
            "parking_spaces_count": stats['spaces_count'] or 0,
            "active_reservations_count": stats['active_reservations'] or 0,
            "last_actuation": stats['last_actuation'].isoformat() if stats['last_actuation'] else None
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "parking-display",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "database_connected": False
        }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {"error": "Internal server error", "detail": str(exc)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2.5 Docker Configuration

#### **Dockerfile**

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
```

---

## Phase 3: Ingest Service Enhancement

### 3.1 Parking Sensor Detection

Create: `services/ingest/app/parking_detector.py`

```python
import asyncio
import httpx
from typing import Set, Dict, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("parking-detector")

class ParkingSensorDetector:
    """
    Fast in-memory cache for parking sensor detection
    Optimized for O(1) lookup performance in uplink processing
    """

    def __init__(self, parking_service_url: str = "http://parking-display-service:8000"):
        self.parking_service_url = parking_service_url
        self.parking_sensors: Set[str] = set()
        self.sensor_to_space: Dict[str, str] = {}  # dev_eui -> space_id
        self.last_refresh: Optional[datetime] = None
        self.refresh_interval = timedelta(minutes=5)

    async def refresh_cache(self):
        """Refresh parking sensor cache from Parking Display Service"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.parking_service_url}/v1/spaces/sensor-list"
                )

                if response.status_code == 200:
                    data = response.json()

                    # Atomic update of cache
                    new_sensors = set(data.get('sensor_deveuis', []))
                    new_mapping = data.get('sensor_to_space', {})

                    self.parking_sensors = new_sensors
                    self.sensor_to_space = new_mapping
                    self.last_refresh = datetime.utcnow()

                    logger.info(f"🅿️ Parking sensor cache refreshed: {len(new_sensors)} sensors")
                    return True
                else:
                    logger.warning(f"Failed to refresh parking cache: HTTP {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error refreshing parking sensor cache: {e}")
            return False

    def is_parking_sensor(self, dev_eui: str) -> bool:
        """Fast O(1) lookup for parking sensor detection"""
        return dev_eui.lower() in self.parking_sensors

    def get_space_id(self, dev_eui: str) -> Optional[str]:
        """Get space ID for parking sensor"""
        return self.sensor_to_space.get(dev_eui.lower())

    def needs_refresh(self) -> bool:
        """Check if cache needs refresh"""
        if self.last_refresh is None:
            return True
        return datetime.utcnow() - self.last_refresh > self.refresh_interval

    async def ensure_fresh_cache(self):
        """Ensure cache is fresh, refresh if needed"""
        if self.needs_refresh():
            await self.refresh_cache()

# Global instance
parking_detector = ParkingSensorDetector()

async def refresh_parking_cache_task():
    """Background task to refresh parking sensor cache"""
    logger.info("Starting parking sensor cache refresh task")

    # Initial refresh
    await parking_detector.refresh_cache()

    while True:
        try:
            await asyncio.sleep(300)  # 5 minutes
            await parking_detector.refresh_cache()
        except Exception as e:
            logger.error(f"Error in parking cache refresh task: {e}")
            await asyncio.sleep(60)  # Retry in 1 minute on error

async def extract_occupancy_from_payload(payload: str, dev_eui: str) -> str:
    """
    Extract occupancy state from device payload
    Device-specific logic based on DevEUI patterns or device database
    """
    try:
        dev_eui = dev_eui.lower()

        # Milesight AM400-MUD sensors
        if dev_eui.startswith("58a0cb"):
            # Example Milesight payload decoding
            # This would be replaced with actual Milesight decoder
            hex_payload = bytes.fromhex(payload)
            if len(hex_payload) > 0:
                # Simplified - replace with actual decoder
                occupied = hex_payload[0] & 0x01
                return "OCCUPIED" if occupied else "FREE"

        # RAK sensors
        elif dev_eui.startswith("ac1f09"):
            # Example RAK payload decoding
            hex_payload = bytes.fromhex(payload)
            if len(hex_payload) > 1:
                # Simplified - replace with actual decoder  
                motion = hex_payload[1] & 0x01
                return "OCCUPIED" if motion else "FREE"

        # Browan sensors
        elif dev_eui.startswith("24e124"):
            # Example Browan payload decoding
            hex_payload = bytes.fromhex(payload)
            if len(hex_payload) > 0:
                # Simplified - replace with actual decoder
                state = hex_payload[0]
                return "OCCUPIED" if state > 0 else "FREE"

        else:
            logger.warning(f"Unknown sensor type for occupancy extraction: {dev_eui}")
            return "FREE"

    except Exception as e:
        logger.error(f"Failed to extract occupancy from {dev_eui}: {e}")
        return "FREE"

async def forward_to_parking_display(uplink_data, space_id: str):
    """Forward parking sensor data to Parking Display Service"""
    try:
        # Extract occupancy state using device-specific logic
        occupancy_state = await extract_occupancy_from_payload(
            uplink_data.get('data', ''), 
            uplink_data.get('devEUI', '')
        )

        # Prepare payload for Parking Display Service
        parking_payload = {
            "sensor_deveui": uplink_data.get('devEUI', '').lower(),
            "space_id": space_id,
            "occupancy_state": occupancy_state,
            "timestamp": uplink_data.get('timestamp', datetime.utcnow().isoformat()),
            "raw_payload": uplink_data.get('data', ''),
            "payload_data": uplink_data.get('object', {}),
            "rssi": None,
            "snr": None
        }

        # Extract RSSI/SNR from rxInfo if available
        rx_info = uplink_data.get('rxInfo', [])
        if rx_info and len(rx_info) > 0:
            parking_payload["rssi"] = rx_info[0].get('rssi')
            parking_payload["snr"] = rx_info[0].get('snr')

        # Send to Parking Display Service (fire-and-forget for speed)
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.post(
                "http://parking-display-service:8000/v1/actuations/sensor-uplink",
                json=parking_payload
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"⚡ Parking forward: {uplink_data.get('devEUI')} → {result.get('status')}")
            else:
                logger.warning(f"Parking forward failed: HTTP {response.status_code} for {uplink_data.get('devEUI')}")

    except Exception as e:
        logger.error(f"Error forwarding to parking display: {e}")
```

### 3.2 Enhanced Ingest Main Handler

Modify: `services/ingest/app/main.py`

```python
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from contextlib import asynccontextmanager

# Import existing modules
from .parsers import actility_parser, netmore_parser, tti_parser, chirpstack_parser
from .forwarders import transform_forwarder, mqtt_publisher

# Import new parking integration
from .parking_detector import (
    parking_detector, 
    refresh_parking_cache_task, 
    forward_to_parking_display
)

logger = logging.getLogger("ingest-service")

# Background tasks
background_tasks = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""

    # Startup
    logger.info("🚀 Starting Ingest Service with Parking Integration")

    try:
        # Start parking sensor cache refresh task
        cache_task = asyncio.create_task(refresh_parking_cache_task())
        background_tasks.append(cache_task)
        logger.info("✅ Parking sensor cache task started")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down Ingest Service")
    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)

app = FastAPI(
    title="Ingest Service",
    description="Multi-LNS LoRaWAN uplink ingestion with parking integration",
    version="0.10.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@router.post("/uplink")
async def handle_uplink(
    request: Request,
    source: str = None,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Enhanced uplink handler with parking sensor detection and routing

    Flow:
    1. Parse uplink based on source LNS
    2. Store raw uplink (existing)
    3. Check if parking sensor (new) → forward to Parking Display Service
    4. Forward to Transform Service (existing)
    5. Publish to MQTT if ChirpStack (existing)
    """

    try:
        # Parse the request body
        raw_data = await request.body()
        uplink_data = await request.json()

        # Auto-detect source if not provided
        if not source:
            source = detect_lns_source(uplink_data)

        # Parse uplink based on source
        if source == "actility":
            parsed_uplink = actility_parser.parse(uplink_data)
        elif source == "netmore":
            parsed_uplink = netmore_parser.parse(uplink_data)
        elif source == "tti":
            parsed_uplink = tti_parser.parse(uplink_data)
        elif source == "chirpstack":
            parsed_uplink = chirpstack_parser.parse(uplink_data)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

        dev_eui = parsed_uplink.get('devEUI', '').lower()

        # Store raw uplink (existing logic)
        background_tasks.add_task(store_raw_uplink, parsed_uplink, raw_data)

        # 🅿️ NEW: Check if this is a parking sensor
        is_parking = parking_detector.is_parking_sensor(dev_eui)
        forwarded_to = ["transform"]

        if is_parking:
            logger.info(f"🅿️ Parking sensor detected: {dev_eui}")

            # Get space ID for this sensor
            space_id = parking_detector.get_space_id(dev_eui)
            if space_id:
                # Forward to Parking Display Service immediately (fire-and-forget for speed)
                background_tasks.add_task(forward_to_parking_display, parsed_uplink, space_id)
                forwarded_to.append("parking-display")
            else:
                logger.warning(f"Parking sensor {dev_eui} not mapped to space")

        # Forward to Transform Service (existing logic - ALL sensors)
        background_tasks.add_task(transform_forwarder.forward, parsed_uplink)

        # MQTT publish for ChirpStack (existing logic)
        if source == "chirpstack":
            background_tasks.add_task(mqtt_publisher.publish, parsed_uplink)

        # Response
        response = {
            "status": "processed",
            "source": source,
            "deveui": dev_eui,
            "timestamp": parsed_uplink.get('timestamp'),
            "is_parking_sensor": is_parking,
            "forwarded_to": forwarded_to
        }

        # Add parking-specific info if applicable
        if is_parking:
            response["parking_space_id"] = parking_detector.get_space_id(dev_eui)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing uplink: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.get("/parking/sensor-cache/status")
async def parking_cache_status():
    """Debug endpoint for parking sensor cache status"""
    return {
        "parking_sensors_count": len(parking_detector.parking_sensors),
        "last_refresh": parking_detector.last_refresh.isoformat() if parking_detector.last_refresh else None,
        "needs_refresh": parking_detector.needs_refresh(),
        "sample_sensors": list(parking_detector.parking_sensors)[:5] if parking_detector.parking_sensors else []
    }

@app.post("/parking/sensor-cache/refresh")
async def force_parking_cache_refresh():
    """Force refresh of parking sensor cache"""
    success = await parking_detector.refresh_cache()
    return {
        "status": "refreshed" if success else "failed",
        "sensors_count": len(parking_detector.parking_sensors),
        "last_refresh": parking_detector.last_refresh.isoformat() if parking_detector.last_refresh else None
    }

# Existing routes and functions...
# (keep all existing ingest service functionality)

def detect_lns_source(uplink_data: dict) -> str:
    """Auto-detect LNS source from payload structure"""
    # Existing auto-detection logic
    if 'deviceInfo' in uplink_data and 'gatewayId' not in uplink_data:
        return "chirpstack"
    elif 'DevEUI_uplink' in uplink_data:
        return "actility"
    elif isinstance(uplink_data, list):
        return "netmore"
    elif 'end_device_ids' in uplink_data:
        return "tti"
    else:
        return "unknown"

async def store_raw_uplink(parsed_uplink: dict, raw_data: bytes):
    """Store raw uplink data (existing logic)"""
    # Existing implementation
    pass

# Health check and other existing endpoints...
```

---

## Phase 4: Docker Compose Integration

### 4.1 Add Parking Display Service

Add to your existing `docker-compose.yml`:

```yaml
  # Add this service to your existing services
  parking-display-service:
    build: ./services/parking-display
    container_name: parking-display-service
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres-primary:5432/${POSTGRES_DB}
      DOWNLINK_SERVICE_URL: http://parking-downlink-service:8000
      LOG_LEVEL: INFO
      PYTHONUNBUFFERED: 1
    volumes:
      - ./services/parking-display/app:/app
      - ./logs:/app/logs
    networks:
      - parking-network
      - web
    depends_on:
      - postgres-primary
      - parking-downlink-service
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.parking-display.rule=Host(`parking.${DOMAIN}`)"
      - "traefik.http.routers.parking-display.entrypoints=websecure"
      - "traefik.http.routers.parking-display.tls.certresolver=letsencrypt"
      - "traefik.http.services.parking-display.loadbalancer.server.port=8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 4.2 Update Environment Variables

Add to your `.env` file:

```bash
# Parking Display Service
PARKING_DISPLAY_SERVICE_URL=http://parking-display-service:8000
PARKING_CACHE_REFRESH_INTERVAL=300

# Database schema for parking (add to existing DATABASE_URL)
# No changes needed - uses same parking_platform database
```

---

## Phase 5: Initial Data Setup

### 5.1 Sample Device Registration

```sql
-- Connect to parking_platform database

-- Register parking sensors
INSERT INTO parking_config.sensor_registry (
    dev_eui, sensor_type, device_model, manufacturer, is_parking_related, enabled
) VALUES 
    ('58a0cb00001019bc', 'occupancy', 'AM400-MUD', 'Milesight', TRUE, TRUE),
    ('58a0cb00001019bd', 'occupancy', 'AM400-MUD', 'Milesight', TRUE, TRUE),
    ('ac1f09fffe013456', 'occupancy', 'RAK7200', 'RAK Wireless', TRUE, TRUE);

-- Register display devices
INSERT INTO parking_config.display_registry (
    dev_eui, display_type, device_model, manufacturer, enabled
) VALUES 
    ('70b3d57ed0067001', 'led_matrix', 'WiFi LoRa 32 V3', 'Heltec', TRUE),
    ('70b3d57ed0067002', 'led_matrix', 'WiFi LoRa 32 V3', 'Heltec', TRUE),
    ('24e124fffed56789', 'e_paper', 'Custom Display', 'Custom', TRUE);

-- Create parking spaces with sensor→display pairing
INSERT INTO parking_spaces.spaces (
    space_name, space_code, location_description, building, floor, zone,
    occupancy_sensor_id, display_device_id, 
    occupancy_sensor_deveui, display_device_deveui,
    auto_actuation, reservation_priority, enabled
) VALUES 
    (
        'Parking Space A1-001', 'A1-001', 'Building A, Level 1, Zone 1, Space 1',
        'Building A', 'Level 1', 'Zone 1',
        (SELECT sensor_id FROM parking_config.sensor_registry WHERE dev_eui = '58a0cb00001019bc'),
        (SELECT display_id FROM parking_config.display_registry WHERE dev_eui = '70b3d57ed0067001'),
        '58a0cb00001019bc', '70b3d57ed0067001',
        TRUE, TRUE, TRUE
    ),
    (
        'Parking Space A1-002', 'A1-002', 'Building A, Level 1, Zone 1, Space 2',
        'Building A', 'Level 1', 'Zone 1',
        (SELECT sensor_id FROM parking_config.sensor_registry WHERE dev_eui = '58a0cb00001019bd'),
        (SELECT display_id FROM parking_config.display_registry WHERE dev_eui = '70b3d57ed0067002'),
        '58a0cb00001019bd', '70b3d57ed0067002',
        TRUE, TRUE, TRUE
    );

-- Verify setup
SELECT 
    s.space_name,
    s.occupancy_sensor_deveui,
    s.display_device_deveui,
    sr.device_model as sensor_model,
    dr.device_model as display_model
FROM parking_spaces.spaces s
JOIN parking_config.sensor_registry sr ON s.occupancy_sensor_id = sr.sensor_id
JOIN parking_config.display_registry dr ON s.display_device_id = dr.display_id
WHERE s.enabled = TRUE;
```

---

## Phase 6: Deployment & Testing

### 6.1 Build and Deploy

```bash
# Navigate to your VPS
cd /opt/smart-parking

# Build the new parking display service
sudo docker compose build parking-display-service

# Start all services
sudo docker compose up -d

# Check service status
sudo docker compose ps

# Check parking display service logs
sudo docker compose logs -f parking-display-service

# Check ingest service logs for parking integration
sudo docker compose logs -f ingest-service
```

### 6.2 Health Checks

```bash
# Check parking display service health
curl https://parking.verdegris.eu/health

# Check ingest service parking cache
curl https://ingest.verdegris.eu/parking/sensor-cache/status

# Force refresh parking sensor cache
curl -X POST https://ingest.verdegris.eu/parking/sensor-cache/refresh
```

### 6.3 Test Parking Space Management

```bash
# List all parking spaces
curl https://parking.verdegris.eu/v1/spaces

# Get specific space status
curl https://parking.verdegris.eu/v1/actuations/status/{space_id}

# Manual actuation test
curl -X POST https://parking.verdegris.eu/v1/actuations/manual \
  -H "Content-Type: application/json" \
  -d '{
    "space_id": "your-space-uuid-here",
    "new_state": "OCCUPIED",
    "reason": "test_actuation",
    "user_id": "admin"
  }'
```

### 6.4 Test Sensor Integration

```bash
# Simulate sensor uplink to test the flow
curl -X POST https://ingest.verdegris.eu/uplink?source=chirpstack \
  -H "Content-Type: application/json" \
  -d '{
    "deviceInfo": {
      "devEui": "58a0cb00001019bc"
    },
    "data": "01", 
    "fPort": 1,
    "object": {
      "occupied": true
    }
  }'

# Check actuation logs
curl https://parking.verdegris.eu/v1/actuations/status/{space_id}
```

### 6.5 Test Reservation System

```bash
# Create a reservation
curl -X POST https://parking.verdegris.eu/v1/reservations \
  -H "Content-Type: application/json" \
  -d '{
    "space_id": "your-space-uuid-here",
    "reserved_from": "2025-10-07T10:00:00Z",
    "reserved_until": "2025-10-07T12:00:00Z",
    "external_booking_id": "BOOK-12345",
    "external_system": "booking_api",
    "booking_metadata": {
      "customer_name": "John Doe",
      "vehicle_plate": "ABC-123"
    }
  }'

# Check that display shows RESERVED
curl https://parking.verdegris.eu/v1/actuations/status/{space_id}
```

---

## Phase 7: Monitoring & Performance

### 7.1 Performance Monitoring

Add performance metrics to track latency:

```bash
# Monitor actuation response times
sudo docker compose logs parking-display-service | grep "processing_time_ms"

# Monitor ingest forwarding
sudo docker compose logs ingest-service | grep "Parking forward"

# Monitor downlink service
sudo docker compose logs downlink-service | grep "Downlink sent"
```

### 7.2 Database Monitoring

```sql
-- Check actuation performance
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as total_actuations,
    COUNT(*) FILTER (WHERE downlink_sent = TRUE) as successful_actuations,
    AVG(response_time_ms) as avg_response_time,
    MAX(response_time_ms) as max_response_time
FROM parking_operations.actuations
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;

-- Check failed actuations
SELECT 
    space_id,
    trigger_type,
    downlink_error,
    created_at
FROM parking_operations.actuations
WHERE downlink_sent = FALSE 
   OR downlink_error IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;

-- Check active reservations
SELECT 
    s.space_name,
    r.reserved_from,
    r.reserved_until,
    r.external_booking_id,
    r.status
FROM parking_spaces.reservations r
JOIN parking_spaces.spaces s ON r.space_id = s.space_id
WHERE r.status = 'active'
ORDER BY r.reserved_from;
```

---

## Success Criteria

### ✅ **Performance Targets**

- **End-to-end latency**: < 1 second from sensor uplink to display update
- **Ingest processing**: < 100ms for parking sensor detection and forwarding
- **Parking display processing**: < 200ms for state determination and downlink queuing
- **Downlink transmission**: < 500ms via ChirpStack gRPC

### ✅ **Functional Requirements**

- **Sensor routing**: Parking sensors automatically forward to both Transform AND Parking Display services
- **State priority**: Reservations override sensor occupancy, manual overrides everything
- **Real-time actuation**: Class C displays update immediately on state changes
- **API integration**: External reservation systems can trigger RESERVED state
- **Audit trail**: Complete log of all actuations with timing and error details

### ✅ **Operational Requirements**

- **Service health**: All services report healthy status
- **Database performance**: Sub-100ms queries for parking state determination
- **Error handling**: Failed downlinks logged and retried
- **Cache management**: Parking sensor cache refreshes automatically every 5 minutes

---

## Next Steps

1. **Deploy Phase 1-2**: Database schema and Parking Display Service
2. **Test with manual actuations**: Verify downlink flow works
3. **Deploy Phase 3**: Enhanced Ingest Service with parking detection
4. **Test sensor integration**: Verify automatic sensor→display flow
5. **Deploy reservation API**: Test external booking system integration
6. **Performance optimization**: Monitor and tune based on real usage
7. **Scale testing**: Add more parking spaces and test concurrent actuations

This implementation provides the foundation for a high-performance, real-time parking display system that can scale to hundreds of parking spaces while maintaining sub-second response times.
