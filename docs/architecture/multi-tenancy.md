Objective

Guarantee strict isolation between organisations and their sites while keeping day-to-day management simple. Provide role-based access so different users manage different parks without stepping on each other.

Recommendations
	•	Data model (minimal & scalable)
	•	tenants(id, name, slug, created_at)
	•	sites(id, tenant_id FK, name, timezone, location_jsonb)
	•	spaces(id, site_id FK, code, label, device_sensor_id, device_display_id, status, UNIQUE(site_id, code))
	•	users(id, email, name, password_hash) and user_memberships(user_id, tenant_id, role ENUM('owner','admin','operator','viewer'))
	•	api_keys(id, tenant_id FK, name, hash, created_at, revoked_at, last_used_at)
	•	Scoping rules
	•	Every API call must resolve a tenant_id via: JWT (user) or API key (service).
	•	All queries include tenant_id predicates; enforce unique indexes like UNIQUE(tenant_id, site_id, code).
	•	RBAC
	•	owner: manage billing & keys; full CRUD.
	•	admin: manage sites/spaces/devices & users (not billing).
	•	operator: manage reservations, view telemetry, trigger displays.
	•	viewer: read-only.
	•	Rate limiting
	•	Redis token buckets per tenant for: webhook QPS, downlink ops/min, reservation attempts/min.
	•	Operational simplicity
	•	Tenant-scoped exports/imports; per-tenant default policies (display colours, hysteresis).

Reuse vs New
	•	Reuse (v5): hashed API key approach; extend to tenant scoping.
	•	New: tenant/site tables, membership model, RBAC middleware, per-tenant rate limits.

Acceptance Criteria
	•	Requests without a resolvable tenant_id are denied (401/403).
	•	A user from Tenant A cannot access any resource from Tenant B (verified by tests).
	•	Per-tenant rate limits work and are observable (metrics).

Risks & Mitigations
	•	Leak via logs: scrub PII and always include tenant_id in structured logs.
	•	Complex invites: start with email-link invites; add SSO later if needed.
