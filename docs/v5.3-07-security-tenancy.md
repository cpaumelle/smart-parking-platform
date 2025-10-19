7) Security & Tenancy Isolation

Filename: docs/v5.3-07-security-tenancy.md

Objective

Protect data boundaries, secure control planes, and enable safe automation access.

Recommendations
	•	Auth
	•	Users: JWT (short-lived) + refresh; password hashing with Argon2.
	•	Services: hashed API keys bound to tenant_id + scopes (reservations:write, devices:read, etc.).
	•	ChirpStack
	•	Separate applications per tenant if shared LNS; otherwise enforce routing to the correct tenant webhook.
	•	Edge
	•	Traefik dashboard behind strong auth and IP allowlist; TLS everywhere.
	•	Secrets
	•	.env via secret manager (1Password/Vault). Rotate webhook secrets quarterly.
	•	Data isolation
	•	All tables include tenant_id; avoid cross-tenant joins; add defensive checks in repository layer.
	•	Auditing
	•	Append-only audit log: who did what, when, on which tenant_id.

Reuse vs New
	•	Reuse (v4): Traefik/dashboard hardening patterns.
	•	Reuse (v5): API key hashing baseline.
	•	New: JWT user auth, scoped keys, audit log, stricter tenant repo layer.

Acceptance Criteria
	•	Pen tests cannot cross tenant boundaries.
	•	Revoking an API key is effective immediately.
	•	All admin actions are traceable in the audit log.

Risks & Mitigations
	•	Key sprawl: per-tenant key inventory view; expiry dates; enforce rotation.
