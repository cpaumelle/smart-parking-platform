8) Testing You Can Believe In

Filename: docs/v5.3-08-testing-strategy.md

Objective

Catch regressions early and prove correctness under concurrency and load.

Recommendations
	•	Unit tests
	•	Reservation overlap, idempotent booking, state-machine transitions, downlink coalescing.
	•	Property tests
	•	Random intervals for reservations; assert no overlaps.
	•	Integration tests (docker-compose)
	•	API + Postgres + Redis + (fake ChirpStack/MQTT). Use the simulator to replay realistic uplinks.
	•	Load tests
	•	500 spaces toggling occupancy, 10 rps reservation attempts; SLOs: p95 actuation < 5s, errors < 1%.
	•	Tooling
	•	pytest, pytest-asyncio, hypothesis (for property tests), locust (load).
	•	CI
	•	Run unit/property on each PR; integration & load nightly or on release branch.

Reuse vs New
	•	Reuse (v4): MQTT simulator scenarios.
	•	New: property tests, Locust suite, CI workflows.

Acceptance Criteria
	•	Test suite green in CI; reproducible load test reports stored as artifacts.
	•	A failing SLO blocks release.

Risks & Mitigations
	•	Flaky async tests: timeouts with margins; use fake clocks where possible.
