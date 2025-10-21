Awesome dump, thanks. I read it end-to-end and here’s a tight review focused on correctness, tenant safety, and performance for LoRa sensors + Class-C displays. I’ve split it into (A) critical fixes, (B) strong improvements, and (C) a ready-to-paste SQL “patch pack”.

⸻

A) Critical fixes (do these first)
	1.	Name collision: orphan_devices table vs view
You can’t have both. Rename the view to v_orphan_devices (or vw_orphan_devices) everywhere you reference it.
	2.	Reservation statuses are inconsistent

	•	Table spec uses: pending | confirmed | expired | cancelled
	•	Later “Enums & Valid Values” says: active | completed | cancelled | no_show
	•	Indexing section mentions status = 'active'.
👉 Pick one set (I recommend the table’s set) and update docs + partial indexes accordingly.

	3.	Case-insensitive email uniqueness isn’t enforced
You list UNIQUE (email) but call it “case-insensitive”. In Postgres that’s not CI. Use a unique index on lower(email) and drop the table-level unique.
	4.	RLS is claimed but not defined
You say “strict tenant isolation via FK”; that’s not isolation. Add Row-Level Security with current_setting('app.current_tenant'). (Patch below.)
	5.	Idempotency is documented but not enforced
Add unique (tenant_id, request_id) where request_id is not null on reservations.
	6.	Downlink/display field naming drift
You use display_eui most places, but actuations has display_deveui. Standardize to display_eui.
	7.	sensor_readings dedup + tenancy missing
Doc talks about FCnt de-dup, but the table has no fcnt (nor tenant_id). Add both, then enforce unique (tenant_id, device_eui, fcnt) for idempotent ingest. (Patch below.)
	8.	Display uniqueness in spaces
You made sensor_eui unique; do the same for display_eui (unique where not null, and ideally where deleted_at is null).
	9.	UUID extension mismatch
You default to gen_random_uuid() (that’s pgcrypto), but you also list uuid-ossp. If you keep gen_random_uuid(), you don’t need uuid-ossp. (Or switch defaults to uuid_generate_v4().)
	10.	Materialized view + multi-tenant risk
v_spaces materializes all tenants. Anyone with SELECT on it can see cross-tenant data regardless of RLS on base tables. Lock it down via privileges, or replace with a secure view (non-materialized) that filters by current_setting('app.current_tenant').
	11.	Retention policy contradiction
Background tasks say “purge old sensor_readings (>30 days)”, but later you say “retained indefinitely”. Decide policy (I suggest partition + retention window) and make both sections agree.

⸻

B) Strong improvements (next sprint)
	•	Add tenant_id to all tenant-scoped operational tables (sensor_readings, state_changes, actuations) + triggers to sync from space_id. This makes RLS fast and simple (no join in policies).
	•	CHECK constraints for EUI formatting
Enforce hex and length once (and normalize to uppercase on write). This prevents subtle join/index misses.
	•	Partial uniques & partial indexes
Keep indexes tiny and relevant (e.g., UNIQUE(display_eui) WHERE display_eui IS NOT NULL AND deleted_at IS NULL).
	•	Typed enums
Replace varchar status fields with Postgres ENUM types to avoid drift and typos.
	•	Time-series partitioning
Convert sensor_readings (and later actuations) to monthly partitions now; add a small retention worker. BRIN stays great on each child.
	•	Deprecate api_keys.is_admin
You already have scopes text[]. Prefer scopes only; if you keep the flag temporarily, add a CHECK that it implies 'admin' ∈ scopes.
	•	FK ON DELETE behavior
Consider spaces.(sensor_device_id|display_device_id) ON DELETE SET NULL so decommissioning a device doesn’t require deleting spaces.
	•	Materialized view safety
If you must keep v_spaces as MV, do not grant global SELECT; expose tenant views/APIs that always filter by tenant.

⸻

C) “Patch pack” — copy/paste SQL

Tweak names to your liking; this assumes Postgres 16 and pgcrypto loaded.

-- 0) Extensions: keep pgcrypto (gen_random_uuid), drop uuid-ossp if unused
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- DROP EXTENSION IF EXISTS "uuid-ossp";

-- 1) Fix email uniqueness (case-insensitive)
-- (a) drop the table-level UNIQUE if present
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key;
-- (b) enforce CI uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_ci ON users (lower(email));

-- 2) Unify actuation naming
ALTER TABLE actuations RENAME COLUMN display_deveui TO display_eui;

-- 3) Display uniqueness in spaces (mirror sensor_eui)
CREATE UNIQUE INDEX IF NOT EXISTS uq_spaces_display_eui
  ON spaces(display_eui)
  WHERE display_eui IS NOT NULL AND deleted_at IS NULL;

-- 4) Reservation idempotency (per-tenant)
CREATE UNIQUE INDEX IF NOT EXISTS uq_reservations_request
  ON reservations(tenant_id, request_id)
  WHERE request_id IS NOT NULL;

-- 5) Reservations: EXCLUDE uses only allowed statuses (keep your set)
-- Ensure btree_gist is present
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Optional: re-create with name for clarity
ALTER TABLE reservations DROP CONSTRAINT IF EXISTS uq_reservations_no_overlap;
ALTER TABLE reservations
  ADD CONSTRAINT uq_reservations_no_overlap
  EXCLUDE USING gist (
    space_id WITH =,
    tstzrange(start_time, end_time) WITH &&
  )
  WHERE (status IN ('pending','confirmed'));

-- 6) Add FCnt + tenant_id to sensor_readings for dedup + RLS
ALTER TABLE sensor_readings
  ADD COLUMN IF NOT EXISTS tenant_id uuid,
  ADD COLUMN IF NOT EXISTS fcnt integer;

-- Keep tenant_id synced from the space when present
CREATE OR REPLACE FUNCTION sensor_readings_sync_tenant_id()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.space_id IS NOT NULL THEN
    SELECT s.tenant_id INTO NEW.tenant_id FROM spaces s WHERE s.id = NEW.space_id;
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_sensor_readings_sync_tenant ON sensor_readings;
CREATE TRIGGER trg_sensor_readings_sync_tenant
  BEFORE INSERT OR UPDATE OF space_id
  ON sensor_readings
  FOR EACH ROW
  EXECUTE FUNCTION sensor_readings_sync_tenant_id();

-- De-dup per device per tenant on FCnt (optional: add WHERE fcnt IS NOT NULL)
CREATE UNIQUE INDEX IF NOT EXISTS uq_readings_device_fcnt
  ON sensor_readings(tenant_id, device_eui, fcnt)
  WHERE fcnt IS NOT NULL;

-- 7) Normalize EUIs and enforce hex/length
-- Uppercase on write
CREATE OR REPLACE FUNCTION enforce_eui_upper()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.dev_eui IS NOT NULL THEN NEW.dev_eui := upper(NEW.dev_eui); END IF;
  IF TG_TABLE_NAME = 'spaces' THEN
    IF NEW.sensor_eui  IS NOT NULL THEN NEW.sensor_eui  := upper(NEW.sensor_eui); END IF;
    IF NEW.display_eui IS NOT NULL THEN NEW.display_eui := upper(NEW.display_eui); END IF;
  END IF;
  RETURN NEW;
END$$;

-- Apply to device registries and spaces
DROP TRIGGER IF EXISTS trg_sensor_eui_upper ON sensor_devices;
CREATE TRIGGER trg_sensor_eui_upper BEFORE INSERT OR UPDATE ON sensor_devices
FOR EACH ROW EXECUTE FUNCTION enforce_eui_upper();

DROP TRIGGER IF EXISTS trg_display_eui_upper ON display_devices;
CREATE TRIGGER trg_display_eui_upper BEFORE INSERT OR UPDATE ON display_devices
FOR EACH ROW EXECUTE FUNCTION enforce_eui_upper();

DROP TRIGGER IF EXISTS trg_spaces_eui_upper ON spaces;
CREATE TRIGGER trg_spaces_eui_upper BEFORE INSERT OR UPDATE ON spaces
FOR EACH ROW EXECUTE FUNCTION enforce_eui_upper();

-- CHECK constraints for hex (16 chars)
ALTER TABLE sensor_devices  DROP CONSTRAINT IF EXISTS chk_sensor_dev_eui_hex;
ALTER TABLE display_devices DROP CONSTRAINT IF EXISTS chk_display_dev_eui_hex;
ALTER TABLE spaces         DROP CONSTRAINT IF EXISTS chk_spaces_eui_hex;

ALTER TABLE sensor_devices
  ADD CONSTRAINT chk_sensor_dev_eui_hex
  CHECK (dev_eui ~ '^[0-9A-F]{16}$');

ALTER TABLE display_devices
  ADD CONSTRAINT chk_display_dev_eui_hex
  CHECK (dev_eui ~ '^[0-9A-F]{16}$');

ALTER TABLE spaces
  ADD CONSTRAINT chk_spaces_eui_hex
  CHECK (
    (sensor_eui  IS NULL OR sensor_eui  ~ '^[0-9A-F]{16}$') AND
    (display_eui IS NULL OR display_eui ~ '^[0-9A-F]{16}$')
  );

-- 8) Row-Level Security: enable + policies (pattern)
-- Use a single setting: app.current_tenant::uuid
DO $$
BEGIN
  PERFORM set_config('app.current_tenant','00000000-0000-0000-0000-000000000000', true);
EXCEPTION WHEN OTHERS THEN
  -- ignore, just ensures the setting exists
END$$;

-- Helper to create a standard policy on a tenant table
-- Example for 'spaces' (has tenant_id)
ALTER TABLE spaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE spaces FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_spaces_tenant ON spaces;
CREATE POLICY p_spaces_tenant ON spaces
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Repeat for other tenant tables:
-- sites, sensor_devices (if you add tenant_id), display_devices (if you add tenant_id),
-- reservations, api_keys, webhook_secrets, orphan_devices, actuations, sensor_readings, state_changes, etc.

-- 9) Rename the conflicting view
DROP VIEW IF EXISTS orphan_devices; -- if it was a view
-- Recreate as v_orphan_devices (definition omitted here)
-- CREATE VIEW v_orphan_devices AS ...;

If you keep v_spaces as a materialized view, do not grant SELECT broadly:

REVOKE ALL ON MATERIALIZED VIEW v_spaces FROM PUBLIC;
-- Grant only to the backend role that always sets app.current_tenant and post-filters.



⸻

A few clarifications for the docs
	•	RLS model: add a short section showing:
	1.	middleware sets SET LOCAL app.current_tenant = '<uuid>'; per request,
	2.	every tenant table has ENABLE RLS + a standard policy,
	3.	service role has no BYPASSRLS.
This turns tenant leaks from “possible” into “impossible”.
	•	Enums: define Postgres ENUMs once and reference them (avoids “active vs confirmed” drifts).
	•	EUI type: you can leave EUIs as varchar(16) (now guarded) or evolve to bytea (8 bytes) later for space + speed; if you do that, keep a generated uppercase hex column for human/search.
	•	Background tasks: document the actual retention (e.g., readings 90 days) and partitioning (monthly). Your ops teams will love you for it.
	•	API keys: keep only scopes[]; remove is_admin when you can.

⸻


openapi: 3.1.0
info:
  title: Smart Parking Platform API
  version: 5.3.0
  summary: API v1 (semantic app version 5.3.0)
  description: |
    REST API for multi-tenant LoRaWAN parking sensors and Class‑C displays.
    
    **Conventions**
    - Path version: `/api/v1` (interface version). App version: `5.3.0` (in headers and /health).
    - Timestamps: ISO 8601 UTC.
    - Idempotency on all mutations via `Idempotency-Key` header.
    - ETag on GET; `If-None-Match` supported. `If-Match` required on PATCH.
    - Pagination: offset **or** cursor; standard envelope.
    - Errors: RFC 7807 `application/problem+json`.
servers:
  - url: https://api.verdegris.eu
    description: Production
security:
  - bearerAuth: []
  - apiKeyAuth: []
  # Either JWT (people) or API key (services) is sufficient

x-standard-response-headers:
  - X-Request-Id
  - X-App-Version
  - X-API-Version
  - X-RateLimit-Limit
  - X-RateLimit-Remaining
  - X-RateLimit-Reset
  - ETag

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: User JWT access token (`Authorization: Bearer <token>`)
    apiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: Tenant-scoped API key. Alternative: `Authorization: ApiKey <token>` if enabled.
    internalProbe:
      type: apiKey
      in: header
      name: X-Internal-Token
      description: Internal-only endpoints (readiness/metrics). Not exposed publicly.
  parameters:
    TenantId:
      name: tenant_id
      in: path
      required: true
      schema: { type: string, format: uuid }
    SiteId:
      name: site_id
      in: path
      required: true
      schema: { type: string, format: uuid }
    SpaceId:
      name: space_id
      in: path
      required: true
      schema: { type: string, format: uuid }
    ReservationId:
      name: reservation_id
      in: path
      required: true
      schema: { type: string, format: uuid }
    ApiKeyId:
      name: key_id
      in: path
      required: true
      schema: { type: string, format: uuid }
    PolicyId:
      name: policy_id
      in: path
      required: true
      schema: { type: string, format: uuid }
    Limit:
      name: limit
      in: query
      schema: { type: integer, minimum: 1, maximum: 1000, default: 100 }
    Offset:
      name: offset
      in: query
      schema: { type: integer, minimum: 0, default: 0 }
    Cursor:
      name: cursor
      in: query
      schema: { type: string, description: Opaque pagination cursor }
    Since:
      name: since
      in: query
      schema: { type: string, format: date-time, description: Return only items updated at/after this timestamp }
    Fields:
      name: fields
      in: query
      schema: { type: string, description: Comma-separated list of fields to include }
    Expand:
      name: expand
      in: query
      schema: { type: string, description: Comma-separated list of relations to include }
    Sort:
      name: sort
      in: query
      schema: { type: string, description: 'Comma separated sort keys, prefix with - for desc' }
    IdempotencyKey:
      name: Idempotency-Key
      in: header
      required: false
      schema: { type: string, description: UUID or unique token identifying this mutation }
    IfMatch:
      name: If-Match
      in: header
      required: false
      schema: { type: string, description: ETag to enforce optimistic concurrency on PATCH }
    IfNoneMatch:
      name: If-None-Match
      in: header
      required: false
      schema: { type: string, description: Return 304 if ETag matches }
    WebhookSignature:
      name: X-Chirpstack-Signature
      in: header
      required: true
      schema: { type: string, description: 'HMAC-SHA256 signature: sha256=<hex>' }
    WebhookTimestamp:
      name: X-Timestamp
      in: header
      required: true
      schema: { type: string, description: RFC3339 timestamp used in signature }
    WebhookNonce:
      name: X-Nonce
      in: header
      required: true
      schema: { type: string, description: Unique nonce (UUID); replay protected' }
  responses:
    Problem:
      description: Error (Problem Details)
      content:
        application/problem+json:
          schema: { $ref: '#/components/schemas/Problem' }
  schemas:
    Problem:
      type: object
      required: [type, title, status]
      properties:
        type: { type: string, format: uri }
        title: { type: string }
        status: { type: integer }
        detail: { type: string }
        instance: { type: string }
        request_id: { type: string }
    Pagination:
      type: object
      properties:
        total: { type: integer }
        limit: { type: integer }
        offset: { type: integer }
        has_more: { type: boolean }
        next_cursor: { type: string, nullable: true }
    User:
      type: object
      properties:
        id: { type: string, format: uuid }
        email: { type: string, format: email }
        name: { type: string }
        role: { type: string, enum: [owner, admin, operator, viewer] }
        tenant_id: { type: string, format: uuid }
    Tenant:
      type: object
      properties:
        id: { type: string, format: uuid }
        name: { type: string }
        slug: { type: string }
        is_active: { type: boolean }
        created_at: { type: string, format: date-time }
    Site:
      type: object
      properties:
        id: { type: string, format: uuid }
        tenant_id: { type: string, format: uuid }
        name: { type: string }
        timezone: { type: string }
        metadata: { type: object, additionalProperties: true }
    Space:
      type: object
      properties:
        id: { type: string, format: uuid }
        tenant_id: { type: string, format: uuid }
        site_id: { type: string, format: uuid }
        code: { type: string }
        name: { type: string }
        floor: { type: string, nullable: true }
        zone: { type: string, nullable: true }
        state: { type: string, enum: [free, occupied, reserved, maintenance] }
        sensor_eui: { type: string, pattern: '^[0-9A-Fa-f]{16}$', nullable: true }
        display_eui: { type: string, pattern: '^[0-9A-Fa-f]{16}$', nullable: true }
        metadata: { type: object, additionalProperties: true }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }
    Reservation:
      type: object
      properties:
        id: { type: string, format: uuid }
        tenant_id: { type: string, format: uuid }
        space_id: { type: string, format: uuid }
        reserved_from: { type: string, format: date-time }
        reserved_until: { type: string, format: date-time }
        status: { type: string, enum: [pending, confirmed, expired, cancelled] }
        user_email: { type: string, format: email, nullable: true }
        user_phone: { type: string, nullable: true }
        request_id: { type: string, nullable: true }
        metadata: { type: object, additionalProperties: true }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }
    Device:
      type: object
      properties:
        id: { type: string, format: uuid }
        dev_eui: { type: string, pattern: '^[0-9A-Fa-f]{16}$' }
        device_type: { type: string, enum: [sensor, display] }
        device_model: { type: string, nullable: true }
        status: { type: string, enum: [orphan, active, inactive, decommissioned] }
        last_seen_at: { type: string, format: date-time, nullable: true }
    DisplayPolicy:
      type: object
      properties:
        id: { type: string, format: uuid }
        tenant_id: { type: string, format: uuid }
        policy_name: { type: string }
        is_active: { type: boolean }
        display_codes:
          type: object
          additionalProperties: true
        created_at: { type: string, format: date-time }
        activated_at: { type: string, format: date-time, nullable: true }
    AuditLog:
      type: object
      properties:
        id: { type: string, format: uuid }
        created_at: { type: string, format: date-time }
        actor_type: { type: string, enum: [user, api_key, system] }
        actor_name: { type: string }
        action: { type: string }
        resource_type: { type: string }
        resource_id: { type: string }
        request_id: { type: string }
        success: { type: boolean }
        old_values: { type: object, additionalProperties: true, nullable: true }
        new_values: { type: object, additionalProperties: true, nullable: true }
    DownlinkMetrics:
      type: object
      properties:
        queue:
          type: object
          properties:
            pending_depth: { type: integer }
            processing_depth: { type: integer }
            dead_letter_depth: { type: integer }
        throughput:
          type: object
          additionalProperties: { type: integer }
        success_rate: { type: number }
        latency:
          type: object
          properties:
            p50_ms: { type: integer }
            p95_ms: { type: integer }
            p99_ms: { type: integer }
        rate_limits:
          type: object
          additionalProperties: true
    Task:
      type: object
      properties:
        id: { type: string }
        status: { type: string, enum: [queued, running, success, failed] }
        result: { type: object, nullable: true }
        error: { $ref: '#/components/schemas/Problem' }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }

paths:
  /health:
    get:
      summary: Liveness ping
      security: []
      responses:
        '200':
          description: Alive
          headers:
            X-App-Version: { schema: { type: string } }
            X-API-Version: { schema: { type: string } }
          content:
            application/json:
              schema:
                type: object
                properties:
                  status: { type: string, enum: [healthy] }
                  version: { type: string }
                  timestamp: { type: string, format: date-time }
  /health/ready:
    get:
      summary: Readiness (internal)
      security: [ { internalProbe: [] } ]
      responses:
        '200':
          description: Ready
        '503':
          description: Unready
  /metrics:
    get:
      summary: Prometheus metrics (internal)
      security: [ { internalProbe: [] } ]
      responses:
        '200':
          description: OpenMetrics text
          content:
            text/plain: { schema: { type: string } }

  /api/v1/me:
    get:
      summary: Current user and memberships
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  user: { $ref: '#/components/schemas/User' }
                  memberships:
                    type: array
                    items:
                      type: object
                      properties:
                        tenant_id: { type: string, format: uuid }
                        role: { type: string }
  /api/v1/me/limits:
    get:
      summary: Current tenant limits and usage
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  limits: { type: object, additionalProperties: true }
                  usage: { type: object, additionalProperties: true }

  /api/v1/tenants:
    post:
      summary: Register tenant + owner user; returns JWT
      security: []
      responses:
        '201':
          description: Created
          headers:
            Location: { schema: { type: string, format: uri } }
          content:
            application/json:
              schema:
                type: object
                properties:
                  tenant: { $ref: '#/components/schemas/Tenant' }
                  user: { $ref: '#/components/schemas/User' }
                  access_token: { type: string }
                  token_type: { type: string }
                  expires_in: { type: integer }
        '400': { $ref: '#/components/responses/Problem' }
        '409': { $ref: '#/components/responses/Problem' }

  /api/v1/auth/login:
    post:
      summary: Login with email + password
      security: []
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  access_token: { type: string }
                  token_type: { type: string }
                  expires_in: { type: integer }
                  refresh_token: { type: string }
                  user: { $ref: '#/components/schemas/User' }
        '401': { $ref: '#/components/responses/Problem' }

  /api/v1/auth/refresh:
    post:
      summary: Refresh JWT using refresh token
      security: []
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  access_token: { type: string }
                  token_type: { type: string }
                  expires_in: { type: integer }
        '401': { $ref: '#/components/responses/Problem' }

  /api/v1/tenants/{tenant_id}:
    get:
      summary: Get tenant
      parameters: [ { $ref: '#/components/parameters/TenantId' } ]
      responses:
        '200':
          description: OK
          headers: { ETag: { schema: { type: string } } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Tenant' }
        '404': { $ref: '#/components/responses/Problem' }

  /api/v1/tenants/{tenant_id}/users:
    get:
      summary: List users in tenant
      parameters: [ { $ref: '#/components/parameters/TenantId' }, { $ref: '#/components/parameters/Limit' }, { $ref: '#/components/parameters/Offset' }, { $ref: '#/components/parameters/Sort' } ]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                allOf:
                  - $ref: '#/components/schemas/Pagination'
                  - type: object
                    properties:
                      items:
                        type: array
                        items: { $ref: '#/components/schemas/User' }
    post:
      summary: Invite user to tenant
      parameters: [ { $ref: '#/components/parameters/TenantId' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '201':
          description: Invite created
          content:
            application/json:
              schema: { $ref: '#/components/schemas/User' }
        '409': { $ref: '#/components/responses/Problem' }

  /api/v1/sites/{site_id}/spaces:
    post:
      summary: Create space in site
      parameters: [ { $ref: '#/components/parameters/SiteId' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '201':
          description: Created
          headers:
            Location: { schema: { type: string, format: uri } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Space' }
        '400': { $ref: '#/components/responses/Problem' }

  /api/v1/spaces:
    get:
      summary: List spaces (tenant-scoped)
      parameters: [
        { $ref: '#/components/parameters/Limit' },
        { $ref: '#/components/parameters/Offset' },
        { $ref: '#/components/parameters/Cursor' },
        { $ref: '#/components/parameters/Fields' },
        { $ref: '#/components/parameters/Expand' },
        { $ref: '#/components/parameters/Sort' },
        { $ref: '#/components/parameters/Since' }
      ]
      responses:
        '200':
          description: OK
          headers: { ETag: { schema: { type: string } } }
          content:
            application/json:
              schema:
                type: object
                allOf:
                  - $ref: '#/components/schemas/Pagination'
                  - type: object
                    properties:
                      items:
                        type: array
                        items: { $ref: '#/components/schemas/Space' }

  /api/v1/spaces/{space_id}:
    get:
      summary: Get space
      parameters: [ { $ref: '#/components/parameters/SpaceId' }, { $ref: '#/components/parameters/IfNoneMatch' } ]
      responses:
        '200':
          description: OK
          headers: { ETag: { schema: { type: string } } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Space' }
        '304': { description: Not modified }
        '404': { $ref: '#/components/responses/Problem' }
    patch:
      summary: Update space (partial)
      parameters: [ { $ref: '#/components/parameters/SpaceId' }, { $ref: '#/components/parameters/IfMatch' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '200':
          description: Updated
          headers: { ETag: { schema: { type: string } } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Space' }
        '412': { $ref: '#/components/responses/Problem' }
    delete:
      summary: Soft delete space
      parameters: [ { $ref: '#/components/parameters/SpaceId' } ]
      responses:
        '204': { description: Deleted }
        '409': { $ref: '#/components/responses/Problem' }

  /api/v1/spaces/{space_id}/availability:
    get:
      summary: Availability window for a space
      parameters: [ { $ref: '#/components/parameters/SpaceId' } ]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  space_id: { type: string, format: uuid }
                  query_start: { type: string, format: date-time }
                  query_end: { type: string, format: date-time }
                  is_available: { type: boolean }
                  reservations:
                    type: array
                    items: { $ref: '#/components/schemas/Reservation' }

  /api/v1/spaces/{space_id}/actuate:
    post:
      summary: Manual actuation/override of display state (TTL optional)
      parameters: [ { $ref: '#/components/parameters/SpaceId' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '202':
          description: Queued
          headers:
            Location: { schema: { type: string, format: uri }, description: Task URL }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Task' }
        '409': { $ref: '#/components/responses/Problem' }

  /api/v1/reservations:
    get:
      summary: List reservations (tenant-scoped)
      parameters: [ { $ref: '#/components/parameters/Limit' }, { $ref: '#/components/parameters/Offset' }, { $ref: '#/components/parameters/Cursor' }, { $ref: '#/components/parameters/Sort' } ]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                allOf:
                  - $ref: '#/components/schemas/Pagination'
                  - type: object
                    properties:
                      items:
                        type: array
                        items: { $ref: '#/components/schemas/Reservation' }
    post:
      summary: Create reservation (idempotent)
      parameters: [ { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '201':
          description: Created
          headers:
            Location: { schema: { type: string, format: uri } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Reservation' }
        '200':
          description: Idempotent replay (existing)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Reservation' }
        '409': { $ref: '#/components/responses/Problem' }

  /api/v1/reservations/{reservation_id}:
    get:
      summary: Get reservation
      parameters: [ { $ref: '#/components/parameters/ReservationId' } ]
      responses:
        '200':
          description: OK
          headers: { ETag: { schema: { type: string } } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Reservation' }
        '404': { $ref: '#/components/responses/Problem' }
    patch:
      summary: Update reservation (e.g., cancel)
      parameters: [ { $ref: '#/components/parameters/ReservationId' }, { $ref: '#/components/parameters/IfMatch' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '200':
          description: Updated
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Reservation' }
        '412': { $ref: '#/components/responses/Problem' }

  /api/v1/devices:
    get:
      summary: List devices (sensors + displays)
      parameters: [ { $ref: '#/components/parameters/Limit' }, { $ref: '#/components/parameters/Offset' }, { $ref: '#/components/parameters/Cursor' }, { $ref: '#/components/parameters/Sort' }, { $ref: '#/components/parameters/Fields' }, { $ref: '#/components/parameters/Expand' } ]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                allOf:
                  - $ref: '#/components/schemas/Pagination'
                  - type: object
                    properties:
                      items:
                        type: array
                        items: { $ref: '#/components/schemas/Device' }

  /api/v1/devices/orphans:
    get:
      summary: List orphan devices
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                allOf:
                  - $ref: '#/components/schemas/Pagination'
                  - type: object
                    properties:
                      items:
                        type: array
                        items: { $ref: '#/components/schemas/Device' }

  /api/v1/spaces/{space_id}/sensor:
    post:
      summary: Assign sensor to space
      parameters: [ { $ref: '#/components/parameters/SpaceId' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '200': { description: Assigned }
        '404': { $ref: '#/components/responses/Problem' }
    delete:
      summary: Unassign sensor
      parameters: [ { $ref: '#/components/parameters/SpaceId' } ]
      responses:
        '204': { description: Unassigned }

  /api/v1/spaces/{space_id}/display:
    post:
      summary: Assign display to space
      parameters: [ { $ref: '#/components/parameters/SpaceId' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '200': { description: Assigned }
    delete:
      summary: Unassign display
      parameters: [ { $ref: '#/components/parameters/SpaceId' } ]
      responses:
        '204': { description: Unassigned }

  /api/v1/tenants/{tenant_id}/display-policies:
    get:
      summary: List display policies
      parameters: [ { $ref: '#/components/parameters/TenantId' } ]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items: { $ref: '#/components/schemas/DisplayPolicy' }
                  active_policy_id: { type: string, format: uuid, nullable: true }
    post:
      summary: Create display policy
      parameters: [ { $ref: '#/components/parameters/TenantId' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema: { $ref: '#/components/schemas/DisplayPolicy' }

  /api/v1/tenants/{tenant_id}/display-policies/{policy_id}/activate:
    post:
      summary: Activate a policy (async)
      parameters: [ { $ref: '#/components/parameters/TenantId' }, { $ref: '#/components/parameters/PolicyId' }, { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '202':
          description: Queued
          headers: { Location: { schema: { type: string, format: uri } } }
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Task' }

  /api/v1/downlinks/queue/metrics:
    get:
      summary: Downlink queue metrics
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/DownlinkMetrics' }

  /api/v1/downlinks/queue/health:
    get:
      summary: Downlink queue health
      responses:
        '200': { description: Healthy }
        '503': { description: Unhealthy }

  /api/v1/downlinks/queue/clear-metrics:
    post:
      summary: Reset queue metrics (admin)
      parameters: [ { $ref: '#/components/parameters/IdempotencyKey' } ]
      responses:
        '200': { description: Cleared }

  /webhooks/uplink:
    post:
      summary: ChirpStack uplink webhook (HMAC + replay protection)
      security: []
      parameters: [
        { $ref: '#/components/parameters/WebhookSignature' },
        { $ref: '#/components/parameters/WebhookTimestamp' },
        { $ref: '#/components/parameters/WebhookNonce' }
      ]
      responses:
        '202': { description: Accepted (processing async) }
        '401': { $ref: '#/components/responses/Problem' }
        '498':
          description: Replay detected
          content:
            application/problem+json:
              schema: { $ref: '#/components/schemas/Problem' }

  /api/v1/tasks/{task_id}:
    get:
      summary: Inspect async task
      parameters:
        - name: task_id
          in: path
          required: true
          schema: { type: string }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Task' }
