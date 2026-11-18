# MES NG Management Center

## Goal

Provide one MES-owned page for configuring and supervising NG routing, repair-order triggers, shared repair queues, retest limits, approvals, and audit history. Station Agents consume the published configuration; they do not edit it.

## Page layout

```text
NG Management
├─ Scope: Domain / Line / Product / Station
├─ Overview: active NG, repair backlog, SLA risk, blocked cases
├─ Routing Rules
├─ Repair-Order Triggers
├─ Priority & Queue Policy
├─ Retest & Disposition
├─ Approvals & Roles
├─ Simulation / Impact Preview
├─ Drafts and Published Versions
└─ Audit History
```

## Configuration sections

### 1. Scope selector

- Domain: `MANUAL_LINE`, `AUTO_LINE`, or another MES domain.
- Line: one or more lines in the selected domain.
- Product/work-order scope.
- Source station and shared repair station.
- Effective time and configuration owner.

The page must show the resulting `queueKey` and route scope before saving.

### 2. NG routing

- source station;
- allowed NG reason codes;
- repair destination;
- return station;
- alternate route and escalation route;
- route revision;
- maximum repair cycles;
- required evidence and approvals;
- block, scrap, replace, or special-release permissions.

### 3. Repair-order triggers

- manual button;
- elapsed time threshold;
- pending NG quantity threshold;
- dispatch period;
- `ANY` or `ALL` combination mode;
- dispatch window and end-of-shift behavior;
- minimum bucket quantity;
- notification recipients.

### 4. Priority and shared queue

- quality escalation weight;
- SLA-risk weight;
- customer/safety priority;
- waiting-time weight;
- source-line fairness weight;
- maximum consecutive claims per line;
- capacity and overflow queue;
- pickup and retest escalation timers.

### 5. Retest and disposition

- maximum retest attempts;
- required retest station;
- approval role for each attempt;
- return-to-source rule;
- special release requirements;
- authorized scrap/replacement reasons.

## Safe workflow

```text
Edit draft
  -> Validate fields and permissions
  -> Simulate representative NG paths
  -> Show impact: affected lines, queues, agents, and open cases
  -> Require approval
  -> Publish immutable version
  -> Agents synchronize read-only snapshot
  -> Monitor adoption and conflicts
```

Publishing must not silently alter active cases. Existing `RepairCase` objects keep the route revision that created them; the new policy applies according to its effective time and MES migration rules.

## Permissions

| Role | View | Edit draft | Simulate | Approve | Publish | Emergency rollback |
|---|---:|---:|---:|---:|---:|---:|
| Operator | Own cases | No | No | No | No | No |
| Line leader | Domain scope | Limited | Yes | No | No | No |
| Quality engineer | Domain scope | Yes | Yes | Yes | No | No |
| MES administrator | All domains | Yes | Yes | Yes | Yes | Yes |
| Plant manager | All domains | No | Yes | Yes | By policy | By policy |

Every edit, simulation, approval, publish, rollback, and emergency override records user, role, reason, timestamp, previous version, and new version.

## UI safety requirements

- Never expose a destructive action without an explicit reason and permission check.
- Show a visible `DRAFT`, `PUBLISHED`, `SUPERSEDED`, or `ROLLED_BACK` status.
- Display route diagrams and queue impact before publish.
- Show validation errors next to fields and provide a complete summary before confirmation.
- Support Chinese, English, and Vietnamese for every label, state, error, and dialog.
- Do not rely on color alone for NG, blocked, escalated, or offline status.
- Provide loading, error, empty, and stale-data states.

## API boundary

The page should call MES APIs such as:

- `GET /mes/ng-management/scopes`
- `GET /mes/ng-management/configurations/{scope}`
- `POST /mes/ng-management/configurations/drafts`
- `POST /mes/ng-management/configurations/{id}/validate`
- `POST /mes/ng-management/configurations/{id}/simulate`
- `POST /mes/ng-management/configurations/{id}/approve`
- `POST /mes/ng-management/configurations/{id}/publish`
- `POST /mes/ng-management/configurations/{id}/rollback`
- `GET /mes/ng-management/audit`

All write APIs require idempotency keys, authorization, configuration version checks, and append-only audit events.
