# Factory UI Design-System Bricks

Figma source: https://www.figma.com/design/v2uY2e6CuXjVumyk5ZDgEb

Mandatory cross-channel specification: [UNIFIED-UI-STANDARD.md](./UNIFIED-UI-STANDARD.md)

## Foundations

- `UI-FND-001 Semantic Color` — neutral, active, PASS, attention, new NG and offline.
- `UI-FND-002 Typography` — Chinese/English/Vietnamese expansion and industrial readability.
- `UI-FND-003 Spacing + Grid` — 1366×768 first, 44px glove-safe controls.
- `UI-FND-004 Motion + Focus` — no looping flash; new alarm only; user overview has priority.

## Components

- `UI-INP-001 Scanner Input`
- `UI-STS-001 Station Header + Identity`
- `UI-MES-001 MES Context Rail`
- `UI-HLT-001 Health Strip`
- `UI-ALT-001 Reserved Alarm Banner`
- `UI-AUT-001 Authorization Dialog`
- `UI-RPR-001 Repair Policy + Workflow`
- `UI-SNG-001 SN Layout Board`
- `UI-BND-001 48-SN Case Grid`
- `UI-QRY-001 Smart Query Drawer`
- `UI-CFG-001 Component Configuration`

Every component must expose normal, processing, newly detected NG, historical NG, MES offline, unauthorized, repair and configuration states where applicable.
