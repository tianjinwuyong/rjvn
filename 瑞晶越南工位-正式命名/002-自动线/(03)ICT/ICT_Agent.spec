# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
AUTO_LINE = SPEC_DIR.parent
FACTORY = AUTO_LINE.parent
MANUAL_LINE = next(path for path in FACTORY.iterdir() if path.is_dir() and path.name.startswith("004-"))
RESERVOIR_PY = (FACTORY / "station-component-reservoir" / "python").resolve()

a = Analysis(
    [str(SPEC_DIR / "ict_agent.py")],
    pathex=[str(SPEC_DIR), str(AUTO_LINE), str(MANUAL_LINE), str(RESERVOIR_PY)],
    binaries=[],
    datas=[
        (str(SPEC_DIR / "ict_config.json"), "."),
        (str(AUTO_LINE / "(03)ICT" / "dist" / "manual_repair" / "station_repair_workflow.py"), "manual_repair"),
        (str(AUTO_LINE / "station_resource_viewer.py"), "manual_repair"),
        (str(MANUAL_LINE / "repair_work_order_store.py"), "manual_repair"),
        (str(AUTO_LINE / "ng-routing.graph.json"), "manual_repair"),
    ],
    hiddenimports=[
        "station_scrap_workflow", "station_data_sync", "station_alarm", "station_i18n", "station_common_agent",
        "station_retest", "station_runtime_safety", "station_domain",
        "station_repair_workflow", "station_resource_viewer", "repair_work_order_store",
        "station_components", "station_components.ng_closed_loop",
        "station_components.repair_cycle_graph", "tkinter.simpledialog", "tkinter.messagebox", "tkinter.ttk",
        "pynput", "pynput.keyboard", "pynput.keyboard._win32", "pynput._util.win32",
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name="Auto_ICT_Agent",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
