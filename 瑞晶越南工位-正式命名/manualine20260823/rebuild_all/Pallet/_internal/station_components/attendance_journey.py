"""MES-owned full product attendance journey across all stations."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Tuple

from .attendance_cycle import AttendanceState, SnAttendanceCycle


class JourneyState(str, Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    HOLD = "HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DependentSequenceState(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class RouteStep:
    step_id: str
    station_code: str
    allowed_next_step_ids: Tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class DependentSequence:
    """MES-issued NG/rework sequence that must close before the main route resumes."""
    sequence_id: str
    reason_code: str
    parent_step_id: str
    step_ids: Tuple[str, ...]
    current_index: int = 0
    state: DependentSequenceState = DependentSequenceState.ACTIVE

    @property
    def current_step_id(self):
        return self.step_ids[self.current_index] if self.state is DependentSequenceState.ACTIVE else ""


@dataclass(frozen=True)
class StationAttendanceSummary:
    attendance_id: str
    step_id: str
    station_code: str
    cycle_no: int
    visit_no: int
    final_state: AttendanceState


@dataclass(frozen=True)
class JourneyTransition:
    sequence: int
    event_type: str
    step_id: str
    occurred_at_ms: int
    actor_id: str
    reference_id: str = ""


@dataclass(frozen=True)
class ProductAttendanceJourney:
    product_attendance_id: str
    sn: str
    work_order_code: str
    line_code: str
    route_revision: str
    route_steps: Tuple[RouteStep, ...]
    current_step_id: str
    state: JourneyState = JourneyState.PLANNED
    station_history: Tuple[StationAttendanceSummary, ...] = ()
    dependent_sequences: Tuple[DependentSequence, ...] = ()
    transitions: Tuple[JourneyTransition, ...] = ()

    def route_step(self, step_id):
        for step in self.route_steps:
            if step.step_id == step_id:
                return step
        raise ValueError(f"unknown route step: {step_id}")


def _append(journey, event_type, step_id, occurred_at_ms, actor_id, reference_id="", **changes):
    if occurred_at_ms <= 0 or not actor_id.strip():
        raise ValueError("positive occurred_at_ms and actor_id are required")
    if journey.transitions and occurred_at_ms < journey.transitions[-1].occurred_at_ms:
        raise ValueError("journey time cannot move backwards")
    item = JourneyTransition(len(journey.transitions) + 1, event_type, step_id,
                             occurred_at_ms, actor_id.strip(), reference_id.strip())
    return replace(journey, transitions=journey.transitions + (item,), **changes)


def start_product_attendance(journey: ProductAttendanceJourney, occurred_at_ms: int, actor_id: str):
    if journey.state is not JourneyState.PLANNED:
        raise ValueError("journey already started")
    first = journey.route_step(journey.current_step_id)
    if not first.step_id:
        raise ValueError("first route step is required")
    return _append(journey, "JOURNEY_STARTED", first.step_id, occurred_at_ms, actor_id,
                   journey.product_attendance_id, state=JourneyState.ACTIVE)


def register_first_station(*, product_attendance_id: str, sn: str, work_order_code: str,
                           line_code: str, route_revision: str,
                           route_steps: Tuple[RouteStep, ...], station_code: str,
                           occurred_at_ms: int, actor_id: str):
    """Create the aggregate only when the SN first registers at the route's first station."""
    if not route_steps:
        raise ValueError("MES route sequence is required")
    first = route_steps[0]
    if station_code.lower() != first.station_code.lower():
        raise ValueError("product attendance can only be created by first-station registration")
    journey = ProductAttendanceJourney(product_attendance_id, sn, work_order_code,
                                       line_code, route_revision, route_steps, first.step_id)
    return _append(journey, "FIRST_STATION_REGISTERED", first.step_id, occurred_at_ms,
                   actor_id, product_attendance_id, state=JourneyState.ACTIVE)


def start_dependent_ng_sequence(journey: ProductAttendanceJourney, *, sequence_id: str,
                                reason_code: str, step_ids: Tuple[str, ...],
                                occurred_at_ms: int, actor_id: str):
    """Pause the main sequence and attach an ordered NG disposition sequence."""
    if journey.state is not JourneyState.ACTIVE:
        raise ValueError("NG sequence requires an active main journey")
    if not sequence_id.strip() or not reason_code.strip() or not step_ids:
        raise ValueError("NG sequence id, reason and steps are required")
    if any(item.sequence_id == sequence_id for item in journey.dependent_sequences):
        raise ValueError("dependent sequence id already exists")
    child = DependentSequence(sequence_id.strip(), reason_code.strip(),
                              journey.current_step_id, tuple(step_ids))
    return _append(journey, "NG_DEPENDENT_SEQUENCE_STARTED", journey.current_step_id,
                   occurred_at_ms, actor_id, sequence_id,
                   state=JourneyState.HOLD,
                   dependent_sequences=journey.dependent_sequences + (child,))


def complete_dependent_step(journey: ProductAttendanceJourney, *, sequence_id: str,
                            step_id: str, occurred_at_ms: int, actor_id: str):
    """Complete exactly the currently expected NG step; resume main route at child closure."""
    if journey.state is not JourneyState.HOLD:
        raise ValueError("main journey is not waiting on an NG sequence")
    items = list(journey.dependent_sequences)
    index = next((i for i, item in enumerate(items) if item.sequence_id == sequence_id), -1)
    if index < 0:
        raise ValueError("dependent sequence not found")
    child = items[index]
    if child.state is not DependentSequenceState.ACTIVE or child.current_step_id != step_id:
        raise ValueError("dependent sequence steps must finish one by one")
    is_last = child.current_index == len(child.step_ids) - 1
    items[index] = replace(child,
                           current_index=child.current_index if is_last else child.current_index + 1,
                           state=DependentSequenceState.COMPLETED if is_last else child.state)
    event = "NG_DEPENDENT_SEQUENCE_COMPLETED" if is_last else "NG_DEPENDENT_STEP_COMPLETED"
    return _append(journey, event, step_id, occurred_at_ms, actor_id, sequence_id,
                   state=JourneyState.ACTIVE if is_last else JourneyState.HOLD,
                   dependent_sequences=tuple(items))


def close_station_and_advance(journey: ProductAttendanceJourney, cycle: SnAttendanceCycle,
                              step_id: str, next_step_id: str, occurred_at_ms: int, actor_id: str):
    """Attach one closed station cycle and advance the same journey."""
    if journey.state is not JourneyState.ACTIVE:
        raise ValueError("journey is not active")
    if step_id != journey.current_step_id:
        raise ValueError("station cycle is not for the current journey step")
    step = journey.route_step(step_id)
    if cycle.state is not AttendanceState.CLOSED:
        raise ValueError("station attendance cycle must be closed before route advance")
    if cycle.sn.upper() != journey.sn.upper() or cycle.route_revision != journey.route_revision:
        raise ValueError("station cycle does not belong to this product attendance journey")
    if cycle.station_code.lower() != step.station_code.lower():
        raise ValueError("station cycle does not match the route step")

    summary = StationAttendanceSummary(cycle.attendance_id, step_id, cycle.station_code,
                                       cycle.cycle_no, cycle.visit_no, cycle.state)
    history = journey.station_history + (summary,)
    if next_step_id:
        if next_step_id not in step.allowed_next_step_ids:
            raise ValueError("next step is not authorized by the MES route revision")
        journey.route_step(next_step_id)
        return _append(journey, "STATION_CLOSED_NEXT_EXPECTED", step_id, occurred_at_ms,
                       actor_id, cycle.attendance_id, station_history=history,
                       current_step_id=next_step_id)
    if step.allowed_next_step_ids:
        raise ValueError("a next step is required before the route is complete")
    return _append(journey, "JOURNEY_COMPLETED", step_id, occurred_at_ms, actor_id,
                   cycle.attendance_id, station_history=history, state=JourneyState.COMPLETED)
