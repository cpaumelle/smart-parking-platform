"""
Load Tests for Smart Parking Platform

Uses Locust to simulate realistic traffic patterns and verify SLOs.

SLO Targets (from v5.3-08-testing-strategy.md):
- Actuation latency p95 < 5 seconds (webhook → display update)
- Error rate < 1%
- 500 spaces per tenant
- 10 reservations/second burst handling

Run:
    locust -f tests/load/locustfile.py --host http://localhost:8000
"""
import time
import json
import random
import hmac
import hashlib
from datetime import datetime, timedelta
from uuid import uuid4
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# ============================================================
# Configuration
# ============================================================

# Test data
TENANT_EMAIL = "loadtest@verdegris.eu"
TENANT_PASSWORD = "LoadTest123!@#"
WEBHOOK_SECRET = "loadtest-webhook-secret-1234567890123456"

# SLO thresholds
ACTUATION_LATENCY_P95_THRESHOLD_MS = 5000  # 5 seconds
ERROR_RATE_THRESHOLD = 0.01  # 1%

# Test parameters
NUM_SPACES = 500
NUM_DEVICES = 500
RESERVATION_BURST_SIZE = 100


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


def generate_device_eui() -> str:
    """Generate random device EUI"""
    return f"0004a30b{uuid4().hex[:8]}"


def generate_webhook_payload(device_eui: str, fcnt: int, occupancy: str) -> dict:
    """Generate ChirpStack webhook payload"""
    return {
        "deviceInfo": {
            "devEui": device_eui,
            "deviceName": f"sensor-{device_eui[-8:]}"
        },
        "fCnt": fcnt,
        "data": {
            "occupancy": occupancy,
            "battery": round(random.uniform(3.0, 4.2), 2)
        },
        "rxInfo": [{
            "rssi": random.randint(-120, -60),
            "snr": round(random.uniform(-5, 15), 1),
            "gatewayId": "test-gateway-001"
        }]
    }


# ============================================================
# Global Test State
# ============================================================

class TestState:
    """Shared state across all locust users"""
    tenant_id = None
    access_token = None
    site_id = None
    spaces = []  # List of {id, code, device_eui}
    actuation_latencies = []  # Track end-to-end latency


test_state = TestState()


# ============================================================
# Locust Test Setup
# ============================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Setup phase: Create tenant, site, and 500 spaces with devices

    Only runs once at the start of the test
    """
    if not isinstance(environment.runner, MasterRunner):
        print("=== Load Test Setup ===")

        # Use a single client for setup
        import requests
        base_url = environment.host

        # 1. Create tenant
        print(f"Creating tenant: {TENANT_EMAIL}")
        response = requests.post(f"{base_url}/api/v1/tenants", json={
            "name": "Load Test Tenant",
            "email": TENANT_EMAIL,
            "password": TENANT_PASSWORD
        })

        if response.status_code == 201:
            tenant = response.json()
            test_state.tenant_id = tenant["id"]
            print(f"✓ Tenant created: {test_state.tenant_id}")
        elif response.status_code == 409:
            # Tenant already exists, login
            print("Tenant already exists, logging in...")
        else:
            print(f"✗ Failed to create tenant: {response.status_code} - {response.text}")
            return

        # 2. Login
        print("Logging in...")
        response = requests.post(f"{base_url}/api/v1/auth/login", json={
            "email": TENANT_EMAIL,
            "password": TENANT_PASSWORD
        })

        if response.status_code == 200:
            auth = response.json()
            test_state.access_token = auth["access_token"]
            if not test_state.tenant_id:
                test_state.tenant_id = auth.get("tenant_id")
            print(f"✓ Logged in successfully")
        else:
            print(f"✗ Login failed: {response.status_code}")
            return

        headers = {"Authorization": f"Bearer {test_state.access_token}"}

        # 3. Create site
        print("Creating test site...")
        response = requests.post(
            f"{base_url}/api/v1/tenants/{test_state.tenant_id}/sites",
            headers=headers,
            json={
                "name": "Load Test Site",
                "address": "Load Test Street",
                "timezone": "UTC"
            }
        )

        if response.status_code == 201:
            site = response.json()
            test_state.site_id = site["id"]
            print(f"✓ Site created: {test_state.site_id}")
        else:
            print(f"✗ Failed to create site: {response.status_code}")
            return

        # 4. Create 500 spaces with devices
        print(f"Creating {NUM_SPACES} spaces with devices...")
        for i in range(NUM_SPACES):
            space_code = f"LOAD-{i:04d}"
            device_eui = generate_device_eui()

            # Create space
            response = requests.post(
                f"{base_url}/api/v1/sites/{test_state.site_id}/spaces",
                headers=headers,
                json={
                    "code": space_code,
                    "name": f"Load Test Space {i}",
                    "space_type": "standard"
                }
            )

            if response.status_code == 201:
                space = response.json()
                space_id = space["id"]

                # Assign device
                response = requests.post(
                    f"{base_url}/api/v1/spaces/{space_id}/sensor",
                    headers=headers,
                    json={"device_eui": device_eui}
                )

                if response.status_code == 200:
                    test_state.spaces.append({
                        "id": space_id,
                        "code": space_code,
                        "device_eui": device_eui,
                        "fcnt": 0  # Track frame counter
                    })

                    if (i + 1) % 50 == 0:
                        print(f"  Created {i + 1}/{NUM_SPACES} spaces...")

        print(f"✓ Created {len(test_state.spaces)} spaces with devices")
        print("=== Setup Complete ===\n")


# ============================================================
# Locust User Behaviors
# ============================================================

class ParkingAPIUser(HttpUser):
    """
    Simulates realistic user behavior:
    - List spaces
    - Create reservations
    - Cancel reservations
    - Check space status
    """
    wait_time = between(1, 5)  # Wait 1-5 seconds between requests

    def on_start(self):
        """Called when user starts"""
        # Use shared access token from setup
        self.headers = {"Authorization": f"Bearer {test_state.access_token}"}

    @task(5)
    def list_spaces(self):
        """List all spaces (common operation)"""
        self.client.get(
            f"/api/v1/sites/{test_state.site_id}/spaces",
            headers=self.headers,
            name="/api/v1/sites/[site_id]/spaces"
        )

    @task(3)
    def get_space_details(self):
        """Get details of a random space"""
        if test_state.spaces:
            space = random.choice(test_state.spaces)
            self.client.get(
                f"/api/v1/spaces/{space['id']}",
                headers=self.headers,
                name="/api/v1/spaces/[space_id]"
            )

    @task(2)
    def create_reservation(self):
        """Create a reservation for a random space"""
        if test_state.spaces:
            space = random.choice(test_state.spaces)

            # Reserve 1-2 hours in the future
            now = datetime.utcnow()
            start = now + timedelta(hours=random.uniform(1, 8))
            end = start + timedelta(hours=random.uniform(1, 4))

            self.client.post(
                "/api/v1/reservations",
                headers=self.headers,
                json={
                    "space_id": space["id"],
                    "reserved_from": start.isoformat(),
                    "reserved_until": end.isoformat(),
                    "user_email": TENANT_EMAIL,
                    "request_id": str(uuid4())
                },
                name="/api/v1/reservations"
            )

    @task(1)
    def list_reservations(self):
        """List all reservations"""
        self.client.get(
            "/api/v1/reservations",
            headers=self.headers,
            name="/api/v1/reservations"
        )


class WebhookUser(HttpUser):
    """
    Simulates LoRaWAN devices sending uplinks via ChirpStack webhooks
    """
    wait_time = between(10, 60)  # Devices send uplinks every 10-60 seconds

    @task
    def send_uplink(self):
        """Send random uplink from a device"""
        if test_state.spaces:
            space = random.choice(test_state.spaces)

            # Increment frame counter
            space["fcnt"] += 1

            # Random occupancy state
            occupancy = random.choice(["free", "occupied"])

            # Generate webhook payload
            payload_dict = generate_webhook_payload(
                space["device_eui"],
                space["fcnt"],
                occupancy
            )

            payload_bytes = json.dumps(payload_dict).encode()
            signature = generate_webhook_signature(payload_bytes, WEBHOOK_SECRET)

            headers = {
                "X-Chirpstack-Signature": signature,
                "Content-Type": "application/json"
            }

            # Track start time for actuation latency
            start_time = time.time()

            response = self.client.post(
                "/webhooks/uplink",
                headers=headers,
                data=payload_bytes,
                name="/webhooks/uplink"
            )

            # Track actuation latency (webhook to API response)
            if response.status_code == 200:
                latency_ms = (time.time() - start_time) * 1000
                test_state.actuation_latencies.append(latency_ms)


class ReservationBurstUser(HttpUser):
    """
    Simulates burst of 100 reservations in quick succession

    Tests the system's ability to handle sudden load spikes
    """
    wait_time = between(60, 300)  # Burst every 1-5 minutes

    def on_start(self):
        self.headers = {"Authorization": f"Bearer {test_state.access_token}"}

    @task
    def reservation_burst(self):
        """Create 100 reservations as fast as possible"""
        print(f"\n=== Starting reservation burst: {RESERVATION_BURST_SIZE} requests ===")

        start_time = time.time()
        success_count = 0
        conflict_count = 0
        error_count = 0

        for i in range(RESERVATION_BURST_SIZE):
            if test_state.spaces:
                space = random.choice(test_state.spaces)

                # Stagger reservation times to avoid all conflicts
                now = datetime.utcnow()
                start = now + timedelta(hours=10 + (i * 0.1))
                end = start + timedelta(hours=1)

                response = self.client.post(
                    "/api/v1/reservations",
                    headers=self.headers,
                    json={
                        "space_id": space["id"],
                        "reserved_from": start.isoformat(),
                        "reserved_until": end.isoformat(),
                        "user_email": TENANT_EMAIL,
                        "request_id": str(uuid4())
                    },
                    name="/api/v1/reservations (burst)"
                )

                if response.status_code == 201:
                    success_count += 1
                elif response.status_code == 409:
                    conflict_count += 1
                else:
                    error_count += 1

        elapsed_ms = (time.time() - start_time) * 1000
        rps = RESERVATION_BURST_SIZE / (elapsed_ms / 1000)

        print(f"Burst complete:")
        print(f"  Time: {elapsed_ms:.0f}ms ({rps:.1f} req/s)")
        print(f"  Success: {success_count}")
        print(f"  Conflicts: {conflict_count}")
        print(f"  Errors: {error_count}\n")


# ============================================================
# SLO Verification
# ============================================================

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Verify SLOs at end of test

    Checks:
    - Actuation latency p95 < 5s
    - Error rate < 1%
    """
    if not isinstance(environment.runner, MasterRunner):
        print("\n=== SLO Verification ===")

        # 1. Calculate actuation latency p95
        if test_state.actuation_latencies:
            sorted_latencies = sorted(test_state.actuation_latencies)
            p95_index = int(len(sorted_latencies) * 0.95)
            p95_latency_ms = sorted_latencies[p95_index]

            print(f"Actuation Latency p95: {p95_latency_ms:.0f}ms")

            if p95_latency_ms < ACTUATION_LATENCY_P95_THRESHOLD_MS:
                print(f"✓ PASS: p95 < {ACTUATION_LATENCY_P95_THRESHOLD_MS}ms")
            else:
                print(f"✗ FAIL: p95 >= {ACTUATION_LATENCY_P95_THRESHOLD_MS}ms")

        # 2. Calculate error rate
        stats = environment.stats
        total_requests = stats.total.num_requests
        total_failures = stats.total.num_failures

        if total_requests > 0:
            error_rate = total_failures / total_requests
            print(f"\nError Rate: {error_rate * 100:.2f}%")

            if error_rate < ERROR_RATE_THRESHOLD:
                print(f"✓ PASS: Error rate < {ERROR_RATE_THRESHOLD * 100}%")
            else:
                print(f"✗ FAIL: Error rate >= {ERROR_RATE_THRESHOLD * 100}%")

        print("\n=== Load Test Complete ===")
