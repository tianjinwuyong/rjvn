"""MES-owned first-observation conflict detection and blocking."""
from dataclasses import dataclass, asdict
import time
import uuid


@dataclass(frozen=True)
class ConflictRecord:
    conflict_id: str
    entity_type: str
    entity_id: str
    existing_version: str
    incoming_version: str
    existing_event_id: str
    incoming_event_id: str
    detected_at: int
    status: str = 'OPEN'


class ConflictManager:
    def __init__(self):
        self._open = {}

    def observe(self, *, entity_type, entity_id, existing, incoming):
        """Return ACCEPTED or the first immutable OPEN conflict; never silently overwrites."""
        key = (str(entity_type), str(entity_id))
        existing_version = str(existing.get('version', ''))
        incoming_version = str(incoming.get('version', ''))
        if existing_version == incoming_version:
            return {'decision': 'ACCEPTED', 'blocked': False, 'conflict': None}
        if key in self._open:
            record = self._open[key]
            return {'decision': 'CONFLICT_ALREADY_OPEN', 'blocked': True, 'conflict': asdict(record)}
        record = ConflictRecord(
            conflict_id='CONFLICT-' + uuid.uuid4().hex,
            entity_type=str(entity_type), entity_id=str(entity_id),
            existing_version=existing_version, incoming_version=incoming_version,
            existing_event_id=str(existing.get('eventId', '')),
            incoming_event_id=str(incoming.get('eventId', '')),
            detected_at=int(time.time() * 1000),
        )
        self._open[key] = record
        return {'decision': 'CONFLICT_FIRST_OBSERVED', 'blocked': True, 'conflict': asdict(record)}

    def resolve(self, entity_type, entity_id):
        key = (str(entity_type), str(entity_id))
        record = self._open.pop(key, None)
        if not record:
            return None
        result = asdict(record)
        result['status'] = 'RESOLVED'
        return result
