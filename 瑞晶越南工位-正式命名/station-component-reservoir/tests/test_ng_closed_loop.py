import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from station_components.ng_closed_loop import ClosedLoopState, append_history, apply_transition


class NgClosedLoopTests(unittest.TestCase):
    def test_confirmed_ng_creates_mes_work_order_path(self):
        result = apply_transition(
            ClosedLoopState.CONFIRMED_NG,
            "CREATE_REPAIR_ORDER",
            {"eventId": "e1", "domainCode": "MANUAL_LINE", "commandId": "cmd1", "mesDecisionId": "d1", "workOrderId": "wo1"},
        )
        self.assertEqual(result["state"], ClosedLoopState.REPAIR_ORDERED.value)
        self.assertEqual(result["nextAction"], "HANDOVER_TO_REPAIR")
        self.assertEqual(result["feedbackStatus"], "EXECUTED")
        self.assertEqual(result["commandId"], "cmd1")

    def test_return_route_requires_mes_decision_and_retest_authorization(self):
        with self.assertRaises(ValueError):
            apply_transition(ClosedLoopState.REPAIR_COMPLETE, "RETURN_TO_ICT", {"eventId": "e2", "domainCode": "MANUAL_LINE"})
        result = apply_transition(
            ClosedLoopState.REPAIR_COMPLETE,
            "RETURN_TO_ICT",
            {"eventId": "e2", "domainCode": "MANUAL_LINE", "commandId": "cmd2", "mesDecisionId": "d2", "retestAuthorizationId": "ra2"},
        )
        self.assertEqual(result["state"], ClosedLoopState.RETEST_PENDING.value)

    def test_pass_does_not_erase_original_ng_history(self):
        result = apply_transition(
            ClosedLoopState.RETEST_PENDING,
            "RETEST_PASS",
            {"eventId": "e3", "domainCode": "MANUAL_LINE", "commandId": "cmd3", "mesDecisionId": "d3", "originalNgEventId": "ng1"},
        )
        self.assertEqual(result["state"], ClosedLoopState.RETURN_PENDING.value)
        self.assertEqual(result["preservedNgEventId"], "ng1")

    def test_domain_is_required(self):
        with self.assertRaises(ValueError):
            apply_transition(ClosedLoopState.CONFIRMED_NG, "CREATE_REPAIR_ORDER", {
                "eventId": "e4", "mesDecisionId": "d4", "workOrderId": "wo4"
            })

    def test_transition_carries_repair_history_identity(self):
        result = apply_transition(
            ClosedLoopState.CONFIRMED_NG,
            "CREATE_REPAIR_ORDER",
            {"eventId": "e5", "domainCode": "MANUAL_LINE", "commandId": "cmd5", "mesDecisionId": "d5",
             "workOrderId": "wo5", "shipmentId": "ship5", "stationQr": "STATION-ICT",
             "sns": ["SN-1", "SN-2"], "quantity": 2},
        )
        self.assertEqual(result["repairWoId"], "wo5")
        self.assertEqual(result["shipmentId"], "ship5")
        self.assertEqual(result["stationQr"], "STATION-ICT")
        self.assertEqual(result["sns"], ["SN-1", "SN-2"])

    def test_history_is_append_only_and_idempotent(self):
        first = {"eventId": "e6", "state": "REPAIR_ORDERED"}
        history = append_history([], first)
        history_again = append_history(history, first)
        self.assertEqual(history_again, [first])
        self.assertIsNot(history_again, history)


if __name__ == "__main__":
    unittest.main()
