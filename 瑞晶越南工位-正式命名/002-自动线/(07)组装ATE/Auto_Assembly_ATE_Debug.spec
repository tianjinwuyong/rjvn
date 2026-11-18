# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['assembly_ate_agent.py'],
    pathex=['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\002-自动线', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\004-手动线'],
    binaries=[],
    datas=[],
    hiddenimports=['station_retest', 'station_domain', 'station_heartbeat', 'station_data_sync', 'station_runtime_safety'],
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
    name='Auto_Assembly_ATE_Debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir='D:\\auto-agent-runtime',
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
