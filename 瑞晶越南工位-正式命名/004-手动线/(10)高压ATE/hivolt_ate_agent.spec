# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['assembly_ate_agent', 'station_common_bootstrap', 'station_common_agent', 'station_runtime_safety', 'station_i18n', 'station_language', 'station_heartbeat', 'station_ui_primitives', 'station_arrival_core', 'station_history_core', 'station_retest', 'repair_work_order_store']
hiddenimports += collect_submodules('station_components')


a = Analysis(
    ['hivolt_ate_agent.py'],
    pathex=['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线\\(10)高压ATE', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线\\(07)组装ATE', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\station-component-reservoir\\python'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'shiboken6', 'numpy', 'pandas', 'lxml', 'matplotlib', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='hivolt_ate_agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='hivolt_ate_agent',
)
