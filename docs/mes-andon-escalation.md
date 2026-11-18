# MES Andon escalation system

## Purpose

Andon turns a missing action, delayed handoff, route violation, equipment fault, or MES-sync failure into a visible, owned, time-bound escalation. It is an operational control loop, not a replacement for MES quality authority.

## Trigger sources

MES evaluates immutable facts from stations, PDA, repair, and its own timers:

- NG bucket or repair work order not picked up before its configured SLA;
- handover started but not accepted, or quantity/SN/bucket QR mismatch;
- repair received but no repair start, pause/resume, or completion action within the configured window;
- repair or retest exceeds SLA, maximum waiting time, or configured quantity/time trigger;
- missing return acknowledgement from ICT, FCT, depanel, aging, or another destination;
- station jumping, wrong work order/product, duplicate scan, or unauthorized action;
- heartbeat, MES connection, device, or Outbox recovery failure;
- participant action required but not acknowledged.

Each trigger creates a unique `andonEventId` and references `repairCaseId`, `workOrderId`, `eventId`, `stationCode`, `lineCode`, `domainCode`, policy version, and the measured deadline.

## Escalation levels

| Level | Meaning | First owner | Escalation action |
|---|---|---|---|
| `L0_INFO` | Early warning; work is still within grace period | Assigned operator/team leader | In-app banner and acknowledgement timer |
| `L1_LINE` | Action overdue or local abnormality | Team leader / line leader | PDA push, audible station banner, acknowledge and assign owner |
| `L2_SUPERVISOR` | SLA breach, repeated mismatch, or blocked queue | Production/QC supervisor | MES Kanban red card, PDA push, escalation timer, reason required |
| `L3_ENGINEERING` | Route violation, repeated NG, equipment/data integrity, or safety risk | Engineering/QC manager | Engineering queue, evidence lock, approval required |
| `L4_MANAGEMENT` | Cross-line outage, prolonged MES-down condition, or unresolved critical event | Plant/quality manager | Management alert, incident record, controlled stop/hold decision |

Severity and level are policy-configurable in MES, but an Agent cannot lower a level or close an event. Safety and data-integrity events bypass grace periods.

## State machine

```text
TRIGGERED -> ACKNOWLEDGED -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> VERIFIED -> CLOSED
     |            |             |             |
     +---------- ESCALATED <---+-------------+
```

- `ACKNOWLEDGED` identifies who saw the event; it does not mean the problem is fixed.
- `ASSIGNED` names the responsible role/person and due time.
- `RESOLVED` requires evidence and a reference to the repaired/accepted event.
- `VERIFIED` is performed by MES or an authorized verifier; quality disposition remains separate.
- `CLOSED` is append-only and requires a closure reason.
- A timer may create an escalation event, but never silently overwrite the prior state.

## Notification channels

1. Station Agent: non-blocking banner, severity color, sound policy, and local acknowledgement.
2. Team-leader PDA: push notification with station, bucket QR, quantity, SN summary, destination, due time, and one-tap claim.
3. MES Kanban: lane, severity, age, owner, next escalation, and evidence links.
4. Line/plant management: summarized alerts with deduplication and escalation history.
5. Offline: the Agent records the alert and acknowledgement in the immutable Outbox; it must not claim MES delivery until acknowledged after recovery.

## Required event fields

```json
{
  "andonEventId": "andon-01J...",
  "triggerType": "PICKUP_SLA_BREACH",
  "severity": "L1_LINE",
  "status": "ACKNOWLEDGED",
  "repairCaseId": "rc-01J...",
  "workOrderId": "wo-01J...",
  "stationCode": "REPAIR",
  "lineCode": "MANUAL-1",
  "domainCode": "MANUAL_LINE",
  "bucketQr": "BKT-0042",
  "expectedQuantity": 8,
  "observedQuantity": 8,
  "triggeredAt": "2026-08-07T10:00:00Z",
  "dueAt": "2026-08-07T10:05:00Z",
  "acknowledgedBy": "TL-023",
  "assignedTo": "LINE-LEADER-02",
  "policyVersion": "andon-policy-v3",
  "evidenceEventIds": ["ppe-01J..."],
  "nextEscalationAt": "2026-08-07T10:10:00Z",
  "syncState": "ACKED"
}
```

## Governance rules

- MES owns trigger policies, severity, recipients, grace periods, escalation timers, and closure authority.
- MES owns every NG route state and transition. Agents may report facts or execute an acknowledged MES command, but may not advance, rewind, skip, or close the NG route locally.
- Every Andon and NG-loop event carries `domainCode`, `lineCode`, and `stationCode`; MES rejects a cross-domain handover unless an authorized domain-transfer decision is present.
- Every MES command has a feedback event keyed by `commandId`: `RECEIVED`, `ACCEPTED`, `EXECUTED`, `REJECTED`, or `BLOCKED`, with actor, reason, timestamp, and resulting `eventId`. A command without feedback remains pending and is eligible for Andon escalation.
- Agents and PDAs report observations and execute acknowledged notifications; they do not change routing, retest limits, final disposition, or severity.
- Every policy change requires authorized user, reason, version, effective time, and audit record.
- Duplicate alerts are correlated by stable fingerprint, but every escalation transition remains historical.
- A late action is still recorded against the original deadline; acknowledgement does not erase lateness.
- Metrics distinguish participant delay, station/device delay, MES outage, material wait, and upstream wait.

## Core MES tables

- `andon_policies`: trigger, severity, grace period, escalation chain, channels, effective version;
- `andon_events`: immutable trigger and current projection;
- `andon_transitions`: acknowledge/assign/escalate/resolve/verify/close history;
- `andon_recipients`: role, user, PDA, line, domain, channel and quiet-hours policy;
- `andon_evidence`: event IDs, images, measurements, logs, bucket/SN evidence;
- `andon_notifications`: delivery attempts, acknowledgement, retry and failure;
- `andon_sla_clock`: due time, paused reason, excluded system-wait intervals;
- `andon_outbox`: offline events and idempotent recovery state.

## Acceptance checks

1. A pickup that passes its grace period creates one `andonEventId` and notifies the configured L1 owner.
2. No acknowledgement escalates at the configured time; acknowledgement alone does not close it.
3. A quantity/SN mismatch escalates immediately and blocks the handover until MES decides.
4. A MES outage shows offline state and stores the alert locally; recovery uploads by idempotent `eventId`.
5. Historical alerts do not replay on Agent restart.
6. Resolution requires evidence and authorized verification; final quality release remains a separate MES action.
