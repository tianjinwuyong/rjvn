# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path.cwd()
MANUAL = ROOT.parent.parent / "004-手动线"
COMMON = ROOT.parent.parent / "common agent"
RESERVOIR = ROOT.parent.parent / "station-component-reservoir" / "python"

a = Analysis(
    [str(ROOT / "station_ng_sync_service.py")],
    pathex=[str(ROOT), str(COMMON), str(RESERVOIR), str(MANUAL)],
    datas=[],
    hiddenimports=["station_ng_sync"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="station_ng_sync_service", console=True)
COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="station_ng_sync_service")
