"""Shared read-only NG query component for station agents, MES, and PDA views."""
from datetime import datetime


def query_ng_records(records, *, sn='', station='', status='', work_order='', box_qr='', shipment_id='',
                    date_from='', date_to='', limit=500):
    """Filter NG records without changing source data; returns newest records first."""
    def text(value):
        return str(value or '').strip().lower()

    wanted = {
        'sn': text(sn), 'station': text(station), 'status': text(status),
        'work_order': text(work_order), 'box_qr': text(box_qr), 'shipment_id': text(shipment_id),
    }
    result = []
    for item in records or []:
        values = {key: text(item.get(key) or item.get(alias)) for key, alias in (
            ('sn', 'ng_sn'), ('station', 'source_station'), ('status', 'result'),
            ('work_order', 'repair_work_order_no'), ('box_qr', 'bucket_qr'), ('shipment_id', 'shipmentId'))}
        if any(wanted[key] and wanted[key] not in values[key] for key in wanted if key not in ('date_from', 'date_to')):
            continue
        stamp = str(item.get('detected_at') or item.get('created_at') or item.get('updated_at') or '')
        if date_from and stamp[:10] < str(date_from)[:10]:
            continue
        if date_to and stamp[:10] > str(date_to)[:10]:
            continue
        result.append(item)
    result.sort(key=lambda row: str(row.get('detected_at') or row.get('created_at') or row.get('updated_at') or ''), reverse=True)
    return result[:max(1, int(limit))]
