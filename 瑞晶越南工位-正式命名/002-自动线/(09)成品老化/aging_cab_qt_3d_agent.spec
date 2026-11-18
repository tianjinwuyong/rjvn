# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['aging_cab_qt_3d_agent.py'],
    pathex=['..', '..\\..\\004-手动线'],
    binaries=[],
    datas=[('aging-line.html','.'),('three.module.js','.'),('OrbitControls.js','.'),('GLTFExporter.js','.')],
    hiddenimports=[
        'station_retest', 'station_data_sync', 'station_runtime_safety',
        'encodings', 'encodings.idna', 'encodings.utf_8',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='Auto_Aging_Cab_3D_Agent', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None, console=False,
    disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None,
)
