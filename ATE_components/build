# standalone common ATE; no legacy station agent
from pathlib import Path

a = Analysis(
    ['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线\\(11)包装ATE\\packing_common_ui.py'],
    pathex=['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线'],
    binaries=[],
    datas=[('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线\\atecommonagent.py', '.'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线\\ate_common_station_ui.py', '.'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线\\station_scan_alarm.py', '.'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线\\station_ui_primitives.py', '.')],
    hiddenimports=['atecommonagent', 'ate_common_station_ui', 'station_scan_alarm', 'station_ui_primitives', 'pynput', 'pynput.keyboard', 'pynput.keyboard._win32', 'pynput._util.win32', 'openpyxl', 'watchdog', 'watchdog.observers', 'watchdog.events', 'win32com.client', 'tkinter.filedialog', 'tkinter.messagebox', 'tkinter.ttk', 'tkinter.simpledialog', 'tkinter.scrolledtext'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "numpy", "pandas", "lxml", "matplotlib", "scipy"],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='packing_ate_common',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               upx_exclude=[], name='packing_ate_common')
