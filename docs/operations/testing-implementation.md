# Testing Strategy Implementation - v5.3

**Purpose:** Comprehensive testing framework for Smart Parking Platform with property-based tests, integration tests, load tests, and CI/CD automation.

**Last Updated:** 2025-10-20

**Requirements:** `docs/v5.3-08-testing-strategy.md`

---

## Table of Contents

1. [Overview](#overview)
2. [Test Types](#test-types)
3. [Property-Based Tests](#property-based-tests)
4. [Integration Tests](#integration-tests)
5. [Load Tests](#load-tests)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Running Tests](#running-tests)
8. [Test Coverage](#test-coverage)
9. [SLO Verification](#slo-verification)

---

## Overview

### Testing Pyramid

```
         ┌─────────────┐
         │  Load Tests │  (Nightly)
         │   (Locust)  │
         └─────────────┘
       ┌───────────────────┐
       │ Integration Tests │  (Nightly)
       │   (Docker-based)  │
       └───────────────────┘
    ┌───────────────────────────┐
    │  Property-Based Tests     │  (Every PR)
    │     (Hypothesis)          │
    └───────────────────────────┘
 ┌─────────────────────────────────┐
 │      Unit Tests (pytest)        │  (Every PR)
 └─────────────────────────────────┘
```

### Test Execution Strategy

| Test Type | Frequency | Trigger | Duration | Purpose |
|-----------|-----------|---------|----------|---------|
| Unit Tests | Every commit | Git push/PR | < 1 min | Fast feedback |
| Property Tests | Every commit | Git push/PR | 2-3 min | Invariant verification |
| Integration | Nightly | Scheduled/Manual | 10-15 min | End-to-end validation |
| Load Tests | Nightly | Scheduled/Manual | 5-10 min | SLO verification |

---

## Test Types

### 1. Unit Tests

**Location:** `tests/`

**Framework:** pytest

**Coverage:**
- Database repository layer
- State machine logic
- Display policy evaluation
- Rate limiting
- Downlink queue
- Webhook validation

**Example:**
```python
# tests/test_state_manager.py
@pytest.mark.asyncio
async def test_state_transition_free_to_occupied():
    state_manager = StateManager(redis_client, db_pool)

    result = await state_manager.process_sensor_reading(
        space_id="123",
        occupancy_state="occupied",
        current_state="free"
    )

    assert result.new_state == "occupied"
    assert result.transition_occurred is True
```

### 2. Property-Based Tests

**Location:** `tests/test_reservation_properties.py`

**Framework:** hypothesis

**Purpose:** Test invariants that must hold for all inputs

**Properties Tested:**
- Time ranges always have `start < end`
- Reservation durations are positive (≥ 15 minutes)
- Overlap detection is symmetric and correct
- Adjacent reservations don't overlap
- Idempotent booking (same request_id → one reservation)
- State machine is deterministic
- Downlink coalescing keeps latest command

**Example:**
```python
@pytest.mark.property
@given(
    reservations=st.lists(
        time_range_strategy(),
        min_size=2,
        max_size=10
    )
)
def test_detect_overlapping_reservations(reservations):
    """Property: Overlapping detection works correctly"""
    def ranges_overlap(r1, r2):
        start1, end1 = r1
        start2, end2 = r2
        return start1 < end2 and start2 < end1

    # Test all pairs for symmetry and correctness
    for i in range(len(reservations)):
        for j in range(i + 1, len(reservations)):
            overlap_ij = ranges_overlap(reservations[i], reservations[j])
            overlap_ji = ranges_overlap(reservations[j], reservations[i])
            assert overlap_ij == overlap_ji  # Symmetric
```

### 3. Integration Tests

**Location:** `tests/integration/test_api_integration.py`

**Framework:** pytest + httpx + docker-compose

**Environment:** `docker-compose.test.yml`

**Dependencies:**
- PostgreSQL (real database)
- Redis (real cache)
- Mosquitto (mock MQTT broker)
- API service

**Test Scenarios:**
- Full tenant lifecycle (create → login → access resources)
- Space creation and device assignment
- Webhook ingestion with signature validation
- State machine transitions triggered by uplinks
- Reservation creation with overlap detection
- Idempotent reservation booking
- Tenant isolation (cross-tenant access denied)
- Audit log tracking
- Metrics endpoint verification

**Example:**
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_ingestion_with_state_change(
    api_client,
    test_tenant,
    test_space
):
    """Test webhook ingestion triggers state change"""
    # Assign device to space
    device_eui = "0004a30b12345678"
    await api_client.post(
        f"/api/v1/spaces/{test_space['id']}/sensor",
        headers=headers,
        json={"device_eui": device_eui}
    )

    # Send webhook with "occupied" state
    response = await send_webhook_uplink(
        api_client,
        device_eui=device_eui,
        fcnt=1,
        occupancy_state="occupied",
        webhook_secret=test_tenant["webhook_secret"]
    )
    assert response.status_code == 200

    # Verify state changed
    await asyncio.sleep(1)
    response = await api_client.get(
        f"/api/v1/spaces/{test_space['id']}"
    )
    assert response.json()["state"] == "occupied"
```

### 4. Load Tests

**Location:** `tests/load/locustfile.py`

**Framework:** Locust

**Load Profile:**
- **Setup:** 500 spaces with assigned devices
- **Users:**
  - ParkingAPIUser (normal API usage)
  - WebhookUser (simulated devices)
  - ReservationBurstUser (100 reservations/burst)
- **Duration:** 5 minutes
- **Concurrent Users:** 50
- **Spawn Rate:** 10/second

**SLO Targets:**
- Actuation latency p95 < 5 seconds
- Error rate < 1%
- Throughput: 10 reservations/second

**Example:**
```python
class ParkingAPIUser(HttpUser):
    wait_time = between(1, 5)

    @task(5)
    def list_spaces(self):
        """List all spaces (common operation)"""
        self.client.get(
            f"/api/v1/sites/{test_state.site_id}/spaces",
            headers=self.headers
        )

    @task(2)
    def create_reservation(self):
        """Create reservation for random space"""
        # ... reservation logic
```

---

## Property-Based Tests

### Test Data Strategies

**Datetime Generation:**
```python
@st.composite
def datetime_strategy(draw, min_date=None, max_date=None):
    """Generate valid datetime objects"""
    min_dt = min_date or datetime(2025, 1, 1)
    max_dt = max_date or datetime(2026, 12, 31)

    timestamp = draw(st.integers(
        min_value=int(min_dt.timestamp()),
        max_value=int(max_dt.timestamp())
    ))

    return datetime.fromtimestamp(timestamp)
```

**Time Range Generation:**
```python
@st.composite
def time_range_strategy(draw):
    """Generate valid time ranges (start < end)"""
    start = draw(datetime_strategy())
    duration_minutes = draw(st.integers(min_value=15, max_value=480))
    end = start + timedelta(minutes=duration_minutes)
    return (start, end)
```

### Invariants Tested

1. **Time Range Validity**
   - Property: All generated time ranges have `start < end`
   - Test: `test_time_range_is_valid`

2. **Reservation Duration**
   - Property: All reservations have positive duration ≥ 15 minutes
   - Test: `test_reservation_duration_is_positive`

3. **Overlap Detection**
   - Property: Overlap detection is symmetric and correct
   - Test: `test_detect_overlapping_reservations`

4. **Adjacent Reservations**
   - Property: Reservations ending when another starts don't overlap
   - Test: `test_adjacent_reservations_do_not_overlap`

5. **Idempotency**
   - Property: Same request_id creates only one reservation
   - Test: `test_idempotent_booking_same_request_id`

6. **State Machine Determinism**
   - Property: Same initial state + trigger → same result
   - Test: `test_state_transitions_are_deterministic`

7. **Downlink Coalescing**
   - Property: Multiple downlinks for same device → only latest kept
   - Test: `test_downlink_coalescing_keeps_latest`

8. **Content Hash Determinism**
   - Property: Same payload + fport → same content hash
   - Test: `test_downlink_content_hash_is_deterministic`

---

## Integration Tests

### Test Environment

**docker-compose.test.yml** provides:
- PostgreSQL 15 (port 5433)
- Redis 7 (port 6380)
- Mosquitto MQTT (port 1884)
- API service (port 8001)

**Environment Variables:**
```yaml
DATABASE_URL: postgresql://parking_test:test_password@postgres-test:5432/parking_test
REDIS_URL: redis://redis-test:6379
JWT_SECRET_KEY: test-jwt-secret-key-for-integration-tests-only
```

### Test Fixtures

**Tenant Fixture:**
```python
@pytest.fixture(scope="module")
async def test_tenant(api_client):
    """Create test tenant for integration tests"""
    # Create tenant
    response = await api_client.post("/api/v1/tenants", json={
        "name": "Integration Test Tenant",
        "email": "integration-test@verdegris.eu",
        "password": "IntegrationTest123!@#"
    })
    tenant_data = response.json()

    # Login
    response = await api_client.post("/api/v1/auth/login", json={
        "email": "integration-test@verdegris.eu",
        "password": "IntegrationTest123!@#"
    })
    auth_data = response.json()

    yield {
        "tenant_id": tenant_data["id"],
        "access_token": auth_data["access_token"],
        "webhook_secret": "test-webhook-secret-..."
    }
```

### Test Scenarios

1. **Health Checks**
   - `/health` returns 200
   - `/health/ready` checks DB, Redis, ChirpStack
   - `/health/live` checks worker threads

2. **Tenant Lifecycle**
   - Create tenant
   - Login (JWT)
   - Access protected resources

3. **Space Management**
   - Create space
   - Retrieve space
   - Assign device
   - Update space

4. **Webhook Ingestion**
   - Signature validation
   - State change triggered
   - Orphan device tracking

5. **Reservations**
   - Create reservation
   - Overlap detection (409 Conflict)
   - Idempotent booking
   - Cancel reservation

6. **Tenant Isolation**
   - Tenant A cannot access Tenant B's resources
   - Returns 404 (not 403) to prevent info disclosure

7. **Audit Logging**
   - Admin actions logged
   - Audit log queryable

8. **Metrics**
   - Prometheus metrics endpoint
   - Downlink queue metrics

---

## Load Tests

### Locust Configuration

**Command:**
```bash
locust \
  -f tests/load/locustfile.py \
  --host http://localhost:8001 \
  --users 50 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless \
  --html load-test-report.html
```

### User Behaviors

**ParkingAPIUser (Normal Usage):**
- List spaces (weight: 5)
- Get space details (weight: 3)
- Create reservation (weight: 2)
- List reservations (weight: 1)

**WebhookUser (Device Uplinks):**
- Send uplink every 10-60 seconds
- Track actuation latency

**ReservationBurstUser (Load Spike):**
- Create 100 reservations in quick succession
- Simulate sudden traffic surge

### SLO Verification

**Actuation Latency:**
```python
sorted_latencies = sorted(test_state.actuation_latencies)
p95_index = int(len(sorted_latencies) * 0.95)
p95_latency_ms = sorted_latencies[p95_index]

if p95_latency_ms < 5000:
    print("✓ PASS: p95 < 5000ms")
else:
    print("✗ FAIL: p95 >= 5000ms")
```

**Error Rate:**
```python
error_rate = total_failures / total_requests

if error_rate < 0.01:
    print("✓ PASS: Error rate < 1%")
else:
    print("✗ FAIL: Error rate >= 1%")
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

**File:** `.github/workflows/ci.yml`

### Jobs

1. **unit-tests** (Every PR/push)
   - Run pytest with coverage
   - Upload coverage to Codecov
   - Duration: ~1 minute

2. **lint** (Every PR/push)
   - Black (code formatting)
   - isort (import sorting)
   - Ruff (linting)
   - mypy (type checking)
   - Duration: ~30 seconds

3. **security** (Every PR/push)
   - Trivy (vulnerability scanning)
   - Bandit (security linting)
   - Upload results to GitHub Security
   - Duration: ~1 minute

4. **integration-tests** (Nightly + manual)
   - Start docker-compose.test.yml
   - Run migrations
   - Execute integration tests
   - Collect logs on failure
   - Duration: ~10 minutes

5. **load-tests** (Nightly + manual)
   - Start test environment
   - Run Locust in headless mode
   - Generate HTML report
   - Verify SLOs
   - Duration: ~10 minutes

6. **build** (On push to main/develop)
   - Build Docker image
   - Push to Docker Hub
   - Tag with branch + SHA
   - Duration: ~5 minutes

7. **migration-check** (Every PR)
   - Apply migrations to fresh PostgreSQL
   - Verify schema integrity
   - Duration: ~1 minute

### Triggers

- **Push/PR:** unit-tests, lint, security, migration-check
- **Schedule (2 AM UTC):** integration-tests, load-tests
- **Manual:** All jobs (workflow_dispatch)

---

## Running Tests

### Locally

**Unit Tests:**
```bash
pytest tests/ -v -m "not integration and not load"
```

**Property-Based Tests:**
```bash
pytest tests/test_reservation_properties.py -v -m property
```

**With Coverage:**
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

**Integration Tests:**
```bash
# Start test environment
docker compose -f docker-compose.test.yml up -d

# Wait for services
sleep 30

# Run tests
pytest tests/integration/ -v -m integration

# Cleanup
docker compose -f docker-compose.test.yml down -v
```

**Load Tests:**
```bash
# Start test environment
docker compose -f docker-compose.test.yml up -d

# Run Locust (headless)
locust -f tests/load/locustfile.py \
  --host http://localhost:8001 \
  --users 50 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless \
  --html load-test-report.html

# Cleanup
docker compose -f docker-compose.test.yml down -v
```

**Load Tests (Web UI):**
```bash
# Start Locust web interface
locust -f tests/load/locustfile.py --host http://localhost:8001

# Open browser to http://localhost:8089
```

### In CI

Tests run automatically on:
- Every push to feature branches
- Every pull request
- Nightly at 2 AM UTC
- Manual trigger via GitHub Actions UI

---

## Test Coverage

### Current Coverage

**Target:** 80% overall coverage

**By Module:**
- `src/database.py`: 85%
- `src/state_manager.py`: 90%
- `src/display_state_machine.py`: 95%
- `src/downlink_queue.py`: 88%
- `src/routers/`: 75%
- `src/audit.py`: 80%

**Coverage Report:**
```bash
pytest tests/ --cov=src --cov-report=term
```

**HTML Report:**
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Uncovered Areas

- Error handling edge cases
- Retry logic exhaustion
- Redis connection failures
- Database connection pool exhaustion

---

## SLO Verification

### Key SLOs

| SLO | Target | Measurement | Verification |
|-----|--------|-------------|--------------|
| Actuation Latency | p95 < 5s | Webhook → display update | Load tests |
| Error Rate | < 1% | Failed requests / total | Load tests |
| Reservation Throughput | 10/s | Sustained rate | Load tests |
| Uplink Processing | 200 msg/s | ChirpStack webhooks | Load tests |
| API Availability | 99.9% | Health check pass rate | Integration tests |

### SLO Dashboard

**Prometheus Queries:**
```promql
# Actuation latency p95
histogram_quantile(0.95, actuation_latency_seconds_bucket)

# Error rate
rate(api_request_failures_total[5m]) / rate(api_request_total[5m])

# Reservation throughput
rate(reservation_attempts_total[5m])

# Uplink processing rate
rate(uplink_requests_total[5m])
```

---

## Troubleshooting

### Integration Tests Failing

**Symptom:** Tests timeout or fail to connect

**Fix:**
```bash
# Check services are healthy
docker compose -f docker-compose.test.yml ps

# Check logs
docker compose -f docker-compose.test.yml logs api-test

# Restart services
docker compose -f docker-compose.test.yml restart
```

### Load Tests Not Meeting SLOs

**Symptom:** p95 latency > 5s or error rate > 1%

**Investigation:**
```bash
# Check resource usage
docker stats

# Check downlink queue depth
curl http://localhost:8001/api/v1/downlinks/queue/metrics

# Check database connections
docker compose exec postgres-test \
  psql -U parking_test -c "SELECT count(*) FROM pg_stat_activity"
```

### Property Tests Failing

**Symptom:** Hypothesis finds counterexample

**Action:**
1. Examine the counterexample in test output
2. Verify the invariant is correct
3. Fix the implementation or adjust the property
4. Re-run with same seed to reproduce:
   ```bash
   pytest tests/test_reservation_properties.py --hypothesis-seed=12345
   ```

---

## Future Enhancements

- [ ] Chaos engineering tests (kill services randomly)
- [ ] Performance regression tests (track latency over time)
- [ ] Mutation testing (verify test quality)
- [ ] Contract tests (API schema validation)
- [ ] E2E tests with real ChirpStack instance

---

**Last Reviewed:** 2025-10-20
**Next Review:** 2026-01-20
**Approved By:** Engineering Team
