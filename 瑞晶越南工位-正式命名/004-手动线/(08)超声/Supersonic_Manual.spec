# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
FACTORY = SPEC_DIR.parents[1]
AUTO_LINE = FACTORY / '002-自动线'
MANUAL_LINE = SPEC_DIR.parents[0]
RESERVOIR_PY = FACTORY / 'station-component-reservoir' / 'python'
REPAIR = AUTO_LINE / '(03)ICT' / 'dist' / 'manual_repair' / 'station_repair_workflow.py'

a = Analysis(
    ['supersonic_agent.py'],
    pathex=[str(SPEC_DIR), str(AUTO_LINE), str(MANUAL_LINE), str(RESERVOIR_PY)],
    binaries=[],
    datas=[(str(REPAIR), 'manual_repair')],
    hiddenimports=[
        'station_arrival_core', 'station_history_core', 'station_core_contract',
        'station_maintenance_core', 'station_common_agent', 'station_common_bootstrap',
        'station_data_sync', 'station_repair_workflow', 'station_components',
        'station_components.ng_closed_loop', 'station_components.repair_cycle_graph',
        'station_retest', 'station_runtime_safety', 'station_alarm', 'station_i18n',
        'station_resource_viewer', 'repair_work_order_store', 'pyodbc',
        'station_sn_client',
        'pynput', 'pynput.keyboard', 'pynput.keyboard._win32', 'pynput._util.win32',
        'tkinter.constants', 'tkinter.simpledialog', 'tkinter.messagebox', 'tkinter.ttk',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PySide6', 'shiboken6'], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='Supersonic',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas, name='Supersonic',
)
