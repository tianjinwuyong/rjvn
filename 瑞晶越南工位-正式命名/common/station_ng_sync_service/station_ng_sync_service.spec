# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['station_ng_sync_service.py'],
    pathex=['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\common\\station_ng_sync_service', 'C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\瑞晶越南工位-正式命名\\common'],
    binaries=[],
    datas=[],
    hiddenimports=['station_ng_sync', 'mes_direct_fallback'],
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
    name='station_ng_sync_service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
