import unittest

from station_components.station_query import StationQuery


class StationQueryTests(unittest.TestCase):
    def setUp(self):
        self.query = StationQuery([
            {'record_type': 'station', 'station_code': 'ICT', 'status': 'ONLINE', 'updated_at': '2026-08-08 12:00'},
            {'record_type': 'station', 'station_code': 'FCT', 'status': 'OFFLINE', 'updated_at': '2026-08-08 11:00'},
            {'record_type': 'product', 'sn': 'SN-1', 'station': 'ICT', 'status': 'IN_PROCESS', 'work_order_no': 'WO-1'},
            {'record_type': 'product', 'sn': 'SN-2', 'station': 'FCT', 'status': 'PASS', 'work_order_no': 'WO-2'},
        ])

    def test_history_filters_by_sn_and_work_order(self):
        self.assertEqual(self.query.history(sn='SN-1', work_order='WO-1')[0]['sn'], 'SN-1')

    def test_stations_and_in_process_are_shared_queries(self):
        self.assertEqual(len(self.query.stations(status='ONLINE')), 1)
        self.assertEqual(len(self.query.in_process()), 1)


if __name__ == '__main__':
    unittest.main()
