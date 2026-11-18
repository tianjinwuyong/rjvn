from pathlib import Path
ROOT = Path(SPEC).resolve().parent
a = Analysis([str(ROOT / "station_mes_api_launcher.py")], pathex=[str(ROOT)],
             binaries=[], datas=[], hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="StartStationMesApi",
          console=True, debug=False, strip=False, upx=True)
