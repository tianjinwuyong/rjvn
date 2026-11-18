from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from smt_station_agent import SmtStationAgent
from smt_station_ui import run_ui
if __name__ == "__main__":
    run_ui(SmtStationAgent(Path(__file__).with_name("station_config.json")))
