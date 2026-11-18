# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\common agent\\unified_ict_station.py'],
    pathex=['C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\common agent'],
    binaries=[],
    datas=[('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\common agent\\deployment_config.json', '.'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\common agent\\station_profiles.json', '.'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\common agent\\stations.json', '.'), ('C:\\Users\\tianj\\Desktop\\越南工厂瑞晶\\common agent\\legacy_ui_manifest.json', '.')],
    hiddenimports=[],
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
    name='unified_ict_station',
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
