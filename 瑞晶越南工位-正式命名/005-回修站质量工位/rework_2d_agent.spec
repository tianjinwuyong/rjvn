# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
base=Path(SPECPATH)
reservoir=(base.parent / 'station-component-reservoir' / 'python').resolve()
a=Analysis(
    ['rework_2d_agent.py'],
    pathex=[str(base), str(reservoir)],
    datas=[],
    hiddenimports=['tkinter','tkinter.ttk','tkinter.messagebox','_tkinter',
                   'station_components','station_components.local_resource_viewer',
                   'station_components.ng_query','station_components.ng_closed_loop',
                   'station_components.repair_cycle_graph'],
    hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False,optimize=0,
)
pyz=PYZ(a.pure)
exe=EXE(
    pyz,a.scripts,a.binaries,a.datas,[],
    name='rework_2d_agent',debug=False,bootloader_ignore_signals=False,
    strip=False,upx=True,upx_exclude=[],runtime_tmpdir=None,console=False,
    disable_windowed_traceback=False,argv_emulation=False,target_arch=None,
    codesign_identity=None,entitlements_file=None,
    uac_admin=True,
)
