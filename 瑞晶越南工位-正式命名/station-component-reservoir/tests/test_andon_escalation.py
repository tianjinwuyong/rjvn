import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from station_components.andon_escalation import evaluate_andon


class AndonEscalationTests(unittest.TestCase):
    def test_pickup_sla_breach_escalates_to_line(self):
        result = evaluate_andon(
            policy={"grace_ms": 0, "levels": {"pickup": "L1_LINE"}},
            observation={
                "triggerType": "PICKUP_SLA_BREACH",
                "occurredAtMs": 1000,
                "nowMs": 2000,
                "dueAtMs": 1500,
                "repairCaseId": "rc-1",
            },
        )
        self.assertEqual(result["status"], "TRIGGERED")
        self.assertEqual(result["severity"], "L1_LINE")
        self.assertEqual(result["nextAction"], "ACKNOWLEDGE")

    def test_mismatch_bypasses_grace_period(self):
        result = evaluate_andon(
            policy={"grace_ms": 999999, "levels": {"mismatch": "L2_SUPERVISOR"}},
            observation={
                "triggerType": "QUANTITY_MISMATCH",
                "occurredAtMs": 1000,
                "nowMs": 1001,
                "expectedQuantity": 8,
                "observedQuantity": 7,
            },
        )
        self.assertEqual(result["severity"], "L2_SUPERVISOR")
        self.assertTrue(result["blocking"])

    def test_unresolved_event_escalates_without_replacing_history(self):
        result = evaluate_andon(
            policy={"escalate_after_ms": 100, "levels": {"pickup": "L1_LINE"}},
            observation={
                "triggerType": "PICKUP_SLA_BREACH",
                "occurredAtMs": 1000,
                "nowMs": 1200,
                "status": "ACKNOWLEDGED",
                "currentSeverity": "L1_LINE",
                "repairCaseId": "rc-1",
            },
        )
        self.assertEqual(result["status"], "ESCALATED")
        self.assertEqual(result["previousStatus"], "ACKNOWLEDGED")
        self.assertEqual(result["previousSeverity"], "L1_LINE")


if __name__ == "__main__":
    unittest.main()
