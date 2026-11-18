import os
import runpy
import sys
from pathlib import Path

os.environ.setdefault("ATE_STATION_CODE", "manu_package_ate")
os.environ.setdefault("ATE_SCANNER_PORT", "1003")
os.environ.setdefault("ATE_WATCH_DIR", r"D:\ATS\测试报表")
os.environ.setdefault("ATE_DISPLAY_NAME", "Packaging ATE / 包装ATE")
os.environ.setdefault("ATE_DB_PATH", str(Path(__file__).resolve().parent / "packing_common.db"))
root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
runpy.run_path(str(root / "ate_common_station_ui.py"), run_name="__main__")
