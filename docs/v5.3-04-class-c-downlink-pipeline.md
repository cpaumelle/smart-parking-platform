4) Class-C Downlink Pipeline (Durable & Rate-Limited)

Filename: docs/v5.3-04-class-c-downlink-pipeline.md

Objective

Deliver display updates fast, exactly-once, and without overwhelming gateways/devices.

Recommendations
	•	Queue design (Redis)
	•	dl:pending (list) of command IDs.
	•	dl:cmd:{id} hash: payload, device_eui, tenant_id, content_hash, attempts, last_error.
	•	dl:last_hash:{device_eui} to dedupe identical successive commands.
	•	Dead-letter dl:dead list for failures after N attempts.
	•	Workers
	•	Pull from dl:pending, check last_hash; if same → skip.
	•	Publish via ChirpStack/MQTT; await ack or timeout → requeue with backoff.
	•	Rate limits
	•	Redis tokens per gateway and tenant (e.g., 30/min gateway, 10/min tenant default).
	•	Coalesce: if multiple enqueued for same device, keep latest only.
	•	Observability
	•	Metrics: queue depth, send latency, success %, dead-letters by tenant/device.

Reuse vs New
	•	Reuse (v4): immediacy semantics and downlink control patterns.
	•	New: durable queue, idempotency hash, rate limiter, dead-letter flow.

Acceptance Criteria
	•	Duplicate display states are not sent.
	•	Burst of 100 updates is drained respecting rate limits without worker crash.
	•	On ChirpStack outage, commands accumulate and drain cleanly when back.

Risks & Mitigations
	•	Worker crash: auto-restart and at-least-once semantics; use idempotency to avoid duplicates.
