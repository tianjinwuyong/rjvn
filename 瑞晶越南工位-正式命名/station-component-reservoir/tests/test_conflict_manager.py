import unittest

from station_components.conflict_manager import ConflictManager


class ConflictManagerTests(unittest.TestCase):
    def test_first_mismatch_blocks_and_second_does_not_replace_it(self):
        manager = ConflictManager()
        first = manager.observe(entity_type='WO', entity_id='WO-1',
                                existing={'version': '1', 'eventId': 'old'},
                                incoming={'version': '2', 'eventId': 'new'})
        second = manager.observe(entity_type='WO', entity_id='WO-1',
                                 existing={'version': '1', 'eventId': 'old'},
                                 incoming={'version': '3', 'eventId': 'newer'})
        self.assertEqual(first['decision'], 'CONFLICT_FIRST_OBSERVED')
        self.assertEqual(second['decision'], 'CONFLICT_ALREADY_OPEN')
        self.assertEqual(first['conflict']['incoming_version'], '2')
        self.assertEqual(manager.resolve('WO', 'WO-1')['status'], 'RESOLVED')


if __name__ == '__main__':
    unittest.main()
