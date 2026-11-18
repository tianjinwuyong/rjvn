# Common Agent

This is the project-level shared runtime for the legacy full station Agents
and the modular manual-line UI.

Two launch modes are kept separately:

- `start_pure.cmd --station mod_manu_fct` runs the untouched legacy baseline.
- `start_mixed.cmd --station mod_manu_fct` runs the same legacy UI with the
  shared Common Agent/Adapter environment.
- `start_mixed.cmd` without arguments opens the shared station dropdown; the
  selected station then uses its configured legacy UI and Adapter.
- `start_auto.cmd` uses the local IP/hostname deployment map to select the
  station automatically. Unknown machines fall back to the safe dropdown and
  are never silently assigned a production station.
- `deployment_config.json` is the main deployment configuration file. Edit
  `ipToStation` or `hostnameToStation` for each station PC; keep
  `unknownHostAction` as `OPEN_SELECTOR` until every host is registered.
- The Common Agent repeats this IP/hostname check at Agent startup. In
  production mode a mismatch blocks startup; in preview mode it is reported
  but allowed for testing.
- The same package supports both `MANUAL_LINE` and `AUTO_LINE`; use
  `defaultLineDomain` or `STATION_LINE_DOMAIN` to select the deployment domain.
- `station_profiles.json` describes each station's data source, accepted file
  formats, motherboard/layout model, MES domain, and line domain. It is loaded
  and validated by `deployment_config_loader.py` before deployment.
- The `sqlite` block defines the local database used by every Agent for
  immutable history, offline Outbox, scans, NG, repair events, and resource
  cursors. Each station gets its own `{stationCode}.sqlite` file in `data/`.
- The `resourceViewer` block configures the local CSV/Excel/JSON/HTML/SQL/log
  viewer: recursive discovery, startup/changed/new/partial reading, polling,
  file-size protection, and station-specific resource roots.
- The `kpiViewer` block configures shared station KPIs such as throughput,
  cycle time, pass/NG rate, queue depth, MES lag, and Outbox depth. Values are
  read from local SQLite plus MES and can be overridden per station.
- Use `station_config("mod_manu_fct")` to get the resolved profile for one
  station; it combines the station data source/layout with shared SQLite,
  resource viewer, KPI viewer, and MES settings.
- `stationAliases` keeps legacy MES codes such as `manu_assembly_ate`
  compatible with the modular code `mod_manu_assembly_ate`; both resolve to
  the same MANUAL_LINE profile and Adapter.
- `qualityGates` configures duplicate-scan blocking and NG evidence checks;
  raw NG history is preserved and MES remains the authoritative decision.

## Boundaries

- `station_common_agent.py` owns identity, local history, scanner gateway,
  MES channel, outbox, diagnostics, alarms, and plugin registration.
- `legacy_station_adapter.py` / `adapters.py` provide the replaceable
  equipment adapter seam. Existing station UI and workflows remain intact.
- `station_adapter_registry.py` defines the canonical `module_*` names.
- `station_registry.py` and `stations.json` define modular station metadata
  and approved NG/repair policy defaults.
- `legacy_ui_manifest.json` maps every modular station to the original full
  UI/Agent source under `004-手动线 - 副本`; that source is the visual and
  workflow baseline for reconstruction.

Run the modular preview from this folder:

```powershell
python modular_manual_line.py --station mod_manu_fct
```

Legacy Agents should add this folder to `PYTHONPATH` (or load it through the
deployment bundle) before importing the shared runtime. Production routing,
permissions, NG closure, and repair decisions remain MES-owned.
