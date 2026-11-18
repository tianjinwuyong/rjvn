import os
import runpy
import sys
from pathlib import Path

_source_base = Path(__file__).resolve().parent.parent
_bundle_base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
_base = _bundle_base if getattr(sys, "frozen", False) else _source_base
root = next(p for p in _base.iterdir() if p.is_dir() and p.name.startswith("(07)"))
sys.path.insert(0, str(root))
os.environ.setdefault("ATE_STATION_CODE", "manu_hivolt_ate")
os.environ.setdefault("ATE_NEXT_STATION", "manu_package_ate")
os.environ.setdefault("ATE_DISPLAY_NAME", "High-Voltage ATE / 2D")
os.environ.setdefault("ATE_WINDOW_TITLE", "High-Voltage ATE / 2D")
os.environ.setdefault("ATE_DB_PATH", str(Path(__file__).resolve().parent / "hivolt_ate_agent.db"))
os.environ.setdefault("MES_PRIMARY_URL", "http://192.168.6.155:8080")
os.environ.setdefault("MES_BACKUP_URL", "http://192.168.6.122:8080")
os.environ.setdefault("MES_LOCAL_URL", "http://127.0.0.1:8080")
os.environ.setdefault("MES_API_URL", "http://192.168.6.155:8080/api/pda/events")
os.environ["ATE_SCANNER_PORT"] = "1010"
os.environ.setdefault("STATION_REQUIRE_NG_SYNC", "1")
runpy.run_path(str(root / "assembly_ate_agent.py"), run_name="__main__")
