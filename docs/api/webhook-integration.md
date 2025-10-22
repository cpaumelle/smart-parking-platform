5) Webhook Ingest (ChirpStack)

Filename: docs/v5.3-05-webhook-ingest.md

Objective

Process uplinks reliably and idempotently, classify unknown devices safely, and never block on transient failures.

Recommendations
	•	API
	•	POST /webhooks/chirpstack (tenant-scoped secret or IP allowlist).
	•	Validation & idempotency
	•	Validate payload; compute key (dev_eui, fcnt); ignore duplicates (unique index in DB).
	•	Persist raw payload for audit; parse into normalized occupancy_events.
	•	ORPHAN intake
	•	Unknown dev_eui → orphans table with first_seen, count; per-tenant rate-limit acceptance; auto-expire after N days.
	•	Back-pressure
	•	If DB slow, buffer to file spool (/var/spool/parking-uplinks) and retry with exponential backoff.
	•	Security
	•	Per-tenant webhook secrets; rotate; structured logging without payload PII.

Reuse vs New
	•	Reuse (v4): simulator & message patterns.
	•	New: (dev_eui, fcnt) uniqueness, orphan handling with rate-limit, file spool.

Acceptance Criteria
	•	Duplicate uplinks do not duplicate events.
	•	Unknown devices visible in an “ORPHAN” admin list with counts.
	•	Ingest sustains 200 msg/s bursts without data loss.

Risks & Mitigations
	•	Malformed payloads: reject early; capture sample for diagnostics.
