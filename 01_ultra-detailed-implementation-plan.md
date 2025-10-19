# Smart Parking v2 - Ultra-Detailed Implementation Plan

## Pre-Work: What to Extract from Old Codebase (2 hours)

### Step 1: Clone Old Code for Reference

```bash
# Keep old code accessible for copying
cd ~/projects
mv smart-parking-platform smart-parking-v4-OLD
cd smart-parking-v4-OLD

# Create a "reusable" folder to collect useful code
mkdir ~/projects/REUSABLE_CODE
```

### Step 2: Extract These EXACT Files/Functions

#### A. ChirpStack Configuration (COPY AS-IS)

```bash
# These work perfectly - don't change them!
sudo cp -r config/chirpstack ~/opt/REUSABLE_CODE/
cp -r config/mosquitto ~/opt/REUSABLE_CODE/

# Specifically these files:
# - chirpstack/chirpstack.toml (lines 1-135)
# - chirpstack/region_eu868.toml
# - mosquitto/mosquitto.conf
# - mosquitto/passwd (MQTT credentials)
```

#### B. Device Payload Parsers (EXTRACT FUNCTIONS)

```python
# From: services/ingest/app/parsers/chirpstack_parser.py
# COPY these exact functions (lines 15-89):

def parse_chirpstack(payload: dict) -> dict:
    """Parse ChirpStack webhook payload"""
    device_info = payload.get("deviceInfo", {})
    rx_info = payload.get("rxInfo", [{}])[0]
    tx_info = payload.get("txInfo", {})

    return {
        "deveui": device_info.get("devEui", "").lower(),
        "device_name": device_info.get("deviceName"),
        "application_id": device_info.get("applicationId"),
        "application_name": device_info.get("applicationName"),
        "frequency": tx_info.get("frequency"),
        "dr": tx_info.get("dr"),
        "adr": payload.get("adr"),
        "fcnt": payload.get("fCnt"),
        "fport": payload.get("fPort"),
        "data": payload.get("data", ""),
        "object": payload.get("object", {}),
        "gateway_id": rx_info.get("gatewayId", "").lower(),
        "rssi": rx_info.get("rssi"),
        "snr": rx_info.get("snr"),
        "timestamp": payload.get("time")
    }

# From: services/ingest/app/parking_detector.py
# COPY the Browan TABS decoder (lines 45-72):

def decode_browan_tabs(data_hex: str) -> dict:
    """Decode Browan TABS Motion Sensor payload"""
    try:
        data = bytes.fromhex(data_hex)
        if len(data) >= 1:
            status = data[0]
            occupied = bool(status & 0x01)

            battery = None
            if len(data) >= 2:
                battery = data[1] / 100.0  # Convert to voltage

            return {
                "occupied": occupied,
                "battery": battery,
                "raw_status": status
            }
    except:
        return {"occupied": False}

# From: services/parking-display/app/utils/tenant_auth.py
# DON'T COPY the multi-tenancy stuff, but KEEP the bcrypt logic (line 115):

# This SQL pattern for API key checking:
WHERE ak.key_hash = crypt($1, ak.key_hash)  # Important!
```

#### C. Database Connection Pattern (SIMPLIFY)

```python
# From: services/parking-display/app/database.py
# EXTRACT the pool config pattern (lines 28-44) but SIMPLIFY:

# OLD (overly complex):
config = DatabaseConfig(
    min_size=10,
    max_size=20,
    max_queries=50000,
    max_inactive_connection_lifetime=300,
    command_timeout=60,
    retry_attempts=3,
    retry_delay=1.0
)

# NEW (simpler but production-ready):
pool = await asyncpg.create_pool(
    dsn,
    min_size=5,
    max_size=20,
    command_timeout=60
)
```

#### D. State Validation Logic (EXTRACT)

```python
# From: services/parking-display/app/routers/actuations.py
# COPY the state transition rules (lines 156-189):

VALID_TRANSITIONS = {
    "FREE": ["OCCUPIED", "RESERVED", "MAINTENANCE"],
    "OCCUPIED": ["FREE", "MAINTENANCE"],
    "RESERVED": ["OCCUPIED", "FREE", "MAINTENANCE"],
    "MAINTENANCE": ["FREE"]
}

def is_valid_transition(current: str, new: str, source: str) -> bool:
    if source == "manual":  # Admin override
        return True
    return new in VALID_TRANSITIONS.get(current, [])
```

#### E. Docker/Deployment Config (REFERENCE)

```yaml
# From: docker-compose.yml
# KEEP these exact service configs:
# - postgres environment variables (lines 41-44)
# - redis command flags (lines 82-84)
# - chirpstack environment setup (lines 97-99)
# - mosquitto volume mounts (lines 83-86)

# DON'T COPY:
# - pgbouncer (not needed yet)
# - all the separate service containers
# - complex traefik rules
```

#### F. Working SQL Schemas (CHERRY-PICK)

```sql
-- From: database/migrations/008_multi_tenancy_schema.sql
-- DON'T COPY the complex RLS stuff
-- BUT KEEP these table structures:

-- Lines 245-289: The spaces table structure (simplify it)
-- Lines 412-456: The sensor_events structure (rename to sensor_readings)
-- Lines 523-567: The reservations table (keep as-is)
```

### Step 3: Create Reuse Checklist

```markdown
# CODE_TO_REUSE.md

## Copy Exactly (No Changes):
- [ ] ChirpStack config files (chirpstack.toml, region_eu868.toml)
- [ ] Mosquitto config and password file
- [ ] Environment variables from .env

## Extract Functions (Modify Slightly):
- [ ] parse_chirpstack() - ChirpStack webhook parser
- [ ] decode_browan_tabs() - Sensor payload decoder
- [ ] State transition validation rules
- [ ] Bcrypt SQL pattern for API keys

## Reference But Rewrite:
- [ ] Database pool configuration (simplify from 50 to 5 lines)
- [ ] Docker service configurations (simplify from 400 to 100 lines)
- [ ] SQL table structures (simplify from 8 schemas to 1)

## Completely Skip:
- [ ] Multi-tenancy/RLS code
- [ ] Complex middleware chains
- [ ] Service-to-service HTTP calls
- [ ] PgBouncer configuration
- [ ] APScheduler code (use simpler approach)
```

---

## Day 1: Project Setup & Core Structure (Monday, 4 hours)

### Hour 1: Initialize Project (9:00-10:00)

```bash
# 1. Create fresh project structure
cd ~/projects
mkdir smart-parking-v2
cd smart-parking-v2
git init

# 2. Create exact directory structure
mkdir -p src
mkdir -p migrations
mkdir -p config/{chirpstack,mosquitto,nginx}
mkdir -p tests
mkdir -p scripts
mkdir -p docs
mkdir -p backups

# 3. Create all empty files upfront
touch src/__init__.py
touch src/main.py
touch src/config.py
touch src/database.py
touch src/models.py
touch src/chirpstack_client.py
touch src/device_handlers.py
touch src/state_manager.py
touch src/background_tasks.py
touch src/exceptions.py
touch src/utils.py

# 4. Create other files
touch requirements.txt
touch requirements-dev.txt
touch Dockerfile
touch docker-compose.yml
touch .env.example
touch .env
touch Makefile
touch README.md
touch pytest.ini
touch .gitignore

# 5. Copy configs from old project
cp -r ~/projects/REUSABLE_CODE/chirpstack config/
cp -r ~/projects/REUSABLE_CODE/mosquitto config/

# 6. Initialize git
git add .
git commit -m "Initial project structure"
```

### Hour 2: Set Up Dependencies (10:00-11:00)

#### requirements.txt (EXACT versions that work)

```txt
# Core
fastapi==0.115.0
uvicorn[standard]==0.32.1
pydantic==2.10.3
pydantic-settings==2.6.1

# Database
asyncpg==0.30.0
psycopg2-binary==2.9.9  # For migrations only

# Redis
redis==5.0.1

# HTTP/gRPC
httpx==0.27.2
grpcio==1.68.1
grpcio-tools==1.68.1

# Utilities
python-json-logger==2.0.7
python-multipart==0.0.6
bcrypt==4.1.2
python-dateutil==2.8.2

# Monitoring (add later)
# prometheus-client==0.19.0
```

#### requirements-dev.txt

```txt
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==5.0.0
black==24.10.0
ruff==0.8.0
mypy==1.11.0
httpx  # For testing
```

#### .env.example (with actual examples)

```bash
# Database
DATABASE_URL=postgresql://parking:parking@localhost:5432/parking
DB_PASSWORD=parking

# Redis
REDIS_URL=redis://localhost:6379/0

# ChirpStack
CHIRPSTACK_HOST=localhost
CHIRPSTACK_PORT=8080
CHIRPSTACK_API_KEY=your-api-key-here  # Get from ChirpStack UI

# Application
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
SECRET_KEY=your-secret-key-here-minimum-32-chars

# Development
DEBUG=true
RELOAD=true
```

#### .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.coverage
.pytest_cache/
htmlcov/
.tox/

# Environment
.env
*.env.local

# Database
*.db
*.sqlite
*.sqlite3
backups/*.sql
backups/*.gz

# Logs
*.log
logs/

# OS
.DS_Store
Thumbs.db
```

### Hour 3: Write Core Configuration (11:00-12:00)

#### src/config.py (COMPLETE FILE)

```python
"""
Configuration management using Pydantic Settings
Single source of truth for all configuration
"""
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
import os
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings with validation"""

    # Database
    database_url: str = Field(
        default="postgresql://parking:parking@localhost:5432/parking",
        description="PostgreSQL connection URL"
    )
    db_pool_min_size: int = Field(default=5, ge=1, le=20)
    db_pool_max_size: int = Field(default=20, ge=5, le=100)

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    redis_max_connections: int = Field(default=50, ge=10, le=200)

    # ChirpStack
    chirpstack_host: str = Field(default="localhost")
    chirpstack_port: int = Field(default=8080)
    chirpstack_api_key: str = Field(default="", description="ChirpStack API key")

    # Application
    app_name: str = Field(default="Smart Parking Platform v2")
    app_version: str = Field(default="2.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )

    # Security
    secret_key: str = Field(
        default="change-this-in-production-minimum-32-characters",
        min_length=32
    )
    api_key_header: str = Field(default="X-API-Key")

    # Timeouts and Limits
    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    max_request_size: int = Field(default=10_485_760, description="Max request size in bytes (10MB)")

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Allow extra fields for forward compatibility
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Use lru_cache to ensure single instance
    """
    return Settings()

# Global settings instance
settings = get_settings()

# Export commonly used values
DATABASE_URL = settings.database_url
REDIS_URL = settings.redis_url
DEBUG = settings.debug
LOG_LEVEL = settings.log_level
```

### Hour 4: Write Models (12:00-13:00)

#### src/models.py (COMPLETE FILE)

```python
"""
Pydantic models for request/response validation
All models in one place for simplicity
"""
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID
import re

# ============================================================
# Enums
# ============================================================

class SpaceState(str, Enum):
    """Parking space states"""
    FREE = "FREE"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    MAINTENANCE = "MAINTENANCE"

class ReservationStatus(str, Enum):
    """Reservation statuses"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class DeviceType(str, Enum):
    """Device types"""
    SENSOR = "sensor"
    DISPLAY = "display"
    GATEWAY = "gateway"

# ============================================================
# Base Models
# ============================================================

class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DevEUIMixin(BaseModel):
    """Mixin for DevEUI validation"""

    @validator("sensor_eui", "display_eui", check_fields=False)
    def validate_deveui(cls, v):
        """Validate DevEUI format (16 hex characters)"""
        if v is not None:
            if not re.match(r"^[0-9a-fA-F]{16}$", v):
                raise ValueError(f"Invalid DevEUI format: {v}")
            return v.lower()
        return v

# ============================================================
# Space Models
# ============================================================

class SpaceBase(BaseModel):
    """Base space model with common fields"""
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    building: Optional[str] = Field(None, max_length=100)
    floor: Optional[str] = Field(None, max_length=20)
    zone: Optional[str] = Field(None, max_length=50)
    gps_latitude: Optional[float] = Field(None, ge=-90, le=90)
    gps_longitude: Optional[float] = Field(None, ge=-180, le=180)

    @root_validator
    def validate_gps_coordinates(cls, values):
        """Both GPS coordinates must be provided or both null"""
        lat = values.get("gps_latitude")
        lon = values.get("gps_longitude")
        if (lat is None) != (lon is None):
            raise ValueError("Both latitude and longitude must be provided or both null")
        return values

class SpaceCreate(SpaceBase, DevEUIMixin):
    """Model for creating a space"""
    sensor_eui: Optional[str] = Field(None, description="16-character hex DevEUI")
    display_eui: Optional[str] = Field(None, description="16-character hex DevEUI")
    state: SpaceState = Field(default=SpaceState.FREE)
    metadata: Optional[Dict[str, Any]] = None

class SpaceUpdate(DevEUIMixin):
    """Model for updating a space (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    building: Optional[str] = Field(None, max_length=100)
    floor: Optional[str] = Field(None, max_length=20)
    zone: Optional[str] = Field(None, max_length=50)
    sensor_eui: Optional[str] = None
    display_eui: Optional[str] = None
    state: Optional[SpaceState] = None
    metadata: Optional[Dict[str, Any]] = None

class Space(SpaceBase, DevEUIMixin, TimestampMixin):
    """Complete space model with all fields"""
    id: UUID
    sensor_eui: Optional[str] = None
    display_eui: Optional[str] = None
    state: SpaceState
    metadata: Optional[Dict[str, Any]] = None
    deleted_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        use_enum_values = True

# ============================================================
# Reservation Models
# ============================================================

class ReservationBase(BaseModel):
    """Base reservation model"""
    space_id: UUID
    start_time: datetime
    end_time: datetime
    user_email: Optional[str] = Field(None, max_length=255)
    user_phone: Optional[str] = Field(None, max_length=20)
    metadata: Optional[Dict[str, Any]] = None

    @root_validator
    def validate_times(cls, values):
        """Validate reservation times"""
        start = values.get("start_time")
        end = values.get("end_time")

        if start and end:
            if end <= start:
                raise ValueError("End time must be after start time")

            # Max 24 hour reservation
            duration = end - start
            if duration.total_seconds() > 86400:
                raise ValueError("Maximum reservation duration is 24 hours")

        return values

class ReservationCreate(ReservationBase):
    """Model for creating a reservation"""
    pass

class Reservation(ReservationBase, TimestampMixin):
    """Complete reservation model"""
    id: UUID
    status: ReservationStatus

    class Config:
        orm_mode = True
        use_enum_values = True

# ============================================================
# Sensor/Device Models
# ============================================================

class SensorUplink(BaseModel):
    """Parsed sensor uplink data"""
    device_eui: str
    timestamp: datetime

    # Occupancy
    occupancy_state: Optional[SpaceState] = None

    # Telemetry
    battery: Optional[float] = Field(None, ge=0, le=100)
    temperature: Optional[float] = Field(None, ge=-50, le=100)

    # Network
    rssi: Optional[int] = Field(None, ge=-200, le=0)
    snr: Optional[float] = Field(None, ge=-20, le=20)
    gateway_id: Optional[str] = None

    # Raw data
    raw_payload: Optional[str] = None

class DownlinkRequest(BaseModel):
    """Downlink request model"""
    payload: Optional[str] = Field(None, description="Hex or Base64 payload")
    fport: int = Field(default=1, ge=1, le=223)
    confirmed: bool = Field(default=False)

    # High-level command (optional)
    command: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

# ============================================================
# Response Models
# ============================================================

class HealthStatus(BaseModel):
    """Health check response"""
    status: str = Field(..., description="healthy, degraded, or unhealthy")
    version: str
    timestamp: datetime
    checks: Dict[str, str]
    stats: Optional[Dict[str, Any]] = None

class ProcessingResult(BaseModel):
    """Uplink processing result"""
    status: str
    device_eui: Optional[str] = None
    space_code: Optional[str] = None
    state: Optional[str] = None
    request_id: Optional[str] = None
    processing_time_ms: Optional[float] = None

class ApiResponse(BaseModel):
    """Generic API response"""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None

# ============================================================
# Query Parameters
# ============================================================

class PaginationParams(BaseModel):
    """Common pagination parameters"""
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

class SpaceFilters(PaginationParams):
    """Space query filters"""
    building: Optional[str] = None
    floor: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[SpaceState] = None
    include_deleted: bool = False

class ReservationFilters(PaginationParams):
    """Reservation query filters"""
    space_id: Optional[UUID] = None
    user_email: Optional[str] = None
    status: Optional[ReservationStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
```

---

## Day 2: Database & Exceptions (Tuesday, 4 hours)

### Hour 1: Create Database Schema (9:00-10:00)

#### migrations/001_initial_schema.sql (COMPLETE)

```sql
-- Smart Parking v2 - Initial Schema
-- Simple, clean, production-ready

-- ============================================================
-- Enable Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- Main Tables
-- ============================================================

-- Parking spaces (the core entity)
CREATE TABLE spaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) NOT NULL,

    -- Location
    building VARCHAR(100),
    floor VARCHAR(20),
    zone VARCHAR(50),
    gps_latitude DECIMAL(10, 8),
    gps_longitude DECIMAL(11, 8),

    -- Devices
    sensor_eui VARCHAR(16),
    display_eui VARCHAR(16),

    -- State
    state VARCHAR(20) NOT NULL DEFAULT 'FREE',

    -- Metadata
    metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT unique_space_code UNIQUE (code),
    CONSTRAINT unique_sensor_eui UNIQUE (sensor_eui),
    CONSTRAINT valid_state CHECK (state IN ('FREE', 'OCCUPIED', 'RESERVED', 'MAINTENANCE')),
    CONSTRAINT valid_gps CHECK (
        (gps_latitude IS NULL AND gps_longitude IS NULL) OR
        (gps_latitude BETWEEN -90 AND 90 AND gps_longitude BETWEEN -180 AND 180)
    )
);

-- Indexes for common queries
CREATE INDEX idx_spaces_state ON spaces(state) WHERE deleted_at IS NULL;
CREATE INDEX idx_spaces_sensor ON spaces(sensor_eui) WHERE deleted_at IS NULL;
CREATE INDEX idx_spaces_building ON spaces(building) WHERE deleted_at IS NULL;
CREATE INDEX idx_spaces_location ON spaces(building, floor, zone) WHERE deleted_at IS NULL;

-- Reservations
CREATE TABLE reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    space_id UUID NOT NULL,

    -- Time
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,

    -- User info
    user_email VARCHAR(255),
    user_phone VARCHAR(20),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'active',

    -- Metadata
    metadata JSONB,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT fk_space FOREIGN KEY (space_id) REFERENCES spaces(id),
    CONSTRAINT valid_status CHECK (status IN ('active', 'completed', 'cancelled', 'no_show')),
    CONSTRAINT valid_times CHECK (end_time > start_time),
    CONSTRAINT valid_duration CHECK (end_time - start_time <= INTERVAL '24 hours')
);

-- Indexes
CREATE INDEX idx_reservations_space ON reservations(space_id);
CREATE INDEX idx_reservations_status ON reservations(status) WHERE status = 'active';
CREATE INDEX idx_reservations_time ON reservations(start_time, end_time) WHERE status = 'active';

-- Sensor readings (time-series data)
CREATE TABLE sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    device_eui VARCHAR(16) NOT NULL,
    space_id UUID,

    -- Sensor data
    occupancy_state VARCHAR(20),
    battery DECIMAL(3, 2),
    temperature DECIMAL(4, 1),
    rssi INTEGER,
    snr DECIMAL(4, 1),

    -- Timestamp
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Foreign key (optional - might have readings from unassigned sensors)
    CONSTRAINT fk_space FOREIGN KEY (space_id) REFERENCES spaces(id)
);

-- Optimize for time-series
CREATE INDEX idx_sensor_readings_device_time ON sensor_readings(device_eui, timestamp DESC);
CREATE INDEX idx_sensor_readings_space_time ON sensor_readings(space_id, timestamp DESC) 
    WHERE space_id IS NOT NULL;
-- BRIN index for timestamp (very efficient for time-series)
CREATE INDEX idx_sensor_readings_timestamp_brin ON sensor_readings 
    USING BRIN(timestamp);

-- State change audit log
CREATE TABLE state_changes (
    id BIGSERIAL PRIMARY KEY,
    space_id UUID NOT NULL,
    previous_state VARCHAR(20),
    new_state VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    request_id VARCHAR(50),
    metadata JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Foreign key
    CONSTRAINT fk_space FOREIGN KEY (space_id) REFERENCES spaces(id)
);

CREATE INDEX idx_state_changes_space ON state_changes(space_id, timestamp DESC);
CREATE INDEX idx_state_changes_timestamp_brin ON state_changes USING BRIN(timestamp);

-- Simple API keys table
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash VARCHAR(255) NOT NULL,
    key_name VARCHAR(100),
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Use unique constraint for hash lookups
    CONSTRAINT unique_key_hash UNIQUE (key_hash)
);

CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = true;

-- ============================================================
-- Functions
-- ============================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables
CREATE TRIGGER update_spaces_updated_at
    BEFORE UPDATE ON spaces
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_reservations_updated_at
    BEFORE UPDATE ON reservations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- Initial Data (Development)
-- ============================================================

-- Insert test API key (password: 'test-api-key-123')
-- This uses bcrypt with salt
INSERT INTO api_keys (key_hash, key_name) VALUES 
('$2b$12$YourHashHere', 'Development Key');

-- Insert sample spaces
INSERT INTO spaces (name, code, building, floor, zone) VALUES
('Parking A-001', 'A001', 'Building A', 'Ground', 'North'),
('Parking A-002', 'A002', 'Building A', 'Ground', 'North'),
('Parking B-001', 'B001', 'Building B', 'Ground', 'South');

-- Grant permissions (adjust for your user)
GRANT ALL ON ALL TABLES IN SCHEMA public TO parking;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO parking;
```

### Hour 2: Write Exceptions (10:00-11:00)

#### src/exceptions.py (COMPLETE FILE)

```python
"""
Custom exceptions for better error handling
Keep it simple but comprehensive
"""
from typing import Optional, Any

class ParkingException(Exception):
    """Base exception for all parking-related errors"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }

# ============================================================
# Database Exceptions
# ============================================================

class DatabaseError(ParkingException):
    """Database connection or query error"""
    pass

class RecordNotFoundError(ParkingException):
    """Record not found in database"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="RECORD_NOT_FOUND",
            details={"resource": resource, "identifier": str(identifier)}
        )

# ============================================================
# Domain Exceptions
# ============================================================

class SpaceNotFoundError(RecordNotFoundError):
    """Parking space not found"""

    def __init__(self, space_id: str):
        super().__init__("Space", space_id)
        self.space_id = space_id

class ReservationNotFoundError(RecordNotFoundError):
    """Reservation not found"""

    def __init__(self, reservation_id: str):
        super().__init__("Reservation", reservation_id)
        self.reservation_id = reservation_id

class DeviceNotFoundError(RecordNotFoundError):
    """Device not found"""

    def __init__(self, device_eui: str):
        super().__init__("Device", device_eui)
        self.device_eui = device_eui

# ============================================================
# Business Logic Exceptions
# ============================================================

class StateTransitionError(ParkingException):
    """Invalid state transition"""

    def __init__(
        self,
        message: str,
        current_state: Optional[str] = None,
        requested_state: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="INVALID_STATE_TRANSITION",
            details={
                "current_state": current_state,
                "requested_state": requested_state
            }
        )
        self.current_state = current_state
        self.requested_state = requested_state

class SpaceNotAvailableError(ParkingException):
    """Space is not available for reservation"""

    def __init__(self, space_id: str, reason: str = "Space is not available"):
        super().__init__(
            message=reason,
            error_code="SPACE_NOT_AVAILABLE",
            details={"space_id": space_id}
        )

class DuplicateResourceError(ParkingException):
    """Resource already exists"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} already exists: {identifier}",
            error_code="DUPLICATE_RESOURCE",
            details={"resource": resource, "identifier": str(identifier)}
        )

# ============================================================
# External Service Exceptions
# ============================================================

class ChirpStackError(ParkingException):
    """ChirpStack API error"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(
            message=message,
            error_code="CHIRPSTACK_ERROR",
            details={"status_code": status_code} if status_code else {}
        )
        self.status_code = status_code

class RedisError(ParkingException):
    """Redis connection or operation error"""
    pass

# ============================================================
# Validation Exceptions
# ============================================================

class ValidationError(ParkingException):
    """Input validation error"""

    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Validation error for {field}: {message}",
            error_code="VALIDATION_ERROR",
            details={"field": field, "error": message}
        )

class AuthenticationError(ParkingException):
    """Authentication failed"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR"
        )

class AuthorizationError(ParkingException):
    """Authorization failed"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR"
        )
```

### Hour 3: Write Utilities (11:00-12:00)

#### src/utils.py (COMPLETE FILE)

```python
"""
Utility functions used across the application
Keep these pure functions without side effects
"""
import hashlib
import secrets
import base64
from datetime import datetime, timezone
from typing import Optional, Any, Dict
import re
import uuid
import logging

logger = logging.getLogger(__name__)

# ============================================================
# ID Generation
# ============================================================

def generate_request_id() -> str:
    """Generate unique request ID for tracing"""
    return f"req_{uuid.uuid4().hex[:12]}"

def get_request_id() -> str:
    """Get or generate request ID"""
    # In production, get from context/header
    return generate_request_id()

# ============================================================
# String Manipulation
# ============================================================

def normalize_deveui(deveui: str) -> str:
    """
    Normalize DevEUI to lowercase hex without separators
    Examples:
        "00:11:22:33:44:55:66:77" -> "0011223344556677"
        "00-11-22-33-44-55-66-77" -> "0011223344556677"
        "0011223344556677" -> "0011223344556677"
    """
    if not deveui:
        return ""

    # Remove common separators
    cleaned = deveui.replace(":", "").replace("-", "").replace(" ", "")

    # Validate hex and length
    if not re.match(r"^[0-9a-fA-F]{16}$", cleaned):
        raise ValueError(f"Invalid DevEUI format: {deveui}")

    return cleaned.lower()

def generate_space_code(building: str, floor: str, number: int) -> str:
    """
    Generate a space code from components
    Example: Building "A", Floor "1", Number 5 -> "A1-005"
    """
    building_code = (building or "X")[:1].upper()
    floor_code = (floor or "0")[:2]
    return f"{building_code}{floor_code}-{number:03d}"

# ============================================================
# Data Encoding/Decoding
# ============================================================

def hex_to_base64(hex_string: str) -> str:
    """Convert hex string to base64"""
    try:
        bytes_data = bytes.fromhex(hex_string)
        return base64.b64encode(bytes_data).decode('ascii')
    except Exception as e:
        logger.error(f"Failed to convert hex to base64: {e}")
        raise ValueError(f"Invalid hex string: {hex_string}")

def base64_to_hex(base64_string: str) -> str:
    """Convert base64 string to hex"""
    try:
        bytes_data = base64.b64decode(base64_string)
        return bytes_data.hex()
    except Exception as e:
        logger.error(f"Failed to convert base64 to hex: {e}")
        raise ValueError(f"Invalid base64 string: {base64_string}")

def detect_encoding(payload: str) -> str:
    """
    Detect if payload is hex or base64 encoded
    Returns: 'hex', 'base64', or 'unknown'
    """
    # Check for hex (only hex chars, even length)
    if re.match(r"^[0-9a-fA-F]+$", payload) and len(payload) % 2 == 0:
        return "hex"

    # Check for base64 (contains base64 chars)
    if re.match(r"^[A-Za-z0-9+/]+=*$", payload):
        return "base64"

    return "unknown"

# ============================================================
# Time Utilities
# ============================================================

def utcnow() -> datetime:
    """Get current UTC time with timezone info"""
    return datetime.now(timezone.utc)

def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human readable
    Examples:
        65 -> "1m 5s"
        3665 -> "1h 1m 5s"
        0.5 -> "500ms"
    """
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")

    return " ".join(parts) or "0s"

# ============================================================
# Validation Helpers
# ============================================================

def is_valid_email(email: str) -> bool:
    """Basic email validation"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

def is_valid_phone(phone: str) -> bool:
    """Basic phone validation (international format)"""
    # Remove spaces and dashes
    cleaned = phone.replace(" ", "").replace("-", "")
    # Check if starts with + and has 10-15 digits
    return bool(re.match(r"^\+?[1-9]\d{9,14}$", cleaned))

# ============================================================
# Security Helpers
# ============================================================

def generate_api_key() -> str:
    """Generate a secure random API key"""
    return secrets.token_urlsafe(32)

def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage
    Note: In production, use bcrypt from the bcrypt library
    """
    # Simple example - use bcrypt in production!
    return hashlib.sha256(api_key.encode()).hexdigest()

# ============================================================
# Color Mappings (for parking displays)
# ============================================================

def get_display_color(state: str) -> str:
    """
    Get hex color for parking state
    Returns 6-character hex string (RGB)
    """
    color_map = {
        "FREE": "00FF00",      # Green
        "OCCUPIED": "FF0000",   # Red
        "RESERVED": "FFFF00",   # Yellow
        "MAINTENANCE": "FFA500", # Orange
        "ERROR": "0000FF"       # Blue
    }
    return color_map.get(state.upper(), "FFFFFF")  # White for unknown

def parse_rgb_hex(hex_color: str) -> tuple:
    """
    Parse hex color to RGB tuple
    Example: "FF0000" -> (255, 0, 0)
    """
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    raise ValueError(f"Invalid hex color: {hex_color}")

# ============================================================
# Debugging Helpers
# ============================================================

def truncate_string(s: str, max_length: int = 100) -> str:
    """Truncate string for logging"""
    if len(s) <= max_length:
        return s
    return s[:max_length] + "..."

def safe_dict_get(d: Dict[str, Any], path: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value
    Example: safe_dict_get(data, "deviceInfo.devEui")
    """
    keys = path.split(".")
    value = d

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default

    return value

def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging
    Example: "secret-api-key-123" -> "secr************"
    """
    if len(data) <= visible_chars:
        return "*" * len(data)

    return data[:visible_chars] + "*" * (len(data) - visible_chars)
```

### Hour 4: Write Database Module - Part 1 (12:00-13:00)

#### src/database.py (FIRST HALF)

```python
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
                    'application_name': 'parking_v2',
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
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire connection from pool"""
        if not self.pool:
            raise DatabaseError("Database pool not initialized")

        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Execute in transaction"""
        async with self.acquire() as conn:
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

        return [Space(**dict(row)) for row in rows]

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

        return Space(**dict(row))

    async def get_space_by_sensor(self, sensor_eui: str) -> Optional[Space]:
        """Get space by sensor DevEUI"""

        query = """
            SELECT * FROM spaces 
            WHERE sensor_eui = $1 AND deleted_at IS NULL
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query, sensor_eui.lower())

        if not row:
            return None

        return Space(**dict(row))

# Continue in next hour...
```

---

## Day 3: Complete Database & Start Core Services (Wednesday, 6 hours)

### Hour 1: Complete Database Module (9:00-10:00)

#### src/database.py (SECOND HALF - append to file)

```python
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
                    space.sensor_eui.lower() if space.sensor_eui else None,
                    space.display_eui.lower() if space.display_eui else None,
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
        timestamp: Optional[datetime] = None
    ):
        """Insert sensor reading"""

        query = """
            INSERT INTO sensor_readings (
                device_eui, space_id, occupancy_state,
                battery, temperature, rssi, snr, timestamp
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """

        async with self.acquire() as conn:
            await conn.execute(
                query,
                device_eui.lower(),
                space_id,
                occupancy_state,
                battery,
                None,  # temperature
                rssi,
                snr,
                timestamp or utcnow()
            )

    async def get_latest_sensor_reading(
        self,
        device_eui: str
    ) -> Optional[Dict[str, Any]]:
        """Get latest reading from a sensor"""

        query = """
            SELECT * FROM sensor_readings
            WHERE device_eui = $1
            ORDER BY timestamp DESC
            LIMIT 1
        """

        async with self.acquire() as conn:
            row = await conn.fetchrow(query, device_eui.lower())

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
```

### Hour 2: Create Device Handlers (10:00-11:00)

#### src/device_handlers.py (COMPLETE - Copy sensor logic from old code)

```python
"""
Device handlers for different sensor types
Copy the decoding logic from your old code here
"""
import base64
import logging
from typing import Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod
import struct

from .models import SpaceState, SensorUplink
from .utils import hex_to_base64, base64_to_hex, get_display_color

logger = logging.getLogger(__name__)

# ============================================================
# Device Handler Protocol
# ============================================================

class DeviceHandler(Protocol):
    """Protocol for device handlers"""

    def can_handle(self, device_eui: str) -> bool:
        """Check if this handler can process the device"""
        ...

    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Parse uplink data from device"""
        ...

    def encode_downlink(self, command: str, params: Dict[str, Any]) -> bytes:
        """Encode downlink command"""
        ...

# ============================================================
# Base Handler
# ============================================================

class BaseDeviceHandler(ABC):
    """Base class for device handlers"""

    def __init__(self):
        self.device_patterns = []  # DevEUI patterns this handler supports

    def can_handle(self, device_eui: str) -> bool:
        """Check if this handler supports the device"""
        device_eui = device_eui.lower()

        for pattern in self.device_patterns:
            if device_eui.startswith(pattern):
                return True

        return False

    @abstractmethod
    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Parse device uplink"""
        pass

    def encode_downlink(self, command: str, params: Dict[str, Any]) -> bytes:
        """Encode downlink - override in subclasses"""
        return b""

    def parse_chirpstack_uplink(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract common ChirpStack fields"""
        device_info = data.get("deviceInfo", {})
        rx_info = data.get("rxInfo", [{}])[0]

        return {
            "device_eui": device_info.get("devEui", "").lower(),
            "payload": data.get("data", ""),
            "rssi": rx_info.get("rssi"),
            "snr": rx_info.get("snr"),
            "gateway_id": rx_info.get("gatewayId"),
            "timestamp": data.get("time")
        }

# ============================================================
# Browan TABS Motion Sensor Handler
# ============================================================

class BrowanTabsHandler(BaseDeviceHandler):
    """
    Handler for Browan TABS Motion sensors
    COPY YOUR EXACT DECODING LOGIC HERE
    """

    def __init__(self):
        super().__init__()
        # Add your actual Browan device EUI prefixes
        self.device_patterns = [
            "58a0cb",  # Browan prefix
            "0011223344"  # Test devices
        ]

    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Parse Browan TABS uplink"""

        # Extract ChirpStack fields
        parsed = self.parse_chirpstack_uplink(data)

        # Decode payload (COPY FROM YOUR OLD CODE)
        payload_b64 = parsed["payload"]

        try:
            # Decode base64
            payload_bytes = base64.b64decode(payload_b64)

            # Parse Browan format (FROM parking_detector.py lines 45-72)
            occupancy = SpaceState.FREE
            battery = None

            if len(payload_bytes) >= 1:
                status_byte = payload_bytes[0]

                # Bit 0 = occupancy
                if status_byte & 0x01:
                    occupancy = SpaceState.OCCUPIED

                # Byte 1 = battery (if present)
                if len(payload_bytes) >= 2:
                    battery = payload_bytes[1] / 100.0  # Convert to voltage

            return SensorUplink(
                device_eui=parsed["device_eui"],
                timestamp=parsed["timestamp"],
                occupancy_state=occupancy,
                battery=battery,
                rssi=parsed["rssi"],
                snr=parsed["snr"],
                gateway_id=parsed["gateway_id"],
                raw_payload=payload_b64
            )

        except Exception as e:
            logger.error(f"Failed to parse Browan payload: {e}")

            # Return minimal data
            return SensorUplink(
                device_eui=parsed["device_eui"],
                timestamp=parsed["timestamp"],
                rssi=parsed["rssi"],
                snr=parsed["snr"],
                raw_payload=payload_b64
            )

# ============================================================
# Heltec Display Handler
# ============================================================

class HeltecDisplayHandler(BaseDeviceHandler):
    """Handler for Heltec WiFi LoRa displays"""

    def __init__(self):
        super().__init__()
        self.device_patterns = [
            "70b3d57ed006",  # Heltec prefix
        ]

    def parse_uplink(self, data: Dict[str, Any]) -> SensorUplink:
        """Heltec displays don't send occupancy data"""
        parsed = self.parse_chirpstack_uplink(data)

        return SensorUplink(
            device_eui=parsed["device_eui"],
            timestamp=parsed["timestamp"],
            rssi=parsed["rssi"],
            snr=parsed["snr"],
            raw_payload=parsed.get("payload")
        )

    def encode_downlink(self, command: str, params: Dict[str, Any]) -> bytes:
        """Encode display command"""

        if command == "set_color":
            state = params.get("state", "FREE")
            color_hex = get_display_color(state)
            return bytes.fromhex(color_hex)

        elif command == "set_rgb":
            r = params.get("r", 0)
            g = params.get("g", 0)
            b = params.get("b", 0)
            return bytes([r, g, b])

        return b""

    def get_color_for_state(self, state: SpaceState) -> bytes:
        """Get color bytes for parking state"""
        color_hex = get_display_color(state.value)
        return bytes.fromhex(color_hex)

# ============================================================
# Kuando Busylight Handler
# ============================================================

class KuandoBusylightHandler(BaseDeviceHandler):
    """
    Handler for Kuando Busylight devices
    COPY FROM YOUR BUSYLIGHT INTEGRATION
    """

    def __init__(self):
        super().__init__()
        self.device_patterns = [
            "202020",  # Kuando prefix
        ]

    def encode_downlink(self, command: str, params: Dict[str, Any]) -> bytes:
        """
        Encode Kuando Busylight command
        Format: [Cmd, R, G, B, Options]
        """

        if command == "set_color":
            state = params.get("state", "FREE")

            # Color mapping for Kuando (FROM BUSYLIGHT_INTEGRATION_GUIDE.md)
            colors = {
                "FREE": (0, 255, 0),      # Green
                "OCCUPIED": (255, 0, 0),   # Red
                "RESERVED": (255, 255, 0), # Yellow
                "MAINTENANCE": (255, 165, 0) # Orange
            }

            r, g, b = colors.get(state, (0, 0, 255))  # Blue for unknown

            # Kuando command format
            return bytes([
                0x00,  # Command byte
                r,     # Red
                g,     # Green
                b,     # Blue
                0x00   # Options (no flash, no dim)
            ])

        return b""

# ============================================================
# Device Handler Registry
# ============================================================

class DeviceHandlerRegistry:
    """Registry for device handlers"""

    def __init__(self):
        self.handlers: List[BaseDeviceHandler] = []
        self._device_cache: Dict[str, BaseDeviceHandler] = {}

    def register(self, handler: BaseDeviceHandler):
        """Register a device handler"""
        self.handlers.append(handler)
        logger.info(f"Registered handler: {handler.__class__.__name__}")

    def get_handler(self, device_eui: str) -> Optional[BaseDeviceHandler]:
        """Get handler for device"""

        # Check cache
        if device_eui in self._device_cache:
            return self._device_cache[device_eui]

        # Find handler
        for handler in self.handlers:
            if handler.can_handle(device_eui):
                self._device_cache[device_eui] = handler
                return handler

        logger.warning(f"No handler found for device {device_eui}")
        return None

    def auto_register(self):
        """Auto-register all built-in handlers"""
        self.register(BrowanTabsHandler())
        self.register(HeltecDisplayHandler())
        self.register(KuandoBusylightHandler())
        logger.info(f"Auto-registered {len(self.handlers)} handlers")

    def list_handlers(self) -> List[str]:
        """List registered handler names"""
        return [h.__class__.__name__ for h in self.handlers]

# ============================================================
# Generic ChirpStack Parser (Fallback)
# ============================================================

def parse_chirpstack_webhook(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generic ChirpStack webhook parser
    COPY FROM services/ingest/app/parsers/chirpstack_parser.py
    """
    device_info = data.get("deviceInfo", {})
    rx_info = data.get("rxInfo", [{}])[0]
    tx_info = data.get("txInfo", {})

    return {
        "device_eui": device_info.get("devEui", "").lower(),
        "device_name": device_info.get("deviceName"),
        "application_id": device_info.get("applicationId"),
        "frequency": tx_info.get("frequency"),
        "dr": tx_info.get("dr"),
        "fport": data.get("fPort"),
        "fcnt": data.get("fCnt"),
        "payload": data.get("data", ""),
        "rssi": rx_info.get("rssi"),
        "snr": rx_info.get("snr"),
        "gateway_id": rx_info.get("gatewayId", "").lower(),
        "timestamp": data.get("time")
    }
```

###
