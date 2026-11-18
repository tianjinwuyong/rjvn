# MES NG 闭环参与者绩效与 Andon

MES records immutable facts for operators, team leaders, repair technicians, testers, QC/engineering approvers, and system accounts. Each record includes `eventId`, `repairCaseId`, `workOrderId`, participant ID/role/shift, station and host IP, action, timestamps, quantity/SN checks, evidence, SLA result, policy version, and sync state.

## Performance facts

- response: notification to pickup;
- handover accuracy: bucket QR, quantity, SN, and destination match;
- repair cycle: receive to repair complete;
- first-retest pass and repeat-repair rate;
- evidence completeness: steps, materials, measurements, images/logs;
- route compliance and station-jump exceptions;
- offline outbox reconciliation success/conflict rate.

Waiting for equipment, MES, material, or upstream handoff is classified as system wait, not personal delay. Metrics show sample size, time window, station, role, and policy version; they do not automatically punish, release, scrap, or change routing.

## Andon escalation

Delayed or missing actions create an immutable `andonEventId`. MES applies the published policy and escalates through `L0_INFO`, `L1_LINE`, `L2_SUPERVISOR`, `L3_ENGINEERING`, and `L4_MANAGEMENT`. Station Agents and PDAs only report facts, display/acknowledge notifications, and submit evidence. MES owns severity, recipients, timers, assignment, verification, and closure.

The shared implementation is `quality.andon-escalation` in the station component reservoir; its event contract is [andon-event.schema.json](../瑞晶越南工位-正式命名/station-component-reservoir/contracts/andon-event.schema.json). The detailed policy and state machine are in [mes-andon-escalation.md](mes-andon-escalation.md).

