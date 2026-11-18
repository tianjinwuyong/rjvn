# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
AUTO_LINE = SPEC_DIR.parent
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
AUTO_LINE = SPEC_DIR.parent
FACTORY = AUTO_LINE.parent
MANUAL_LINE = next((p for p in FACTORY.iterdir() if p.is_dir() and p.name.startswith('004-')), FACTORY)
RESERVOIR_PY = (FACTORY / 'station-component-reservoir' / 'python').resolve()

a = Analysis(
    ['supersonic_agent.py'],
    pathex=[str(SPEC_DIR), str(AUTO_LINE), str(MANUAL_LINE), str(RESERVOIR_PY)],
    binaries=[],
    datas=[(str(AUTO_LINE / '(03)ICT' / 'dist' / 'manual_repair' / 'station_repair_workflow.py'), 'manual_repair')],
    hiddenimports=[
        'station_arrival_core', 'station_history_core', 'station_core_contract',
        'station_maintenance_core', 'station_common_agent', 'station_common_bootstrap',
        'station_data_sync', 'station_repair_workflow', 'station_components',
        'station_components.ng_closed_loop', 'station_components.repair_cycle_graph',
        'station_retest', 'station_runtime_safety', 'station_alarm', 'station_i18n', 'station_resource_viewer', 'repair_work_order_store', 'pyodbc',
        'pynput', 'pynput.keyboard', 'pynput.keyboard._win32', 'pynput._util.win32', 'tkinter.simpledialog', 'tkinter.messagebox', 'tkinter.ttk',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PySide6', 'shiboken6'], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='Auto_Supersonic_Agent',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
