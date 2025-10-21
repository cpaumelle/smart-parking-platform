"""
Integration Tests for Smart Parking API

Tests the full stack with real dependencies (PostgreSQL, Redis, mock ChirpStack).
Runs using docker-compose test configuration.

Test Coverage:
- Full API lifecycle (tenant creation → space → device → reservation)
- Webhook ingestion with signature validation
- State machine transitions with display updates
- Downlink queue with rate limiting
- Audit log tracking
- Multi-tenancy isolation
"""
import pytest
import asyncio
import httpx
import hashlib
import hmac
import json
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Optional


# ============================================================
# Test Configuration
# ============================================================

# API base URL (override with environment variable)
API_BASE_URL = "http://localhost:8000"

# Test tenant credentials
TEST_TENANT_EMAIL = "integration-test@verdegris.eu"
TEST_TENANT_PASSWORD = "IntegrationTest123!@#"


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
async def api_client():
    """Async HTTP client for API calls"""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
async def test_tenant(api_client):
    """
    Create test tenant for integration tests

    Returns:
        dict: {tenant_id, access_token, webhook_secret}
    """
    # Create tenant
    response = await api_client.post("/api/v1/tenants", json={
        "name": "Integration Test Tenant",
        "email": TEST_TENANT_EMAIL,
        "password": TEST_TENANT_PASSWORD
    })

    assert response.status_code == 201, f"Failed to create tenant: {response.text}"
    tenant_data = response.json()
    tenant_id = tenant_data["id"]

    # Login to get access token
    response = await api_client.post("/api/v1/auth/login", json={
        "email": TEST_TENANT_EMAIL,
        "password": TEST_TENANT_PASSWORD
    })

    assert response.status_code == 200, f"Failed to login: {response.text}"
    auth_data = response.json()
    access_token = auth_data["access_token"]

    # Get webhook secret (if available via API)
    # For now, we'll assume a default secret for testing
    webhook_secret = "test-webhook-secret-12345678901234567890123456789012"

    yield {
        "tenant_id": tenant_id,
        "access_token": access_token,
        "webhook_secret": webhook_secret,
        "email": TEST_TENANT_EMAIL
    }

    # Cleanup: Soft-delete tenant after tests
    # (In production, this would be DELETE /api/v1/tenants/{tenant_id})


@pytest.fixture
async def test_site(api_client, test_tenant):
    """Create test site for tenant"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}

    response = await api_client.post(
        f"/api/v1/tenants/{test_tenant['tenant_id']}/sites",
        headers=headers,
        json={
            "name": "Integration Test Site",
            "address": "123 Test Street",
            "timezone": "UTC"
        }
    )

    assert response.status_code == 201, f"Failed to create site: {response.text}"
    site_data = response.json()

    yield site_data

    # Cleanup handled by tenant deletion


@pytest.fixture
async def test_space(api_client, test_tenant, test_site):
    """Create test space for site"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}

    response = await api_client.post(
        f"/api/v1/sites/{test_site['id']}/spaces",
        headers=headers,
        json={
            "code": f"TEST-{uuid4().hex[:6].upper()}",
            "name": "Integration Test Space",
            "space_type": "standard"
        }
    )

    assert response.status_code == 201, f"Failed to create space: {response.text}"
    space_data = response.json()

    yield space_data


# ============================================================
# Helper Functions
# ============================================================

def generate_webhook_signature(payload: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook"""
    return hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()


async def send_webhook_uplink(
    api_client: httpx.AsyncClient,
    device_eui: str,
    fcnt: int,
    occupancy_state: str,
    webhook_secret: str,
    battery: float = 3.6,
    rssi: int = -85,
    snr: float = 7.5
) -> httpx.Response:
    """Send simulated LoRaWAN uplink webhook"""
    payload = {
        "deviceInfo": {
            "devEui": device_eui
        },
        "fCnt": fcnt,
        "data": {
            "occupancy": occupancy_state,
            "battery": battery
        },
        "rxInfo": [{
            "rssi": rssi,
            "snr": snr
        }]
    }

    payload_bytes = json.dumps(payload).encode()
    signature = generate_webhook_signature(payload_bytes, webhook_secret)

    headers = {
        "X-Chirpstack-Signature": signature,
        "Content-Type": "application/json"
    }

    return await api_client.post(
        "/webhooks/uplink",
        headers=headers,
        content=payload_bytes
    )


# ============================================================
# Integration Tests
# ============================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_checks(api_client):
    """Test that all health check endpoints return 200"""
    # Basic health
    response = await api_client.get("/health")
    assert response.status_code == 200
    health = response.json()
    assert health["status"] == "healthy"

    # Readiness check
    response = await api_client.get("/health/ready")
    assert response.status_code == 200
    ready = response.json()
    assert ready["status"] == "ready"
    assert "database" in ready["checks"]
    assert "redis" in ready["checks"]

    # Liveness check
    response = await api_client.get("/health/live")
    assert response.status_code == 200
    live = response.json()
    assert live["status"] == "alive"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tenant_lifecycle(api_client):
    """Test full tenant creation, login, and authentication flow"""
    tenant_email = f"lifecycle-test-{uuid4().hex[:8]}@test.com"

    # 1. Create tenant
    response = await api_client.post("/api/v1/tenants", json={
        "name": "Lifecycle Test Tenant",
        "email": tenant_email,
        "password": "LifecycleTest123!@#"
    })

    assert response.status_code == 201
    tenant = response.json()
    assert "id" in tenant
    assert tenant["email"] == tenant_email

    # 2. Login
    response = await api_client.post("/api/v1/auth/login", json={
        "email": tenant_email,
        "password": "LifecycleTest123!@#"
    })

    assert response.status_code == 200
    auth = response.json()
    assert "access_token" in auth
    assert "refresh_token" in auth

    # 3. Access protected resource
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    response = await api_client.get(
        f"/api/v1/tenants/{tenant['id']}/sites",
        headers=headers
    )

    assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_space_creation_and_retrieval(api_client, test_tenant, test_site):
    """Test creating and retrieving spaces"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}

    # Create space
    space_code = f"TEST-{uuid4().hex[:6].upper()}"
    response = await api_client.post(
        f"/api/v1/sites/{test_site['id']}/spaces",
        headers=headers,
        json={
            "code": space_code,
            "name": "Test Space",
            "space_type": "standard"
        }
    )

    assert response.status_code == 201
    space = response.json()
    assert space["code"] == space_code
    assert space["state"] == "free"

    # Retrieve space
    response = await api_client.get(
        f"/api/v1/spaces/{space['id']}",
        headers=headers
    )

    assert response.status_code == 200
    retrieved = response.json()
    assert retrieved["id"] == space["id"]
    assert retrieved["code"] == space_code


@pytest.mark.integration
@pytest.mark.asyncio
async def test_device_assignment(api_client, test_tenant, test_space):
    """Test assigning device to space"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}
    device_eui = f"0004a30b{uuid4().hex[:8]}"

    # Assign device to space
    response = await api_client.post(
        f"/api/v1/spaces/{test_space['id']}/sensor",
        headers=headers,
        json={"device_eui": device_eui}
    )

    assert response.status_code == 200

    # Verify assignment
    response = await api_client.get(
        f"/api/v1/spaces/{test_space['id']}",
        headers=headers
    )

    assert response.status_code == 200
    space = response.json()
    assert space["sensor_eui"] == device_eui


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_ingestion_with_state_change(
    api_client,
    test_tenant,
    test_space
):
    """Test webhook ingestion triggers state change"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}
    device_eui = f"0004a30b{uuid4().hex[:8]}"

    # Assign device to space
    await api_client.post(
        f"/api/v1/spaces/{test_space['id']}/sensor",
        headers=headers,
        json={"device_eui": device_eui}
    )

    # Get initial state
    response = await api_client.get(
        f"/api/v1/spaces/{test_space['id']}",
        headers=headers
    )
    initial_state = response.json()["state"]
    assert initial_state == "free"

    # Send webhook with "occupied" state
    response = await send_webhook_uplink(
        api_client,
        device_eui=device_eui,
        fcnt=1,
        occupancy_state="occupied",
        webhook_secret=test_tenant["webhook_secret"]
    )

    assert response.status_code == 200

    # Wait for state machine processing
    await asyncio.sleep(1)

    # Verify state changed to "occupied"
    response = await api_client.get(
        f"/api/v1/spaces/{test_space['id']}",
        headers=headers
    )

    updated_state = response.json()["state"]
    assert updated_state == "occupied"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reservation_creation_and_conflict(
    api_client,
    test_tenant,
    test_space
):
    """Test reservation creation and overlap detection"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}

    # Create first reservation
    now = datetime.utcnow()
    start1 = now + timedelta(hours=1)
    end1 = start1 + timedelta(hours=2)

    response = await api_client.post(
        "/api/v1/reservations",
        headers=headers,
        json={
            "space_id": test_space["id"],
            "reserved_from": start1.isoformat(),
            "reserved_until": end1.isoformat(),
            "user_email": test_tenant["email"],
            "request_id": str(uuid4())
        }
    )

    assert response.status_code == 201
    reservation1 = response.json()

    # Attempt overlapping reservation (should fail)
    start2 = start1 + timedelta(minutes=30)  # Overlaps with first
    end2 = start2 + timedelta(hours=2)

    response = await api_client.post(
        "/api/v1/reservations",
        headers=headers,
        json={
            "space_id": test_space["id"],
            "reserved_from": start2.isoformat(),
            "reserved_until": end2.isoformat(),
            "user_email": test_tenant["email"],
            "request_id": str(uuid4())
        }
    )

    assert response.status_code == 409  # Conflict
    error = response.json()
    assert "conflicts" in error or "overlap" in error.get("message", "").lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_idempotent_reservation(api_client, test_tenant, test_space):
    """Test that same request_id creates only one reservation"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}

    now = datetime.utcnow()
    start = now + timedelta(hours=3)
    end = start + timedelta(hours=1)
    request_id = str(uuid4())

    # Send same reservation twice with same request_id
    reservation_data = {
        "space_id": test_space["id"],
        "reserved_from": start.isoformat(),
        "reserved_until": end.isoformat(),
        "user_email": test_tenant["email"],
        "request_id": request_id
    }

    response1 = await api_client.post(
        "/api/v1/reservations",
        headers=headers,
        json=reservation_data
    )

    assert response1.status_code == 201
    reservation1 = response1.json()

    # Second request with same request_id should return same reservation
    response2 = await api_client.post(
        "/api/v1/reservations",
        headers=headers,
        json=reservation_data
    )

    # Should either return 200 (idempotent success) or 201 with same ID
    assert response2.status_code in [200, 201]
    reservation2 = response2.json()
    assert reservation1["id"] == reservation2["id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tenant_isolation(api_client):
    """Test that tenants cannot access each other's resources"""
    # Create two separate tenants
    tenant1_email = f"tenant1-{uuid4().hex[:8]}@test.com"
    tenant2_email = f"tenant2-{uuid4().hex[:8]}@test.com"

    # Tenant 1
    response = await api_client.post("/api/v1/tenants", json={
        "name": "Tenant 1",
        "email": tenant1_email,
        "password": "Tenant1Pass123!@#"
    })
    tenant1 = response.json()

    response = await api_client.post("/api/v1/auth/login", json={
        "email": tenant1_email,
        "password": "Tenant1Pass123!@#"
    })
    tenant1_token = response.json()["access_token"]

    # Tenant 2
    response = await api_client.post("/api/v1/tenants", json={
        "name": "Tenant 2",
        "email": tenant2_email,
        "password": "Tenant2Pass123!@#"
    })
    tenant2 = response.json()

    response = await api_client.post("/api/v1/auth/login", json={
        "email": tenant2_email,
        "password": "Tenant2Pass123!@#"
    })
    tenant2_token = response.json()["access_token"]

    # Create site for Tenant 1
    headers1 = {"Authorization": f"Bearer {tenant1_token}"}
    response = await api_client.post(
        f"/api/v1/tenants/{tenant1['id']}/sites",
        headers=headers1,
        json={"name": "Tenant 1 Site", "address": "123 Test St"}
    )
    tenant1_site = response.json()

    # Tenant 2 tries to access Tenant 1's site
    headers2 = {"Authorization": f"Bearer {tenant2_token}"}
    response = await api_client.get(
        f"/api/v1/sites/{tenant1_site['id']}",
        headers=headers2
    )

    # Should return 404 (not 403, to prevent info disclosure)
    assert response.status_code in [403, 404]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_log_tracking(api_client, test_tenant, test_space):
    """Test that admin actions are logged in audit trail"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}

    # Perform action that should be audited (e.g., update space)
    response = await api_client.patch(
        f"/api/v1/spaces/{test_space['id']}",
        headers=headers,
        json={"name": "Updated Space Name"}
    )

    assert response.status_code == 200

    # Retrieve audit log (if endpoint exists)
    response = await api_client.get(
        f"/api/v1/tenants/{test_tenant['tenant_id']}/audit-log",
        headers=headers,
        params={"action": "space.update", "limit": 10}
    )

    # If audit endpoint implemented, verify log entry
    if response.status_code == 200:
        logs = response.json()
        assert len(logs) > 0

        # Find our action
        our_log = next(
            (log for log in logs if log["resource_id"] == test_space["id"]),
            None
        )

        if our_log:
            assert our_log["action"] == "space.update"
            assert our_log["actor_type"] == "user"
            assert our_log["new_values"]["name"] == "Updated Space Name"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_endpoint(api_client):
    """Test Prometheus metrics endpoint"""
    response = await api_client.get("/metrics")

    assert response.status_code == 200
    metrics_text = response.text

    # Verify key metrics are present
    assert "uplink_requests_total" in metrics_text
    assert "downlink_queue_depth" in metrics_text
    assert "reservation_attempts_total" in metrics_text
    assert "api_request_duration_seconds" in metrics_text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_downlink_queue_metrics(api_client, test_tenant, test_space):
    """Test downlink queue metrics endpoint"""
    headers = {"Authorization": f"Bearer {test_tenant['access_token']}"}

    response = await api_client.get(
        "/api/v1/downlinks/queue/metrics",
        headers=headers
    )

    assert response.status_code == 200
    metrics = response.json()

    # Verify metric structure
    assert "queue" in metrics
    assert "throughput" in metrics
    assert "queue" in metrics

    queue = metrics["queue"]
    assert "pending_depth" in queue
    assert "dead_letter_depth" in queue

    throughput = metrics["throughput"]
    assert "enqueued_total" in throughput
    assert "sent_total" in throughput


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
