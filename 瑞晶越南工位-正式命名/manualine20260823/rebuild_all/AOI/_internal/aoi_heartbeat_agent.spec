# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

SPEC_DIR = Path(r'C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名\004-手动线\(02)AOI质量工位')
MANUAL_LINE = SPEC_DIR.parent
RESERVOIR_PY = MANUAL_LINE.parent / 'station-component-reservoir' / 'python'
COMMON_AGENT = MANUAL_LINE.parent.parent / 'common agent'
AUTO_LINE = Path(r'C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名\002-自动线')

a = Analysis(
    [str(SPEC_DIR / 'aoi_heartbeat_agent.py')],
    pathex=[str(SPEC_DIR), str(MANUAL_LINE), str(AUTO_LINE), str(COMMON_AGENT), str(RESERVOIR_PY)],
    binaries=[], datas=[],
    hiddenimports=['station_arrival_core','station_history_core','station_common_agent','station_common_bootstrap','station_data_sync','station_domain','station_retest','station_components','station_components.ng_closed_loop','station_components.repair_cycle_graph'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='aoi_heartbeat_agent', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None, console=False, disable_windowed_traceback=False, argv_emulation=False, target_arch=None, codesign_identity=None, entitlements_file=None)
