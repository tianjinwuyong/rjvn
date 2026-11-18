import os
import runpy
from pathlib import Path

os.environ.setdefault("ATE_WATCH_DIR", r"D:\ATS\测试报表")
runpy.run_path(str(Path(__file__).resolve().parent / "ate_common_station_ui.py"), run_name="__main__")
