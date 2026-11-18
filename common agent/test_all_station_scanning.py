import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from deployment_config_loader import load_deployment_config, station_config
from quality_gates import check_duplicate, check_ng_evidence
from station_common_agent import build_common_agent


STATIONS = (
    "manu_pda", "manu_aoi", "manu_ict", "manu_fct", "manu_depanel",
    "manu_case_binding", "manu_assembly_ate", "manu_supersonic", "manu_aging",
    "manu_hivolt_ate", "manu_packing_ate", "manu_outer_box_binding",
    "manu_pallet_binding", "auto_pda", "auto_aoi", "auto_ict", "auto_fct",
    "auto_depanel", "auto_case_binding", "auto_assembly_ate", "auto_supersonic",
    "auto_aging", "auto_hivolt_ate", "auto_packing_ate_left",
    "auto_packing_ate_right", "auto_outer_box_binding", "auto_pallet_binding",
)


class AllStationScanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_deployment_config(Path(__file__).with_name("deployment_config.json"))

    def test_every_station_accepts_normalized_sn_and_persists_audit_rows(self):
        with tempfile.TemporaryDirectory(prefix="ruijing-scan-") as temp:
            for index, alias in enumerate(STATIONS, 1):
                with self.subTest(station=alias):
                    profile = station_config(alias, self.config)
                    db_path = Path(temp) / (alias + ".sqlite")
                    agent = build_common_agent(
                        profile["stationCode"], line_domain=profile["lineDomain"],
                        mes_base_url=profile["mes"]["baseUrl"], preview=True,
                        db_path=db_path,
                    )
                    sn = "TEST-%s-%04d" % (profile["stationId"], index)
                    accepted = agent.scan("  " + sn + "\x00\r\n", scanner_id="TCP:1003")
                    duplicate = agent.scan(sn, scanner_id="TCP:1003")
                    empty = agent.scan(" \x00\r\n", scanner_id="TCP:1003")

                    self.assertTrue(accepted.accepted)
                    self.assertEqual(sn, accepted.normalized_value)
                    self.assertFalse(duplicate.accepted)
                    self.assertEqual("DUPLICATE_SCAN", duplicate.reason)
                    self.assertFalse(empty.accepted)
                    self.assertEqual("EMPTY_SCAN", empty.reason)
                    self.assertFalse(check_duplicate(duplicate, config=self.config["qualityGates"])["accepted"])

                    with closing(sqlite3.connect(str(db_path))) as db:
                        scans = db.execute("SELECT COUNT(*) FROM station_scans").fetchone()[0]
                        sns = db.execute("SELECT COUNT(*) FROM station_sn WHERE sn=?", (sn,)).fetchone()[0]
                    self.assertEqual(3, scans)
                    self.assertEqual(1, sns)

    def test_ng_scan_requires_source_defect_and_raw_evidence(self):
        rejected = check_ng_evidence(
            sn="TEST-NG-001", source_station="", defect_code="", raw_evidence=None,
            config=self.config["qualityGates"],
        )
        self.assertFalse(rejected["accepted"])
        self.assertEqual(["SOURCE_STATION", "DEFECT_CODE", "RAW_EVIDENCE"], rejected["missing"])

        accepted = check_ng_evidence(
            sn="TEST-NG-001", source_station="mod_manu_ict", defect_code="ICT_FAIL",
            raw_evidence={"raw": "TEST-NG-001"}, config=self.config["qualityGates"],
        )
        self.assertTrue(accepted["accepted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
