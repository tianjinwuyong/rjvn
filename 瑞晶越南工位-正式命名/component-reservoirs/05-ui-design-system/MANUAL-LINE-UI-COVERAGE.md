# Manual Line UI Migration

Priority: manual line first. Auto line, MES, PDA and Android source migrations are frozen except for shared design-system work.

| Station / surface | UI family | Interaction | Font | Color | Layout | Balance | Motion | Current migration |
|---|---|---|---|---|---|---|---|---|
| 01 PDA incoming/load | Compose + Python | audit | audit | audit | audit | audit | audit | not started |
| 02 AOI quality/MySQL | Tk | shared new-only alarm | fail: mojibake | audit | fail: 720x340 | audit | alarm pass | in progress |
| 03 ICT motherboard 3x4 | Tk + Qt | arrival UI disabled: backend gap | Figma mapped | Figma mapped | 1366x768 mapped | pass | specified | backend arrival integration missing |
| 04 FCT | Tk + Qt | arrival UI disabled: backend gap | fail: incomplete | audit | audit | audit | alarm pass | backend arrival integration missing |
| 05 depanel | Tk + Qt | arrival UI disabled: backend gap | fail: incomplete | audit | audit | audit | alarm pass | backend arrival integration missing |
| 06 shell binding | Tk + Qt | arrival UI disabled: backend gap | fail: incomplete | audit | audit | audit | alarm pass | backend arrival integration missing |
| 07 assembly ATE | Tk + Qt | shared Arrival & Route + scanner focus | fail: mojibake | shared tokens | 1366x768 Tk pass | actual source reviewed | alarm pass | arrival preview verified |
| 08 supersonic | Tk + Qt | scanner focus + preview pass | partial: labels need review | shared tokens | 1366x768 Tk pass | actual source reviewed | alarm pass | Tk preview verified |
| 09 aging cabinets | Tk + Qt | write-blocked preview pass | partial: labels need review | shared tokens | 1366x768 Tk pass | 7-cab actual source reviewed | alarm pass | Tk preview verified |
| 10 high-voltage ATE | Tk + Qt | shared new-only alarm; focus pending | fail: mojibake | audit | fail: 1500x900 | audit | alarm pass | in progress |
| 11 packaging ATE | Tk + Qt | shared new-only alarm; focus pending | fail: mojibake | audit | fail: 1500x900 | audit | alarm pass | in progress |
| 12 outer-box binding | Tk + Qt | Figma mapped | Figma mapped | Figma mapped | 1366x768 mapped | pass | specified | source pending |
| 13 pallet binding | Tk + Qt | scanner focus + write-blocked preview | partial: labels need review | shared tokens | 1366x768 Tk pass | action-strip overlap fixed | audit | Tk preview verified |
| Shared repair station/workflow | Tk/MES | focus theft found | fail: mojibake | audit | overlay collision risk | audit | audit | not started |
| Shared auth/config/diagnostics dialogs | Tk + Qt | audit | audit | audit | audit | audit | audit | not started |

## Implemented shared reach

`station_alarm.py` now supplies calm new-only presentation to AOI, FCT, depanel and shell binding.  
`station_scan_alarm.py` now supplies calm new-only presentation to assembly ATE, supersonic, aging, high-voltage ATE and packaging ATE.

Both paths:

- suppress repeated presentation of the same status/SN/detail event during the retained session;
- give one brief topmost/taskbar/audio cue;
- remain persistently visible without looping flash, repeated voice or repeated lift;
- do not grab or force scanner focus;
- preserve existing MES reporting and release callbacks.

## Acceptance evidence

- Actual Agent source was launched only with `UI_PREVIEW=1` for stations marked preview verified.
- Preview mode uses deterministic sample state, visibly watermarks the window, skips production core/store creation and disables heartbeat, MES sync, device/scanner listeners and repair/retest integrations.
- No MES, scanner, equipment or database write was performed.
- Actual source captures:
  - Assembly ATE: `outputs/station-ui-progress/actual-assembly-ate-preview-1366x768.png`
  - Assembly ATE shared arrival component: `outputs/station-ui-progress/actual-assembly-ate-arrival-preview-1366x768.png`
  - Assembly ATE Product Gate: `outputs/station-ui-progress/actual-assembly-product-gate-preview-1366x768.png`
  - Arrival route timeline/details: `outputs/station-ui-progress/actual-arrival-route-details-preview.png`
  - Supersonic: `outputs/station-ui-progress/actual-supersonic-preview-1366x768.png`
  - Aging cabinets: `outputs/station-ui-progress/actual-aging-cab-preview-1366x768.png`
  - Pallet binding: `outputs/station-ui-progress/actual-pallet-binding-preview-1366x768.png`
- Design references only (not implementation proof):
  - ICT: `outputs/station-ui-progress/ict-standardized.png`
  - Outer-box: `outputs/station-ui-progress/outer-box-48sn-processing.png`
  - Alarm lifecycle: `outputs/station-ui-progress/alarm-motion-lifecycle-spec.png`

## Arrival decision contract represented by the shared UI

The UI renders an explicit backend decision and never infers a route jump merely from an unexpected arrival:

- expected next;
- early/unexpected arrival;
- duplicate network replay;
- same-station rescan;
- blocked forward jump with missing stations;
- authorized process exemption;
- authorized repair/retest return;
- active-NG block;
- offline decision pending;
- route-version mismatch.

## Product Gate migration safety

The compact shared panel consumes existing snapshot evidence only. It displays product identity (`PCBA` or `SHELL`), explicit gate result (`ALLOW`, `HOLD`, `REJECT`, `REPAIR_ROUTE`, `COMPLETED`), reason and next required action. It does not calculate or write a decision.

- Safe Tk consumers with existing `StationArrivalStore` snapshot evidence: 07 Assembly ATE, 08 Supersonic, 09 Aging, 10 High-voltage ATE, 11 Packaging ATE, 12 Outer-box binding and 13 Pallet binding.
- 01 PDA and 02 AOI have arrival evidence but their primary screens are Streamlit; they need a Streamlit presentation adapter rather than importing the Tk component.
- Qt/3D station views need a Qt presentation adapter over the same read-only contract.
- 03 ICT, 04 FCT, 05 Depanel and 06 Shell binding lack arrival backend integration. They may show only a disabled `UNKNOWN / backend gap` placeholder until that backend gap is closed.

### Product Gate implementation coverage

- 01 PDA: lightweight Streamlit Product Gate added; explicitly `UNKNOWN / BACKEND GAP` because its current snapshot does not supply a gate decision.
- 02 AOI: lightweight Streamlit Product Gate added; explicitly `UNKNOWN / BACKEND GAP` because its current snapshot does not supply a gate decision.
- 03 ICT: visible disabled Tk Product Gate placeholder; `UNKNOWN / BACKEND GAP`, no local `ALLOW`.
- 04 FCT: visible disabled Tk Product Gate placeholder; `UNKNOWN / BACKEND GAP`, no local `ALLOW`.
- 05 Depanel: visible disabled Qt Product Gate placeholder; `UNKNOWN / BACKEND GAP`, no local `ALLOW`.
- 06 Shell binding: visible disabled Tk Product Gate placeholder; `UNKNOWN / BACKEND GAP`, no local `ALLOW`.
- 07 Assembly ATE: integrated; legacy pre-arrival/arrival/exception tabs and fill code removed.
- 08 Supersonic: integrated; legacy arrival/arrival-exception tabs and fill code removed.
- 09 Aging: integrated using existing arrival snapshot.
- 10 High-voltage ATE: integrated; legacy pre-arrival/arrival/exception tabs and fill code removed.
- 11 Packaging ATE: integrated; legacy pre-arrival/arrival/exception tabs and fill code removed.
- 12 Outer-box binding: integrated read-only through existing arrival store; arrival resource ledgers are no longer Agent-facing.
- 13 Pallet binding: integrated read-only through existing arrival store; arrival resource tabs are no longer Agent-facing.
- Product Gate Trace contains decision audit only: time, identity, gate, reason, action, authorization/reference, plus compact route when supplied. Backend database evidence remains unchanged.
- Trace decision audit now includes a horizontal scrollbar and wider Reason/Action/Auth columns for the 1120px window.
- 03–06 were not given invented route data or a false integrated state.

Authorized exemption and repair/retest return use calm authorization styling, not an NG alarm treatment. Missing decision evidence is shown as `DECISION UNKNOWN`, and stations 03–06 remain explicit backend gaps.
