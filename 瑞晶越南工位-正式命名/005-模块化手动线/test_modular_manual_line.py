import unittest

from station_registry import StationRegistry
from visualizations.ng_route_timeline import build_ng_route_steps
from visualizations.ate_8sn_panel import AteSlotState
from modular_i18n import LOCALES, STATIONS, TEXT, validate as validate_i18n
from modular_history import StationHistoryLedger
from modular_scanner import ScannerGatewayPanel
from modular_repair import RepairWorkflowController, create_preview_case
import tempfile
from pathlib import Path


class ModularManualLineTests(unittest.TestCase):
    def setUp(self):
        self.registry = StationRegistry()

    def test_all_thirteen_stations_exist_in_sequence(self):
        stations = self.registry.all()
        self.assertEqual(13, len(stations))
        self.assertEqual(list(range(1, 14)), [station.sequence for station in stations])

    def test_every_station_has_normal_and_ng_routes(self):
        for station in self.registry.all():
            self.assertTrue(station.normal_next)
            self.assertTrue(station.ng_policy.repair_destination)
            station.ng_policy.validate()

    def test_aging_dependent_repairs_repeat_aging(self):
        for code in ("mod_manu_aging", "mod_manu_hivolt_ate"):
            self.assertEqual("REPEAT_AGING", self.registry.get(code).ng_policy.return_route)

    def test_aoi_is_mark_only(self):
        self.assertEqual("MARK_ONLY", self.registry.get("mod_manu_aoi").ng_policy.action_mode)

    def test_depanel_removes_ng_immediately(self):
        self.assertEqual("REMOVE_IMMEDIATELY", self.registry.get("mod_manu_depanel").ng_policy.action_mode)

    def test_mark_only_route_has_no_repair_receipt(self):
        steps = build_ng_route_steps(self.registry.get("mod_manu_aoi").ng_policy)
        self.assertNotIn("RECEIPT", [step.code for step in steps])

    def test_repair_route_contains_receipt_repair_and_return(self):
        steps = build_ng_route_steps(self.registry.get("mod_manu_assembly_ate").ng_policy)
        codes = [step.code for step in steps]
        self.assertLess(codes.index("RECEIPT"), codes.index("REPAIR"))
        self.assertLess(codes.index("REPAIR"), codes.index("RETURN"))

    def test_ate_has_eight_independent_slots(self):
        slots = [AteSlotState(index + 1) for index in range(8)]
        self.assertEqual(list(range(1, 9)), [slot.slot for slot in slots])
        self.assertEqual(8, len({slot.slot for slot in slots}))

    def test_every_station_selects_a_visualization_adapter(self):
        for station in self.registry.all():
            self.assertTrue(station.adapter)

    def test_all_shell_languages_have_same_keys(self):
        self.assertTrue(validate_i18n())
        self.assertEqual(set(TEXT["en"]),set(TEXT["zh"]))
        self.assertEqual(set(TEXT["en"]),set(TEXT["vi"]))

    def test_every_station_has_three_names(self):
        self.assertEqual({station.code for station in self.registry.all()},set(STATIONS))

    def test_history_is_persistent_and_immutable(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=StationHistoryLedger(Path(folder)/"history.db")
            event=ledger.append("mod_manu_ict","NG_DETECTED",sn="SN001",result="NG")
            self.assertEqual(event,ledger.list("mod_manu_ict")[0]["event_id"])
            db=ledger.connect()
            try:
                with self.assertRaises(Exception): db.execute("UPDATE station_history SET result='PASS' WHERE event_id=?",(event,))
                db.rollback()
            finally:
                db.close()

    def test_scanner_normalizes_whitespace_and_case(self):
        self.assertEqual("RJ-SN-001",ScannerGatewayPanel.normalize(" rj-sn-001\r\n"))

    def test_full_repair_happy_path_closes(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=StationHistoryLedger(Path(folder)/"repair.db"); policy=self.registry.get("mod_manu_assembly_ate").ng_policy
            controller=RepairWorkflowController(ledger,create_preview_case("mod_manu_assembly_ate","SN001","FAIL",policy),preview=True)
            sequence=(("CONFIRM_NG","OPERATOR"),("SEND_REPAIR","OPERATOR"),("RECEIVE","REPAIR"),("ACTIVATE_ORDER","REPAIR"),("START_REPAIR","REPAIR"),("COMPLETE_REPAIR","REPAIR"),("AUTHORIZE_RETEST","QC"),("START_RETEST","OPERATOR"),("RETEST_PASS","OPERATOR"),("RETURN_ROUTE","OPERATOR"),("CLOSE","QC"))
            for action,role in sequence: controller.execute(action,"TESTER",role,"unit test")
            self.assertEqual("CLOSED",controller.case.state)
            self.assertEqual(12,len(ledger.list("mod_manu_assembly_ate")))

    def test_repair_role_is_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger=StationHistoryLedger(Path(folder)/"repair.db"); policy=self.registry.get("mod_manu_assembly_ate").ng_policy
            controller=RepairWorkflowController(ledger,create_preview_case("mod_manu_assembly_ate","SN001","FAIL",policy),preview=True)
            with self.assertRaises(PermissionError): controller.execute("CONFIRM_NG","OP","REPAIR","bad role")


if __name__ == "__main__": unittest.main()
