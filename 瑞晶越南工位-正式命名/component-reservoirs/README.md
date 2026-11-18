# Ruijing Component Reservoirs

Five independent reservoirs build one factory platform. They share contracts, not business ownership.

```text
component-reservoirs/
├─ 01-station-agent-runtime/   # Windows/Linux station execution bricks
├─ 02-mes-management/         # Product + NG management and closed-loop orchestration
├─ 03-pda/                    # Warehouse/production handheld workflows
├─ 04-android-app/            # Employee/manager mobile experiences
├─ 05-ui-design-system/       # Visual bricks, layouts, states, accessibility and i18n
└─ shared-contracts/          # Versioned facts, commands, policies and identity contracts
```

## Assembly rule

`Experience = UI bricks + channel workflow bricks + shared contracts + MES decisions`

- MES owns product, route, NG, authorization, policy and workflow decisions.
- Station/PDA/Android collect facts and execute or display MES decisions.
- UI bricks never contain hidden production rules.
- Every brick has an asset ID, owner, version, maturity, compatibility and acceptance test.

Primary cross-station lifecycle: `PRD-ATT-001 Product Attendance Management / 产品考勤管理`.

## Asset bills

- Station Agent BOM: `../../outputs/station-component-reservoir/瑞晶工站Agent组件积木BOM.xlsx`
- MES, PDA, Android and UI BOMs are maintained inside their own reservoir folders.

## Design preview

Figma: https://www.figma.com/design/v2uY2e6CuXjVumyk5ZDgEb
