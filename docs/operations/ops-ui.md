9) Minimal UI for Simple Ops

Filename: docs/v5.3-09-ops-ui.md

Objective

Give operators a compact UI to manage tenants, sites, spaces, devices, and reservations without touching the database or YAML.

Recommendations
	•	Scopes & navigation
	•	Tenant switcher → Sites list → Spaces table/calendar → Device detail.
	•	Key screens
	•	Bulk import CSV for spaces/devices (tenant/site-scoped).
	•	Reservation calendar (per site & space) with create/cancel actions.
	•	Policies editor (display colours, hysteresis, reserved-soon threshold).
	•	ORPHAN devices inbox: claim or ignore; pagination & rate-limited actions.
	•	Activity log (audit trail) & metrics summary per site.
	•	Safety
	•	Confirmations for destructive actions; RBAC gates in UI.
	•	Usability
	•	Search/filter by code/label/status; inline edits for labels & codes.

Reuse vs New
	•	Reuse (v5): existing Device Manager UI foundation.
	•	New: bulk import/export, reservation calendar, policy editor, orphan inbox, audit view.

Acceptance Criteria
	•	Operator can fully manage a site (spaces, devices, reservations, policies) without CLI.
	•	Bulk import creates 100+ spaces/devices with validation & rollback on errors.

Risks & Mitigations
	•	CSV drift: publish a versioned CSV template; validate headers strictly.
