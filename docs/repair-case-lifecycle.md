# MES RepairCase lifecycle

## Purpose

When MES issues a repair work order, it also creates one `RepairCase`. The case is the long-lived tracking object for the original NG and every related work order, handover, repair step, retest, return, approval, and final disposition.

The case is closed only by MES. Agents append facts; they do not close, delete, or rewrite the case.

## Core object

```json
{
  "repairCaseId": "RC-20260807-000123",
  "eventId": "ng-01J...",
  "workOrderId": "RWO-20260807-000123",
  "domain": "MANUAL_LINE",
  "status": "REPAIR_RECEIVED",
  "originalNg": {
    "station": "ICT",
    "sn": "TEST-SN-001",
    "defectCode": "DEFECT-CODE",
    "occurredAt": "2026-08-07T10:20:00+07:00",
    "evidenceRefs": []
  },
  "route": {
    "routeRevision": 7,
    "sourceStation": "ICT",
    "repairStation": "REPAIR-01",
    "returnStation": "ICT",
    "maxRetests": 2
  },
  "tracking": {
    "currentStation": "REPAIR-01",
    "currentOwner": "repair-team",
    "currentHostIp": "192.168.6.160",
    "currentBucketQr": "BUCKET-QR-001",
    "currentHandoverId": "handover-01J...",
    "lastEventAt": "2026-08-07T10:30:00+07:00",
    "lastEventId": "handover-01J...",
    "lastEventType": "REPAIR_RECEIVED",
    "lastActorId": "operator-001",
    "lastActorRole": "REPAIR_OPERATOR",
    "sequenceNo": 2,
    "stateVersion": 4,
    "routeDecisionId": "route-01J...",
    "slaDueAt": "2026-08-07T12:30:00+07:00",
    "pickupNotifiedAt": null,
    "mesSyncState": "SYNCED",
    "outboxPendingCount": 0,
    "correlationId": "corr-01J..."
  },
  "counts": {
    "repairCycles": 1,
    "retestAttempts": 0,
    "quantityAssigned": 1,
    "quantityReceived": 1,
    "quantityReturned": 0
  },
  "approvals": [],
  "evidenceRefs": [],
  "historyEventIds": ["ng-01J...", "handover-01J..."],
  "createdAt": "2026-08-07T10:30:00+07:00",
  "closedAt": null,
  "configurationVersion": 12
}
```

## Lifecycle

```text
NG_CONFIRMED
  -> WO_ISSUED
  -> REPAIR_RECEIVED
  -> IN_REPAIR
  -> WAITING_RETEST
  -> RETURN_PENDING
  -> RETURN_RECEIVED
  -> CLOSED
```

Exceptional states are `BLOCKED`, `ESCALATED`, `AUTHORIZED_SCRAP`, `REPLACED`, and `CANCELLED_BY_MES`. They require an authorized reason and remain in history.

## Transition ownership

| Transition | MES responsibility | Agent responsibility |
|---|---|---|
| `NG_CONFIRMED -> WO_ISSUED` | Create `RepairCase`, work order, route revision, and event IDs | Submit NG facts and trigger request |
| `WO_ISSUED -> REPAIR_RECEIVED` | Validate route, SN, bucket, and quantity | Scan and report physical receipt |
| `REPAIR_RECEIVED -> IN_REPAIR` | Authorize repair start | Record operator and start time |
| `IN_REPAIR -> WAITING_RETEST` | Validate steps/materials and authorize retest | Append repair evidence and measurements |
| `WAITING_RETEST -> RETURN_PENDING` | Decide destination and retest limit | Submit retest result |
| `RETURN_PENDING -> RETURN_RECEIVED` | Validate return handover | Scan destination receipt |
| `RETURN_RECEIVED -> CLOSED` | Verify final result and approvals | Report station result; never self-close |

## Invariants

- `repairCaseId`, original `eventId`, and original NG are immutable.
- Every transition has a new immutable event ID and actor.
- `currentStation` and `currentOwner` always identify where the case is waiting.
- `currentHostIp`, `currentBucketQr`, and `currentHandoverId` identify the physical custody point.
- `sequenceNo` increases once per accepted event; `stateVersion` increases once per state transition.
- `lastEventId`, `lastEventType`, actor, station, and timestamp are updated atomically with the state transition.
- `routeDecisionId` and `slaDueAt` identify the MES decision and its deadline.
- `mesSyncState` and `outboxPendingCount` make MES recovery and unsynchronized evidence visible.
- `retestAttempts` cannot exceed the MES-published `maxRetests`.
- A later PASS creates a new result event; it never deletes the original NG.
- A case cannot close without destination receipt, required evidence, and MES authorization.
- A case cannot be simultaneously owned by two stations.
- MES-down events remain in the local Outbox and do not create final closure.

## Queries and monitoring

MES should expose case views for:

- active cases by station, bucket, owner, and SLA;
- cases waiting for pickup or return receipt;
- cases blocked by missing evidence or approval;
- retest attempts and repeated NG cycles;
- full event history by SN, `repairCaseId`, `workOrderId`, or `eventId`.
