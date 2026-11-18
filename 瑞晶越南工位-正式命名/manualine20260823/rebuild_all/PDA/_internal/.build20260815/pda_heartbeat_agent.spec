# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['..\\pda_heartbeat_agent.py'],
    pathex=['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线\\(01)PDA扫码上料', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\common agent', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\station-component-reservoir\\python'],
    binaries=[],
    datas=[('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线\\(04)FCT\\dist\\manual_repair', 'manual_repair')],
    hiddenimports=['station_i18n', 'station_components', 'station_components.ng_closed_loop', 'station_components.repair_cycle_graph', 'repair_work_order_store', 'station_arrival_core', 'station_history_core', 'station_repair_workflow', 'station_retest', 'station_resource_viewer', 'station_common_bootstrap'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='pda_heartbeat_agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
