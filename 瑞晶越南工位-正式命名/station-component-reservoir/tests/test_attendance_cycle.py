import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from station_components.attendance_cycle import (AttendanceEvent, AttendanceState,
    InvalidAttendanceTransition, SnAttendanceCycle, advance_attendance)


def cycle():
    return SnAttendanceCycle("att-1", "SN-1", "MANUAL", "manu_ict", "ict-01", "R18", 1, 1)


class AttendanceCycleTests(unittest.TestCase):
    def step(self, value, event, at):
        return advance_attendance(value, event, at, "MES")

    def test_happy_path_closes(self):
        value = cycle()
        for event, at in [
            (AttendanceEvent.EXPECTATION_ISSUED, 1000),
            (AttendanceEvent.ARRIVAL_OBSERVED, 2000),
            (AttendanceEvent.MES_ACCEPTED, 2100),
            (AttendanceEvent.WORK_COMPLETED, 3000),
            (AttendanceEvent.PRODUCT_CHECKED_OUT, 3100),
            (AttendanceEvent.CYCLE_CLOSED, 3200),
        ]:
            value = self.step(value, event, at)
        self.assertEqual(AttendanceState.CLOSED, value.state)
        self.assertEqual(6, len(value.transitions))

    def test_missing_can_arrive_late_and_continue(self):
        value = self.step(cycle(), AttendanceEvent.EXPECTATION_ISSUED, 1000)
        value = self.step(value, AttendanceEvent.DUE_WINDOW_MISSED, 5000)
        value = self.step(value, AttendanceEvent.ARRIVAL_OBSERVED, 6000)
        value = self.step(value, AttendanceEvent.MES_ACCEPTED, 6100)
        self.assertEqual(AttendanceState.IN_STATION, value.state)

    def test_blocked_jump_needs_authorization_before_acceptance(self):
        value = self.step(cycle(), AttendanceEvent.ARRIVAL_OBSERVED, 1000)
        value = self.step(value, AttendanceEvent.MES_BLOCKED, 1100)
        value = self.step(value, AttendanceEvent.EXCEPTION_AUTHORIZED, 1200)
        value = self.step(value, AttendanceEvent.MES_ACCEPTED, 1300)
        self.assertEqual(AttendanceState.IN_STATION, value.state)

    def test_invalid_transition_is_rejected(self):
        with self.assertRaises(InvalidAttendanceTransition):
            self.step(cycle(), AttendanceEvent.WORK_COMPLETED, 1000)


if __name__ == "__main__":
    unittest.main()
