# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线\\(07)组装ATE\\assembly_ate_agent.py'],
    pathex=['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线\\(07)组装ATE', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线 - 副本', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线 - 副本\\(12)外箱绑码', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\station-component-reservoir\\python'],
    binaries=[],
    datas=[('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线 - 副本\\station_repair_workflow.py', 'manual_repair'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线 - 副本\\station_resource_viewer.py', 'manual_repair'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线 - 副本\\repair_work_order_store.py', 'manual_repair'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线\\ng-routing.graph.json', 'manual_repair')],
    hiddenimports=['station_components', 'station_components.ng_closed_loop', 'station_components.repair_cycle_graph', 'station_common_agent', 'station_i18n', 'repair_work_order_store', 'station_resource_viewer', 'case_binding_core', 'tkinter.simpledialog', 'tkinter.messagebox', 'tkinter.ttk'],
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
    name='auto_assembly_ate_ui',
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
