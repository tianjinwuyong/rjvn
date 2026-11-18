import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from station_components.arrival import (ArrivalContext, ArrivalDecision, ArrivalExpectation,
    ArrivalFact, ArrivalPolicy, ReconciliationStatus, evaluate_arrival, reconcile_arrivals)


def fact(**changes):
    values = dict(event_id="evt-1", idempotency_key="key-1", sn="SN-1", line_code="MANUAL",
                  station_code="manu_ict", station_instance="ict-01", occurred_at_ms=2000,
                  source_type="SCANNER")
    values.update(changes)
    return ArrivalFact(**values)


def expectation(**changes):
    values = dict(expectation_id="exp-1", sn="SN-1", station_code="manu_ict",
                  route_revision="R18", cycle_no=1, opens_at_ms=1000, due_at_ms=3000)
    values.update(changes)
    return ArrivalExpectation(**values)


def context(**changes):
    values = dict(mes_online=True, work_order_active=True, active_ng=False,
                  repair_route_authorized=False, route_allows_station=True,
                  expectation=expectation())
    values.update(changes)
    return ArrivalContext(**values)


class ArrivalLogicTests(unittest.TestCase):
    def test_expected_arrival_is_accepted(self):
        result = evaluate_arrival(fact(), context(), ArrivalPolicy())
        self.assertEqual(ArrivalDecision.ACCEPTED_EXPECTED, result.decision)
        self.assertTrue(result.allow_station_work)

    def test_active_ng_is_blocked_before_route(self):
        result = evaluate_arrival(fact(), context(active_ng=True), ArrivalPolicy())
        self.assertEqual(ArrivalDecision.BLOCKED_NG, result.decision)
        self.assertFalse(result.allow_station_work)

    def test_authorized_repair_route_can_continue(self):
        result = evaluate_arrival(fact(), context(active_ng=True, repair_route_authorized=True), ArrivalPolicy())
        self.assertEqual(ArrivalDecision.ACCEPTED_EXPECTED, result.decision)

    def test_duplicate_network_replay_is_not_process_exception(self):
        result = evaluate_arrival(fact(), context(seen_idempotency_keys=frozenset({"key-1"})), ArrivalPolicy())
        self.assertEqual(ArrivalDecision.DUPLICATE_REPLAY, result.decision)
        self.assertFalse(result.create_exception)

    def test_unexpected_arrival_waits_for_authorization(self):
        result = evaluate_arrival(fact(), context(expectation=None), ArrivalPolicy())
        self.assertEqual(ArrivalDecision.HOLD_AUTH_REQUIRED, result.decision)

    def test_offline_queue_does_not_start_station_work(self):
        result = evaluate_arrival(fact(), context(mes_online=False), ArrivalPolicy(allow_offline_queue=True))
        self.assertEqual(ArrivalDecision.QUEUED_OFFLINE, result.decision)
        self.assertFalse(result.allow_station_work)

    def test_late_expected_arrival_is_accepted_and_exception_recorded(self):
        result = evaluate_arrival(fact(occurred_at_ms=5000), context(), ArrivalPolicy(late_grace_ms=500))
        self.assertEqual(ArrivalDecision.ACCEPTED_LATE, result.decision)
        self.assertTrue(result.allow_station_work)
        self.assertTrue(result.create_exception)

    def test_reconciliation_distinguishes_pending_missing_and_unexpected(self):
        expectations = [
            expectation(expectation_id="pending", sn="SN-P", due_at_ms=9000),
            expectation(expectation_id="missing", sn="SN-M", due_at_ms=3000),
            expectation(expectation_id="arrived", sn="SN-A", due_at_ms=6000),
        ]
        facts = [
            fact(event_id="arr-a", idempotency_key="a", sn="SN-A", expectation_id="arrived"),
            fact(event_id="arr-x", idempotency_key="x", sn="SN-X"),
        ]
        rows = reconcile_arrivals(expectations, facts, now_ms=7000, missing_grace_ms=500)
        by_sn = {row.sn: row.status for row in rows}
        self.assertEqual(ReconciliationStatus.EXPECTED_PENDING, by_sn["SN-P"])
        self.assertEqual(ReconciliationStatus.MISSING_OVERDUE, by_sn["SN-M"])
        self.assertEqual(ReconciliationStatus.ARRIVED_EXPECTED, by_sn["SN-A"])
        self.assertEqual(ReconciliationStatus.ARRIVED_UNEXPECTED, by_sn["SN-X"])


if __name__ == "__main__":
    unittest.main()
