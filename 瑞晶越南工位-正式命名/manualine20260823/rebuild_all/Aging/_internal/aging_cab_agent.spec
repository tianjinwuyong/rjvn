# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(r'C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名\004-手动线\(09)成品老化')
MANUAL_LINE = SPEC_DIR.parent
AUTO_LINE = MANUAL_LINE.parent / '002-自动线'
COMMON_AGENT = MANUAL_LINE.parent.parent / 'common agent'
RESERVOIR_PY = (MANUAL_LINE.parent / 'station-component-reservoir' / 'python').resolve()
REPAIR_SOURCE = AUTO_LINE / '(03)ICT' / 'dist' / 'manual_repair' / 'station_repair_workflow.py'
REPAIR_STORE = MANUAL_LINE / 'repair_work_order_store.py'

a = Analysis(
    ['aging_cab_agent.py'],
    pathex=[str(SPEC_DIR), str(MANUAL_LINE), str(AUTO_LINE), str(COMMON_AGENT), str(RESERVOIR_PY)],
    binaries=[],
    datas=[(str(REPAIR_SOURCE), 'manual_repair/shared_station_repair_workflow.py'), (str(REPAIR_STORE), 'manual_repair'), (str(REPAIR_STORE), '.')],
    hiddenimports=collect_submodules('tkinter') + [
        'station_arrival_core', 'station_history_core', 'station_core_contract',
        'station_maintenance_core', 'station_components',
        'station_components.ng_closed_loop', 'station_components.repair_cycle_graph',
        'station_common_agent', 'station_common_bootstrap', 'station_i18n',
        'station_repair_workflow', 'station_data_sync', 'station_retest',
        'tkinter.simpledialog', 'tkinter.scrolledtext', 'tkinter.ttk', 'tkinter.messagebox',
        'pymysql', 'pyodbc', 'openpyxl', 'openpyxl.cell', 'openpyxl.reader.excel'
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=['PySide6', 'shiboken6', 'numpy', 'pandas', 'lxml', 'matplotlib', 'scipy'], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='aging_cab_agent', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=True, upx_exclude=[],
          runtime_tmpdir=None, console=False, disable_windowed_traceback=False,
          argv_emulation=False, target_arch=None, codesign_identity=None, entitlements_file=None,
          uac_admin=True)
