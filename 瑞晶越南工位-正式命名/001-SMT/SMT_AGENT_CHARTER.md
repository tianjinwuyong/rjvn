# SMT L001 Agent Charter

## Canonical station sequence

| Seq | Station code | Official name | Source |
|---:|---|---|---|
| 0 | `smt_pda_loading` | PD扫码上料 / PDA Material Loading | scanner guard |
| 1 | `smt_laser_marking` | 镭雕机 / Laser Marking | machine record |
| 2 | `smt_auto_insertion` | AI插件机 / Automatic Insertion | machine record |
| 3 | `smt_printer` | 印刷机 / Solder Paste Printer | machine record |
| 4 | `smt_spi` | SPI锡膏检测 / Solder Paste Inspection | database/file |
| 5 | `smt_placement` | 贴片机 / Pick and Place | machine record |
| 6 | `smt_aoi` | SMT-AOI | database/file |

## Authority and data direction

- Station Agent owns raw machine evidence, scanner audit, and the offline outbox.
- MES owns canonical SN registration, duplicate decisions, confirmed-NG lifecycle,
  route sequence, work orders, and global trace history.
- 3D reads MES state for display, monitoring, and alarm visualization. It cannot
  lock, release, edit, or override station production.
- Scanner input always performs confirmed-NG, duplicate-SN, and route checks.
  Scanner input is observation only and never registers a formal production SN.
- Only trusted machine/file/database records can register production results.
- Events replay in original order after reconnection. Reconnection never reverses
  the configured source-to-MES direction.

## Industry-aligned station responsibilities

All stations publish endpoint identity, heartbeat/state, WIP arrival/start/
completion/departure, recipe visibility, fault lifecycle, route/status validation,
raw evidence, and ordered offline replay. Station-specific responsibilities are:

- PD loading: material identity, work-order binding, and operator trace.
- Laser: unit initialization, personalization/marking, and mark result.
- AI insertion: installed-material, tool, insertion activity, and result trace.
- Printer: paste-print result, stencil identity/cleaning, and paste material.
- SPI: solder-paste inspection, measurements, and defects.
- Placement: exact component/feeder/tool trace, placement cycles, failed pickups.
- AOI: optical inspection, component-offset measurements, and defects.

The runtime models IPC-CFX vertical reporting. Hermes board-transfer observations
can be recorded when a machine exposes them, but the Agent does not replace the
machine conveyor controller or PLC.

## Commissioning

`stationIp` and physical `source.path` are intentionally pending. When each real
station is ready, only its `station_config.json` is updated. MES can enforce the
final IP registry with `SMT_STATION_IPS_JSON`; until then it enforces station
identity and the `smt / L001` domain without inventing addresses.
