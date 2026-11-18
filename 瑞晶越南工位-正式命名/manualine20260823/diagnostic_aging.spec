from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

FORMAL = Path(r"C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名")
MANUAL = FORMAL / "004-手动线"
COMMON = MANUAL / "(07)组装ATE" / "stationcommononcomponents_clean"
ENTRY = MANUAL / "(09)成品老化" / "aging_cab_agent.py"
REAL_REPAIR = FORMAL / "002-自动线" / "(03)ICT" / "dist" / "manual_repair" / "station_repair_workflow.py"
REPAIR_STORE = MANUAL / "repair_work_order_store.py"

hidden = [
    "station_common_bootstrap", "station_common_agent", "station_runtime_safety",
    "station_repair_workflow", "repair_work_order_store", "station_i18n",
    "station_language", "station_heartbeat", "station_ui_primitives",
    "station_scan_alarm", "station_arrival_core", "station_arrival_ui",
    "station_resource_viewer", "station_retest", "station_history_core",
    "station_excel_safe", "station_excel_events", "pynput.keyboard",
    "watchdog.observers", "watchdog.events", "win32com.client",
] + collect_submodules("station_components")

a = Analysis(
    [str(ENTRY)],
    pathex=[str(ENTRY.parent), str(MANUAL), str(COMMON), str(FORMAL / "station-component-reservoir" / "python")],
    binaries=[],
    datas=[(str(REAL_REPAIR), "manual_repair"), (str(REPAIR_STORE), "manual_repair")],
    hiddenimports=hidden,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "numpy", "pandas", "lxml", "matplotlib", "scipy"],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AgingDiag",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               upx_exclude=[], name="AgingDiag")
