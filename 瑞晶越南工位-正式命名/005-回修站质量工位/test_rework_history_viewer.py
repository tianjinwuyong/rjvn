import unittest
import tempfile
from pathlib import Path

from rework_2d_agent import build_wo_history_text, build_wo_history_rows, build_all_wo_history_rows, build_local_resource_view
import rework_core
from station_components.local_resource_viewer import build_local_resource_view as build_common_resource_view


class WorkOrderHistoryViewerTests(unittest.TestCase):
    def test_all_history_rows_include_station_and_recent_filter(self):
        snapshot = {
            'work_orders': [
                {'work_order_no': 'RWO-001', 'ng_sn': 'SN-001', 'source_station': 'ICT', 'status': 'CLOSED', 'updated_at': '2026-08-08T10:00:00Z'},
                {'work_order_no': 'RWO-002', 'ng_sn': 'SN-002', 'source_station': 'FCT', 'status': 'REPAIR_IN_PROGRESS', 'updated_at': '2026-08-08T09:00:00Z'},
            ],
            'history': [{'work_order_no': 'RWO-001', 'action': 'RECEIVE', 'result': 'OK'}],
            'step_progress': [{'work_order_no': 'RWO-001', 'step_code': 'DIAG', 'confirmed_by': 'op'}],
            'test_progress': [{'work_order_no': 'RWO-001', 'test_code': 'ICT', 'result': 'PASS'}],
            'materials': [],
        }
        rows = build_all_wo_history_rows(snapshot)
        self.assertEqual([row['work_order_no'] for row in rows], ['RWO-001', 'RWO-002'])
        self.assertEqual(rows[0]['source_station'], 'ICT')
        self.assertEqual(rows[0]['events'], 3)
        self.assertEqual(len(build_all_wo_history_rows(snapshot, 'FCT')), 1)

    def test_history_text_includes_identity_and_events(self):
        snapshot = {
            'station_code': 'manu_rework',
            'work_orders': [{
                'work_order_no': 'RWO-001', 'ng_sn': 'SN-001',
                'source_station': 'ICT', 'status': 'REPAIR_RECEIVED',
                'updated_at': '2026-08-08T10:00:00Z',
            }],
            'history': [{'work_order_no': 'RWO-001', 'action': 'RECEIVE', 'result': 'OK'}],
            'step_progress': [{'work_order_no': 'RWO-001', 'step_code': 'DIAG', 'confirmed_by': 'op'}],
            'test_progress': [{'work_order_no': 'RWO-001', 'test_code': 'ICT', 'result': 'PASS'}],
            'materials': [{'work_order_no': 'RWO-001', 'material_code': 'MAT-1', 'quantity': 1}],
        }
        text = build_wo_history_text(snapshot, 'RWO-001')
        self.assertIn('RWO-001', text)
        self.assertIn('SN-001', text)
        self.assertIn('RECEIVE', text)
        self.assertIn('DIAG', text)
        self.assertIn('PASS', text)
        self.assertIn('MAT-1', text)

    def test_history_rows_are_searchable_and_include_timeline_types(self):
        snapshot = {
            'work_orders': [{'work_order_no': 'RWO-002', 'ng_sn': 'SN-002'}],
            'history': [{'work_order_no': 'RWO-002', 'action': 'PICKUP', 'result': 'ACK'}],
            'step_progress': [{'work_order_no': 'RWO-002', 'step_code': 'CLEAN'}],
            'test_progress': [{'work_order_no': 'RWO-002', 'test_code': 'FCT', 'result': 'PASS'}],
            'materials': [],
        }
        rows = build_wo_history_rows(snapshot, 'RWO-002', 'fct')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['type'], 'RETEST')
        self.assertEqual(rows[0]['result'], 'PASS')

    def test_mes_event_is_saved_to_outbox_when_mes_is_offline(self):
        with tempfile.TemporaryDirectory() as td:
            core = rework_core.ReworkCore(db_path=Path(td) / 'rework.db', mes_api='http://127.0.0.1:9/api')
            original_http = rework_core.http
            try:
                rework_core.http = lambda *args, **kwargs: (0, {'code': 'MES_OFFLINE'})
                result = core._emit('TEST_EVENT', {'sn': 'SN-OFFLINE'}, idempotent_id='evt-offline-1')
            finally:
                rework_core.http = original_http
            self.assertEqual(result['status'], 'QUEUED_OFFLINE')
            with core.connect() as db:
                row = db.execute('SELECT event_id,event_type,sn FROM mes_sync_queue').fetchone()
            self.assertEqual(tuple(row), ('evt-offline-1', 'TEST_EVENT', 'SN-OFFLINE'))
            db.close()

    def test_local_resource_view_reports_sqlite_and_outbox(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / 'rework.db'
            db_path.write_bytes(b'abc')
            view = build_local_resource_view(db_path, {'outbox': [{'id': 1}, {'id': 2}], 'station_code': 'manu_rework'})
            self.assertEqual(view['database']['path'], str(db_path))
            self.assertEqual(view['database']['bytes'], 3)
            self.assertEqual(view['outbox_pending'], 2)
            self.assertEqual(view['station_code'], 'manu_rework')
            self.assertTrue('tables' in view and 'outbox_events' in view)
            self.assertEqual(build_common_resource_view(db_path, {'outbox': []})['database']['bytes'], 3)


if __name__ == '__main__':
    unittest.main()
