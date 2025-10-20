"""
Prometheus Metrics for Smart Parking Platform v5.3

Implements comprehensive observability as per docs/v5.3-06-observability-ops.md

Metrics Categories:
- Ingest: uplink processing, deduplication, orphans
- Reservations: attempts, conflicts, active count
- Downlinks: queue depth, latency, success/failure rates
- Tenancy: per-tenant rate limiting
- Infrastructure: DB/Redis latency
"""
import time
from typing import Optional
from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)

# Create custom registry (allows multiple instances for testing)
registry = CollectorRegistry()

# ============================================================
# Ingest Metrics
# ============================================================

uplink_requests_total = Counter(
    'uplink_requests_total',
    'Total uplink webhook requests received',
    ['status', 'tenant_id'],
    registry=registry
)

uplink_processing_duration_seconds = Histogram(
    'uplink_processing_duration_seconds',
    'Uplink processing duration in seconds',
    ['status'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry
)

uplink_duplicates_total = Counter(
    'uplink_duplicates_total',
    'Total duplicate uplinks detected (fcnt deduplication)',
    ['tenant_id'],
    registry=registry
)

uplink_orphans_total = Counter(
    'uplink_orphans_total',
    'Total orphan device uplinks (device not assigned to space)',
    [],
    registry=registry
)

orphan_devices_gauge = Gauge(
    'orphan_devices_gauge',
    'Current number of orphan devices tracked',
    [],
    registry=registry
)

webhook_signature_failures_total = Counter(
    'webhook_signature_failures_total',
    'Total webhook signature validation failures',
    ['tenant_id'],
    registry=registry
)

webhook_spooled_total = Counter(
    'webhook_spooled_total',
    'Total webhooks spooled to disk due to database unavailability',
    [],
    registry=registry
)

# ============================================================
# Reservation Metrics
# ============================================================

reservation_attempts_total = Counter(
    'reservation_attempts_total',
    'Total reservation creation attempts',
    ['status', 'tenant_id'],
    registry=registry
)

reservation_conflicts_total = Counter(
    'reservation_conflicts_total',
    'Total reservation conflicts (409 errors)',
    ['tenant_id'],
    registry=registry
)

reservation_active_gauge = Gauge(
    'reservation_active_gauge',
    'Current number of active reservations',
    ['tenant_id', 'status'],
    registry=registry
)

reservation_processing_duration_seconds = Histogram(
    'reservation_processing_duration_seconds',
    'Reservation processing duration',
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=registry
)

# ============================================================
# Downlink Metrics
# ============================================================

downlink_queue_depth = Gauge(
    'downlink_queue_depth',
    'Current depth of downlink queue',
    ['queue_type'],  # pending, dead_letter
    registry=registry
)

downlink_enqueued_total = Counter(
    'downlink_enqueued_total',
    'Total downlinks enqueued',
    ['tenant_id'],
    registry=registry
)

downlink_sent_total = Counter(
    'downlink_sent_total',
    'Total downlinks sent successfully',
    ['tenant_id'],
    registry=registry
)

downlink_failed_total = Counter(
    'downlink_failed_total',
    'Total downlink failures',
    ['tenant_id', 'reason'],
    registry=registry
)

downlink_dead_letter_total = Counter(
    'downlink_dead_letter_total',
    'Total downlinks moved to dead-letter queue',
    ['tenant_id'],
    registry=registry
)

downlink_deduplicated_total = Counter(
    'downlink_deduplicated_total',
    'Total downlinks deduplicated (content hash match)',
    ['tenant_id'],
    registry=registry
)

downlink_coalesced_total = Counter(
    'downlink_coalesced_total',
    'Total downlinks coalesced (replaced pending command)',
    ['tenant_id'],
    registry=registry
)

downlink_latency_seconds = Histogram(
    'downlink_latency_seconds',
    'Downlink processing latency (enqueue to send)',
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry
)

downlink_rate_limited_total = Counter(
    'downlink_rate_limited_total',
    'Total downlinks rate limited',
    ['limit_type', 'tenant_id'],  # gateway, tenant
    registry=registry
)

# ============================================================
# Tenancy & Rate Limiting Metrics
# ============================================================

rate_limit_rejections_total = Counter(
    'rate_limit_rejections_total',
    'Total API requests rejected by rate limiter',
    ['tenant_id', 'endpoint'],
    registry=registry
)

api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code', 'tenant_id'],
    registry=registry
)

api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'API request duration',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry
)

# ============================================================
# Infrastructure Metrics
# ============================================================

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation'],  # select, insert, update, delete
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=registry
)

db_connection_pool_size = Gauge(
    'db_connection_pool_size',
    'Database connection pool size',
    ['state'],  # idle, active, total
    registry=registry
)

redis_command_duration_seconds = Histogram(
    'redis_command_duration_seconds',
    'Redis command duration',
    ['command'],  # get, set, incr, etc
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25),
    registry=registry
)

redis_connection_errors_total = Counter(
    'redis_connection_errors_total',
    'Total Redis connection errors',
    [],
    registry=registry
)

chirpstack_api_duration_seconds = Histogram(
    'chirpstack_api_duration_seconds',
    'ChirpStack API call duration',
    ['operation'],  # queue_downlink, get_device, etc
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry
)

chirpstack_api_errors_total = Counter(
    'chirpstack_api_errors_total',
    'Total ChirpStack API errors',
    ['operation', 'error_type'],
    registry=registry
)

# ============================================================
# State Machine Metrics
# ============================================================

space_state_transitions_total = Counter(
    'space_state_transitions_total',
    'Total space state transitions',
    ['from_state', 'to_state', 'trigger', 'tenant_id'],
    registry=registry
)

display_updates_total = Counter(
    'display_updates_total',
    'Total display updates sent',
    ['display_type', 'state', 'tenant_id'],
    registry=registry
)

state_machine_errors_total = Counter(
    'state_machine_errors_total',
    'Total state machine errors',
    ['error_type', 'tenant_id'],
    registry=registry
)

# ============================================================
# Business Metrics (SLOs)
# ============================================================

actuation_latency_seconds = Histogram(
    'actuation_latency_seconds',
    'End-to-end actuation latency (sensor uplink to display update)',
    ['tenant_id'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=registry
)

# ============================================================
# Helper Functions
# ============================================================

class MetricsTimer:
    """Context manager for timing operations"""

    def __init__(self, histogram, labels: Optional[dict] = None):
        self.histogram = histogram
        self.labels = labels or {}
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if self.labels:
            self.histogram.labels(**self.labels).observe(duration)
        else:
            self.histogram.observe(duration)


def track_uplink(status: str, tenant_id: str = "unknown"):
    """Track uplink request"""
    uplink_requests_total.labels(status=status, tenant_id=tenant_id).inc()


def track_uplink_duplicate(tenant_id: str = "unknown"):
    """Track duplicate uplink"""
    uplink_duplicates_total.labels(tenant_id=tenant_id).inc()


def track_orphan_uplink():
    """Track orphan device uplink"""
    uplink_orphans_total.inc()


def track_reservation_attempt(status: str, tenant_id: str = "unknown"):
    """Track reservation creation attempt"""
    reservation_attempts_total.labels(status=status, tenant_id=tenant_id).inc()


def track_reservation_conflict(tenant_id: str = "unknown"):
    """Track reservation conflict"""
    reservation_conflicts_total.labels(tenant_id=tenant_id).inc()


def update_orphan_count(count: int):
    """Update orphan devices gauge"""
    orphan_devices_gauge.set(count)


def track_downlink_enqueue(tenant_id: str = "unknown"):
    """Track downlink enqueue"""
    downlink_enqueued_total.labels(tenant_id=tenant_id).inc()


def track_downlink_success(tenant_id: str = "unknown", latency_ms: Optional[float] = None):
    """Track successful downlink"""
    downlink_sent_total.labels(tenant_id=tenant_id).inc()
    if latency_ms is not None:
        downlink_latency_seconds.observe(latency_ms / 1000.0)


def track_downlink_failure(tenant_id: str = "unknown", reason: str = "unknown"):
    """Track downlink failure"""
    downlink_failed_total.labels(tenant_id=tenant_id, reason=reason).inc()


def track_downlink_dead_letter(tenant_id: str = "unknown"):
    """Track downlink moved to dead-letter queue"""
    downlink_dead_letter_total.labels(tenant_id=tenant_id).inc()


def update_downlink_queue_depth(pending: int, dead_letter: int):
    """Update downlink queue depth gauges"""
    downlink_queue_depth.labels(queue_type="pending").set(pending)
    downlink_queue_depth.labels(queue_type="dead_letter").set(dead_letter)


def track_rate_limit_rejection(tenant_id: str, endpoint: str):
    """Track rate limit rejection"""
    rate_limit_rejections_total.labels(tenant_id=tenant_id, endpoint=endpoint).inc()


def track_api_request(method: str, endpoint: str, status_code: int, tenant_id: str = "unknown", duration: Optional[float] = None):
    """Track API request"""
    api_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
        tenant_id=tenant_id
    ).inc()

    if duration is not None:
        api_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)


def track_state_transition(from_state: str, to_state: str, trigger: str, tenant_id: str = "unknown"):
    """Track space state transition"""
    space_state_transitions_total.labels(
        from_state=from_state,
        to_state=to_state,
        trigger=trigger,
        tenant_id=tenant_id
    ).inc()


def track_actuation_latency(latency_seconds: float, tenant_id: str = "unknown"):
    """Track end-to-end actuation latency"""
    actuation_latency_seconds.labels(tenant_id=tenant_id).observe(latency_seconds)


def get_metrics_text() -> bytes:
    """Get metrics in Prometheus text format"""
    return generate_latest(registry)


def get_metrics_content_type() -> str:
    """Get Prometheus content type"""
    return CONTENT_TYPE_LATEST
