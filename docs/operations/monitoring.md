6) Observability & Ops

Filename: docs/v5.3-06-observability-ops.md

Objective

Make the platform operable by a small team: clear health checks, actionable metrics, simple runbooks.

Recommendations
	•	Metrics (/metrics)
	•	Ingest: uplink_qps, uplink_duplicates, orphan_count
	•	Reservations: reserve_attempts_total, reserve_conflicts_total, reserve_active_gauge
	•	Downlinks: dl_queue_depth, dl_latency_ms, dl_success_total, dl_dead_letter_total
	•	Tenancy: per-tenant rate limit rejections
	•	DB/Redis latency histograms
	•	Health
	•	/health/ready: DB, Redis, MQTT, ChirpStack connectivity checks.
	•	/health/live: process heartbeat & worker thread checks.
	•	Logging
	•	JSON logs with tenant_id, site_id, space_id, request_id.
	•	Mask secrets; log at INFO by default, DEBUG behind header.
	•	Runbooks
	•	Common incidents: ChirpStack down; Redis full; Postgres failover; how to drain dead-letters; backup/restore steps.
	•	Backups
	•	Nightly Postgres dumps + WAL; retention 7/30 days; quarterly restore drill.

Reuse vs New
	•	Reuse (v4): health/ops notes & backup/restore procedures.
	•	New: Prometheus metrics, structured logging fields, ready/live endpoints.

Acceptance Criteria
	•	Dashboards show SLOs at a glance (<5s actuation p95, <1% DL failures).
	•	Pager alerts only on actionable conditions (not noise).

Risks & Mitigations
	•	Metric cardinality blow-up: limit per-device labels; aggregate per-site/tenant.
