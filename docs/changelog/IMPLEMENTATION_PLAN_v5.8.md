# Implementation Plan: Smart Parking Platform v5.8
## Architectural Improvements & Production Hardening

**Created:** 2025-10-22
**Based on:** docs/20251022_recommendations.md
**Target Version:** v5.8.0
**Estimated Duration:** 4-6 weeks

---

## Executive Summary

This implementation plan addresses architectural improvements, performance optimizations, and production hardening based on the comprehensive review in `docs/20251022_recommendations.md`. The plan is organized into 4 phases with clear milestones and success criteria.

**Current State:** v5.7.0 (Multi-tenancy + Critical EUI fix)
**Target State:** v5.8.0 (Production-ready with observability and performance optimization)

---

## Phase 1: Quick Wins (Week 1-2)
**Goal:** Low-hanging fruit that provide immediate value with minimal risk

### 1.1 Documentation Consolidation ✅ Priority: HIGH
**Duration:** 2 days

#### Tasks:
1. **Reorganize docs directory**
   ```
   docs/
   ├── architecture/
   │   ├── README.md (main architecture overview)
   │   ├── database-schema.md (V5_DATABASE_SCHEMA.md)
   │   ├── multi-tenancy.md (v5.3-01)
   │   └── state-machine.md (v5.3-03)
   ├── api/
   │   ├── openapi.yaml
   │   ├── reference.md (API_REFERENCE_v5.3.md)
   │   └── webhook-integration.md (v5.3-05)
   ├── operations/
   │   ├── deployment.md (RLS_DEPLOYMENT_GUIDE.md)
   │   ├── monitoring.md (v5.3-06)
   │   └── runbooks.md (OPERATIONAL_RUNBOOKS.md)
   ├── security/
   │   ├── rbac.md
   │   └── tenancy.md (SECURITY_TENANCY.md)
   └── changelog/
       ├── BUILD_NOTES.md (consolidate all BUILD_*.md)
       └── FIXES.md (consolidate 20251021_fixes.md, etc.)
   ```

2. **Update README.md**
   - Remove duplicate "Services" section (~line 900)
   - Add "Documentation" section with links to organized docs
   - Keep only high-level overview in README

3. **Create index files**
   - `docs/README.md` - Documentation index
   - `docs/architecture/README.md` - Architecture guide
   - `docs/api/README.md` - API documentation guide

**Success Criteria:**
- [ ] No duplicate content between files
- [ ] All docs referenced from main README
- [ ] Clear navigation structure

---

### 1.2 Database Performance Indexes ✅ Priority: HIGH
**Duration:** 1 day

#### Migration: `migrations/012_performance_indexes.sql`

```sql
-- Performance indexes for high-traffic queries
-- Migration 012: Performance Optimization Indexes

BEGIN;

-- Actuations table - critical for display update queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actuations_created_at
  ON actuations(created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actuations_tenant_space
  ON actuations(tenant_id, space_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actuations_display_eui
  ON actuations(display_eui, created_at DESC)
  WHERE downlink_sent = TRUE;

-- Reservations - availability queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reservations_tenant_status_time
  ON reservations(tenant_id, status, start_time, end_time)
  WHERE status IN ('pending', 'confirmed');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_reservations_space_overlap
  ON reservations(space_id, start_time, end_time)
  WHERE status IN ('pending', 'confirmed');

-- API keys - authentication queries (partial index for active keys only)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_active
  ON api_keys(tenant_id, key_hash)
  WHERE is_active = TRUE;

-- Sensor readings - telemetry queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sensor_readings_device_time
  ON sensor_readings(device_eui, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sensor_readings_space_time
  ON sensor_readings(space_id, timestamp DESC)
  WHERE space_id IS NOT NULL;

-- Spaces - common lookup patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spaces_tenant_site
  ON spaces(tenant_id, site_id)
  WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spaces_sensor_eui
  ON spaces(sensor_eui)
  WHERE sensor_eui IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spaces_display_eui
  ON spaces(display_eui)
  WHERE display_eui IS NOT NULL AND deleted_at IS NULL;

COMMIT;
```

**Testing:**
```sql
-- Verify index usage with EXPLAIN ANALYZE
EXPLAIN ANALYZE
SELECT * FROM actuations
WHERE tenant_id = 'xxx' AND space_id = 'yyy'
ORDER BY created_at DESC LIMIT 10;

-- Should show "Index Scan using idx_actuations_tenant_space"
```

**Success Criteria:**
- [ ] All indexes created without blocking writes
- [ ] Query performance improved (measure with EXPLAIN ANALYZE)
- [ ] No impact on write performance

---

### 1.3 Service Health Checks ✅ Priority: MEDIUM
**Duration:** 1 day

#### Update `docker-compose.yml`:

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 40s
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  contact-api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 30s
```

**Success Criteria:**
- [ ] All services have health checks
- [ ] Dependent services wait for dependencies
- [ ] Failed health checks trigger restart

---

### 1.4 Resource Limits ✅ Priority: MEDIUM
**Duration:** 1 day

#### Update `docker-compose.yml`:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
    restart: unless-stopped

  postgres:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G

  redis:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
        reservations:
          cpus: '0.25'
          memory: 128M
```

**Monitoring:**
```bash
# Monitor resource usage
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

**Success Criteria:**
- [ ] Resource limits prevent runaway processes
- [ ] Services operate within allocated resources
- [ ] No OOM kills under normal load

---

### 1.5 Structured Logging ✅ Priority: HIGH
**Duration:** 2 days

#### Create `src/logging_config.py`:

```python
"""
Structured logging configuration using structlog
Provides JSON-formatted logs with request context
"""
import logging
import structlog
from datetime import datetime
from typing import Any


def add_app_context(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Add application-level context to all log entries"""
    event_dict['app'] = 'parking-v5-api'
    event_dict['environment'] = 'production'  # From env var
    return event_dict


def configure_logging(log_level: str = "INFO"):
    """Configure structured logging for the application"""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            add_app_context,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


# Usage in application code:
# from src.logging_config import configure_logging
# logger = configure_logging(os.getenv("LOG_LEVEL", "INFO"))
#
# logger.info("reservation_created",
#     tenant_id=tenant_id,
#     space_id=space_id,
#     reservation_id=str(reservation_id),
#     start_time=start_time.isoformat()
# )
```

**Update `src/main.py`:**

```python
from src.logging_config import configure_logging

# Initialize logging
logger = configure_logging(os.getenv("LOG_LEVEL", "INFO"))

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with structured data"""
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start_time = time.time()

    logger.info("request_started",
        method=request.method,
        path=request.url.path,
        client_host=request.client.host
    )

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000

    logger.info("request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2)
    )

    structlog.contextvars.unbind_contextvars("request_id")
    return response
```

**Success Criteria:**
- [ ] All logs in JSON format
- [ ] Request ID propagates through all log entries
- [ ] Easy to parse with log aggregation tools (ELK, Loki)

---

## Phase 2: Performance Optimization (Week 3-4)
**Goal:** Improve response times and reduce database load

### 2.1 Redis Caching Layer ✅ Priority: HIGH
**Duration:** 3 days

#### Create `src/cache.py`:

```python
"""
Redis caching layer with automatic invalidation
"""
import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps
import redis.asyncio as redis
from datetime import timedelta

class CacheManager:
    """Manages caching operations with Redis"""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        cached = await self.redis.get(key)
        return json.loads(cached) if cached else None

    async def set(self, key: str, value: Any, ttl: int = 300):
        """Set cached value with TTL"""
        await self.redis.setex(key, ttl, json.dumps(value))

    async def delete(self, key: str):
        """Delete cached value"""
        await self.redis.delete(key)

    async def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self.redis.delete(*keys)

    def cached(self, ttl: int = 300, key_prefix: str = ""):
        """Decorator for caching function results"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key from function name and arguments
                key_data = f"{func.__name__}:{json.dumps(args)}:{json.dumps(kwargs, default=str)}"
                cache_key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"

                # Try cache first
                cached = await self.get(cache_key)
                if cached is not None:
                    return cached

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                await self.set(cache_key, result, ttl)
                return result
            return wrapper
        return decorator


# Usage example:
cache = CacheManager(os.getenv("REDIS_URL"))

@cache.cached(ttl=60, key_prefix="spaces")
async def get_space_list(tenant_id: str, filters: dict):
    # Expensive database query
    pass

# Invalidation on write:
async def update_space(space_id: str, data: dict):
    # Update database
    await db.execute(...)

    # Invalidate related caches
    await cache.delete_pattern(f"spaces:*")
```

**Success Criteria:**
- [ ] Cache hit rate > 70% for read endpoints
- [ ] Response time reduced by 50% for cached endpoints
- [ ] Automatic invalidation on writes

---

### 2.2 Database Query Optimization ✅ Priority: HIGH
**Duration:** 2 days

#### Update `src/database.py` with eager loading:

```python
from sqlalchemy.orm import selectinload, joinedload

async def get_spaces_with_devices(tenant_id: UUID) -> list:
    """Fetch spaces with sensor/display info in single query (N+1 prevention)"""

    stmt = (
        select(Space)
        .options(
            # Eager load related devices
            selectinload(Space.sensor),
            selectinload(Space.display),
            joinedload(Space.site)
        )
        .where(Space.tenant_id == tenant_id)
        .where(Space.deleted_at == None)
        .order_by(Space.code)
    )

    result = await db.execute(stmt)
    return result.unique().scalars().all()


async def get_reservations_with_space(
    tenant_id: UUID,
    date_from: datetime,
    date_to: datetime
) -> list:
    """Fetch reservations with space details in single query"""

    stmt = (
        select(Reservation)
        .options(joinedload(Reservation.space))
        .where(Reservation.tenant_id == tenant_id)
        .where(Reservation.start_time >= date_from)
        .where(Reservation.end_time <= date_to)
        .order_by(Reservation.start_time)
    )

    result = await db.execute(stmt)
    return result.unique().scalars().all()
```

**Query Performance Testing:**

```python
# Add to tests/test_performance.py
import pytest
from sqlalchemy import text

@pytest.mark.asyncio
async def test_space_list_query_count(db_session):
    """Verify space list uses single query, not N+1"""

    # Reset query counter
    await db_session.execute(text("SELECT pg_stat_reset();"))

    # Execute query
    spaces = await get_spaces_with_devices(tenant_id)

    # Check query count
    result = await db_session.execute(text("""
        SELECT calls FROM pg_stat_statements
        WHERE query LIKE '%spaces%'
    """))

    query_count = result.scalar()
    assert query_count <= 2, f"Expected ≤2 queries, got {query_count}"
```

**Success Criteria:**
- [ ] No N+1 query patterns
- [ ] Query count reduced for list endpoints
- [ ] Performance tests in place

---

### 2.3 Materialized Views for Analytics ✅ Priority: MEDIUM
**Duration:** 2 days

#### Migration: `migrations/013_materialized_views.sql`

```sql
-- Materialized views for dashboard queries
-- Migration 013: Analytics Performance

BEGIN;

-- Daily space utilization summary
CREATE MATERIALIZED VIEW IF NOT EXISTS space_utilization_daily AS
SELECT
    sc.tenant_id,
    sc.space_id,
    s.code as space_code,
    s.name as space_name,
    DATE(sc.timestamp) as date,
    COUNT(*) FILTER (WHERE sc.new_state = 'OCCUPIED') as occupancy_count,
    COUNT(*) FILTER (WHERE sc.new_state = 'FREE') as vacancy_count,
    COUNT(DISTINCT sc.request_id) as total_state_changes,
    AVG(
        EXTRACT(EPOCH FROM (
            LEAD(sc.timestamp) OVER (PARTITION BY sc.space_id ORDER BY sc.timestamp)
            - sc.timestamp
        ))
    ) FILTER (WHERE sc.new_state = 'OCCUPIED') as avg_occupancy_duration_seconds
FROM state_changes sc
JOIN spaces s ON sc.space_id = s.id
WHERE sc.timestamp >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY sc.tenant_id, sc.space_id, s.code, s.name, DATE(sc.timestamp);

CREATE UNIQUE INDEX ON space_utilization_daily(tenant_id, space_id, date);
CREATE INDEX ON space_utilization_daily(tenant_id, date DESC);

-- Tenant API usage summary (hourly)
CREATE MATERIALIZED VIEW IF NOT EXISTS api_usage_hourly AS
SELECT
    tenant_id,
    DATE_TRUNC('hour', timestamp) as hour,
    endpoint,
    COUNT(*) as request_count,
    COUNT(*) FILTER (WHERE status_code >= 500) as error_count,
    AVG(response_time_ms) as avg_response_time_ms,
    MAX(response_time_ms) as max_response_time_ms
FROM api_usage
WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY tenant_id, DATE_TRUNC('hour', timestamp), endpoint;

CREATE UNIQUE INDEX ON api_usage_hourly(tenant_id, hour, endpoint);
CREATE INDEX ON api_usage_hourly(tenant_id, hour DESC);

-- Refresh schedule (run via cron or APScheduler)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY space_utilization_daily;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY api_usage_hourly;

COMMIT;
```

**Refresh Function** in `src/background_tasks.py`:

```python
async def refresh_materialized_views():
    """Refresh materialized views for analytics"""
    logger.info("refreshing_materialized_views")

    views = [
        "space_utilization_daily",
        "api_usage_hourly"
    ]

    for view in views:
        try:
            await db.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view};")
            logger.info("materialized_view_refreshed", view=view)
        except Exception as e:
            logger.error("materialized_view_refresh_failed", view=view, error=str(e))

# Schedule refresh every hour
scheduler.add_job(
    refresh_materialized_views,
    trigger="cron",
    minute=0,
    id="refresh_materialized_views"
)
```

**Success Criteria:**
- [ ] Dashboard queries 10x faster
- [ ] Materialized views refresh hourly
- [ ] No impact on transactional tables

---

## Phase 3: Observability (Week 5)
**Goal:** Comprehensive monitoring and debugging capabilities

### 3.1 Centralized Configuration ✅ Priority: HIGH
**Duration:** 2 days

#### Create `src/config.py`:

```python
"""
Centralized configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application
    app_name: str = "Smart Parking Platform v5"
    app_version: str = "5.8.0"
    environment: str = Field(default="production", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_workers: int = Field(default=4, env="API_WORKERS")

    # Database
    database_url: PostgresDsn = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(default=20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, env="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, env="DATABASE_POOL_TIMEOUT")
    database_pool_recycle: int = Field(default=3600, env="DATABASE_POOL_RECYCLE")

    # Redis
    redis_url: RedisDsn = Field(default="redis://parking-redis:6379/0", env="REDIS_URL")
    redis_ttl_seconds: int = Field(default=86400, env="REDIS_TTL_SECONDS")

    # ChirpStack
    chirpstack_api_url: str = Field(..., env="CHIRPSTACK_API_URL")
    chirpstack_api_token: str = Field(..., env="CHIRPSTACK_API_TOKEN")

    # Background Tasks
    scheduler_enabled: bool = Field(default=True, env="SCHEDULER_ENABLED")
    reconciliation_interval_minutes: int = Field(default=10, env="RECONCILIATION_INTERVAL_MINUTES")

    # Multi-Tenancy
    require_api_key: bool = Field(default=True, env="REQUIRE_API_KEY")
    default_tenant_id: Optional[str] = Field(default=None, env="DEFAULT_TENANT_ID")

    # Security
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=100, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, env="RATE_LIMIT_PER_HOUR")

    # Monitoring
    prometheus_enabled: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Usage throughout application:
# from src.config import get_settings
# settings = get_settings()
# db_url = settings.database_url
```

**Success Criteria:**
- [ ] All configuration centralized
- [ ] Environment variables validated
- [ ] Easy to override for testing

---

### 3.2 Request Tracing with Context ✅ Priority: MEDIUM
**Duration:** 2 days

#### Add to `src/middleware.py`:

```python
"""
Request tracing and context propagation
"""
import uuid
import time
from contextvars import ContextVar
from fastapi import Request
import structlog

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")

logger = structlog.get_logger()


@app.middleware("http")
async def request_tracing_middleware(request: Request, call_next):
    """Add request ID and timing to all requests"""

    # Generate or extract request ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_var.set(request_id)

    # Bind to structlog context
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path
    )

    start_time = time.time()

    logger.info("request_started",
        client_host=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )

    # Process request
    response = await call_next(request)

    # Add timing
    duration_ms = (time.time() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

    logger.info("request_completed",
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2)
    )

    # Clear context
    structlog.contextvars.unbind_contextvars("request_id", "method", "path")

    return response
```

**Success Criteria:**
- [ ] Every request has unique ID
- [ ] Request ID in all log entries
- [ ] Response time headers added

---

## Phase 4: Production Hardening (Week 6)
**Goal:** Security, resilience, and deployment best practices

### 4.1 Rate Limiting per Tenant ✅ Priority: HIGH
**Duration:** 2 days

#### Create `src/rate_limiter.py`:

```python
"""
Tenant-aware rate limiting using Redis
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi import Request
import redis.asyncio as redis

redis_client = redis.from_url(os.getenv("REDIS_URL"))


def get_tenant_id(request: Request) -> str:
    """Extract tenant ID for rate limiting"""
    # From authenticated context
    if hasattr(request.state, "tenant_id"):
        return request.state.tenant_id

    # From API key (set by auth middleware)
    return request.headers.get("X-Tenant-ID", "anonymous")


limiter = Limiter(
    key_func=get_tenant_id,
    default_limits=["100/minute", "1000/hour"],
    storage_uri=os.getenv("REDIS_URL")
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Usage in routes:
@router.post("/spaces")
@limiter.limit("10/minute")  # Override for write operations
async def create_space(
    space: SpaceCreate,
    request: Request
):
    pass
```

**Success Criteria:**
- [ ] Rate limits enforced per tenant
- [ ] 429 responses for exceeded limits
- [ ] Different limits for read vs write

---

### 4.2 Docker Secrets Management ✅ Priority: MEDIUM
**Duration:** 1 day

#### Update `docker-compose.yml`:

```yaml
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  postgres_app_password:
    file: ./secrets/postgres_app_password.txt
  chirpstack_api_token:
    file: ./secrets/chirpstack_api_token.txt
  jwt_secret_key:
    file: ./secrets/jwt_secret_key.txt

services:
  api:
    secrets:
      - postgres_app_password
      - chirpstack_api_token
      - jwt_secret_key
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_app_password
      CHIRPSTACK_API_TOKEN_FILE: /run/secrets/chirpstack_api_token
      JWT_SECRET_KEY_FILE: /run/secrets/jwt_secret_key
```

#### Create `src/secrets.py`:

```python
"""
Docker secrets loader
"""
from pathlib import Path
from typing import Optional


def load_secret(secret_name: str, default: Optional[str] = None) -> str:
    """Load secret from Docker secrets or environment variable"""

    # Try Docker secrets first
    secret_path = Path(f"/run/secrets/{secret_name}")
    if secret_path.exists():
        return secret_path.read_text().strip()

    # Try environment variable with _FILE suffix
    env_file_var = f"{secret_name.upper()}_FILE"
    env_file_path = os.getenv(env_file_var)
    if env_file_path:
        return Path(env_file_path).read_text().strip()

    # Fallback to direct environment variable
    env_value = os.getenv(secret_name.upper())
    if env_value:
        return env_value

    # Use default if provided
    if default is not None:
        return default

    raise ValueError(f"Secret '{secret_name}' not found")


# Usage in config.py:
jwt_secret_key: str = Field(default_factory=lambda: load_secret("jwt_secret_key"))
```

**Success Criteria:**
- [ ] No secrets in .env files
- [ ] Secrets loaded from files
- [ ] Backward compatible with env vars

---

### 4.3 Deployment Automation ✅ Priority: MEDIUM
**Duration:** 2 days

#### Create `scripts/deploy.sh`:

```bash
#!/bin/bash
# Zero-downtime deployment script with health checks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== Smart Parking Platform Deployment ==="
echo "Version: $(git describe --tags --always)"
echo "Branch: $(git rev-parse --abbrev-ref HEAD)"
echo ""

# Pre-deployment checks
echo "1. Running pre-deployment checks..."
docker compose config > /dev/null || exit 1
echo "   ✓ Docker Compose configuration valid"

# Database backup
echo "2. Backing up database..."
./scripts/backup-database.sh
echo "   ✓ Database backup complete"

# Pull latest images
echo "3. Pulling latest images..."
docker compose pull
echo "   ✓ Images updated"

# Run database migrations
echo "4. Running database migrations..."
docker compose run --rm api python -m scripts.run_migrations
echo "   ✓ Migrations complete"

# Rolling update of services
echo "5. Updating services..."

SERVICES=("api" "contact-api" "device-manager-ui" "website")

for service in "${SERVICES[@]}"; do
    echo "   Updating $service..."

    # Start new container
    docker compose up -d --no-deps --scale $service=2 $service

    # Wait for health check
    for i in {1..30}; do
        if docker compose ps $service | grep -q "healthy"; then
            echo "   ✓ $service is healthy"
            break
        fi
        sleep 2
    done

    # Remove old container
    docker compose up -d --no-deps --scale $service=1 $service

    sleep 5
done

echo "6. Cleaning up old images..."
docker image prune -f

echo ""
echo "=== Deployment Complete ==="
echo "Services running:"
docker compose ps
```

**Success Criteria:**
- [ ] Zero-downtime deployments
- [ ] Automated health checks
- [ ] Rollback on failure

---

## Testing Strategy

### Unit Tests
```bash
# Run unit tests
pytest tests/unit -v --cov=src --cov-report=html
```

### Integration Tests
```bash
# Run integration tests
pytest tests/integration -v
```

### Performance Tests
```bash
# Run load tests
locust -f tests/performance/locustfile.py --host=http://localhost
```

---

## Rollout Schedule

| Week | Phase | Focus | Risk |
|------|-------|-------|------|
| 1 | Phase 1.1-1.3 | Documentation, Indexes, Health Checks | LOW |
| 2 | Phase 1.4-1.5 | Resource Limits, Logging | LOW |
| 3 | Phase 2.1-2.2 | Caching, Query Optimization | MEDIUM |
| 4 | Phase 2.3 | Materialized Views | MEDIUM |
| 5 | Phase 3.1-3.2 | Configuration, Tracing | LOW |
| 6 | Phase 4.1-4.3 | Rate Limiting, Secrets, Deployment | MEDIUM |

---

## Success Metrics

### Performance
- [ ] API response time P95 < 200ms (currently ~500ms)
- [ ] Database query time P95 < 50ms
- [ ] Cache hit rate > 70%

### Reliability
- [ ] Uptime > 99.9%
- [ ] Error rate < 0.1%
- [ ] Zero-downtime deployments

### Observability
- [ ] 100% of requests have trace IDs
- [ ] All errors logged with context
- [ ] Grafana dashboards for all services

---

## Dependencies

### New Python Packages
```txt
# Add to requirements.txt
structlog==24.1.0
python-json-logger==2.0.7
slowapi==0.1.9
redis[hiredis]==5.0.1
sentry-sdk[fastapi]==1.40.0
prometheus-client==0.19.0
```

### Infrastructure
- Redis (already deployed)
- Prometheus (optional, Phase 3)
- Grafana (optional, Phase 3)

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Database migration failure | HIGH | Test on staging, backup before migration |
| Cache inconsistency | MEDIUM | Short TTLs, pattern-based invalidation |
| Resource limit too low | MEDIUM | Monitor metrics, adjust incrementally |
| Rate limiting too strict | MEDIUM | Start with high limits, decrease gradually |

---

## Next Steps

1. **Review this plan** with team
2. **Set up staging environment** for testing
3. **Begin Phase 1** with documentation cleanup
4. **Weekly checkpoint meetings** to track progress

---

**Document Version:** 1.0
**Last Updated:** 2025-10-22
**Author:** Smart Parking Platform Team
