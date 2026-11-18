# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
MANUAL = SPEC_DIR.parent
FORMAL = MANUAL.parent
AUTO = next(p for p in FORMAL.iterdir() if p.is_dir() and p.name.startswith("002-"))
ASSEMBLY = next(p for p in MANUAL.iterdir() if p.is_dir() and p.name.startswith("(07)"))
RESERVOIR = FORMAL / "station-component-reservoir" / "python"
REPAIR = ASSEMBLY / "dist" / "assembly_ate_agent" / "_internal" / "manual_repair" / "station_repair_workflow.py"
STORE = MANUAL / "repair_work_order_store.py"

a = Analysis(
    [str(SPEC_DIR / "packing_ate_agent.py")],
    pathex=[str(SPEC_DIR), str(MANUAL), str(ASSEMBLY), str(AUTO), str(RESERVOIR)],
    binaries=[],
    datas=[(str(p), ASSEMBLY.name) for p in ASSEMBLY.glob("*.py")] +
          [(str(REPAIR), "manual_repair"), (str(STORE), "manual_repair")],
    hiddenimports=["assembly_ate_agent", "station_arrival_core", "station_excel_events",
                   "station_excel_safe", "station_common_agent", "station_common_bootstrap",
                   "station_runtime_safety", "station_i18n", "station_repair_workflow",
                   "repair_work_order_store", "station_resource_viewer",
                   "station_components.ng_closed_loop", "station_components.repair_cycle_graph",
                   "pynput.keyboard"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "numpy", "pandas", "lxml", "matplotlib", "scipy"],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="packing_ate_agent",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[],
               name="packing_ate_agent")
