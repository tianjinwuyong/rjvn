# -*- coding: utf-8 -*-
import argparse
import json
from pathlib import Path

from smt_station_agent import SmtStationAgent

ROOT = Path(__file__).resolve().parent
STATIONS = {
    "00": "(00)PD扫码上料",
    "01": "(01)镭雕机",
    "02": "(02)AI插件机",
    "03": "(03)印刷机",
    "04": "(04)SPI",
    "05": "(05)贴片机",
    "06": "(06)SMT-AOI",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("station", choices=STATIONS)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--heartbeat-once", action="store_true")
    args = parser.parse_args()
    agent = SmtStationAgent(ROOT / STATIONS[args.station] / "station_config.json")
    if args.self_test:
        print(json.dumps(agent.self_test(), ensure_ascii=False))
    elif args.heartbeat_once:
        agent.heartbeat()
    else:
        agent.run()


if __name__ == "__main__":
    main()
