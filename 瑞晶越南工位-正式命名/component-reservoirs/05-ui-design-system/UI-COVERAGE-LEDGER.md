# Ruijing Unified UI Coverage Ledger

Source of truth: `UNIFIED-UI-STANDARD.md`  
Figma: https://www.figma.com/design/v2uY2e6CuXjVumyk5ZDgEb

Status values: `mapped`, `migrating`, `audit`, `exception`. A row is complete only when Interaction, Font, Color, Layout, Balance, and Motion all pass.

## Canonical component IDs

| ID | Component |
|---|---|
| UI-STS-001 | Station header, host/IP, operator, language and role |
| UI-ALT-001 | Reserved alarm/status banner; new event cue only |
| UI-INP-001 | Scanner input and stable focus contract |
| UI-MES-001 | Work order/product/MES policy rail |
| UI-HLT-001 | Scanner/equipment/MES/outbox/clock health strip |
| UI-AUT-001 | Authorization requirement and approval context |
| UI-RPR-001 | Repair policy and repair workflow drawer |
| UI-SNG-001 | Non-overlapping SN layout board |
| UI-BND-001 | 48-SN case grid |
| UI-CFG-001 | Versioned configuration drawer |
| UI-DIA-001 | Diagnostics drawer |
| UI-PRN-001 | Print state, template and reprint audit |
| UI-UPD-001 | Agent update/version state |

## Production stations

| Line / page | Framework | Canonical workflow components | Status | Interaction | Font zh/en/vi | Color | Layout | Balance | Motion | Evidence / exception |
|---|---|---|---|---|---|---|---|---|---|---|
| Manual PDA incoming/load | Android Compose + Python | STS, INP, MES, HLT, AUT | audit | audit | audit | audit | mobile | audit | audit | Startup entry must be pinned |
| Manual AOI quality / MySQL | Tk | STS, ALT, INP, MES, HLT, AUT, RPR | migrating | audit | fail: mojibake | audit | fail: 720x340 | audit | audit | Shared i18n dependency and geometry |
| Manual ICT 3x4 motherboard | Tk + Qt 3D | STS, ALT, INP, MES, HLT, SNG, AUT, RPR | mapped | mapped | mapped in Figma | mapped | mapped 1366x768 | mapped | specified | Figma 3:3, 4:2, 3:135, 3:269, 3:401, 4:134, 3:533 |
| Manual FCT | Tk + Qt 3D | STS, ALT, INP, MES, HLT, AUT, RPR | audit | audit | fail: incomplete | audit | audit | audit | audit | Station-local tabs and focus behavior |
| Manual PCBA depanel | Tk + Qt 3D | STS, ALT, INP, MES, HLT, AUT, RPR | audit | audit | fail: incomplete | audit | audit | audit | audit | Immediate-removal state required |
| Manual PCBA shell binding | Tk + Qt 3D | STS, ALT, INP, MES, HLT, AUT, RPR | audit | audit | fail: incomplete | audit | audit | audit | audit | Multiple modal grabs |
| Manual Assembly ATE | Tk + Qt 3D | STS, ALT, INP, MES, HLT, SNG, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | Multi-SN board |
| Manual Supersonic | Tk + Qt 3D | STS, ALT, INP, MES, HLT, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | Mark-only exception; SQL result |
| Manual aging cabinets | Tk + Qt 3D | STS, ALT, INP, MES, HLT, RPR | audit | audit | fail: mojibake | audit | fail: 1600x920 | audit | audit | Seven cabinet/slot progress model |
| Manual high-voltage ATE | Tk + Qt 3D | STS, ALT, INP, MES, HLT, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | A-T-E voice convention |
| Manual packaging ATE | Tk + Qt 3D | STS, ALT, INP, MES, HLT, SNG, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | Multi-SN board |
| Manual outer-box binding 48 SN | Tk + Qt 3D | STS, ALT, INP, MES, HLT, BND, PRN, RPR | mapped | mapped | mapped in Figma | mapped | mapped 1366x768 | mapped | specified | Figma 5:2, 5:239, 5:476, 5:713, 5:950, 5:1187, 5:1444 |
| Manual pallet binding | Tk + Qt 3D | STS, ALT, INP, MES, HLT, PRN, RPR | migrating | audit | fail: mojibake | audit | fail: 1420x800 | fail: dual grid | audit | Confirm/retest overlap reported |
| Auto PDA incoming/load | Android Compose + Python | STS, INP, MES, HLT, AUT | audit | audit | audit | audit | mobile | audit | audit | Startup entry must be pinned |
| Auto AOI quality / MySQL | Tk | STS, ALT, INP, MES, HLT, AUT, RPR | migrating | audit | fail: mojibake | audit | fail: 720x340 | audit | audit | No packaged spec; missing local i18n module |
| Auto ICT 3x4 motherboard | Tk + Qt 3D | STS, ALT, INP, MES, HLT, SNG, AUT, RPR | mapped | mapped by family | mapped in Figma | mapped | mapped | mapped | specified | Manual/auto parity; host/line differ |
| Auto FCT | Tk + Qt 3D | STS, ALT, INP, MES, HLT, AUT, RPR | audit | audit | fail: incomplete | audit | audit | audit | audit | Shared topmost paths |
| Auto PCBA depanel | Tk + Qt 3D | STS, ALT, INP, MES, HLT, AUT, RPR | audit | audit | fail: incomplete | audit | audit | audit | audit | Immediate-removal state required |
| Auto PCBA shell binding | Tk + Qt 3D | STS, ALT, INP, MES, HLT, AUT, RPR | audit | audit | fail: incomplete | audit | audit | audit | audit | Multiple modal grabs |
| Auto Assembly ATE | Tk + Qt 3D | STS, ALT, INP, MES, HLT, SNG, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | Multi-SN board |
| Auto Supersonic | Tk + Qt 3D | STS, ALT, INP, MES, HLT, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | Mark-only exception; SQL result |
| Auto aging tunnel/equipment | Tk + Qt 3D | STS, ALT, INP, MES, HLT, RPR | audit | audit | fail: mojibake | audit | fail: 1600x920 | audit | audit | Must not reuse manual cabinet geometry |
| Auto high-voltage ATE | Tk + Qt 3D | STS, ALT, INP, MES, HLT, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | A-T-E voice convention |
| Auto packaging ATE left | Tk + Qt 3D | STS, ALT, INP, MES, HLT, SNG, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | Independent host/station identity |
| Auto packaging ATE right | Tk + Qt 3D | STS, ALT, INP, MES, HLT, SNG, RPR | audit | fail: scan refocus | fail: mojibake | audit | fail: 1500x900 | audit | audit | Independent host/station identity |
| Auto outer-box binding 48 SN | Tk + Qt 3D | STS, ALT, INP, MES, HLT, BND, PRN, RPR | mapped | mapped by family | mapped in Figma | mapped | mapped | mapped | specified | Same case contract; auto station identity |
| Auto pallet binding | Tk + Qt 3D | STS, ALT, INP, MES, HLT, PRN, RPR | migrating | audit | fail: mojibake | audit | fail: fixed width | audit | audit | Confirm/retest layout family |
| Repair station / repair orders | Tk/MES | STS, ALT, INP, MES, HLT, AUT, RPR | audit | audit | fail: shared mojibake | audit | audit | audit | audit | Receipt, repair, return and retest states |

## Management and employee surfaces

| Surface | Framework | Components | Status | Interaction | Font | Color | Layout | Balance | Motion | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| MES product flow | React | STS, MES, SNG, QRY, CFG | audit | audit | audit | audit | desktop | audit | audit | Product is primary theme |
| MES NG/repair/alarm management | React | ALT, AUT, RPR, QRY, CFG | audit | audit | audit | audit | desktop | audit | audit | Immutable history and SLA |
| MES station inventory/health | React | STS, HLT, DIA, UPD | audit | audit | audit | audit | desktop | audit | audit | Host IP/source IP/version |
| WMS warehouse/storage 3D | React/Three | QRY, AUT, HLT | audit | audit | audit | audit | desktop/fullscreen | audit | audit | Camera overview priority |
| PDA receiving/placement/consumption | Web/Android | INP, AUT, HLT | audit | audit | audit | audit | mobile | audit | audit | 48dp touch targets |
| Android employee app pages | Compose | AUT, STS | audit | audit | audit | audit | mobile | audit | audit | Employee language and role |
| Shared auth dialog | Tk/Qt/Web/Compose | AUT | audit | audit | audit | audit | responsive | audit | audit | Never discard scan context |
| Shared repair/config/query drawers | Tk/Qt/Web | RPR, CFG, QRY | audit | audit | audit | audit | responsive | audit | audit | Scanner/result stay visible |

## Motion contract

- Entry/state transition: 120-240 ms ease-out.
- Exit: 120-200 ms ease-in.
- Slot fill, progress, drawer and 3D camera navigation are interruptible.
- Reduced-motion mode replaces transitions with immediate state changes.
- No loop, flash, focus theft, scan delay, or animation for historical alarms.

## Current blockers

1. Existing shared Chinese/Vietnamese source dictionaries contain mojibake; correction requires a verified terminology source, not automated guessing.
2. Figma Starter plan limits the file to three pages, so sections consolidate the planned five-page information architecture.
3. Qt/3D entries lack a shared trilingual/repair adapter and require a separate UI-family migration.
4. Pixel acceptance must be run one GUI at a time on isolated/offline fixtures; production agents must not be launched for visual tests.
