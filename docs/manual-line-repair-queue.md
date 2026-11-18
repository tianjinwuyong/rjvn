# Per-line RepairCase queue

## Purpose

MES owns one logical repair queue for each **domain + line** pair. The queue holds references to `RepairCase` objects; it does not copy or replace the case history.

The queue identity is:

```text
queueKey = domainCode + ":" + lineCode
```

Examples:

- `MANUAL_LINE:MANUAL_LINE-01`
- `AUTO_LINE:AUTO_LINE-01`

Manual-line repair cases must stay in the `MANUAL_LINE` queue. They must not be mixed with auto-line or another product-domain queue.

When several lines share one repair station, use two queue layers:

```text
Source queues (preserve line ownership)
  MANUAL_LINE:LINE-01 ─┐
  MANUAL_LINE:LINE-02 ─┼─> REPAIR_STATION:REPAIR-01 execution queue
  MANUAL_LINE:LINE-03 ─┘
```

The source queues remain separate for reporting, SLA, and accountability. MES creates the shared execution queue by referencing those cases; it does not merge their histories or change their return routes.

```text
MANUAL_LINE-01
  ├─ WAITING_REPAIR
  ├─ WAITING_PICKUP
  ├─ WAITING_RETEST
  ├─ BLOCKED
  └─ ESCALATED
```

## Queue object

```json
{
  "queueId": "RQ-MANUAL_LINE-01",
  "queueKey": "MANUAL_LINE:MANUAL_LINE-01",
  "lineCode": "MANUAL_LINE-01",
  "domain": "MANUAL_LINE",
  "queueVersion": 18,
  "capacity": 50,
  "policyVersion": 12,
  "items": [
    {
      "repairCaseId": "RC-20260807-000123",
      "workOrderId": "RWO-20260807-000123",
      "queueState": "WAITING_REPAIR",
      "priority": "HIGH",
      "enqueuedAt": "2026-08-07T10:30:00+07:00",
      "slaDueAt": "2026-08-07T12:30:00+07:00",
      "sourceStation": "ICT",
      "sourceLineCode": "MANUAL_LINE-01",
      "sourceQueueKey": "MANUAL_LINE:MANUAL_LINE-01",
      "targetStation": "REPAIR-01",
      "bucketQr": "BUCKET-QR-001",
      "quantity": 1,
      "claim": null
    }
  ]
}
```

## Queue states

- `WAITING_REPAIR`: issued and waiting for a repair operator.
- `IN_REPAIR`: claimed by one repair station/operator.
- `WAITING_PICKUP`: repair complete; line/team leader must collect it.
- `WAITING_RETEST`: returned and waiting for the destination station.
- `BLOCKED`: missing evidence, approval, material, bucket, or MES decision.
- `ESCALATED`: SLA breach or quality escalation.
- `DONE`: queue reference removed only after the `RepairCase` is closed; history retains the item.

## Ordering rules

1. MES selects the next item using `priority`, SLA risk, queue time, and configured station policy.
2. FIFO is the tie-breaker for equal priority and SLA risk.
3. An Agent may request the next item but cannot reorder or delete queue entries.
4. A queue item references exactly one `RepairCase` and one current handover.
5. Bucket QR and quantity must match the case at issue, receipt, pickup, and return.

## Shared repair-station rules

- The shared queue is keyed by `REPAIR_STATION:stationCode` and contains references, not copied cases.
- MES orders work using priority, SLA risk, age, approved line fairness, and material readiness.
- A line may not starve another line: configure a maximum consecutive claim count per source line.
- Every claim records `sourceLineCode`, `sourceQueueKey`, `repairCaseId`, operator, station, and policy version.
- The repair station must return the case to the source line recorded in the case; it may not select a different line.
- If the shared station is blocked, MES escalates the affected source lines separately.
- Reporting can show both views: source-line backlog and shared-station workload.

## Configurable MES priority policy

Priority is a versioned MES policy, not an Agent decision. A policy may combine:

```json
{
  "policyVersion": 12,
  "effectiveAt": "2026-08-07T08:00:00+07:00",
  "ordering": [
    "QUALITY_ESCALATION",
    "SLA_RISK",
    "SAFETY_OR_CUSTOMER_PRIORITY",
    "WAIT_TIME",
    "SOURCE_LINE_FAIRNESS"
  ],
  "weights": {
    "slaRisk": 50,
    "qualityEscalation": 30,
    "waitTime": 15,
    "lineFairness": 5
  },
  "maxConsecutiveClaimsPerLine": 3,
  "manualOverride": {
    "enabled": true,
    "requiredRole": "QUALITY_MANAGER",
    "reasonRequired": true
  }
}
```

MES records the policy version and score inputs on every claim. Authorized personnel may override priority only with a reason and audit event. Agents receive the published ordering and display it; they cannot edit it locally.

## Claim and concurrency

```text
unclaimed -> claimed -> acknowledged -> processing -> released
```

- Claim requires MES authorization and an atomic compare-and-set on `queueVersion`.
- Only one operator/station can hold a claim at a time.
- Claims expire by heartbeat or timeout and return to the queue with an audit event.
- Duplicate claim requests are idempotent by `eventId`.
- Agents never mark an item `DONE`; they submit facts and MES advances the queue.

## Offline behavior

Agents may cache the last published queue snapshot for display and append local pickup/repair facts to Outbox. They may not create, reorder, reprioritize, delete, or finalize queue entries while MES is offline. MES reconciles cached claims by `repairCaseId`, `eventId`, and `queueVersion` after recovery.

## Required MES views

- queue by line and domain;
- waiting repair / pickup / retest counts;
- SLA risk and escalations;
- current claim owner and heartbeat;
- bucket and quantity reconciliation;
- blocked reason and required approver;
- full queue and `RepairCase` history.
