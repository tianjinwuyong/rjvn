# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
SPEC_DIR=Path(SPECPATH).resolve(); AUTO_LINE=SPEC_DIR.parent; FACTORY=AUTO_LINE.parent
MANUAL_LINE=next(p for p in FACTORY.iterdir() if p.is_dir() and p.name.startswith('004-'))
a=Analysis([str(SPEC_DIR/'pallet_binding_qt_3d_agent.py')],pathex=[str(SPEC_DIR),str(AUTO_LINE),str(MANUAL_LINE)],binaries=[],datas=[],hiddenimports=['PySide6','pallet_binding_core','station_arrival_core','station_history_core','station_retest'],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False, optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Auto_Pallet_Binding_3D_Agent',debug=False,bootloader_ignore_signals=False,strip=False,upx=True,upx_exclude=[],runtime_tmpdir=None,console=False,disable_windowed_traceback=False,argv_emulation=False,target_arch=None,codesign_identity=None,entitlements_file=None)
