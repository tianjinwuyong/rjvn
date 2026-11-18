# -*- coding: utf-8 -*-
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from smt_station_agent import SmtStationAgent

STATIONS = [
    "(00)PD扫码上料", "(01)镭雕机", "(02)AI插件机", "(03)印刷机",
    "(04)SPI", "(05)贴片机", "(06)SMT-AOI",
]


def run():
    observed_codes = set()
    for folder in STATIONS:
        source = json.loads((ROOT / folder / "station_config.json").read_text(encoding="utf-8"))
        assert source["stationIp"] is None
        observed_codes.add(source["stationCode"])
        with tempfile.TemporaryDirectory() as tmp:
            cfg = dict(source)
            cfg["mesUrl"] = "http://127.0.0.1:1/api"
            cfg_path = Path(tmp) / "station_config.json"
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
            agent = SmtStationAgent(cfg_path)
            agent.flush = lambda limit=100: 0
            assert agent.self_test()["ok"]
            assert "WIP_TRACKING" in agent.responsibilities()
            assert agent.scan("SMT-SCAN-GUARD-001")["decision"] == "PENDING_MES_GUARD"
            agent.activity("UNIT_ARRIVED", "SMT-SCAN-GUARD-001", {"lane": 1})
            agent.complete_process("SMT-SCAN-GUARD-001", {"lane": 1})
            agent.fault("TEST_FAULT", "contract test", "WARNING")
            agent.acknowledge_fault("TEST_FAULT", "TEST_OPERATOR")
            agent.clear_fault("TEST_FAULT", "TEST_OPERATOR", "contract test complete")
            assert agent.counts()["activeFaults"] == 0
            assert agent.counts()["pendingSync"] == 6
            if source["sequence"] == 5:
                assert agent.ingest_file(ROOT / "tests" / "sample_results.csv") == 2
                assert agent.ingest_file(ROOT / "tests" / "sample_results.csv") == 0
                assert agent.counts()["rawRecords"] == 2
                assert agent.counts()["pendingSync"] == 8
                result_types = {row["event_type"] for row in agent.recent_resources()["outbox"]}
                assert {"STATION_TEST_RESULT", "NG_DEFECT"}.issubset(result_types)
                agent.send_ng_to_repair("SMT-E2E-0002", "TEST_OPERATOR")
                assert agent.recent_resources()["outbox"][0]["event_type"] == "STATION_ROUTE_SELECTED"
    assert len(observed_codes) == 7
    print("SMT agent contract tests: 7 distinct stations passed")


if __name__ == "__main__":
    run()
