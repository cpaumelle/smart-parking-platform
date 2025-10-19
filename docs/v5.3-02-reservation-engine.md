2) Reservation Engine (Correctness First)
Filename: docs/v5.3-02-reservation-engine.md
Objective
Eliminate double-booking under concurrency and network retries; make reservation APIs idempotent.
Recommendations
DB-level guarantees (authoritative)
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE reservations (
  id UUID PRIMARY KEY,
  space_id UUID NOT NULL REFERENCES spaces(id),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  user_id UUID NULL REFERENCES users(id),
  start_at timestamptz NOT NULL,
  end_at   timestamptz NOT NULL,
  status   text NOT NULL CHECK (status IN ('pending','confirmed','cancelled','expired')),
  request_id uuid NOT NULL, -- for idempotency
  created_at timestamptz DEFAULT now()
);

-- No overlaps per space (within tenant)
CREATE INDEX ON reservations(tenant_id, space_id);
ALTER TABLE reservations
  ADD CONSTRAINT no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    space_id  WITH =,
    tstzrange(start_at, end_at, '[)') WITH &&
  );
API idempotency
POST /reservations requires request_id (UUID). If retried, return existing result.
States
pending → confirmed (payment/approval optional) → expired by job at end_at.
Admin override: cancelled.
Queries
GET /spaces/{id}/availability?from=&to= computes free/occupied/reserved from DB (no cache correctness bugs).
Reuse vs New
Reuse (v5): existing reservation model & endpoints (extend).
New: EXCLUDE constraint, request_id idempotency, expiry job.
Acceptance Criteria
Concurrent bookings for same slot result in single confirmed reservation.
Retries with same request_id do not create duplicates.
Availability endpoints reflect DB truth within <1s.
Risks & Mitigations
Clock skew: rely on DB timestamps; run servers on
