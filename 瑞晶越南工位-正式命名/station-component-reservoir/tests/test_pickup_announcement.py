import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from station_components.pickup_announcement import (
    DEFAULT_PICKUP_POLICY, build_pickup_announcement, build_pickup_feedback,
    evaluate_pickup_trigger, pickup_alarm_id,
)


class PickupAnnouncementTests(unittest.TestCase):
    def test_default_policy_announces_at_quantity_or_age_or_human_request(self):
        self.assertEqual(DEFAULT_PICKUP_POLICY["quantityThreshold"], 10)
        self.assertEqual(DEFAULT_PICKUP_POLICY["timeThresholdMinutes"], 30)
        self.assertEqual(evaluate_pickup_trigger(DEFAULT_PICKUP_POLICY, 10, 0, False)["ready"], True)
        self.assertEqual(evaluate_pickup_trigger(DEFAULT_PICKUP_POLICY, 1, 30, False)["ready"], True)
        self.assertEqual(evaluate_pickup_trigger(DEFAULT_PICKUP_POLICY, 1, 0, True)["ready"], True)

    def test_trigger_is_not_ready_before_any_threshold(self):
        result = evaluate_pickup_trigger(DEFAULT_PICKUP_POLICY, 9, 29, False)
        self.assertFalse(result["ready"])
        self.assertEqual(result["reasons"], [])

    def payload(self):
        return {
            "domainCode": "MANUAL_LINE", "lineCode": "L004", "repairStation": "MANU-REWORK",
            "sourceStation": "MANU-ICT", "workOrderId": "WO-1", "eventId": "ng-1",
            "bucketQr": "BKT-1", "sns": ["SN-1", "SN-2"], "destinationStation": "MANU-ICT",
        }

    def test_announcement_targets_station_pda_and_mes(self):
        result = build_pickup_announcement(self.payload())
        self.assertEqual(result["eventType"], "NG_PICKUP_ANNOUNCEMENT")
        self.assertEqual(result["quantity"], 2)
        self.assertEqual(result["channels"], ["STATION", "TEAM_LEADER_PDA", "MES_KANBAN"])
        self.assertEqual(result["status"], "READY_FOR_PICKUP")
        self.assertEqual(result["alarmId"], pickup_alarm_id(result["commandId"]))

    def test_feedback_is_explicit_and_idempotent(self):
        announcement = build_pickup_announcement(self.payload())
        result = build_pickup_feedback(announcement, "CLAIMED", "TL-1")
        self.assertEqual(result["commandId"], announcement["commandId"])
        self.assertEqual(result["feedbackStatus"], "CLAIMED")
        self.assertEqual(result["alarmId"], pickup_alarm_id(announcement["commandId"]))
        self.assertTrue(result["appendOnly"])

    def test_revival_uses_a_distinct_stable_alarm_id(self):
        self.assertEqual(pickup_alarm_id("batch-7", "NG_REVIVAL"), "NG_REVIVAL:batch-7")


if __name__ == "__main__":
    unittest.main()
