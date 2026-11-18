"""Shared read-only query component for MES, station Agents, and PDA apps."""


class StationQuery:
    def __init__(self, records):
        self.records = list(records or [])

    @staticmethod
    def _match(row, key, value, aliases=()):
        if not value:
            return True
        wanted = str(value).strip().lower()
        actual = row.get(key)
        if actual is None:
            for alias in aliases:
                actual = row.get(alias)
                if actual is not None:
                    break
        return wanted in str(actual or '').lower()

    def _filter(self, rows, *, sn='', station='', status='', work_order='', box_qr='', shipment_id='', query=''):
        result = []
        for row in rows:
            if not self._match(row, 'sn', sn, ('ng_sn',)):
                continue
            if not self._match(row, 'station', station, ('source_station', 'station_code')):
                continue
            if not self._match(row, 'status', status, ('result', 'state')):
                continue
            if not self._match(row, 'work_order', work_order, ('repair_work_order_no', 'work_order_no')):
                continue
            if not self._match(row, 'box_qr', box_qr, ('bucket_qr', 'station_qr')):
                continue
            if not self._match(row, 'shipment_id', shipment_id, ('shipmentId', 'shipment')):
                continue
            if query and str(query).strip().lower() not in str(row).lower():
                continue
            result.append(row)
        return sorted(result, key=lambda r: str(r.get('updated_at') or r.get('created_at') or r.get('detected_at') or ''), reverse=True)

    def history(self, **filters):
        return self._filter(self.records, **filters)

    def stations(self, **filters):
        return self._filter([r for r in self.records if r.get('record_type', 'station') == 'station'], **filters)

    def in_process(self, **filters):
        active = {'IN_PROCESS', 'REPAIR_RECEIVED', 'WAITING_RECEIPT', 'WAITING_RETEST', 'WIP'}
        rows = [r for r in self.records if str(r.get('status') or r.get('state') or '').upper() in active]
        return self._filter(rows, **filters)
