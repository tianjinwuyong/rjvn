# Station Component Reservoir

This is the shared component reservoir for every manual-line and auto-line station Agent.

## Structure

```text
station-component-reservoir/
├─ catalog.json                 # Machine-readable component catalog
├─ station-map.json             # Station → component composition
├─ contracts/                   # Stable MES/Agent message contracts
│  ├─ station-identity.schema.json
│  └─ component-event.schema.json
├─ python/station_components/   # Reusable, UI-independent Python components
│  ├─ identity.py
│  ├─ scanner.py
│  ├─ alarm.py
│  ├─ language.py
│  ├─ authorization.py
│  └─ repair_policy.py
├─ adapters/                    # Compatibility path to existing station_*.py modules
├─ tests/                       # Offline tests; never write production MES data
└─ design/FIGMA.md              # Figma ownership and component-page mapping
```

## Component layers

1. **Foundation** — station identity, host IP, MES connection, health, diagnostics.
2. **Operator input** — scanner, manual input, authorization, language.
3. **Production control** — product gate, result ingestion, duplicate/NG decision display.
4. **Closed-loop workflow** — alarm, repair, retest, scrap, maintenance, escalation.
5. **Station-specific capability** — ICT/FCT/depanel/ATE/aging/binding equipment adapters.

## Rules

- MES owns production decisions; station components collect facts and execute/display decisions.
- Every event carries `lineCode`, `stationCode`, `stationInstance`, `hostname`, `hostIp`, and component version.
- Alarm history is visible, but only a newly observed alarm may trigger sound/flash/camera focus.
- Components are configurable by MES policy and can run with a last-known-good cached policy offline.
- Existing station modules are migrated through adapters; live Agents are not replaced in one risky step.

## First reusable components

| ID | Purpose | Shared by |
|---|---|---|
| `foundation.identity` | Station identity, hostname and host IP | All stations |
| `foundation.mes-connection` | MES availability, retry and offline state | All stations |
| `input.scanner` | Scanner normalization, duplicate guard and focus policy | All scan stations |
| `ui.language` | Chinese / English / Vietnamese catalog and completeness check | All stations |
| `security.authorization` | Operator role and privileged-action gates | All stations |
| `quality.alarm` | New-alarm detection, acknowledge and duration tracking | All stations |
| `quality.repair` | Repair trigger, dispatch timing, SLA, return and closure | All stations |
| `production.product-gate` | MES route/NG/duplicate decision presentation | All stations |
| `quality.policy-compliance` | Compare the published MES policy with local facts and report compliance | All stations |
| `quality.andon-escalation` | Evaluate overdue/mismatch facts into MES-owned Andon levels without closing the event locally | All stations |
| `operations.health` | Heartbeat, version, component health and diagnostics | All stations |

The authoritative full list is [catalog.json](./catalog.json); station compositions are in [station-map.json](./station-map.json).
