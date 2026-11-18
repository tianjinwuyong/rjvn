# Local Resource Inspection

Inspection scope: current manual-line, auto-line, MES web/API/worker, WMS/QMS, PDA, Android employee app and Figma resources on this computer.

## Executive result

| Reservoir | Local evidence | Assessment | Required consolidation |
|---|---|---|---|
| Station Agent | Manual and auto station folders 01–13 plus shared `station_*.py` modules | Broad coverage; shared runtime is much richer on manual line | Extract adapters; remove duplicated runtime; make auto/manual use the same contracts |
| MES Management | `smt-factory-system/apps/web/src/mes`, API modules and worker services | Repair, retest, scrap, station monitoring and warehouse functions exist | Register components, define ownership, connect events into one product/NG lifecycle |
| PDA | PDA station source, API module, worker receiving/IQC and APK builds | Receiving, IQC and station scanning exist in several places | One PDA workflow catalog and one offline/idempotency contract |
| Android App | `apps/employee-app` and Android material-loader projects | Employee app and material workflows exist | Separate employee app from industrial PDA; reuse shared identity/task contracts |
| UI Design System | Figma file plus repeated Tk/Qt/React/Compose components | Valuable patterns exist but are duplicated | Canonical tokens/components/states with channel-specific implementations |

## Station Agent evidence

Manual shared modules already cover alarm, arrival, ATE UI, contracts, data sync, domain, Excel events/safety, heartbeat, history, i18n/language, maintenance, repair, retest, runtime safety, scan alarm and scrap.

Auto shared modules currently cover alarm, domain, Excel events/safety, language, repair adapter, retest and scan alarm. Missing parity must be supplied from the shared reservoir rather than copied again.

All production stations 01–13 exist for both lines; auto packaging has left/right instances.

## Repair-station evidence

Existing MES screens:

- `smt-factory-system/apps/web/src/mes/RepairStation.tsx`
- `smt-factory-system/apps/web/src/mes/RepairWorkflow.tsx`
- `smt-factory-system/apps/web/src/mes/ReworkDashboard.tsx`
- `smt-factory-system/apps/web/src/mes/RetestRules.tsx`
- `smt-factory-system/apps/web/src/mes/ScrapRegistration.tsx`

Existing station runtime:

- `瑞晶越南工位-正式命名/004-手动线/station_repair_workflow.py`
- `瑞晶越南工位-正式命名/004-手动线/station_retest.py`
- `瑞晶越南工位-正式命名/004-手动线/station_scrap_workflow.py`

Conclusion: repair capability exists in fragments. The reservoir now registers `quality.repair-workbench` as an independent shared-service station. The remaining work is contract alignment and end-to-end acceptance, not inventing another disconnected screen.

## Incoming inspection / IQC evidence

Existing WMS and QMS screens:

- `smt-factory-system/apps/web/src/wms/WmsIncoming.tsx`
- `smt-factory-system/apps/web/src/wms/WmsIqcInspection.tsx`
- `smt-factory-system/apps/web/src/wms/WmsIqcStandards.tsx`
- `smt-factory-system/apps/web/src/wms/WmsIqcReport.tsx`
- `smt-factory-system/apps/web/src/wms/WmsIqcClosedLoop.tsx`
- `smt-factory-system/apps/web/src/qms/QmsIqc.tsx`
- `smt-factory-system/apps/web/src/qms/QmsIqcCockpit.tsx`
- `smt-factory-system/apps/web/src/qms/QmsIqcAndon.tsx`
- `smt-factory-system/apps/web/src/qms/iqcOfflineQueue.ts`

Existing PDA/worker resources:

- `smt-factory-system/apps/web/src/wms/WmsPdaReceiving.tsx`
- `smt-factory-system/apps/web/src/wms/WmsPdaIqc.tsx`
- `smt-factory-system/services/worker/pda-receiving.js`
- `smt-factory-system/services/worker/pda-iqc.js`
- `smt-factory-system/services/api/src/modules/pda/index.ts`

Conclusion: IQC has substantial local implementation but overlapping entry points. The canonical component is now `quality.incoming-inspection`; WMS owns stock hold/release, QMS owns inspection standards/results/NCR, MES owns work-order/product impact, and PDA performs receipt/evidence capture.

## Canonical closed loops

### Repair

Confirmed NG → repair order activated → assigned → received → diagnosed → repaired → retest → PASS return to route / NG escalation or scrap → MES closure.

### Incoming inspection

Receipt → lot/QR registration → sampling plan → inspection and documents → PASS release / NG hold + NCR → disposition → WMS stock state and supplier history updated → closure.

## Local safety finding

Compiled outputs, backups and `node_modules` must never be treated as source assets. Catalog evidence points to maintained source files only. No production Agent or MES process was started during this inspection.
