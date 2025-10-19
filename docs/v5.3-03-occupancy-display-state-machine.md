3) Occupancy → Display State Machine

Filename: docs/v5.3-03-occupancy-display-state-machine.md

Objective

Deterministically translate sensor + reservation + admin overrides into a single display command (colour/pattern) with minimal flicker and clear priority rules.

Recommendations
	•	Inputs
	•	Sensor: occupied | vacant | unknown (+ RSSI/SNR; last_seen).
	•	Reservation: reserved_now | reserved_soon(Δt) | free.
	•	Admin: blocked | out_of_service | normal.
	•	Policy table (per tenant)
	•	display_policies(tenant_id, reserved_soon_threshold_sec, occupied_color, free_color, reserved_color, blocked_color, out_of_service_color, blink_reserved_soon bool, ...)
	•	Priority & hysteresis
	1.	out_of_service → out_of_service_color
	2.	blocked → blocked_color
	3.	reserved_now → reserved_color
	4.	reserved_soon (Δt ≤ threshold) → reserved_color (blink if enabled)
	5.	Else: occupied → occupied_color; vacant → free_color; unknown → last stable for 60s
	•	Debounce: require 2 consecutive identical sensor readings within 5–10s to switch.
	•	Output
	•	Canonical command object {space_id, display_mode, color, blink, expires_at} passed to downlink queue.

Reuse vs New
	•	Reuse (v4): class-C real-time actuation approach.
	•	New: policy table, explicit state machine, debouncing logic.

Acceptance Criteria
	•	Documented truth table; tests show stable behaviour under noisy signals.
	•	Policy can be changed without code deploy, per tenant.

Risks & Mitigations
	•	Edge oscillation: tune hysteresis; expose as policy knobs.
