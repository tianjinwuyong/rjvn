"""Pure arrival decision contract shared by MES and station preview/tests.

The station creates :class:`ArrivalFact`.  MES supplies route/NG/work-order
context and owns the final decision.  This module contains no network, UI,
database, scanner or device access, so the rules are deterministic and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Iterable, Optional, Tuple


class ArrivalDecision(str, Enum):
    ACCEPTED_EXPECTED = "ACCEPTED_EXPECTED"
    ACCEPTED_LATE = "ACCEPTED_LATE"
    ACCEPTED_UNEXPECTED = "ACCEPTED_UNEXPECTED"
    DUPLICATE_REPLAY = "DUPLICATE_REPLAY"
    HOLD_AUTH_REQUIRED = "HOLD_AUTH_REQUIRED"
    QUEUED_OFFLINE = "QUEUED_OFFLINE"
    BLOCKED_NG = "BLOCKED_NG"
    BLOCKED_ROUTE = "BLOCKED_ROUTE"
    BLOCKED_WORK_ORDER = "BLOCKED_WORK_ORDER"
    BLOCKED_OFFLINE = "BLOCKED_OFFLINE"
    INVALID_FACT = "INVALID_FACT"


@dataclass(frozen=True)
class ArrivalFact:
    event_id: str
    idempotency_key: str
    sn: str
    line_code: str
    station_code: str
    station_instance: str
    occurred_at_ms: int
    source_type: str
    source_record_id: str = ""
    operator_id: str = ""
    expectation_id: str = ""
    route_revision: str = ""
    cycle_no: int = 0


@dataclass(frozen=True)
class ArrivalExpectation:
    expectation_id: str
    sn: str
    station_code: str
    route_revision: str
    cycle_no: int
    opens_at_ms: int
    due_at_ms: int
    source_station: str = ""


@dataclass(frozen=True)
class ArrivalContext:
    mes_online: bool
    work_order_active: bool
    active_ng: bool
    repair_route_authorized: bool
    route_allows_station: bool
    seen_idempotency_keys: FrozenSet[str] = frozenset()
    expectation: Optional[ArrivalExpectation] = None


@dataclass(frozen=True)
class ArrivalPolicy:
    allow_offline_queue: bool = False
    unexpected_requires_authorization: bool = True
    allow_unexpected_with_mark: bool = False
    late_grace_ms: int = 0


@dataclass(frozen=True)
class ArrivalResult:
    decision: ArrivalDecision
    allow_station_work: bool
    create_exception: bool
    reason_code: str
    reason: str
    expectation_id: str = ""
    route_revision: str = ""
    cycle_no: int = 0


class ReconciliationStatus(str, Enum):
    EXPECTED_PENDING = "EXPECTED_PENDING"
    ARRIVED_EXPECTED = "ARRIVED_EXPECTED"
    ARRIVED_LATE = "ARRIVED_LATE"
    MISSING_OVERDUE = "MISSING_OVERDUE"
    ARRIVED_UNEXPECTED = "ARRIVED_UNEXPECTED"


@dataclass(frozen=True)
class ReconciliationItem:
    status: ReconciliationStatus
    sn: str
    station_code: str
    expectation_id: str = ""
    arrival_event_id: str = ""
    route_revision: str = ""
    cycle_no: int = 0
    due_at_ms: int = 0
    arrived_at_ms: int = 0


def _result(decision, allow, exception, code, reason, expectation=None):
    return ArrivalResult(
        decision=decision,
        allow_station_work=allow,
        create_exception=exception,
        reason_code=code,
        reason=reason,
        expectation_id=expectation.expectation_id if expectation else "",
        route_revision=expectation.route_revision if expectation else "",
        cycle_no=expectation.cycle_no if expectation else 0,
    )


def evaluate_arrival(fact: ArrivalFact, context: ArrivalContext, policy: ArrivalPolicy) -> ArrivalResult:
    """Return one MES-owned arrival decision without side effects."""
    if not all((fact.event_id.strip(), fact.idempotency_key.strip(), fact.sn.strip(),
                fact.line_code.strip(), fact.station_code.strip(),
                fact.station_instance.strip(), fact.source_type.strip())) or fact.occurred_at_ms <= 0:
        return _result(ArrivalDecision.INVALID_FACT, False, True, "INVALID_FACT", "Required arrival fact fields are missing")

    if fact.idempotency_key in context.seen_idempotency_keys:
        return _result(ArrivalDecision.DUPLICATE_REPLAY, False, False, "IDEMPOTENT_REPLAY", "Event was already accepted; return the original MES result", context.expectation)

    if not context.work_order_active:
        return _result(ArrivalDecision.BLOCKED_WORK_ORDER, False, True, "WORK_ORDER_INACTIVE", "The product work order is not active", context.expectation)

    if context.active_ng and not context.repair_route_authorized:
        return _result(ArrivalDecision.BLOCKED_NG, False, True, "ACTIVE_NG", "Product has an active NG and no authorized repair route", context.expectation)

    if not context.route_allows_station:
        return _result(ArrivalDecision.BLOCKED_ROUTE, False, True, "ROUTE_BLOCK", "MES route revision does not allow this station", context.expectation)

    if not context.mes_online:
        if policy.allow_offline_queue:
            return _result(ArrivalDecision.QUEUED_OFFLINE, False, False, "MES_OFFLINE_QUEUED", "Fact is stored locally; station work waits for MES decision", context.expectation)
        return _result(ArrivalDecision.BLOCKED_OFFLINE, False, True, "MES_OFFLINE", "MES decision is required before station work", context.expectation)

    expectation = context.expectation
    expected_here = bool(expectation and expectation.sn.upper() == fact.sn.upper() and expectation.station_code.lower() == fact.station_code.lower())
    if expected_here:
        late_after = expectation.due_at_ms + max(0, policy.late_grace_ms)
        if expectation.due_at_ms > 0 and fact.occurred_at_ms > late_after:
            return _result(ArrivalDecision.ACCEPTED_LATE, True, True, "LATE_ARRIVAL", "Expected product arrived after its due window", expectation)
        return _result(ArrivalDecision.ACCEPTED_EXPECTED, True, False, "EXPECTED", "Expected product arrived at the MES-authorized station", expectation)

    if policy.allow_unexpected_with_mark:
        return _result(ArrivalDecision.ACCEPTED_UNEXPECTED, True, True, "UNEXPECTED_ARRIVAL", "Unexpected product accepted by explicit MES policy", expectation)
    if policy.unexpected_requires_authorization:
        return _result(ArrivalDecision.HOLD_AUTH_REQUIRED, False, True, "UNEXPECTED_AUTH_REQUIRED", "Unexpected arrival requires authorized disposition", expectation)
    return _result(ArrivalDecision.BLOCKED_ROUTE, False, True, "NO_EXPECTATION", "No valid MES expectation exists for this station", expectation)


def reconcile_arrivals(expectations: Iterable[ArrivalExpectation], facts: Iterable[ArrivalFact],
                       now_ms: int, missing_grace_ms: int = 0) -> Tuple[ReconciliationItem, ...]:
    """Reconcile MES pre-arrivals with actual facts without mislabeling in-transit SNs.

    Exact ``expectation_id`` wins.  Legacy facts without it are paired only when
    SN, station, route revision and cycle are compatible.  Unpaired facts remain
    explicit unexpected arrivals for MES route evaluation.
    """
    expected = list(expectations)
    actual = list(facts)
    used = set()
    rows = []
    grace = max(0, int(missing_grace_ms))

    for exp in expected:
        match_index = None
        for index, fact in enumerate(actual):
            if index in used:
                continue
            exact_id = bool(fact.expectation_id and fact.expectation_id == exp.expectation_id)
            compatible = (
                fact.sn.upper() == exp.sn.upper()
                and fact.station_code.lower() == exp.station_code.lower()
                and (not fact.route_revision or fact.route_revision == exp.route_revision)
                and (not fact.cycle_no or fact.cycle_no == exp.cycle_no)
            )
            if exact_id or compatible:
                match_index = index
                if exact_id:
                    break
        if match_index is not None:
            fact = actual[match_index]
            used.add(match_index)
            late = exp.due_at_ms > 0 and fact.occurred_at_ms > exp.due_at_ms + grace
            rows.append(ReconciliationItem(
                status=ReconciliationStatus.ARRIVED_LATE if late else ReconciliationStatus.ARRIVED_EXPECTED,
                sn=exp.sn, station_code=exp.station_code, expectation_id=exp.expectation_id,
                arrival_event_id=fact.event_id, route_revision=exp.route_revision,
                cycle_no=exp.cycle_no, due_at_ms=exp.due_at_ms, arrived_at_ms=fact.occurred_at_ms,
            ))
            continue
        overdue = exp.due_at_ms > 0 and now_ms > exp.due_at_ms + grace
        rows.append(ReconciliationItem(
            status=ReconciliationStatus.MISSING_OVERDUE if overdue else ReconciliationStatus.EXPECTED_PENDING,
            sn=exp.sn, station_code=exp.station_code, expectation_id=exp.expectation_id,
            route_revision=exp.route_revision, cycle_no=exp.cycle_no, due_at_ms=exp.due_at_ms,
        ))

    for index, fact in enumerate(actual):
        if index in used:
            continue
        rows.append(ReconciliationItem(
            status=ReconciliationStatus.ARRIVED_UNEXPECTED,
            sn=fact.sn, station_code=fact.station_code, expectation_id=fact.expectation_id,
            arrival_event_id=fact.event_id, route_revision=fact.route_revision,
            cycle_no=fact.cycle_no, arrived_at_ms=fact.occurred_at_ms,
        ))
    return tuple(rows)
