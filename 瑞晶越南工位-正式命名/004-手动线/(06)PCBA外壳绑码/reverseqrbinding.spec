# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

SPEC_DIR = Path.cwd().resolve()
NAMING_ROOT = SPEC_DIR.parents[1]
AUTO_ROOT = next((p for p in NAMING_ROOT.iterdir() if p.is_dir() and p.name.startswith("002-")), None)
AUTO_QR = next((p for p in AUTO_ROOT.iterdir() if p.is_dir() and p.name.startswith("(06)")), None)
MANUAL_ROOT = SPEC_DIR.parent
COMMON_AGENT = NAMING_ROOT / "common agent"
RESERVOIR = NAMING_ROOT / "station-component-reservoir" / "python"
MANUAL_REPAIR = NAMING_ROOT / "manualine20260823" / "QRBinding" / "_internal" / "manual_repair"
MANUAL_REPAIR_DATAS = [(str(path), "manual_repair") for path in MANUAL_REPAIR.iterdir() if path.is_file()] if MANUAL_REPAIR and MANUAL_REPAIR.is_dir() else []

a = Analysis(
    [str(SPEC_DIR / "reverseqrbinding.py")],
    pathex=[str(SPEC_DIR), str(AUTO_ROOT), str(AUTO_QR), str(MANUAL_ROOT), str(COMMON_AGENT), str(RESERVOIR)],
    datas=MANUAL_REPAIR_DATAS,
    hiddenimports=[
        "qrbinding", "mes_direct_fallback", "station_repair_workflow", "station_common_agent",
        "station_common_bootstrap", "station_i18n", "station_data_sync",
        "station_domain", "station_heartbeat", "station_retest",
        "station_maintenance_core", "station_scan_alarm",
        "pyodbc", "repair_work_order_store",
        "pynput", "pynput.keyboard", "pynput.keyboard._win32",
    ],
    hookspath=[], excludes=['PySide6', 'shiboken6', 'numpy', 'pandas', 'lxml', 'matplotlib', 'scipy'], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="reverseqrbinding", debug=False, console=False, upx=True, disable_windowed_traceback=False)
