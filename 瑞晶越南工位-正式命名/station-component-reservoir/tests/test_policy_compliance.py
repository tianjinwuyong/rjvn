import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from station_components.policy_compliance import build_compliance_report


class PolicyComplianceTests(unittest.TestCase):
    def policy(self):
        return {
            "policyVersion": 12,
            "domain": "MANUAL_LINE",
            "lineCode": "MANUAL_LINE-01",
            "stationCode": "manu_ict",
            "routeRevision": "R7",
            "requiredComponents": ["quality.repair", "quality.retest"],
            "trigger": {"mode": "ANY", "timeMinutes": 60, "quantity": 10},
        }

    def observed(self):
        return {
            "domain": "MANUAL_LINE",
            "lineCode": "MANUAL_LINE-01",
            "stationCode": "manu_ict",
            "hostIp": "192.168.6.91",
            "agentVersion": "2.4.0",
            "componentVersions": {"quality.repair": "1.2.0", "quality.retest": "1.1.0"},
            "policyVersion": 12,
            "routeRevision": "R7",
            "mesOnline": True,
        }

    def test_matching_station_reports_compliant(self):
        report = build_compliance_report(self.policy(), self.observed(), observed_at_ms=1000)
        self.assertTrue(report["compliant"])
        self.assertEqual([], report["violations"])
        self.assertEqual("MANUAL_LINE", report["domain"])
        self.assertEqual("192.168.6.91", report["hostIp"])

    def test_version_or_component_drift_is_reported(self):
        observed = self.observed()
        observed["policyVersion"] = 11
        observed["componentVersions"].pop("quality.retest")
        report = build_compliance_report(self.policy(), observed, observed_at_ms=1000)
        self.assertFalse(report["compliant"])
        self.assertIn("POLICY_VERSION_MISMATCH", report["violations"])
        self.assertIn("MISSING_COMPONENT:quality.retest", report["violations"])

    def test_offline_report_is_explicit(self):
        observed = self.observed()
        observed["mesOnline"] = False
        report = build_compliance_report(self.policy(), observed, observed_at_ms=1000)
        self.assertEqual("OFFLINE", report["complianceState"])
        self.assertIn("MES_OFFLINE", report["violations"])


if __name__ == "__main__":
    unittest.main()
