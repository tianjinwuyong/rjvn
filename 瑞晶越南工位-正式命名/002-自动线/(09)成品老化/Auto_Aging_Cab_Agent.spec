# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
AUTO_DIR = SPEC_DIR.parent
NAMING_ROOT = SPEC_DIR.parents[1]
MANUAL_LINE = next(path for path in NAMING_ROOT.iterdir() if path.is_dir() and path.name.startswith("004-"))
RESERVOIR_PY = (NAMING_ROOT / "station-component-reservoir" / "python").resolve()
MANUAL_BUNDLE_DIR = "manual_repair"

a = Analysis(
    ["aging_cab_agent.py"],
    pathex=[str(SPEC_DIR), str(AUTO_DIR), str(MANUAL_LINE), str(RESERVOIR_PY)],
    binaries=[],
    datas=[
        (str(AUTO_DIR / "(03)ICT" / "dist" / "manual_repair" / "station_repair_workflow.py"), MANUAL_BUNDLE_DIR + "/shared_station_repair_workflow.py"),
        (str(AUTO_DIR / "station_resource_viewer.py"), MANUAL_BUNDLE_DIR),
        (str(MANUAL_LINE / "repair_work_order_store.py"), MANUAL_BUNDLE_DIR),
        (str(AUTO_DIR / "ng-routing.graph.json"), MANUAL_BUNDLE_DIR),
    ],
    hiddenimports=[
        "station_retest", "station_data_sync", "station_runtime_safety",
        "station_arrival_core", "station_history_core",
        "station_repair_workflow", "station_resource_viewer", "repair_work_order_store",
        "station_common_agent", "station_i18n",
        "station_components", "station_components.ng_closed_loop",
        "station_components.repair_cycle_graph", "tkinter.simpledialog", "tkinter.messagebox", "tkinter.ttk", "pyodbc", "pymysql",
        "pynput", "pynput.keyboard", "pynput.keyboard._win32", "pynput._util.win32",
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Auto_Aging_Cab_Agent", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
