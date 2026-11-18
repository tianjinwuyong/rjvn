# Product Attendance Management — Check-in Compatibility Component

Canonical asset ID: `PRD-ATT-001 / production.product-attendance`

This folder preserves the existing `arrival` implementation name during migration. Arrival/check-in is one part of Product Attendance Management.

## Ownership

- Agent owns the immutable observation: what SN appeared, where, when and from which source.
- MES owns expectation, work-order validity, route revision, NG/repair state and final disposition.
- UI displays the decision and next required action; it never reconstructs route truth from local tabs.

## State sequence

`OBSERVED_LOCAL → DECISION_PENDING → ACCEPTED / HOLD / BLOCKED / OFFLINE_QUEUED → MES_RECORDED → DEPARTED`

An accepted product visit is identified by `(SN, routeRevision, cycleNo, stationCode)`. A repeated network event uses the same idempotency key and returns the original result. A legitimate repair/retest visit uses a new cycle number and is not treated as a duplicate.

## Pre-arrival reconciliation

For each station, route revision and cycle:

- `Expected ∩ Actual` → `ARRIVED_EXPECTED` or `ARRIVED_LATE`.
- `Expected − Actual`, before due time → `EXPECTED_PENDING` (still in transit).
- `Expected − Actual`, after due time + grace → `MISSING_OVERDUE`.
- `Actual − Expected` → `ARRIVED_UNEXPECTED`, then MES determines early arrival, blocked jump, authorized exemption or repair return.

Missing is never inferred merely because the next polling cycle has no actual record. It requires an explicit due window and grace policy.

## MES decisions

- `ACCEPTED_EXPECTED`
- `ACCEPTED_LATE`
- `ACCEPTED_UNEXPECTED` — only by explicit policy
- `DUPLICATE_REPLAY` — technical replay; no new exception
- `HOLD_AUTH_REQUIRED`
- `QUEUED_OFFLINE` — fact retained, production still waits
- `BLOCKED_NG`
- `BLOCKED_ROUTE`
- `BLOCKED_WORK_ORDER`
- `BLOCKED_OFFLINE`
- `INVALID_FACT`

## Exceptions

Exceptions are append-only facts with reason, responsible operator, timestamps, related arrival/expectation/route revision and final disposition. Creating an exception does not automatically mean maintenance; routing to repair, quality hold, maintenance or data correction is an MES policy decision.

## Migration from the current implementation

1. Keep existing `expected_sns`, `sn_arrivals`, `arrival_exceptions` and outbox data.
2. Add `expectation_id`, `route_revision`, `cycle_no`, `station_instance`, `idempotency_key` and MES decision fields.
3. Stop using Agent-local `STATION_NEXT` as the production authority.
4. MES returns a decision for every arrival fact and stores the idempotent result.
5. Integrate stations 03–06 through the same adapter.
6. Replace station-specific arrival tabs with the shared Arrival & Route UI component.
