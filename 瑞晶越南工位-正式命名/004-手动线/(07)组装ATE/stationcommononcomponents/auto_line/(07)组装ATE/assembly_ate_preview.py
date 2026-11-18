# -*- coding: utf-8 -*-
"""Read-only deterministic data source for the automatic-line Assembly ATE UI."""
from pathlib import Path


class AutoAssemblyAtePreviewCore:
    watch_dir = Path("PREVIEW-NO-FILESYSTEM-WATCH")

    def snapshot(self):
        results=[]
        for index in range(1,9):
            results.append({
                "test_time":f"2026-08-04 10:{index:02d}:00","channel":f"L{index}",
                "sn":f"AUTO-ATE-L{index}-000{index}","result":"FAIL" if index==3 else "PASS",
                "error_code":"ATE-RES-014" if index==3 else "","duplicate":False,
                "mes_synced":index!=8,"source_file":"preview.xlsx","source_row":index,
                "test_cycle_id":"AUTO-PREVIEW-CYCLE-001",
            })
        return {
            "results":results,
            "arrival":{
                "expected":[],"arrivals":[],"exceptions":[],
                "route":{"sn":"AUTO-ATE-L3-0003","identity_type":"PRODUCT","identity":"AUTO-ATE-L3-0003",
                         "gate_state":"BLOCK","reason":"Confirmed NG requires repair disposition",
                         "decision_time":"2026-08-04 10:03:02","authorization_reference":"",
                         "current_station":"AUTO_ASSEMBLY_ATE","route_revision":"AUTO-R17","cycle":"1",
                         "decision":"REPAIR_REQUIRED","next_action":"Confirm NG and create repair handover",
                         "steps":[{"station":"ICT","state":"COMPLETED"},{"station":"FCT","state":"COMPLETED"},
                                  {"station":"DEPANEL","state":"COMPLETED"},{"station":"ASSEMBLY ATE","state":"CURRENT"},
                                  {"station":"SUPERSONIC","state":"BLOCKED"}]},
            },
            "maintenance":{"cases":[{"local_case_id":"LOCAL-RPR-001","mes_work_order_id":"MES-RPR-001",
                "sn":"AUTO-ATE-L3-0003","reason_code":"ATE-RES-014","department":"REPAIR",
                "status":"WAITING_RECEIPT","created_at":"2026-08-04 10:03:05"}]},
            "history":{"batches":[{"archive_batch_id":"ARCH-AUTO-001","reason":"Automatic ATE history seal",
                "record_count":8,"content_hash":"preview-sha256-read-only","sealed_at":"2026-08-04 10:04:00","created_by":"SYSTEM"}],
                "records":[]},
            "checks":[{"created_at":"2026-08-04 10:03:01","sn":"AUTO-ATE-L3-0003","status":"NG","detail":"ATE-RES-014"}],
            "outbox":[{"event_id":"PREVIEW-EVT-001","sent_at":"","retry_count":0,"last_error":"PREVIEW: production write blocked"}],
            "ng":[{"sn":"AUTO-ATE-L3-0003","reason":"ATE-RES-014","source_station":"auto_assem_ate","received_at":"2026-08-04 10:03:00"}],
            "changes":[{"change_id":"AUTO-ATE-UI-001","version":"5.0","component":"station-agent-standard",
                "reason":"Feature parity","summary":"Unified route, NG, repair, history and diagnostics","verification":"preview smoke","changed_at":"2026-08-04"}],
            "watch_dir":"PREVIEW / NO FILE ACCESS","source_connected":True,
        }

    def check_scan(self,value):
        sn=(value or "AUTO-ATE-DEMO-0001").strip().upper()
        blocked=sn=="AUTO-ATE-L3-0003"
        return {"status":"NG" if blocked else "PREVIEW","sn":sn,
                "detail":"Confirmed NG requires repair" if blocked else "Read-only route check passed","blocked":blocked}

    def set_watch_dir(self,_value): raise RuntimeError("Preview blocks filesystem changes")
    def ingest_once(self): return {"added":[],"errors":[]}
    def ingest_partial_once(self): return {"added":[],"errors":[]}
    def sync_once(self): return 0
