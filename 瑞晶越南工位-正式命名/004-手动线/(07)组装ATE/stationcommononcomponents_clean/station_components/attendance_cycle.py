"""State machine for one SN attendance cycle at one station."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Tuple


class AttendanceState(str, Enum):
    CREATED = "CREATED"
    EXPECTED = "EXPECTED"
    DECISION_PENDING = "DECISION_PENDING"
    OFFLINE_QUEUED = "OFFLINE_QUEUED"
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"
    MISSING_OVERDUE = "MISSING_OVERDUE"
    IN_STATION = "IN_STATION"
    COMPLETED = "COMPLETED"
    CHECKED_OUT = "CHECKED_OUT"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class AttendanceEvent(str, Enum):
    EXPECTATION_ISSUED = "EXPECTATION_ISSUED"
    ARRIVAL_OBSERVED = "ARRIVAL_OBSERVED"
    DUE_WINDOW_MISSED = "DUE_WINDOW_MISSED"
    MES_ACCEPTED = "MES_ACCEPTED"
    MES_HELD = "MES_HELD"
    MES_BLOCKED = "MES_BLOCKED"
    MES_UNAVAILABLE = "MES_UNAVAILABLE"
    RETRY_DECISION = "RETRY_DECISION"
    EXCEPTION_AUTHORIZED = "EXCEPTION_AUTHORIZED"
    WORK_COMPLETED = "WORK_COMPLETED"
    PRODUCT_CHECKED_OUT = "PRODUCT_CHECKED_OUT"
    EXCEPTION_RESOLVED = "EXCEPTION_RESOLVED"
    CYCLE_CLOSED = "CYCLE_CLOSED"
    EXPECTATION_CANCELLED = "EXPECTATION_CANCELLED"


class InvalidAttendanceTransition(ValueError):
    pass


@dataclass(frozen=True)
class AttendanceTransition:
    sequence: int
    event: AttendanceEvent
    from_state: AttendanceState
    to_state: AttendanceState
    occurred_at_ms: int
    actor_id: str
    reason_code: str = ""
    reference_id: str = ""


@dataclass(frozen=True)
class SnAttendanceCycle:
    attendance_id: str
    sn: str
    line_code: str
    station_code: str
    station_instance: str
    route_revision: str
    cycle_no: int
    visit_no: int
    state: AttendanceState = AttendanceState.CREATED
    transitions: Tuple[AttendanceTransition, ...] = ()

    @property
    def identity_key(self):
        return f"{self.sn}|{self.route_revision}|{self.cycle_no}|{self.station_code}|{self.station_instance}|{self.visit_no}"


TRANSITIONS = {
    (AttendanceState.CREATED, AttendanceEvent.EXPECTATION_ISSUED): AttendanceState.EXPECTED,
    (AttendanceState.CREATED, AttendanceEvent.ARRIVAL_OBSERVED): AttendanceState.DECISION_PENDING,
    (AttendanceState.EXPECTED, AttendanceEvent.ARRIVAL_OBSERVED): AttendanceState.DECISION_PENDING,
    (AttendanceState.EXPECTED, AttendanceEvent.DUE_WINDOW_MISSED): AttendanceState.MISSING_OVERDUE,
    (AttendanceState.MISSING_OVERDUE, AttendanceEvent.ARRIVAL_OBSERVED): AttendanceState.DECISION_PENDING,
    (AttendanceState.DECISION_PENDING, AttendanceEvent.MES_ACCEPTED): AttendanceState.IN_STATION,
    (AttendanceState.DECISION_PENDING, AttendanceEvent.MES_HELD): AttendanceState.HOLD,
    (AttendanceState.DECISION_PENDING, AttendanceEvent.MES_BLOCKED): AttendanceState.BLOCKED,
    (AttendanceState.DECISION_PENDING, AttendanceEvent.MES_UNAVAILABLE): AttendanceState.OFFLINE_QUEUED,
    (AttendanceState.OFFLINE_QUEUED, AttendanceEvent.RETRY_DECISION): AttendanceState.DECISION_PENDING,
    (AttendanceState.HOLD, AttendanceEvent.EXCEPTION_AUTHORIZED): AttendanceState.DECISION_PENDING,
    (AttendanceState.BLOCKED, AttendanceEvent.EXCEPTION_AUTHORIZED): AttendanceState.DECISION_PENDING,
    (AttendanceState.IN_STATION, AttendanceEvent.WORK_COMPLETED): AttendanceState.COMPLETED,
    (AttendanceState.COMPLETED, AttendanceEvent.PRODUCT_CHECKED_OUT): AttendanceState.CHECKED_OUT,
    (AttendanceState.CHECKED_OUT, AttendanceEvent.CYCLE_CLOSED): AttendanceState.CLOSED,
    (AttendanceState.MISSING_OVERDUE, AttendanceEvent.EXCEPTION_RESOLVED): AttendanceState.CLOSED,
    (AttendanceState.HOLD, AttendanceEvent.EXCEPTION_RESOLVED): AttendanceState.CLOSED,
    (AttendanceState.BLOCKED, AttendanceEvent.EXCEPTION_RESOLVED): AttendanceState.CLOSED,
    (AttendanceState.CREATED, AttendanceEvent.EXPECTATION_CANCELLED): AttendanceState.CANCELLED,
    (AttendanceState.EXPECTED, AttendanceEvent.EXPECTATION_CANCELLED): AttendanceState.CANCELLED,
}


def advance_attendance(cycle: SnAttendanceCycle, event: AttendanceEvent, occurred_at_ms: int,
                       actor_id: str, reason_code: str = "", reference_id: str = "") -> SnAttendanceCycle:
    """Advance one cycle and append immutable transition evidence."""
    target = TRANSITIONS.get((cycle.state, event))
    if target is None:
        raise InvalidAttendanceTransition(f"{cycle.state.value} cannot handle {event.value}")
    if occurred_at_ms <= 0:
        raise ValueError("occurred_at_ms must be positive")
    if not actor_id.strip():
        raise ValueError("actor_id is required")
    if cycle.transitions and occurred_at_ms < cycle.transitions[-1].occurred_at_ms:
        raise ValueError("attendance transition time cannot move backwards")
    transition = AttendanceTransition(
        sequence=len(cycle.transitions) + 1,
        event=event,
        from_state=cycle.state,
        to_state=target,
        occurred_at_ms=occurred_at_ms,
        actor_id=actor_id.strip(),
        reason_code=reason_code.strip(),
        reference_id=reference_id.strip(),
    )
    return replace(cycle, state=target, transitions=cycle.transitions + (transition,))
