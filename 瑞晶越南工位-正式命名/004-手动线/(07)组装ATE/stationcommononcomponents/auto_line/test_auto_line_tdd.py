"""TDD contract tests for the automatic-line 2D station domain.

Fixtures use temporary SQLite databases and never contact MES or production
station databases.
"""
import json
import tempfile
import unittest
from pathlib import Path

from station_common_agent import build_common_agent
import station_repair_workflow

LINE_ROOT = Path(__file__).resolve().parent


class AutoLineTddTests(unittest.TestCase):
    def test_domain_identity_is_auto_line(self):
        db = Path(tempfile.mkdtemp()) / "agent.sqlite"
        agent = build_common_agent("auto_ict", line_domain="AUTO_LINE", preview=True, db_path=db)
        identity = agent.identity()
        event = agent.event("TEST_RESULT", payload={"result": "PASS"})
        self.assertEqual(identity["processDomain"], "AUTO_LINE")
        self.assertEqual(identity["lineCode"], "L002")
        self.assertEqual(event["station"]["lineDomain"], "AUTO_LINE")

    def test_scan_gate_blocks_duplicate_and_records_ng(self):
        db = Path(tempfile.mkdtemp()) / "agent.sqlite"
        agent = build_common_agent("auto_fct", line_domain="AUTO_LINE", preview=True, db_path=db)
        first = agent.scan("AUTO-TDD-SN-001", scanner_id="fixture")
        duplicate = agent.scan("AUTO-TDD-SN-001", scanner_id="fixture")
        ng = agent.record_ng("AUTO-TDD-SN-002", "TDD_DEFECT", source="FIXTURE")
        self.assertTrue(first.accepted)
        self.assertFalse(duplicate.accepted)
        self.assertEqual(duplicate.reason, "DUPLICATE_SCAN")
        self.assertEqual(ng["eventType"], "NG_DETECTED")

    def test_auto_ng_graph_contains_repair_and_return_cycle(self):
        graph = json.loads((LINE_ROOT / "ng-routing.graph.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(graph["authority"], "MES")
        edges = {(edge["from"], edge["to"]) for edge in graph["edges"]}
        for edge in (
            ("repair_order", "repair_handover"),
            ("repair_handover", "auto_rework"),
            ("auto_rework", "retest"),
            ("retest", "source_retest"),
        ):
            self.assertIn(edge, edges)

    def test_repair_adapter_uses_shared_workflow_and_mes_is_authority(self):
        self.assertTrue(callable(station_repair_workflow.install_repair_workflow))
        config = json.loads((LINE_ROOT / "stations.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(config["routingAuthority"], "MES")
        self.assertTrue(config["localSuggestion"]["mesApprovalRequired"])

    def test_all_13_auto_station_ports_are_deterministic(self):
        config = json.loads((LINE_ROOT / "stations.json").read_text(encoding="utf-8-sig"))
        stations = config["stations"]
        self.assertEqual(len(stations), 13)
        ports = [12100 + int(item["sequence"]) for item in stations]
        self.assertEqual(ports, list(range(12101, 12114)))
        self.assertEqual(len({item["stationCode"] for item in stations}), 13)


if __name__ == "__main__":
    unittest.main()
