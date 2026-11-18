import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from station_components.attendance_cycle import AttendanceEvent, SnAttendanceCycle, advance_attendance
from station_components.attendance_journey import (JourneyState, ProductAttendanceJourney,
    RouteStep, close_station_and_advance, complete_dependent_step, register_first_station,
    start_dependent_ng_sequence, start_product_attendance)


def closed_cycle(station, attendance_id, at=100):
    value = SnAttendanceCycle(attendance_id, "SN-1", "MANUAL", station, station + "-01", "R18", 1, 1)
    for event in [AttendanceEvent.EXPECTATION_ISSUED, AttendanceEvent.ARRIVAL_OBSERVED,
                  AttendanceEvent.MES_ACCEPTED, AttendanceEvent.WORK_COMPLETED,
                  AttendanceEvent.PRODUCT_CHECKED_OUT, AttendanceEvent.CYCLE_CLOSED]:
        at += 10
        value = advance_attendance(value, event, at, "MES")
    return value, at


class ProductAttendanceJourneyTests(unittest.TestCase):
    def test_first_registration_creates_journey_and_ng_dependency_blocks_main_route(self):
        route = (RouteStep("S1", "manu_pda", ("S2",)), RouteStep("S2", "manu_ict", ()))
        journey = register_first_station(product_attendance_id="pa-1", sn="SN-1",
            work_order_code="WO-1", line_code="MANUAL", route_revision="R18",
            route_steps=route, station_code="manu_pda", occurred_at_ms=100, actor_id="MES")
        journey = start_dependent_ng_sequence(journey, sequence_id="ng-1",
            reason_code="ICT_NG", step_ids=("NG_CONFIRM", "REPAIR", "RETEST"),
            occurred_at_ms=110, actor_id="MES")
        first, at = closed_cycle("manu_pda", "att-pda", 110)
        with self.assertRaises(ValueError):
            close_station_and_advance(journey, first, "S1", "S2", at + 10, "MES")
        journey = complete_dependent_step(journey, sequence_id="ng-1", step_id="NG_CONFIRM",
                                          occurred_at_ms=at + 10, actor_id="MES")
        journey = complete_dependent_step(journey, sequence_id="ng-1", step_id="REPAIR",
                                          occurred_at_ms=at + 20, actor_id="MES")
        journey = complete_dependent_step(journey, sequence_id="ng-1", step_id="RETEST",
                                          occurred_at_ms=at + 30, actor_id="MES")
        self.assertEqual(JourneyState.ACTIVE, journey.state)
        journey = close_station_and_advance(journey, first, "S1", "S2", at + 40, "MES")
        self.assertEqual("S2", journey.current_step_id)

    def test_cannot_create_from_non_first_station(self):
        route = (RouteStep("S1", "manu_pda", ("S2",)), RouteStep("S2", "manu_ict", ()))
        with self.assertRaises(ValueError):
            register_first_station(product_attendance_id="pa-1", sn="SN-1",
                work_order_code="WO-1", line_code="MANUAL", route_revision="R18",
                route_steps=route, station_code="manu_ict", occurred_at_ms=100, actor_id="MES")

    def test_same_component_follows_first_to_last_station(self):
        route = (RouteStep("S1", "manu_pda", ("S2",)), RouteStep("S2", "manu_ict", ()))
        journey = ProductAttendanceJourney("pa-1", "SN-1", "WO-1", "MANUAL", "R18", route, "S1")
        journey = start_product_attendance(journey, 100, "MES")
        first, at = closed_cycle("manu_pda", "att-pda", 100)
        journey = close_station_and_advance(journey, first, "S1", "S2", at + 10, "MES")
        second, at = closed_cycle("manu_ict", "att-ict", at + 10)
        journey = close_station_and_advance(journey, second, "S2", "", at + 10, "MES")
        self.assertEqual(JourneyState.COMPLETED, journey.state)
        self.assertEqual("pa-1", journey.product_attendance_id)
        self.assertEqual(2, len(journey.station_history))

    def test_cannot_skip_to_unauthorized_station(self):
        route = (RouteStep("S1", "manu_pda", ("S2",)), RouteStep("S2", "manu_ict", ()),
                 RouteStep("S3", "manu_fct", ()))
        journey = start_product_attendance(ProductAttendanceJourney(
            "pa-1", "SN-1", "WO-1", "MANUAL", "R18", route, "S1"), 100, "MES")
        first, at = closed_cycle("manu_pda", "att-pda", 100)
        with self.assertRaises(ValueError):
            close_station_and_advance(journey, first, "S1", "S3", at + 10, "MES")


if __name__ == "__main__":
    unittest.main()
