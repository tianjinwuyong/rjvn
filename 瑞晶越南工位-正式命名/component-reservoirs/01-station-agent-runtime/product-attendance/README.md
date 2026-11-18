# Product Attendance Management / 产品考勤管理

Asset ID: `PRD-ATT-001`

## Purpose

Track whether every product attended every required station in the correct route revision and production cycle, while preserving authorized exceptions such as optional steps, repair return and controlled process exemption.

## Full-line component lifetime

The component is created once by MES when the product is released to the first route step. Its stable `productAttendanceId` follows the SN through every station until the final route step checks out and the journey closes.

- MES stores the full `ProductAttendanceJourney` aggregate.
- Each station Agent receives the same journey ID and opens only its current `SnAttendanceCycle`.
- Closing a station cycle creates the next station expectation inside the same journey.
- Repair/retest creates another cycle/visit under the same journey.
- A route revision change is an audited journey transition; it never silently rewrites history.
- The final station check-out changes the journey to `COMPLETED`.

## Attendance lifecycle

```text
MES issues expected attendance
        ↓
Product checks in at station
        ↓
MES evaluates route / WO / NG / authorization
        ↓
ACCEPTED → IN_STATION → COMPLETED → CHECKED_OUT
     ↘ HOLD / BLOCKED / EXCEPTION → disposition → closed
        ↓
MES issues expected attendance for the next authorized station
```

The executable lifecycle is implemented by the reusable `SnAttendanceCycle` state machine. Every change appends an immutable numbered transition with time, actor, reason and reference.

### State machine

```text
CREATED
 ├─ expectation issued → EXPECTED
 │   ├─ due missed → MISSING_OVERDUE ─┬─ arrival observed → DECISION_PENDING
 │   │                                └─ exception resolved → CLOSED
 │   └─ arrival observed → DECISION_PENDING
 └─ arrival without expectation → DECISION_PENDING

DECISION_PENDING
 ├─ accepted → IN_STATION → COMPLETED → CHECKED_OUT → CLOSED
 ├─ held → HOLD ─┬─ authorized → DECISION_PENDING
 │               └─ resolved/closed
 ├─ blocked → BLOCKED ─┬─ authorized exemption/repair → DECISION_PENDING
 │                     └─ resolved/closed
 └─ MES unavailable → OFFLINE_QUEUED → retry → DECISION_PENDING
```

## Canonical attendance states

| State | Meaning |
|---|---|
| `EXPECTED_PENDING` | Expected but still within the arrival window |
| `ARRIVED_EXPECTED` | Checked in at the expected station |
| `ARRIVED_LATE` | Checked in after due time + grace |
| `MISSING_OVERDUE` | Expected but absent after due time + grace |
| `ARRIVED_UNEXPECTED` | Actual check-in has no matching expectation |
| `DUPLICATE_REPLAY` | Same technical event replayed; not a second attendance |
| `SAME_STATION_RESCAN` | Operator rescanned during the same visit |
| `JUMP_BLOCKED` | Required station(s) would be skipped |
| `EXEMPTION_AUTHORIZED` | MES-approved optional/skip rule |
| `REPAIR_RETURN_AUTHORIZED` | MES-approved backward/retest route |
| `IN_STATION` | Product is currently being processed |
| `CHECKED_OUT` | Station work completed and departure recorded |

## Attendance identity

One legitimate attendance is uniquely identified by:

`SN + routeRevision + cycleNo + stationCode + stationInstance + visitNo`

Network retry uses the same `idempotencyKey`. Repair/retest creates a new cycle or visit; it is never collapsed into the original attendance.

## Management views

- Product attendance card: current SN, expected/current/next station, route revision, cycle and status.
- Station attendance board: expected, present, late, missing, unexpected, blocked and in-process counts.
- Route timeline: completed, current, expected, missing, exempted, repair-return and blocked steps.
- Exception queue: owner, reason, SLA, disposition and closure evidence.
- Attendance history: immutable check-in/check-out and MES decision ledger.

## Ownership

- MES: route version, expected attendance, decision, exception ownership and closure.
- Agent: immutable actual check-in/check-out facts, local durable outbox and UI execution.
- Equipment adapter: trustworthy source record reference.
- Operator/supervisor: authorized exception evidence and disposition actions.

## Metrics

- Expected attendance rate
- On-time attendance rate
- Missing/overdue count
- Unexpected arrival count
- Station-jump attempts and authorized exemptions
- Station dwell time and overdue dwell
- Offline reporting delay
- Exception response and closure time

## Compatibility

Existing `station_arrival_core.py`, tables and MES arrival endpoints remain the migration source. They are progressively adapted to this contract; historical evidence is not deleted or rewritten.
