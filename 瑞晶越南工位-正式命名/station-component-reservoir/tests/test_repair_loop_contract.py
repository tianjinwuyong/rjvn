import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from station_components.repair_loop_contract import (
    append_outbox,
    build_pickup_ack,
    build_repair_evidence,
    build_return_handover,
    evaluate_sla,
)


class RepairLoopContractTests(unittest.TestCase):
    def test_pickup_ack_binds_scan_and_actor(self):
        result = build_pickup_ack({"eventId": "e1", "workOrderId": "wo1", "bucketQr": "b1"}, "TL-1", "b1")
        self.assertEqual(result["status"], "CLAIMED")
        self.assertEqual(result["actor"], "TL-1")

    def test_repair_evidence_requires_step_and_operator(self):
        result = build_repair_evidence("wo1", "e2", "OP-1", [{"step": "REPLACE", "result": "DONE"}])
        self.assertEqual(result["workOrderId"], "wo1")
        self.assertTrue(result["appendOnly"])

    def test_sla_escalates_after_deadline(self):
        self.assertEqual(evaluate_sla(0, 31, 30)["status"], "BREACHED")
        self.assertEqual(evaluate_sla(0, 29, 30)["status"], "ON_TRACK")

    def test_return_handover_requires_retest_authorization(self):
        result = build_return_handover("wo1", "ICT", "ra1", ["SN1"], "ship1")
        self.assertEqual(result["destinationStation"], "ICT")

    def test_outbox_is_idempotent(self):
        event = {"eventId": "e1", "eventType": "REPAIR_STEP"}
        once = append_outbox([], event)
        twice = append_outbox(once, event)
        self.assertEqual(len(twice), 1)


if __name__ == "__main__":
    unittest.main()
