import unittest

from station_components.ng_query import query_ng_records


class NgQueryTests(unittest.TestCase):
    def test_filters_by_sn_station_and_status(self):
        rows = [
            {'sn': 'SN-1', 'source_station': 'ICT', 'status': 'CONFIRMED_NG', 'detected_at': '2026-08-08 10:00:00'},
            {'sn': 'SN-2', 'source_station': 'FCT', 'status': 'PASS', 'detected_at': '2026-08-08 11:00:00'},
        ]
        result = query_ng_records(rows, sn='sn-1', station='ict', status='ng')
        self.assertEqual([item['sn'] for item in result], ['SN-1'])

    def test_date_range_and_newest_first(self):
        rows = [{'sn': 'A', 'detected_at': '2026-08-07 10:00:00'}, {'sn': 'B', 'detected_at': '2026-08-08 10:00:00'}]
        result = query_ng_records(rows, date_from='2026-08-08', date_to='2026-08-08')
        self.assertEqual([item['sn'] for item in result], ['B'])


if __name__ == '__main__':
    unittest.main()
