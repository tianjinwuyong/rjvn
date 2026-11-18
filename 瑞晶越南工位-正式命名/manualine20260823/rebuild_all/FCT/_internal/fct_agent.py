# -*- coding: utf-8 -*-
"""Manual-line FCT Agent: monitor daily ATS Excel reports in 12-SN groups."""

import json
import os
import queue
import random
import sqlite3
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
import uuid
import subprocess
import socket
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from station_common_bootstrap import attach_common_agent
COMMON_AGENT = attach_common_agent("manu_fct", __file__, "fct")
from station_arrival_core import StationArrivalStore, ArrivalError
from station_repair_workflow import install_repair_workflow
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox, simpledialog

try:
    from openpyxl import Workbook
except ImportError:
    raise SystemExit("openpyxl is required: pip install openpyxl")


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
sys.path.insert(0,str(APP_DIR.parent))
from station_excel_safe import load_workbook
from station_excel_events import ExcelEventWatcher
from station_ui_primitives import install_kpi_skeleton, install_station_tabs, update_station_kpi, register_scanner_entry

try:
    from station_alarm import StationAlarm
except ImportError:
    class StationAlarm:
        def __init__(self, *a, **k): pass

try:
    from station_i18n import TrilingualController
except ImportError:
    class TrilingualController:
        def __init__(self, *a, **k): pass

try:
    from station_data_sync import reconcile_inventory, ConfirmedNgGuard, ExpectedSnManifest, mes_scan_gate
except ImportError:
    def reconcile_inventory(*a, **k): pass
    class ConfirmedNgGuard:
        def __init__(self, *a, **k): pass
    class ExpectedSnManifest:
        def __init__(self, *a, **k): pass
    class _DummyGate:
        def get(self, *a, **k): return None
    mes_scan_gate = _DummyGate()

try:
    from station_retest import RetestController, is_unlimited_retest
except ImportError:
    class RetestController:
        def __init__(self, *a, **k): pass

try:
    from station_runtime_safety import acquire_single_instance, wait_file_stable, run_diagnostics
except ImportError:
    def acquire_single_instance(name):
        # Fail closed: a missing safety module must never allow two Agents.
        return None
    def wait_file_stable(*a, **k): return True
    def run_diagnostics(*a, **k): return {}
APP_VERSION = "2026.07.18-safety1"
SAMPLE_DIR = APP_DIR / "fctdatasmple"
# Mirror the ATS station's production layout on this computer.
REAL_REPORT_ROOT = Path(r"D:\ATS\测试报表")
SIM_PRODUCT = "NBT-(26V5056)EPS18R1G-36-FCT"
SIM_DIR = REAL_REPORT_ROOT / SIM_PRODUCT
DB_PATH = APP_DIR / "fct_agent.db"
FCT_NG_DB_PATH = APP_DIR / "fct_ng.db"
POLL_SECONDS = 1.0
STATION_CODE = "manu_fct"
AGENT_DISPLAY_NAME = "FCT"
STATION_NAME_ZH = "FCT测试工位"
SOLID_MOTHERBOARD = True
RESOLVE_BINDING_SCAN = False
ROUTE_OPTIONS = ("维修站", "分板FCT NG箱", "申请报废")
DEFAULT_ROUTE_OPTION = "分板FCT NG箱"
NEXT_STATION_CODE = ""
WORK_ITEM_LABEL = "Motherboard"
WAITING_TEXT = "Waiting for a complete 12-SN motherboard"
NG_ROUTE_DESTINATION = "DEPANEL"
NG_ROUTE_WORKFLOW = "MES_DEPANEL_FCT_NG_HANDOVER"
NG_ROUTE_LABEL = "分板FCT不良箱"
NG_ROUTE_STATION_CODE = "manu_depanel"
NG_ROUTE_REASON = "FCT_CONFIRMED_NG"
MAX_AUTHORIZED_RETESTS = 1
RESULT_EVENT_TYPE = "fct_xlsx"
DISPLAY_SLOT_COUNT = 12
INDEPENDENT_TWO_SIDED_LAYOUT = False
# FCT owns and displays only FCT test results.  ICT defects are merged by
# Depanel; showing upstream ICT NG here makes an FCT board look like it failed
# at FCT and can also contaminate the FCT motherboard visualization.
SHOW_UPSTREAM_NG_CLASSIFICATION = False
SCRAP_REASONS = {
    "S01": "PCB断裂、缺角或严重变形", "S02": "PCB烧焦、碳化、分层或起泡",
    "S03": "焊盘、线路或金手指严重脱落", "S04": "关键元器件损坏且无法更换",
    "S05": "连接器、端子或接口不可修复", "S06": "外壳破裂、残缺或尺寸严重超差",
    "S07": "进水、腐蚀或严重污染", "S08": "高压、绝缘等安全缺陷不可修复",
    "S09": "多次维修或复测仍不合格", "S10": "已用完规定复测机会且无维修价值",
    "S11": "维修成本超过允许标准", "S12": "SN、板码或产品身份无法追溯",
    "S13": "工艺异常导致无法进入后续工序", "S14": "存在不可接受的可靠性风险",
    "S15": "工程变更、客户要求或质量指令报废", "S16": "人为破坏",
    "S17": "操作不当", "S18": "测试设备不良", "S19": "机械撞击",
    "S99": "其他原因",
}
SIM_SN_PREFIX = "FCT"
CONFIG_PATH = APP_DIR / "fct_config.json"
DEFAULT_CONFIG = {
    "mes_url": "http://192.168.6.155:8080/api/pda/events",
    "watch_dir": str(REAL_REPORT_ROOT),
    "scanner_tcp_port": 1003,
    "enable_simulator": False,
    "confirm_after_fail_count": 1,
}
try:
    CONFIG = dict(DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
except Exception:
    CONFIG = dict(DEFAULT_CONFIG)
MES_URL = os.environ.get("MES_API_URL", str(CONFIG["mes_url"])).strip()
CONFIG["watch_dir"] = os.environ.get("FCT_WATCH_DIR", str(CONFIG["watch_dir"])).strip()
SCANNER_TCP_PORT = int(os.environ.get("FCT_SCANNER_TCP_PORT", CONFIG["scanner_tcp_port"]))
ENABLE_SIMULATOR = bool(CONFIG.get("enable_simulator", False))
CONFIRM_AFTER_FAIL_COUNT = max(1, int(CONFIG.get("confirm_after_fail_count", 1)))
HEARTBEAT_SECONDS = 5.0
QT_COMMAND_PATH = APP_DIR / "fct_qt_command.json"

def mes_sn_is_duplicate(sn):
    """Station-scoped MES processed-history lookup for FCT ingestion."""
    base = MES_URL.replace("/api/pda/events", "").rstrip("/")
    url = (f"{base}/api/station/sn-guard/check/{urllib.parse.quote(str(sn).strip().upper())}"
           f"?stationCode={urllib.parse.quote(STATION_CODE)}")
    with urllib.request.urlopen(url, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    return bool(data.get("duplicate"))

def mes_identify_ict_motherboard(sns):
    """Resolve the immutable ICT motherboard identity from any daughterboard SN."""
    normalized = [str(sn).strip().upper() for sn in sns if str(sn).strip()]
    if not normalized:
        raise ValueError("FCT motherboard contains no SN")
    base = MES_URL.replace("/api/pda/events", "").rstrip("/")
    last_error = None
    for sn in normalized:
        try:
            url = (
                f"{base}/api/station/confirmed-motherboards/identify/"
                f"{urllib.parse.quote(sn)}?line=manual"
            )
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            members = data.get("members") or []
            member_sns = {str(item.get("sn", "")).strip().upper() for item in members}
            if member_sns != set(normalized):
                raise ValueError("FCT 12-SN set does not match the ICT motherboard layout")
            motherboard_id = str(data.get("motherboardId") or data.get("ictBatchId") or "").strip()
            if not motherboard_id:
                raise ValueError("MES returned no ICT motherboardId")
            return motherboard_id
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code != 404:
                raise
    raise ValueError(f"MES cannot identify ICT motherboard from FCT SNs: {last_error}")

def mes_latest_ict_motherboard_members():
    """Return the newest complete motherboard authored by ICT."""
    base = MES_URL.replace("/api/pda/events", "").rstrip("/")
    url = f"{base}/api/station/confirmed-motherboards?line=manual&limit=5000"
    with urllib.request.urlopen(url, timeout=8) as response:
        items = json.loads(response.read().decode("utf-8")).get("items") or []
    complete = [
        item for item in items
        if item.get("ictBatchId") and len(item.get("members") or []) == 12
    ]
    if not complete:
        raise ValueError("MES has no complete ICT motherboard for FCT simulation")
    latest = max(complete, key=lambda item: str(item.get("updatedAt") or ""))
    members = sorted(latest["members"], key=lambda item: int(item.get("slot") or 0))
    return str(latest.get("motherboardId") or latest["ictBatchId"]), members


def inventory_reconcile_worker():
    while True:
        try:
            with sqlite3.connect(str(DB_PATH)) as conn:
                rows = conn.execute("SELECT payload FROM fct_batches ORDER BY created_at,batch_id").fetchall()
                sn_rows = conn.execute("SELECT sn,test_time,batch_id,channel,result FROM all_sns ORDER BY created_at,sn").fetchall()
            passed = []
            confirmed = []
            latest_board = None
            for (raw,) in rows:
                try:
                    motherboard = json.loads(raw)
                except Exception:
                    continue
                boards = motherboard.get("subBoards", [])
                if boards:
                    latest_board = motherboard
                failed = [board for board in boards
                          if str(board.get("result", "")).upper() == "FAIL"]
                if failed:
                    confirmed.append(motherboard)
                elif boards:
                    passed.append(motherboard)
            # FCT is a one-test station: every FAIL is immediately NG. The
            # station owns and publishes PASS/NG box state; MES only mirrors it.
            base = MES_URL.replace("/api/pda/events", "").rstrip("/")
            sn_records = [{"sn": row[0], "testTime": row[1], "batchId": row[2],
                           "channel": row[3], "result": row[4]} for row in sn_rows]
            reconcile_inventory(MES_URL, STATION_CODE, "sn_records", sn_records,
                                int(time.time() * 1000), "sn")
            # Publish the complete live motherboard, including all 12 slots.
            # The process bucket is the digital-twin current-board pointer;
            # publishing only the scalar process record leaves the 3D view
            # falling back to an older historical confirmed_ng board.
            if latest_board:
                body = json.dumps({"payload": latest_board}, ensure_ascii=False).encode("utf-8")
                request = urllib.request.Request(
                    f"{base}/api/station/bucket-snapshots/{STATION_CODE}/process",
                    data=body, method="PUT", headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=8) as response:
                    response.read()
            for bucket_name, records in (("pass", passed), ("confirmed_ng", confirmed), ("pending_ng", [])):
                body = json.dumps({"payload": records}, ensure_ascii=False).encode("utf-8")
                request = urllib.request.Request(
                    f"{base}/api/station/bucket-snapshots/{STATION_CODE}/{bucket_name}",
                    data=body, method="PUT", headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=8) as response:
                    response.read()
        except Exception:
            pass
        time.sleep(5)

def speak(text):
    safe = str(text).replace('"', '')
    script = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{safe}")'
    import base64
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def init_db():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_groups (
                file_path TEXT NOT NULL,
                test_time TEXT NOT NULL,
                side TEXT NOT NULL,
                row_start INTEGER,
                row_end INTEGER,
                payload TEXT NOT NULL,
                processed_at INTEGER NOT NULL,
                PRIMARY KEY (file_path, test_time, side)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS all_sns (
                sn TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                result TEXT NOT NULL,
                error_code TEXT,
                test_time TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fct_batches (
                batch_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                created_at INTEGER
            )
        """)
        try:
            conn.execute("ALTER TABLE fct_batches ADD COLUMN created_at INTEGER")
        except sqlite3.OperationalError:
            pass
        conn.execute("""CREATE TABLE IF NOT EXISTS mes_event_outbox (
            event_id TEXT PRIMARY KEY,event_json TEXT NOT NULL,created_at INTEGER NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 0,last_error TEXT,last_attempt INTEGER,
            status TEXT NOT NULL DEFAULT 'PENDING')""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fct_boards (
                batch_id TEXT NOT NULL,
                slot INTEGER NOT NULL,
                channel TEXT NOT NULL,
                sn TEXT NOT NULL,
                result_1 TEXT,
                result_2 TEXT,
                result_3 TEXT,
                test_count INTEGER NOT NULL DEFAULT 1,
                retest_remaining INTEGER NOT NULL DEFAULT 0,
                is_confirmed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (batch_id, slot)
            )
        """)
        conn.execute("""CREATE TABLE IF NOT EXISTS fct_parse_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,file_path TEXT NOT NULL,
            test_cycle_id TEXT NOT NULL,motherboard_id TEXT,slot INTEGER,
            channel TEXT,sn TEXT NOT NULL,result TEXT,error_code TEXT,test_time TEXT,
            decision TEXT NOT NULL,reason TEXT,parsed_at INTEGER NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fct_parse_audit_sn_time ON fct_parse_audit(sn,parsed_at)")
    # ICT-compatible local traceability database for the FCT station.
    with sqlite3.connect(str(FCT_NG_DB_PATH)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS all_sns (sn TEXT, scan_time INTEGER, batch_id TEXT, slot INTEGER, result TEXT)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fct_all_sns_sn ON all_sns(sn)")
        conn.execute("CREATE TABLE IF NOT EXISTS ng_batches (batch_id TEXT PRIMARY KEY, main_sn TEXT, sn_obj TEXT, batch_start INTEGER, created_at INTEGER)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ng_boards (
                batch_id TEXT, slot INTEGER, sn TEXT, result_1 TEXT, result_2 TEXT,
                result_3 TEXT, final_result TEXT, repair_result TEXT, test_count INTEGER,
                retest_remaining INTEGER, is_confirmed INTEGER, test_time_1 INTEGER,
                test_time_2 INTEGER, test_time_3 INTEGER, PRIMARY KEY (batch_id, slot)
            )
        """)
        conn.execute("CREATE TABLE IF NOT EXISTS aged_ng (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT, main_sn TEXT, aged_time INTEGER, status TEXT DEFAULT 'pending')")
        conn.execute("CREATE TABLE IF NOT EXISTS maintenance_ng (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT, main_sn TEXT, slot INTEGER, sn TEXT, confirm_time INTEGER, status TEXT DEFAULT 'pending')")


def sync_ict_compatible_db(lifecycle):
    now = int(time.time() * 1000)
    boards = lifecycle.get("subBoards") or []
    main_sn = boards[0]["sn"] if boards else ""
    with sqlite3.connect(str(FCT_NG_DB_PATH)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ng_batches VALUES (?,?,?,?,?)",
            (lifecycle["batchId"], main_sn, json.dumps(lifecycle, ensure_ascii=False), now, now),
        )
        for board in boards:
            results = list(board.get("results") or []) + [None, None, None]
            conn.execute(
                "INSERT INTO all_sns VALUES (?,?,?,?,?)",
                (board["sn"], now, lifecycle["batchId"], board["slot"], board.get("result")),
            )
            conn.execute("""
                INSERT OR REPLACE INTO ng_boards
                (batch_id,slot,sn,result_1,result_2,result_3,final_result,repair_result,
                 test_count,retest_remaining,is_confirmed,test_time_1,test_time_2,test_time_3)
                VALUES (?,?,?,?,?,?,?,NULL,?,?,?,?,?,?)
            """, (
                lifecycle["batchId"], board["slot"], board["sn"], results[0], results[1], results[2],
                board.get("result"), board.get("testCount", 1), board.get("retestRemaining", 0),
                int(bool(board.get("isConfirmedNG"))), now if results[0] else None,
                now if results[1] else None, now if results[2] else None,
            ))


def valid_sn(value):
    value = str(value or "").strip().upper()
    return len(value) == 10 and value.isalnum()

def record_parse_audit(file_path, group, decision, reason="", motherboard_id=""):
    now = int(time.time() * 1000)
    rows = []
    for index, board in enumerate(group.get("subBoards") or [], 1):
        rows.append((str(file_path), str(group.get("batchId") or ""), str(motherboard_id or ""),
            int(board.get("slot") or index), str(board.get("channel") or ""),
            str(board.get("sn") or "").strip().upper(), str(board.get("result") or "").upper(),
            str(board.get("errorCode") or ""), str(board.get("testTime") or group.get("testTime") or ""),
            str(decision), str(reason or ""), now))
    if rows:
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.executemany("""INSERT INTO fct_parse_audit
                (file_path,test_cycle_id,motherboard_id,slot,channel,sn,result,error_code,test_time,decision,reason,parsed_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", rows)


def local_sn_is_duplicate(sn):
    """Offline-safe duplicate lookup against FCT's authoritative ingested data."""
    normalized = str(sn or "").strip().upper()
    if not normalized:
        return False
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            return conn.execute("SELECT 1 FROM all_sns WHERE sn=? LIMIT 1", (normalized,)).fetchone() is not None
    except sqlite3.Error:
        return False


def latest_xlsx(folder):
    files = [p for p in Path(folder).rglob("*.xlsx") if not p.name.startswith("~$")]
    return max(files, key=lambda p: (p.stat().st_mtime_ns, p.name)) if files else None


def is_simulation_workbook(path):
    """Recognize agent-generated simulation by workbook content, never folder."""
    try:
        wb = load_workbook(str(path), read_only=True, data_only=True)
        ws = wb.active
        program_name = str(ws.cell(2, 1).value or "").strip().upper()
        operator = str(ws.cell(2, 2).value or "").strip().upper()
        wb.close()
        return program_name == "FCT-SIM.ATS" and operator == "SIM"
    except Exception:
        return False


def _normalized_header(value):
    return "".join(ch for ch in str(value or "").strip().lower() if ch not in " ._-/\\")


def _result_value(value):
    raw = str(value or "").strip().upper()
    if raw in {"FAIL", "NG", "NOK", "FAILED"}:
        return "FAIL"
    if raw in {"PASS", "OK", "PASSED"}:
        return "PASS"
    return ""


def _channel_value(value):
    raw = str(value or "").strip().upper().replace(" ", "")
    if raw.isdigit():
        raw = f"L{int(raw)}"
    if len(raw) >= 2 and raw[0] in ("L", "R") and raw[1:].isdigit():
        return f"{raw[0]}{int(raw[1:])}"
    return raw


def read_result_groups(path):
    """Parse ATS results by header names, then return motherboard groups."""
    wb = load_workbook(str(path), read_only=True, data_only=True)
    ws = wb.active
    aliases = {
        "number": {"no", "number", "序号"},
        "result": {"result", "testresult", "结果", "测试结果"},
        "channel": {"channel", "channelno", "通道", "通道号"},
        "sn": {"barcode", "sn", "serialnumber", "条码", "序列号"},
        "test_time": {"time", "testtime", "时间", "测试时间"},
        "error_code": {"errorcode", "error", "faultcode", "错误码", "故障码"},
    }
    header_row = None
    columns = {}
    for candidate_row, row in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row, 80), values_only=True), 1):
        normalized = [_normalized_header(value) for value in row]
        found = {}
        for field, names in aliases.items():
            for index, value in enumerate(normalized):
                if value in names:
                    found[field] = index
                    break
        if {"result", "channel", "sn", "test_time"}.issubset(found):
            header_row = candidate_row
            columns = found
            break
    if header_row is None:
        wb.close()
        raise ValueError("FCT report header not found (Result/Channel/BarCode/Time)")

    groups = {}
    for row_no, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), header_row + 1):
        values = list(row)
        get = lambda field: values[columns[field]] if field in columns and columns[field] < len(values) else None
        number = get("number")
        result = _result_value(get("result"))
        channel = _channel_value(get("channel"))
        sn = str(get("sn") or "").strip().upper()
        test_time_value = get("test_time")
        if isinstance(test_time_value, datetime):
            test_time = test_time_value.strftime("%Y-%m-%d/%H:%M:%S")
        else:
            test_time = str(test_time_value or "").strip()
        error_code = get("error_code")
        if not result or not test_time:
            continue
        if not SOLID_MOTHERBOARD:
            if not valid_sn(sn):
                continue
            groups[(test_time, f"ROW{row_no}")] = [{
                "row": row_no,
                "number": number,
                "result": result,
                "channel": channel or "1",
                "sn": sn,
                "testTime": test_time,
                "errorCode": str(error_code or ""),
                "measurements": list(values[max(columns.values()) + 1:max(columns.values()) + 7]),
            }]
            continue
        if len(channel) < 2 or channel[0] not in ("L", "R") or not channel[1:].isdigit():
            continue
        side = channel[0]
        key = (test_time, side)
        groups.setdefault(key, []).append({
            "row": row_no,
            "number": number,
            "result": result,
            "channel": channel,
            "sn": sn,
            "testTime": test_time,
            "errorCode": str(error_code or ""),
            "measurements": list(values[max(columns.values()) + 1:max(columns.values()) + 7]),
        })
    wb.close()

    complete = []
    for (test_time, side), rows in groups.items():
        if not SOLID_MOTHERBOARD:
            row = rows[0]
            complete.append({
                "batchId": row["sn"],
                "testTime": test_time,
                "side": side,
                "rowStart": row["row"],
                "rowEnd": row["row"],
                "overallResult": row["result"],
                "isComplete": True,
                "discoveredCount": 1,
                "subBoards": [row],
            })
            continue
        by_channel = {r["channel"]: r for r in rows}
        expected = [f"{side}{i}" for i in range(1, 13)]
        present = [channel for channel in expected if channel in by_channel]
        if not present:
            continue
        ordered = [by_channel[channel] for channel in present]
        # Production examples contain complete groups with 12 blank barcodes.
        # They are invalid tests and must not be saved, displayed, or spoken.
        if not all(valid_sn(row["sn"]) for row in ordered):
            continue
        complete.append({
            "batchId": test_time.replace("-", "").replace("/", "").replace(":", ""),
            "testTime": test_time,
            "side": side,
            "rowStart": min(r["row"] for r in ordered),
            "rowEnd": max(r["row"] for r in ordered),
            "overallResult": "FAIL" if any(r["result"] == "FAIL" for r in ordered) else "PASS",
            "isComplete": len(ordered) == 12,
            "discoveredCount": len(ordered),
            "subBoards": ordered,
        })
    return sorted(complete, key=lambda group: (group["testTime"], group["side"]))


class FctAgent:
    def __init__(self, root):
        self.root = root
        self.arrivals = StationArrivalStore(DB_PATH, STATION_CODE, MES_URL)
        self.root.title(f"{AGENT_DISPLAY_NAME} Agent — {WORK_ITEM_LABEL} Monitor")
        self.root.geometry("1060x760")
        self.root.configure(bg="#0f172a")
        self.running = False
        self.worker = None
        self.sim_running = False
        self.active_retest_batch = None
        self.active_retest_attempt = 0
        self.active_retest_sn = None
        self.mes_retest = RetestController(STATION_CODE, MES_URL.replace('/pda/events',''))
        self.retest_scan_mode = False
        self.retest_partial_windows = {}
        self.ng_guard = ConfirmedNgGuard(DB_PATH,MES_URL)
        self.expected_sn_manifest = ExpectedSnManifest(DB_PATH,MES_URL,STATION_CODE)
        self.overtime_permission = False
        self.route_target_batch = ""
        self.mes_box_cache = {}
        self.embedded_detail_views = {}
        self.ict_ng_sns = set()
        self.duplicate_sns = []
        self.duplicate_alarm_on = False
        self.ui_queue = queue.Queue()
        self.mes_queue = queue.Queue()
        self.watch_dir = tk.StringVar(value=str(CONFIG["watch_dir"]))
        self.status = tk.StringVar(value="Stopped")
        self.batch_text = tk.StringVar(value=WAITING_TEXT)
        self._latest_view_signature = None
        self.slot_vars = []
        self.slot_frames = []
        self.scanner_var = tk.StringVar()
        self._last_scan_value = ""
        self._last_scan_time = 0.0
        self.route_var = tk.StringVar(value=DEFAULT_ROUTE_OPTION)
        self._build_ui()
        threading.Thread(target=self._mes_worker, daemon=True, name="fct-mes-sender").start()
        threading.Thread(target=self._heartbeat_worker, daemon=True, name="fct-heartbeat").start()
        threading.Thread(target=inventory_reconcile_worker, daemon=True,
                         name="fct-inventory-reconcile").start()
        threading.Thread(target=self._scanner_tcp_worker, daemon=True, name="fct-scanner-tcp").start()
        if SHOW_UPSTREAM_NG_CLASSIFICATION:
            threading.Thread(target=self._depanel_box_worker, daemon=True, name="fct-depanel-box-sync").start()
        threading.Thread(target=self._qt_command_worker, daemon=True, name="fct-qt-command").start()
        self.root.after(100, self._drain_ui)
        self.root.after(200, self._refresh_local_fct_boxes)
        self.root.after(350, self._refresh_latest_motherboard_view)
        self.root.after(250, self.start)

    def _refresh_latest_motherboard_view(self):
        """Restore the newest completed motherboard from local SQLite."""
        try:
            with sqlite3.connect(str(DB_PATH)) as conn:
                row = conn.execute(
                    """SELECT batch_id,payload,updated_at
                       FROM fct_batches
                       ORDER BY updated_at DESC LIMIT 1"""
                ).fetchone()
            if row:
                signature = (str(row[0]), int(row[2] or 0))
                if signature != self._latest_view_signature:
                    group = json.loads(row[1])
                    if isinstance(group, dict) and group.get("subBoards"):
                        lifecycle = group.get("lifecycle") or {}
                        group.setdefault("batchId", str(row[0]))
                        group.setdefault("stableBatchId", str(row[0]))
                        group.setdefault("side", "L")
                        group.setdefault(
                            "overallResult",
                            lifecycle.get("overallResult", "PASS"),
                        )
                        for index, board in enumerate(group["subBoards"], 1):
                            board.setdefault("channel", f"Slot {index}")
                            board.setdefault(
                                "result",
                                str(board.get("finalResult") or "PASS").upper(),
                            )
                            board.setdefault(
                                "errorCode",
                                str(board.get("defectCode") or ""),
                            )
                        self._show_group(group)
                        self._latest_view_signature = signature
        except Exception as exc:
            self.log(f"Motherboard display restore retry: {exc}")
        finally:
            self.root.after(2000, self._refresh_latest_motherboard_view)

    def _qt_command_worker(self):
        """Execute one-shot commands from the FCT Qt 3D shell."""
        last_request = ""
        while True:
            try:
                if QT_COMMAND_PATH.exists():
                    command = json.loads(QT_COMMAND_PATH.read_text(encoding="utf-8"))
                    QT_COMMAND_PATH.unlink(missing_ok=True)
                    request_id = str(command.get("requestId") or "")
                    if request_id and request_id != last_request:
                        last_request = request_id
                        action = str(command.get("command") or "")
                        if action == "simulate_motherboard":
                            self.root.after(0, self.simulate)
                        elif action == "simulate_bank":
                            side = str(command.get("side") or "L").strip().upper()
                            if side in ("L", "R"):
                                self.root.after(0, lambda requested_side=side: self.simulate(requested_side))
                        elif action == "arm_retest_scan":
                            def arm_once():
                                self.retest_scan_mode = True
                                self.status.set("复检已启动：下一次扫码或Excel读取不做重码检测")
                                speak("复检已启动，请扫描板码并开始测试")
                            self.root.after(0, arm_once)
                        elif action == "release_duplicate_alarm":
                            self.root.after(0, self._release_duplicate_alarm)
                        elif action == "clear_local_sqlite":
                            self.root.after(0, self._clear_local_sqlite)
                        elif action == "grant_overtime_retest":
                            self.root.after(0, self._grant_overtime)
                        elif action == "show_handover_sheet":
                            self.root.after(0, self._show_handover_sheet)
                        elif action == "confirm_route":
                            self.root.after(0, self._confirm_route)
                        elif action == "run_self_test":
                            self.root.after(0, self._run_self_test)
                        elif action == "show_sn_sqlite":
                            self.root.after(0, lambda: (self.root.deiconify(), self.notebook.select(1), self.root.lift()))
                        elif action == "show_ng_sqlite":
                            self.root.after(0, lambda: (self.root.deiconify(), self.notebook.select(2), self.root.lift()))
                        elif action == "scan_sn":
                            sn = str(command.get("sn") or "").strip().upper()
                            if sn:
                                self.root.after(0, lambda value=sn: (self.scanner_var.set(value), self._handle_scan()))
            except Exception as exc:
                self.log(f"Qt command retry: {exc}")
            time.sleep(0.2)

    def _mes_worker(self):
        while True:
            event = None
            try:
                event = self.mes_queue.get(timeout=1)
            except queue.Empty:
                pass
            if event is not None:
                event.setdefault("eventId", f"fct-{uuid.uuid4()}")
                with sqlite3.connect(str(DB_PATH)) as conn:
                    conn.execute("INSERT OR IGNORE INTO mes_event_outbox(event_id,event_json,created_at) VALUES(?,?,?)",
                                 (event["eventId"], json.dumps(event, ensure_ascii=False), int(time.time()*1000)))
                self.mes_queue.task_done()
            with sqlite3.connect(str(DB_PATH)) as conn:
                row = conn.execute("SELECT event_id,event_json,retry_count FROM mes_event_outbox WHERE status='PENDING' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                continue
            event_id, event_json, retry_count = row
            event = json.loads(event_json)
            try:
                request = urllib.request.Request(
                    MES_URL,
                    data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    response.read()
                with sqlite3.connect(str(DB_PATH)) as conn:
                    conn.execute("DELETE FROM mes_event_outbox WHERE event_id=?", (event_id,))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                self.log(f"MES rejected event {event_id}: HTTP {exc.code} {detail}")
                with sqlite3.connect(str(DB_PATH)) as conn:
                    if 400 <= exc.code < 500 and exc.code not in (408, 429):
                        conn.execute("UPDATE mes_event_outbox SET status='QUARANTINED',retry_count=retry_count+1,last_error=?,last_attempt=? WHERE event_id=?",
                                     (f"HTTP {exc.code}: {detail}", int(time.time()*1000), event_id))
                    else:
                        conn.execute("UPDATE mes_event_outbox SET retry_count=retry_count+1,last_error=?,last_attempt=? WHERE event_id=?",
                                     (f"HTTP {exc.code}: {detail}", int(time.time()*1000), event_id))
                time.sleep(0.2)
            except Exception as exc:
                self.log(f"MES send retry: {exc}")
                with sqlite3.connect(str(DB_PATH)) as conn:
                    conn.execute("UPDATE mes_event_outbox SET retry_count=retry_count+1,last_error=?,last_attempt=? WHERE event_id=?",
                                 (str(exc), int(time.time()*1000), event_id))
                # Exponential retry prevents a temporary MES/DB slowdown from
                # turning every station outbox into a connection-pool storm.
                time.sleep(min(30, max(2, 2 ** min(int(retry_count) + 1, 5))))

    def _heartbeat_worker(self):
        while True:
            try:
                event = {"type": "AGENT_HEARTBEAT", "stationCode": STATION_CODE, "payload": {
                    "agent": "fct_agent",
                    "status": "running" if self.running else "ready",
                    "watchDir": self.watch_dir.get(),
                    "timestamp": int(time.time() * 1000),
                }}
                request = urllib.request.Request(MES_URL,
                    data=json.dumps(event, ensure_ascii=False).encode("utf-8"), method="POST",
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=3) as response:
                    response.read()
            except Exception as exc:
                self.log(f"Heartbeat retry: {exc}")
            time.sleep(HEARTBEAT_SECONDS)

    def _depanel_box_worker(self):
        url = MES_URL.replace("/api/pda/events", "/api/station/bucket-snapshots")
        while True:
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    items = json.loads(response.read().decode("utf-8")).get("items", [])
                records = next((item.get("payload", []) for item in items
                                if item.get("stationCode") == "manu_depanel" and item.get("bucketName") == "pending_ng"), []) or []
                counts = {code: sum(1 for row in records if row.get("defectCode") == code)
                          for code in self.depanel_box_vars}
                fct_buckets = {item.get("bucketName"): item.get("payload", []) for item in items if item.get("stationCode") == STATION_CODE}
                ict_buckets = {item.get("bucketName"): item.get("payload", []) for item in items if item.get("stationCode") == "manu_ict"}
                ict_ng_sns = self._extract_ng_child_sns(
                    (ict_buckets.get("pending_ng", []) or [])
                    + (ict_buckets.get("confirmed_ng", []) or [])
                )
                def apply(values=counts, incoming_ict_ng=ict_ng_sns):
                    self.ict_ng_sns = set(incoming_ict_ng)
                    for key, value in values.items(): self.depanel_box_vars[key].set(str(value))
                    for code in self.depanel_box_vars:
                        self.mes_box_cache[f"depanel:{code}"] = [row for row in records if row.get("defectCode") == code]
                self.root.after(0, apply)
            except Exception:
                pass
            time.sleep(3)

    def _refresh_local_fct_boxes(self):
        """FCT box UI is owned by local SQLite, never written back by MES."""
        try:
            with sqlite3.connect(str(DB_PATH)) as conn:
                rows = conn.execute("SELECT payload FROM fct_batches ORDER BY created_at,batch_id").fetchall()
            local = {"ng": [], "pass": [], "confirmed": []}
            for (raw,) in rows:
                try:
                    board = json.loads(raw)
                except Exception:
                    continue
                failed = [item for item in board.get("subBoards", [])
                          if str(item.get("result", "")).upper() == "FAIL"]
                if any(bool(item.get("isConfirmedNG")) for item in failed):
                    local["confirmed"].append(board)
                elif failed:
                    local["ng"].append(board)
                else:
                    local["pass"].append(board)
            for key, records in local.items():
                self.fct_box_vars[key].set(str(len(records)))
                self.mes_box_cache[f"fct:{key}"] = records
            all_ng = local["ng"] + local["confirmed"]
            self.fct_box_vars["confirmed"].set(str(len(all_ng)))
            self.mes_box_cache["fct:confirmed"] = all_ng
        except Exception as exc:
            self.log(f"Local FCT box refresh failed: {exc}")
        self.root.after(1000, self._refresh_local_fct_boxes)

    @staticmethod
    def _extract_ng_child_sns(records):
        """Extract only defective ICT daughterboard SNs from motherboard payloads."""
        found = set()
        def visit(value, inside_ng_bucket=False):
            if isinstance(value, list):
                for item in value:
                    visit(item, inside_ng_bucket)
                return
            if not isinstance(value, dict):
                return
            sub_boards = value.get("subBoards")
            if isinstance(sub_boards, list):
                for board in sub_boards:
                    if not isinstance(board, dict):
                        continue
                    is_ng = (
                        str(board.get("result", "")).upper() in {"FAIL", "NG", "CONFIRMED_NG"}
                        or bool(board.get("isConfirmedNG"))
                    )
                    if is_ng and board.get("sn"):
                        found.add(str(board["sn"]).strip().upper())
                # Still inspect nested wrappers, but never mark good siblings.
                for key, nested in value.items():
                    if key != "subBoards":
                        visit(nested, True)
                return
            if inside_ng_bucket and value.get("sn"):
                found.add(str(value["sn"]).strip().upper())
            for nested in value.values():
                visit(nested, inside_ng_bucket)
        visit(records, True)
        return found

    @staticmethod
    def _is_fct_repair_revival_order(row):
        """The FCT handover page only receives maintenance revival returns."""
        return (
            str(row.get("destinationType", "")).strip().upper() == "REPAIR_RETURN"
            and str(row.get("destinationStation", "")).strip().lower() == STATION_CODE.lower()
            and str(row.get("sourceStation", "")).strip().lower()
                in {"manu_rework", "maintenance", "repair", "repair_center"}
        )

    def _publish_lifecycle(self, lifecycle):
        payload = dict(lifecycle)
        source_retest_authorized = self.active_retest_batch is not None or any(
            int(board.get("testCount", 1) or 1) > 1 for board in lifecycle.get("subBoards", [])
        )
        payload["sameMotherboardRetest"] = source_retest_authorized
        payload["sourceStation"] = STATION_CODE
        payload["eventType"] = RESULT_EVENT_TYPE
        payload["mainSn"] = lifecycle["subBoards"][0]["sn"] if lifecycle["subBoards"] else ""
        # Publish the complete FCT motherboard as its own canonical process
        # event before PASS/NG bucket events. ICT-confirmed NG members are
        # expected at FCT and may legitimately be intercepted by downstream
        # business guards; that must never prevent MES from receiving the
        # complete 12-slot FCT result and merging it with the ICT motherboard.
        self.mes_queue.put({
            "type": "FCT_PROCESS",
            "stationCode": STATION_CODE,
            "payload": {
                **payload,
                "result": payload.get("overallResult", "PASS"),
                "sourceStationCode": STATION_CODE,
                "destinationStationCode": NEXT_STATION_CODE,
                "canonicalMotherboardMerge": True,
            },
        })
        # Per-SN read pulses actuate the FCT station's top light in the 3D line.
        # READ is deliberately not PASS, so these pulses do not change bucket counts.
        for board in lifecycle["subBoards"]:
            self.mes_queue.put({
                "type": "SN_SCAN",
                "stationCode": STATION_CODE,
                "payload": {
                    "sn": board["sn"],
                    "result": "READ",
                    "slot": board["slot"],
                    "batchId": lifecycle["batchId"],
                    "motherboardId": lifecycle["batchId"],
                    "testCycleId": lifecycle.get("testCycleId"),
                    "eventType": RESULT_EVENT_TYPE,
                    "retestAuthorized": source_retest_authorized,
                    "sameMotherboardRetest": source_retest_authorized,
                    "lightPulse": True,
                },
            })
        if not SOLID_MOTHERBOARD:
            for board in lifecycle["subBoards"]:
                if board.get("result") == "PASS":
                    self.mes_queue.put({
                        "type": "SN_SCAN", "stationCode": STATION_CODE,
                        "payload": {"sn": board["sn"], "result": "PASS", "slot": board.get("slot"),
                                    "batchId": board["sn"], "eventType": RESULT_EVENT_TYPE,
                                    "sourceStationCode": STATION_CODE,
                                    "destinationStationCode": NEXT_STATION_CODE,
                                    "testTime": board.get("testTime"), "retestAuthorized": source_retest_authorized},
                    })
                else:
                    single_payload = dict(payload)
                    single_payload["batchId"] = board["sn"]
                    single_payload["mainSn"] = board["sn"]
                    single_payload["subBoards"] = [dict(board, slot=1)]
                    single_payload["destinationStationCode"] = NG_ROUTE_STATION_CODE
                    self.mes_queue.put({"type": "NG_DEFECT", "stationCode": STATION_CODE, "payload": single_payload})
            return
        # Always publish the complete motherboard.  The 3D line needs all 12
        # daughterboards together to validate the two-SN ICT identity and group PASS.
        self.mes_queue.put({"type": "NG_DEFECT", "stationCode": STATION_CODE, "payload": payload})
        for board in lifecycle["subBoards"]:
            if board.get("result") == "PASS":
                self.mes_queue.put({"type": "SN_SCAN", "stationCode": STATION_CODE,
                    "payload": {"sn": board["sn"], "result": "PASS", "slot": board["slot"],
                                "batchId": lifecycle["batchId"], "eventType": "fct_xlsx", "testTime": board.get("testTime"), "retestAuthorized": source_retest_authorized}})

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#0b1f35")
        header.pack(fill="x")
        tk.Label(header, text=f"{AGENT_DISPLAY_NAME} TEST STATION / {STATION_NAME_ZH}", font=("Segoe UI", 20, "bold"), bg="#0b1f35", fg="#e0f2fe").pack(side="left", padx=20, pady=12)
        mode_text = "12片母板" if SOLID_MOTHERBOARD else "独立产品"
        tk.Label(header, text=f"EXCEL实时检测 | {mode_text} | MES同步", font=("Microsoft YaHei UI", 11), bg="#0b1f35", fg="#7dd3fc").pack(side="left")
        tk.Label(header, text="♥ ONLINE · HEARTBEAT", font=("Segoe UI", 10, "bold"), bg="#0b1f35", fg="#22c55e").pack(side="right", padx=12)
        self.language=TrilingualController(self.root,header)
        tk.Label(header, textvariable=self.watch_dir, font=("Consolas", 9), bg="#0b1f35", fg="#a7f3d0").pack(side="left", padx=12)
        tk.Label(header, textvariable=self.status, font=("Arial", 11, "bold"), bg="#0b1f35", fg="#fbbf24").pack(side="right", padx=16)
        self.station_alarm=StationAlarm(self.root,lambda sns:self._release_duplicate_alarm(),STATION_CODE,MES_URL)

        controls = tk.Frame(self.root, bg="#0b1728", highlightbackground="#1e3a5f", highlightthickness=1)
        controls.pack(fill="x", padx=10, pady=8)
        from station_arrival_ui import ProductGateComponent
        # FCT participates in the shared product-attendance and repair loop.
        # Keep the route decision read-only here; MES remains authoritative.
        self.product_gate = ProductGateComponent(self.root, enabled=True,
                                                  backend_note="MES FCT arrival/repair route")
        tk.Entry(controls, textvariable=self.watch_dir, font=("Consolas", 10), width=72).pack(side="left", padx=8, pady=8)
        tk.Button(controls, text="Browse", command=self._browse, bg="#475569", fg="white").pack(side="left", padx=3)
        self.test_button = tk.Button(
            controls,
            text="测试左侧 8 个" if INDEPENDENT_TWO_SIDED_LAYOUT else "模拟测试母板",
            command=(lambda: self.simulate("L")) if INDEPENDENT_TWO_SIDED_LAYOUT else self.simulate,
            bg="#2563eb",
            fg="white",
        )
        self.test_button.pack(side="left", padx=3)
        self.right_test_button = None
        if INDEPENDENT_TWO_SIDED_LAYOUT:
            self.right_test_button = tk.Button(controls,text="测试右侧 8 个",command=lambda: self.simulate("R"),bg="#0e7490",fg="white")
            self.right_test_button.pack(side="left",padx=3)
        tk.Button(controls, text="系统自检", command=self._run_self_test,
                  bg="#0369a1", fg="white", font=("Microsoft YaHei UI", 10, "bold")).pack(side="right", padx=4)

        scan_row = tk.Frame(self.root, bg="#083344")
        scan_row.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(scan_row, text="扫码枪", bg="#083344", fg="#67e8f9", font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=8)
        scanner_entry = tk.Entry(scan_row, textvariable=self.scanner_var, font=("Consolas", 16), bg="#10243b", fg="white", insertbackground="white")
        scanner_entry.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        register_scanner_entry(self.root, scanner_entry)
        scanner_entry.bind("<Return>", lambda _event: self._handle_scan())
        tk.Button(scan_row, text="确认扫码", command=self._handle_scan, bg="#0891b2", fg="white").pack(side="left", padx=6)

        self.route_selector = ttk.Combobox(scan_row, textvariable=self.route_var,
            values=ROUTE_OPTIONS, state="readonly", width=16,
            style="Route.TCombobox", font=("Microsoft YaHei UI", 10, "bold"))
        # FCT confirmed NG has a fixed route to the depanel FCT NG box.
        self.route_button = tk.Button(scan_row, text="确认去向", command=self._confirm_route,
            state="disabled", bg="#f97316", activebackground="#ea580c", fg="white",
            disabledforeground="#cbd5e1", font=("Microsoft YaHei UI", 10, "bold"),
            relief="flat", padx=12, pady=5)
        self.duplicate_alarm_var = tk.StringVar(value="重码报警：正常")
        self.duplicate_alarm_label = tk.Label(scan_row, textvariable=self.duplicate_alarm_var,
            bg="#0f172a", fg="#94a3b8", font=("Microsoft YaHei UI", 10, "bold"), padx=8)
        self.duplicate_alarm_label.pack(side="left", padx=4)
        tk.Button(scan_row, text="快速解除重码", command=self._release_duplicate_alarm,
                  bg="#facc15", fg="#111827").pack(side="left", padx=4)

        self.depanel_box_vars = {key: tk.StringVar(value="0") for key in ("ICT_ONLY_NG", "FCT_ONLY_NG", "ICT_FCT_NG")}
        self.fct_box_vars = {key: tk.StringVar(value="0") for key in ("ng", "pass", "confirmed")}
        def compact_box(parent, title, color, count_var, cache_key):
            box = tk.Frame(parent, bg="#10243b", highlightbackground=color,
                           highlightthickness=2, padx=7, pady=5)
            box.pack(side="left", fill="x", expand=True, padx=3)
            tk.Label(box, text="▱", bg="#10243b", fg=color,
                     font=("Segoe UI Symbol", 16, "bold")).pack(side="left", padx=(0, 5))
            tk.Label(box, text=title, bg="#10243b", fg=color,
                     font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Label(box, textvariable=count_var, bg=color, fg="white", width=3,
                     font=("Segoe UI", 9, "bold")).pack(side="right", padx=(5, 0))
            self._bind_mes_box(box, title, cache_key)
        own_box_row = tk.Frame(self.root, bg="#07111f", padx=8, pady=5)
        own_box_row.pack(fill="x", padx=10, pady=(0, 4))
        for key, title, color in (("pass", "PASS 母板", "#22c55e"),
                                  ("confirmed", "NG 母板", "#ef4444")):
            compact_box(own_box_row, title, color, self.fct_box_vars[key], f"fct:{key}")
        # Depanel classification stays in MES and is displayed at Depanel only.

        tk.Label(self.root, textvariable=self.batch_text, font=("Arial", 12, "bold"), bg="#0f172a", fg="#e2e8f0").pack(pady=(3, 8))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        monitor_tab = tk.Frame(self.notebook, bg="#0f172a")
        pass_motherboard_tab = tk.Frame(self.notebook, bg="#07111f")
        ng_motherboard_tab = tk.Frame(self.notebook, bg="#07111f")
        sn_tab = tk.Frame(self.notebook, bg="#0f172a")
        ng_tab = tk.Frame(self.notebook, bg="#0f172a")
        handover_tab = tk.Frame(self.notebook, bg="#0f172a")
        residence_tab = tk.Frame(self.notebook, bg="#0f172a")
        raw_tab = tk.Frame(self.notebook, bg="#0f172a")
        self.notebook.add(monitor_tab, text="实时监控 / LIVE")
        self.notebook.add(pass_motherboard_tab, text="PASS 母板")
        self.notebook.add(ng_motherboard_tab, text="NG 母板")
        self.notebook.add(sn_tab, text="SN记录 / SN")
        self.notebook.add(ng_tab, text="NG记录 / NG")
        self.notebook.add(handover_tab, text="维修复活令 / REPAIR RETURN")
        self.notebook.add(residence_tab, text="工位滞留监控 / RESIDENCE")
        self.notebook.add(raw_tab, text="原始数据 / RAW DATA")
        self._build_embedded_detail(pass_motherboard_tab, "PASS 母板历史", "fct:pass", "#22c55e")
        self._build_embedded_detail(ng_motherboard_tab, "NG 母板历史", "fct:confirmed", "#ef4444")
        tk.Button(controls, text="查看 SN SQLite", command=lambda: self.notebook.select(3),
                  bg="#0e7490", fg="white", font=("Microsoft YaHei UI", 10, "bold")).pack(side="right", padx=4)
        tk.Button(controls, text="查看 NG SQLite", command=lambda: self.notebook.select(4),
                  bg="#b45309", fg="white", font=("Microsoft YaHei UI", 10, "bold")).pack(side="right", padx=4)
        self.raw_tree=ttk.Treeview(raw_tab,columns=("time","source","location","raw","status","sn"),show="headings")
        for key,label,width in (("time","接收时间",135),("source","数据源",80),("location","文件/位置",180),("raw","原始内容",430),("status","解析状态",90),("sn","关联SN",160)):
            self.raw_tree.heading(key,text=label); self.raw_tree.column(key,width=width,anchor="w")
        self.raw_tree.pack(fill="both",expand=True,padx=8,pady=8)
        self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self._refresh_record_tabs())
        self.kpi_tab = tk.Frame(self.notebook, bg="#0f172a")
        self.notebook.add(self.kpi_tab, text="KPI / ANALYSIS")
        install_kpi_skeleton(self.kpi_tab)
        install_station_tabs(self.root)

        board = tk.Frame(monitor_tab, bg="#0f172a")
        board.pack(fill="x", padx=16)
        for slot in range(1, DISPLAY_SLOT_COUNT + 1):
            frame = tk.Frame(board, bg="#334155", highlightthickness=2, highlightbackground="#64748b", width=245, height=92)
            if INDEPENDENT_TWO_SIDED_LAYOUT:
                frame.grid(row=(slot - 1) % 8, column=0 if slot <= 8 else 1, padx=6, pady=3, sticky="nsew")
            else:
                frame.grid(row=(slot - 1) // 4, column=(slot - 1) % 4, padx=6, pady=6, sticky="nsew")
            frame.grid_propagate(False)
            position = (f"L{slot}" if slot <= 8 else f"R{slot - 8}") if INDEPENDENT_TWO_SIDED_LAYOUT else f"Slot {slot}"
            var = tk.StringVar(value=f"{position}\n—\nWAIT")
            tk.Label(frame, textvariable=var, font=("Consolas", 11, "bold"), bg="#334155", fg="#cbd5e1", justify="center").pack(expand=True, fill="both")
            self.slot_vars.append(var)
            self.slot_frames.append(frame)
        for column in range(2 if INDEPENDENT_TWO_SIDED_LAYOUT else 4):
            board.grid_columnconfigure(column, weight=1)

        self.log_box = scrolledtext.ScrolledText(monitor_tab, height=10, bg="#020617", fg="#cbd5e1", font=("Consolas", 9))
        self.log_box.pack(fill="both", expand=True, padx=16, pady=10)
        self.log_box.pack_forget()

        self.sn_tree = ttk.Treeview(sn_tab, columns=("sn","batch","channel","result","time"), show="headings")
        batch_column_label = "产品SN" if not SOLID_MOTHERBOARD else "母板号"
        for key, label in (("sn","SN"),("batch",batch_column_label),("channel","通道"),("result","结果"),("time","测试时间")):
            self.sn_tree.heading(key, text=label)
        self.sn_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.ng_tree = ttk.Treeview(ng_tab, columns=("batch","slot","sn","result","count","remaining"), show="headings")
        for key, label in (("batch",batch_column_label),("slot","位置" if not SOLID_MOTHERBOARD else "槽位"),("sn","SN"),("result","结果"),("count","测试次数"),("remaining","剩余复检")):
            self.ng_tree.heading(key, text=label)
        self.ng_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.ng_tree.bind("<<TreeviewSelect>>", self._select_route_from_ng_tree)
        self.handover_tree = ttk.Treeview(handover_tab, columns=("id","batch","source","destination","members","status","sent","received","accepted"), show="headings")
        for key, label in (("id","交接单号"),("batch","整盘编号"),("source","来源工位"),("destination","目标工位"),
                           ("members","SN数量"),("status","交接状态"),("sent","送出时间"),("received","接收时间"),("accepted","接收人/扫码枪")):
            self.handover_tree.heading(key, text=label)
        self.handover_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.residence_tree = ttk.Treeview(residence_tab, columns=("sn","batch","state","ng","entered","duration","alarm"), show="headings")
        for key,label in (("sn","SN"),("batch","整盘编号"),("state","状态"),("ng","NG"),("entered","入站时间"),("duration","滞留时间"),("alarm","报警")):
            self.residence_tree.heading(key,text=label)
        self.residence_tree.pack(fill="both",expand=True,padx=8,pady=8)

    def _refresh_record_tabs(self):
        try:
            with sqlite3.connect(str(DB_PATH)) as conn:
                sn_rows = conn.execute("SELECT sn,batch_id,channel,result,test_time FROM all_sns ORDER BY created_at DESC LIMIT 1000").fetchall()
                ng_rows = conn.execute("""SELECT batch_id,slot,sn,COALESCE(result_3,result_2,result_1),test_count,retest_remaining
                    FROM fct_boards WHERE COALESCE(result_3,result_2,result_1)='FAIL' ORDER BY rowid DESC LIMIT 1000""").fetchall()
            self.sn_tree.delete(*self.sn_tree.get_children())
            self.ng_tree.delete(*self.ng_tree.get_children())
            for row in sn_rows: self.sn_tree.insert("", "end", values=row)
            for row in ng_rows: self.ng_tree.insert("", "end", values=row)
            url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=manu_fct")
            with urllib.request.urlopen(url, timeout=5) as response:
                handovers = [row for row in json.loads(response.read().decode("utf-8")).get("items", [])
                             if self._is_fct_repair_revival_order(row)]
            self.handover_tree.delete(*self.handover_tree.get_children())
            for row in handovers:
                self.handover_tree.insert("", "end", values=(row.get("transferId",""), row.get("batchId",""),
                    row.get("sourceStation",""), row.get("destinationStation",""), row.get("memberCount",""),
                    row.get("status",""), row.get("sentAt",""), row.get("receivedAt",""), row.get("acceptedBy","")))
            url = MES_URL.replace("/api/pda/events", f"/api/station/residence-stats?stationCode={STATION_CODE}")
            with urllib.request.urlopen(url, timeout=5) as response:
                residence = json.loads(response.read().decode("utf-8"))
            threshold = int(residence.get("thresholdMinutes",30))*60
            self.residence_tree.delete(*self.residence_tree.get_children())
            for row in residence.get("current",[]):
                seconds=int(row.get("seconds",0))
                self.residence_tree.insert("","end",values=(row.get("sn",""),row.get("batchId",""),row.get("productState",""),
                    "是" if row.get("isNg") else "否",row.get("enteredAt",""),f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}",
                    "超时" if seconds>=threshold else "正常"))
        except Exception as error:
            self.log(f"Record tab refresh: {error}")

    def _bind_mes_box(self, widget, title, cache_key):
        callback = lambda _event, name=title, key=cache_key: self._show_mes_box(name, key)
        widget.bind("<Button-1>", callback)
        widget.configure(cursor="hand2")
        for child in widget.winfo_children():
            child.bind("<Button-1>", callback)
            child.configure(cursor="hand2")

    def _build_embedded_detail(self, tab, title, cache_key, tone):
        header = tk.Frame(tab, bg="#0b1f35", padx=14, pady=9)
        header.pack(fill="x")
        tk.Label(header, text=title, bg="#0b1f35", fg=tone,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        summary = tk.StringVar(value="等待 MES 数据")
        tk.Label(header, textvariable=summary, bg="#0b1f35", fg="#cbd5e1",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="right")
        canvas = tk.Canvas(tab, bg="#07111f", highlightthickness=0)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="#07111f")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", width=1010)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll.pack(side="right", fill="y", pady=8)
        self.embedded_detail_views[cache_key] = {"tab": tab, "content": content, "summary": summary}

    def _render_embedded_motherboards(self, cache_key):
        view = self.embedded_detail_views[cache_key]
        content = view["content"]
        for child in content.winfo_children():
            child.destroy()
        layouts = {}
        for record in list(self.mes_box_cache.get(cache_key, [])):
            children = next((record.get(key) for key in ("subBoards", "members", "boards")
                             if isinstance(record.get(key), list)), None) or [record]
            batch_id = str(record.get("batchId") or record.get("mainSn") or "")
            for member in children:
                member_batch = str(member.get("batchId") or batch_id or member.get("mainSn") or "UNKNOWN")
                slot = int(member.get("slot") or len(layouts.get(member_batch, {})) + 1)
                layouts.setdefault(member_batch, {})[slot] = member
        view["summary"].set(f"{len(layouts)} 块母板 / {sum(len(rows) for rows in layouts.values())} 个子板")
        if not layouts:
            tk.Label(content, text="暂无 MES 母板记录", bg="#07111f", fg="#64748b",
                     font=("Microsoft YaHei UI", 15, "bold"), pady=70).pack(fill="x")
            return
        for batch_id, members in layouts.items():
            card = tk.Canvas(content, height=228, bg="#0b1b2d", highlightbackground="#334155",
                             highlightthickness=1)
            card.pack(fill="x", padx=7, pady=6)
            card.create_text(12, 15, text=f"母板 {batch_id} · 12 SLOTS", anchor="w",
                             fill="#7dd3fc", font=("Consolas", 11, "bold"))
            for slot in range(1, 13):
                member = members.get(slot, {})
                result = str(member.get("result") or member.get("overallResult") or "EMPTY").upper()
                failed = result in ("FAIL", "NG", "CONFIRMED_NG")
                passed = result in ("PASS", "OK")
                background = "#7f1d1d" if failed else ("#064e3b" if passed else "#1e293b")
                border = "#ef4444" if failed else ("#22c55e" if passed else "#475569")
                column, row_index = (slot - 1) % 4, (slot - 1) // 4
                x1, y1 = 10 + column * 247, 32 + row_index * 63
                x2, y2 = x1 + 238, y1 + 56
                card.create_rectangle(x1, y1, x2, y2, fill=background, outline=border, width=2)
                card.create_text(x1 + 7, y1 + 9, text=f"#{slot}  {result}", anchor="w",
                                 fill="white", font=("Consolas", 9, "bold"))
                card.create_text(x1 + 7, y1 + 27, text=str(member.get("sn") or "—"), anchor="w",
                                 fill="#e2e8f0", font=("Consolas", 8))
                card.create_text(x1 + 7, y1 + 44,
                                 text=f"测试 {member.get('testCount', 0)} · 剩余 {member.get('retestRemaining', 0)}",
                                 anchor="w", fill="#cbd5e1", font=("Microsoft YaHei UI", 8))

    def _show_mes_box(self, title, cache_key):
        if cache_key in self.embedded_detail_views:
            self._render_embedded_motherboards(cache_key)
            self.notebook.select(self.embedded_detail_views[cache_key]["tab"])
            return
        window = tk.Toplevel(self.root)
        window.title(f"{title} · MES同步内容")
        window.geometry("980x520")
        tree = ttk.Treeview(window, columns=("batch","slot","sn","result","source","tests","status"), show="headings")
        for key, label in (("batch","母板号"),("slot","槽位"),("sn","SN"),("result","结果"),
                           ("source","来源工位"),("tests","测试次数"),("status","交接状态")):
            tree.heading(key, text=label)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for row in self.mes_box_cache.get(cache_key, []):
            tree.insert("", "end", values=(row.get("batchId",""), row.get("slot",""), row.get("sn",""),
                row.get("result") or row.get("overallResult",""), row.get("sourceStationCode") or row.get("sourceStation",""),
                row.get("testCount",""), row.get("transferStatus", "")))
        if cache_key in ("fct:ng","fct:confirmed"):
            tree.bind("<<TreeviewSelect>>",lambda _event:self._select_route_from_popup(tree,window))

    def _arm_route_target(self,batch_id):
        batch_id=str(batch_id or "").strip()
        if not batch_id:
            self.status.set("请先选择需要处理的NG或整盘")
            return False
        self.route_target_batch=batch_id
        self._confirm_route()
        return True

    def _select_route_from_ng_tree(self,_event=None):
        selected=self.ng_tree.selection()
        if selected:self._arm_route_target(self.ng_tree.item(selected[0],"values")[0])

    def _select_route_from_popup(self,tree,window):
        selected=tree.selection()
        if selected and self._arm_route_target(tree.item(selected[0],"values")[0]):window.destroy()

    def _show_handover_sheet(self):
        window = tk.Toplevel(self.root)
        window.title("维修复活接收单 / REPAIR REVIVAL ORDER")
        window.geometry("1080x540")
        tree = ttk.Treeview(window, columns=("id","batch","source","destination","members","status","sent","received","accepted"), show="headings")
        for key, label in (("id","交接单号"),("batch","整盘编号"),("source","来源工位"),("destination","目标工位"),
                           ("members","SN数量"),("status","交接状态"),("sent","送出时间"),("received","接收时间"),("accepted","接收人/扫码枪")):
            tree.heading(key, text=label)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        try:
            url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=manu_fct")
            with urllib.request.urlopen(url, timeout=5) as response:
                rows = [row for row in json.loads(response.read().decode("utf-8")).get("items", [])
                        if self._is_fct_repair_revival_order(row)]
            for row in rows:
                tree.insert("", "end", values=(row.get("transferId",""), row.get("batchId",""), row.get("sourceStation",""),
                    row.get("destinationStation",""), row.get("memberCount",""), row.get("status",""),
                    row.get("sentAt",""), row.get("receivedAt",""), row.get("acceptedBy","")))
        except Exception as exc:
            tree.insert("", "end", values=("MES连接失败", str(exc), "", "", "", "", "", "", ""))

    def _browse(self):
        chosen = filedialog.askdirectory(initialdir=self.watch_dir.get())
        if chosen:
            self.watch_dir.set(chosen)

    def _clear_local_sqlite(self):
        if not messagebox.askyesno(
            "清空 FCT 本地 SQLite",
            "确认清空 fct_agent.db 和 fct_ng.db 的全部业务记录？\n\n"
            "只删除 SQLite 数据并保留表结构；不会删除 Excel、MES 或 3D 数据。",
            icon="warning",
        ):
            return
        try:
            table_count = 0
            for db_path in (DB_PATH, FCT_NG_DB_PATH):
                with sqlite3.connect(str(db_path), timeout=30) as conn:
                    conn.execute("PRAGMA foreign_keys=OFF")
                    tables = [row[0] for row in conn.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    )]
                    for table in tables:
                        conn.execute(f'DELETE FROM "{table}"')
                    try:
                        conn.execute("DELETE FROM sqlite_sequence")
                    except sqlite3.OperationalError:
                        pass
                    conn.commit()
                    table_count += len(tables)
            self.active_retest_batch = None
            self.active_retest_attempt = 0
            self.active_retest_sn = None
            self.retest_scan_mode = False
            self.retest_partial_windows.clear()
            self.route_target_batch = ""
            self.mes_box_cache.clear()
            self.ict_ng_sns.clear()
            self._release_duplicate_alarm()
            self.batch_text.set(WAITING_TEXT)
            for index, var in enumerate(self.slot_vars, 1):
                var.set(f"Slot {index}\n—\nWAIT")
            for key in ("ng", "pass", "confirmed"):
                self.fct_box_vars[key].set("0")
            self._refresh_record_tabs()
            self.status.set("FCT 本地 SQLite 已清空")
            self.log(f"[CLEAR] FCT local SQLite cleared: {table_count} tables")
            messagebox.showinfo("清空完成", "FCT 本地 SQLite 数据已清空。\nExcel、MES 和 3D 数据未删除。")
        except Exception as exc:
            self.log(f"[CLEAR ERR] {exc}")
            messagebox.showerror("清空失败", str(exc))

    def _run_self_test(self):
        results = run_diagnostics(MES_URL, self.watch_dir.get(), SCANNER_TCP_PORT,
                                  (DB_PATH, FCT_NG_DB_PATH))
        lines = [f"{'通过' if ok else '失败'} · {name} · {detail}" for name, ok, detail in results]
        lines.insert(0, f"FCT v{APP_VERSION} · 首次确认阈值 {CONFIRM_AFTER_FAIL_COUNT}")
        messagebox.showinfo("FCT 系统自检", "\n".join(lines))

    def _scanner_tcp_worker(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", SCANNER_TCP_PORT))
            server.listen(5)
            while True:
                client, _address = server.accept()
                with client:
                    data = client.recv(256).decode("utf-8", errors="ignore").strip().upper()
                    if valid_sn(data):
                        self.ui_queue.put(("scanner", data))
        except Exception as error:
            self.log(f"Scanner TCP {SCANNER_TCP_PORT}: {error}")

    def _start_duplicate_alarm(self, sns):
        self.duplicate_sns = list(dict.fromkeys(str(sn) for sn in sns))
        self.duplicate_alarm_on = True
        self.duplicate_alarm_var.set("发现重复编码：" + " | ".join(self.duplicate_sns))
        speak("发现重复编码，禁止离开本站")
        self._flash_duplicate_alarm()

    def _flash_duplicate_alarm(self):
        if not self.duplicate_alarm_on:
            self.duplicate_alarm_label.configure(bg="#0f172a", fg="#94a3b8")
            return
        current = self.duplicate_alarm_label.cget("bg")
        self.duplicate_alarm_label.configure(bg="#dc2626" if current != "#dc2626" else "#facc15",
                                             fg="white" if current != "#dc2626" else "#111827")
        self.root.after(350, self._flash_duplicate_alarm)

    def _release_duplicate_alarm(self):
        # Keep the compact status alarm and the full-screen station alarm in
        # one state.  Either quick-release button must restore both UIs.
        if getattr(self, "station_alarm", None) is not None and self.station_alarm.active:
            self.station_alarm.release()
            return
        released = list(self.duplicate_sns)
        self.duplicate_alarm_on = False
        self.duplicate_sns = []
        self.duplicate_alarm_var.set("重码报警：正常")
        self.mes_queue.put({"type": "DUPLICATE_ALARM_RELEASE", "stationCode": STATION_CODE,
                            "payload": {"sns": released, "releasedAt": int(time.time()*1000)}})

    def log(self, message):
        self.ui_queue.put(("log", f"[{datetime.now():%H:%M:%S}] {message}"))

    def start(self):
        folder = Path(self.watch_dir.get())
        folder.mkdir(parents=True, exist_ok=True)
        if self.running:
            return
        self.running = True
        self.status.set("RUNNING")
        self.excel_event = threading.Event()
        self.excel_watcher = ExcelEventWatcher(folder, self.excel_event.set)
        self.excel_watcher.start()
        self.worker = threading.Thread(target=self._monitor, daemon=True, name="fct-xlsx-monitor")
        self.worker.start()
        self.log(f"Monitoring {folder}")

    def stop(self):
        self.running = False
        if hasattr(self, "excel_event"):
            self.excel_event.set()
        if hasattr(self, "excel_watcher"):
            self.excel_watcher.stop()
        self.status.set("STOPPED")
        self.log("Monitor stopped")

    def _already_processed(self, file_path, group):
        with sqlite3.connect(str(DB_PATH)) as conn:
            return conn.execute(
                "SELECT 1 FROM processed_groups WHERE file_path=? AND test_time=? AND side=?",
                (str(file_path), group["testTime"], group["side"]),
            ).fetchone() is not None

    def _save_group(self, file_path, group):
        now = int(time.time() * 1000)
        source_repeat_batch = None
        is_simulation = is_simulation_workbook(file_path)
        try:
            # ICT is the sole authority that creates a motherboard identity.
            # FCT must resolve and reuse that identity from the member SNs,
            # including during simulation. It must never mint a replacement
            # motherboard ID from its own test timestamp.
            ict_motherboard_id = group["batchId"] if not SOLID_MOTHERBOARD else mes_identify_ict_motherboard(
                [board["sn"] for board in group["subBoards"]]
            )
        except Exception as exc:
            # FCT owns its measured results, not the motherboard identity.
            # Upload the complete real 12-SN result immediately; MES stages it
            # and resolves the ICT motherboard by SN now or when ICT arrives.
            ict_motherboard_id = ""
            record_parse_audit(file_path, group, "IDENTITY_PENDING_MES", str(exc))
            self.log(f"MES will resolve ICT motherboard from FCT SNs: {exc}")
        group["motherboardId"] = ict_motherboard_id
        group["testCycleId"] = group["batchId"]
        if is_simulation:
            self.log("[TEST] DUP check bypassed for simulator workbook")
        if self.active_retest_batch is None and not is_unlimited_retest(STATION_CODE) and not is_simulation:
            incoming_sns = [board["sn"] for board in group["subBoards"]]
            with sqlite3.connect(str(DB_PATH)) as check_conn:
                placeholders = ",".join("?" for _ in incoming_sns)
                duplicates = [
                    row[0] for row in check_conn.execute(
                        f"SELECT sn FROM all_sns WHERE sn IN ({placeholders}) ORDER BY sn",
                        incoming_sns,
                    )
                ]
            # MES owns the factory-wide duplicate registry. Local SQLite is
            # checked first for speed; MES adds current-day and history scope.
            local_hits = set(duplicates)
            # At FCT these SNs are expected to exist upstream at ICT.  Their
            # factory-master presence is identity evidence, not a duplicate.
            # The exact ICT motherboard match above plus local FCT history
            # provides the correct cross-batch duplicate protection.
            if not SOLID_MOTHERBOARD:
                for sn in incoming_sns:
                    if sn in local_hits:
                        continue
                    try:
                        if mes_sn_is_duplicate(sn):
                            duplicates.append(sn)
                    except Exception as exc:
                        self.log(f"MES duplicate lookup unavailable; local fallback for {sn}: {exc}")
            duplicates = sorted(set(duplicates))
            if duplicates:
                record_parse_audit(file_path, group, "DUPLICATE_BLOCKED",
                    "duplicate SNs: " + ",".join(duplicates), ict_motherboard_id)
                with sqlite3.connect(str(DB_PATH)) as check_conn:
                    check_conn.execute(
                        "INSERT OR IGNORE INTO processed_groups VALUES (?,?,?,?,?,?,?)",
                        (str(file_path), group["testTime"], group["side"], group["rowStart"], group["rowEnd"], json.dumps(group, ensure_ascii=False), now),
                    )
                group["duplicateSns"] = duplicates
                group["stableBatchId"] = group["batchId"]
                group["lifecycle"] = {"batchId": group["batchId"], "overallResult": "DUPLICATE", "subBoards": group["subBoards"]}
                for sn in duplicates:
                    self.mes_queue.put({
                        "type": "DUPLICATE_SN",
                        "stationCode": STATION_CODE,
                        "payload": {"sn": sn, "batchId": group["batchId"] if SOLID_MOTHERBOARD else sn, "duplicateSns": duplicates, "eventType": "fct_xlsx"},
                    })
                self.log(f"Duplicate motherboard blocked: {len(duplicates)} duplicate SN(s)")
                self.ui_queue.put(("dup_alarm", duplicates))
                return
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_groups VALUES (?,?,?,?,?,?,?)",
                (str(file_path), group["testTime"], group["side"], group["rowStart"], group["rowEnd"], json.dumps(group, ensure_ascii=False), now),
            )
            if self.active_retest_batch is None and source_repeat_batch is None:
                for board in group["subBoards"]:
                    conn.execute(
                        "INSERT OR IGNORE INTO all_sns VALUES (?,?,?,?,?,?,?)",
                        (board["sn"], group["batchId"], board["channel"], board["result"], board["errorCode"], board["testTime"], now),
                    )
                stable_batch_id = ict_motherboard_id or group["batchId"]
                for slot, board in enumerate(group["subBoards"], 1):
                    conn.execute(
                        """INSERT OR REPLACE INTO fct_boards
                           (batch_id,slot,channel,sn,result_1,result_2,result_3,test_count,retest_remaining,is_confirmed)
                           VALUES (?,?,?,?,?,NULL,NULL,1,?,?)""",
                        (stable_batch_id, slot, board["channel"], board["sn"], board["result"],
                         MAX_AUTHORIZED_RETESTS if board["result"] == "FAIL" else 0,
                         int(board["result"] == "FAIL" and CONFIRM_AFTER_FAIL_COUNT <= 1)),
                    )
            else:
                stable_batch_id = self.active_retest_batch or source_repeat_batch
                expected = {
                    row[0]: row[1]
                    for row in conn.execute(
                        "SELECT sn,slot FROM fct_boards WHERE batch_id=?",
                        (stable_batch_id,),
                    )
                }
                incoming = {board["sn"] for board in group["subBoards"]}
                if not incoming or not incoming.issubset(set(expected)):
                    raise ValueError("Retest SN rows do not belong to the armed motherboard")
                if source_repeat_batch is not None:
                    prior_count = conn.execute(
                        "SELECT MAX(test_count) FROM fct_boards WHERE batch_id=?", (stable_batch_id,)
                    ).fetchone()[0] or 1
                    repeat_attempt = min(int(prior_count), 2)
                    self.log(f"MES source-result conflict check: automatic result set {repeat_attempt + 1} for {stable_batch_id}")
                else:
                    repeat_attempt = self.active_retest_attempt
                result_column = "result_2" if repeat_attempt == 1 else "result_3"
                for board in group["subBoards"]:
                    test_count = repeat_attempt + 1
                    remaining = max(0, MAX_AUTHORIZED_RETESTS - (test_count - 1))
                    confirmed = int(board["result"] == "FAIL" and test_count >= CONFIRM_AFTER_FAIL_COUNT)
                    conn.execute(
                        f"""UPDATE fct_boards SET {result_column}=?, test_count=?,
                            retest_remaining=?, is_confirmed=? WHERE batch_id=? AND sn=?""",
                        (board["result"], test_count, remaining, confirmed, stable_batch_id, board["sn"]),
                    )

            board_rows = conn.execute(
                """SELECT slot,channel,sn,result_1,result_2,result_3,test_count,
                          retest_remaining,is_confirmed
                   FROM fct_boards WHERE batch_id=? ORDER BY slot""",
                (stable_batch_id,),
            ).fetchall()
            lifecycle = {
                "batchId": stable_batch_id,
                "motherboardId": stable_batch_id,
                "ictBatchId": stable_batch_id,
                "testCycleId": group.get("testCycleId", group["batchId"]),
                "stationCode": STATION_CODE,
                "overallResult": "CONFIRMED_NG" if any(row[8] for row in board_rows)
                    else ("FAIL" if any((row[5] or row[4] or row[3]) == "FAIL" for row in board_rows) else "PASS"),
                "subBoards": [
                    {
                        "slot": row[0], "channel": row[1], "sn": row[2],
                        "results": [value for value in row[3:6] if value is not None],
                        "result": row[5] or row[4] or row[3],
                        "resultConflict": len(set(value for value in row[3:6] if value is not None)) > 1,
                        "finalResultPolicy": "LATEST_TEST_RESULT",
                        "testCount": row[6], "retestRemaining": row[7],
                        "isConfirmedNG": bool(row[8]),
                    }
                    for row in board_rows
                ],
            }
            conn.execute(
                """INSERT INTO fct_batches(batch_id,payload,updated_at,created_at) VALUES(?,?,?,?)
                   ON CONFLICT(batch_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at""",
                (stable_batch_id, json.dumps(lifecycle, ensure_ascii=False), now, now),
            )
        record_parse_audit(file_path, group,
            "AUTHORIZED_RETEST" if self.active_retest_batch is not None else "ACCEPTED",
            motherboard_id=stable_batch_id)
        group["stableBatchId"] = stable_batch_id
        group["lifecycle"] = lifecycle
        sync_ict_compatible_db(lifecycle)
        self._publish_lifecycle(lifecycle)
        fail_boards = [board for board in lifecycle["subBoards"] if board["result"] == "FAIL"]
        if fail_boards:
            slots = "、".join(str(board["slot"]) for board in fail_boards)
            remaining = min(int(board["retestRemaining"]) for board in fail_boards)
            if remaining:
                speak(f"母板号{stable_batch_id}，不良槽位{slots}，剩余复检机会{remaining}次")
            else:
                self.route_target_batch = stable_batch_id
                self._confirm_route()
                speak(f"母板号{stable_batch_id}，不良槽位{slots}，没有复检机会，整盘自动送往分板FCT不良箱")
        else:
            speak(f"母板号{stable_batch_id}，本盘测试通过")
        if self.active_retest_batch is not None:
            self.log(f"Retest {self.active_retest_attempt} complete; normal test mode restored")
            self.active_retest_batch = None
            self.active_retest_attempt = 0
            self.active_retest_sn = None

    def _enable_retest_scan(self):
        self.retest_scan_mode = True
        self.status.set("复检一次性旁路：请扫码或开始Excel复检")
        speak("请扫描需要复检的板码，或者开始复检")

    def _grant_overtime(self):
        if messagebox.askyesno("超时复检许可", "确认授权一次超过2小时的整盘复检？"):
            self.overtime_permission = True
            self.status.set("已授权一次超时复检")
            speak("超时复检已许可，请扫描板码")

    def _handle_scan(self):
        sn = self.scanner_var.get().strip().upper()
        self._last_scan_value = sn
        self._last_scan_time = time.monotonic()
        self.scanner_var.set("")
        if not sn or (not RESOLVE_BINDING_SCAN and not valid_sn(sn)):
            return

        scanned_code = sn
        if RESOLVE_BINDING_SCAN:
            try:
                url = MES_URL.replace("/api/pda/events", "/api/station/bucket-snapshots")
                with urllib.request.urlopen(url, timeout=5) as response:
                    snapshots = json.loads(response.read().decode("utf-8")).get("items", [])
                binding_rows = next((row.get("payload", []) for row in snapshots
                    if row.get("stationCode") == "manu_shellbinding" and row.get("bucketName") == "pass"), [])
                mapped = next((row for row in binding_rows if str(row.get("shellSn", "")).upper() == sn), None)
                if mapped and mapped.get("sn"):
                    sn = str(mapped["sn"]).strip().upper()
                    self.status.set(f"外壳码 {scanned_code} → PCBA {sn}")
                    speak(f"已识别外壳码，对应板码{sn}")
            except Exception as error:
                self.log(f"Binding lookup failed: {error}")
        if not valid_sn(sn):
            self.status.set(f"未找到有效绑定：{scanned_code}")
            speak("没有找到有效绑定，请检查外壳码")
            return
        allowed, verdict = mes_scan_gate(
            MES_URL, STATION_CODE, sn, event_type="physical_scanner",
            scannedCode=scanned_code, retestAuthorized=bool(self.retest_scan_mode),
        )
        _mes_guard_code = str(verdict.get("code") or "MES_GUARD_UNAVAILABLE") if isinstance(verdict, dict) else "MES_GUARD_UNAVAILABLE"
        if not allowed and _mes_guard_code != "MES_GUARD_UNAVAILABLE":
            code = str(verdict.get("code") or "MES_GUARD_UNAVAILABLE")
            self.status.set(f"MES禁止扫码：{code} · {sn}")
            self.station_alarm.trigger("MES扫码拦截", [sn], f"{code}，禁止产品离开本站")
            self.log(f"MES fail-closed scanner block {sn}: {verdict}")
            return
        retest_authorized = bool(self.retest_scan_mode or is_unlimited_retest(STATION_CODE))
        if self.retest_scan_mode:
            self.retest_scan_mode = False
            self.log(f"[RETEST BYPASS] shared one-time token consumed by scanner {sn}")
        if self.ng_guard.contains(sn) and not retest_authorized:
            self.status.set(f"确认不良，全线拦截 / CONFIRMED NG BLOCKED: {sn}")
            self.mes_queue.put({"type":"SN_SCAN","stationCode":STATION_CODE,
                                "payload":{"sn":sn,"result":"BLOCKED","decision":"CONFIRMED_NG_BLOCKED","eventType":"fct_scanner"}})
            return
        # Every FCT scanner read goes through MES first; it may automatically
        # complete an incoming ICT handover before normal FCT processing.
        local_duplicate = local_sn_is_duplicate(sn)
        with self.arrivals.connect() as arrival_db:
            arrival_previous = arrival_db.execute(
                "SELECT arrival_status,arrived_at FROM sn_arrivals WHERE station_code=? AND sn=?",
                (STATION_CODE, sn),
            ).fetchone()
        mes_duplicate = False
        mes_lookup_ok = True
        try:
            mes_duplicate = mes_sn_is_duplicate(sn)
        except Exception as exc:
            mes_lookup_ok = False
            self.log(f"MES duplicate lookup unavailable; local fallback for scanner {sn}: {exc}")
        self.mes_queue.put({"type": "SCAN_GUARD_CHECK", "stationCode": STATION_CODE,
                            "payload": {"sn": sn, "scannedCode": scanned_code, "result": "READ",
                                        "localProcessedHit": local_duplicate,
                                        "mesStationProcessedHit": mes_duplicate,
                                        "expectedByMes": self.expected_sn_manifest.contains(sn),
                                        "mesLookupOk": mes_lookup_ok,
                                        "retestAuthorized": retest_authorized, "eventType": "fct_scanner"}})
        if not retest_authorized:
            if local_duplicate or mes_duplicate or arrival_previous:
                self._start_duplicate_alarm([sn])
                self.station_alarm.trigger("重码报警", [sn], "发现重复编码，禁止离开本站")
                self.status.set(f"发现重复编码：{sn}")
                self.mes_queue.put({"type":"DUPLICATE_SN","stationCode":STATION_CODE,
                                    "payload":{"sn":sn,"localProcessedHit":local_duplicate,
                                               "mesStationProcessedHit":mes_duplicate,
                                               "eventType":"fct_scanner_duplicate"}})
            else:
                self.status.set(f"已扫描 {sn}")
                speak(f"板码{sn}，请开始测试")
            return
        with sqlite3.connect(str(DB_PATH)) as conn:
            row = conn.execute("""SELECT b.batch_id,b.test_count,b.retest_remaining,f.created_at
                FROM fct_boards b JOIN fct_batches f ON f.batch_id=b.batch_id
                WHERE b.sn=? ORDER BY f.updated_at DESC LIMIT 1""", (sn,)).fetchone()
        if not row:
            self.status.set("未找到该板所属FCT母板")
            speak("没有找到该母板")
            return
        try:
            self.arrivals.record_arrival(sn, "SCANNER", "manual-fct-scanner")
        except ArrivalError as exc:
            self.log(f"FCT scanner arrival blocked for {sn}: {exc}")
            self.status.set(f"扫码登记失败：{sn}")
            self.station_alarm.trigger("扫码登记失败", [sn], str(exc))
            return
        batch_id, test_count, remaining, created_at = row
        if remaining <= 0:
            self.route_target_batch = batch_id
            self.ui_queue.put(("route_required", batch_id))
            speak("没有复检机会，整盘自动送往分板FCT不良箱")
            return
        overtime = created_at and int(time.time()*1000) - int(created_at) > 2 * 3600 * 1000
        if overtime and not self.overtime_permission:
            self.status.set("超过2小时，需要主管许可")
            speak("该母板已超过两小时，需要主管许可后才能复检")
            return
        permission_by = "LOCAL_SUPERVISOR" if overtime and self.overtime_permission else None
        ok, mes_retest = self.mes_retest.arm(sn, batch_id, created_at, permission_by,
                                             "local supervisor permission" if permission_by else None)
        if not ok:
            code = mes_retest.get("code", "MES_RETEST_DENIED")
            self.status.set(f"MES复检拒绝：{code}")
            speak("MES未批准本次复检")
            return
        self.overtime_permission = False
        self.active_retest_batch = batch_id
        self.active_retest_attempt = int(test_count)
        self.active_retest_sn = sn
        self.status.set(f"复检已启动：{batch_id}，剩余{remaining}次")
        speak(f"母板号{batch_id}，还有{remaining}次复检机会，请开始测试")
        self.mes_queue.put({"type": "FCT_PROCESS", "stationCode": STATION_CODE,
                            "payload": {"stage": "RETEST_ARMED", "batchId": batch_id, "remaining": remaining}})

    def _start_ate_keyboard_hook(self):
        """Use the proven ATE-base keyboard-wedge listener for FCT."""
        try:
            from pynput import keyboard
        except ImportError:
            self.log("[SCANNER] pynput unavailable; FCT global keyboard hook disabled")
            return
        buffer = []

        def on_press(key):
            try:
                char = key.char.upper() if getattr(key, "char", None) else None
                if char and char.isalnum():
                    buffer.append(char)
                elif key == keyboard.Key.enter:
                    raw = "".join(buffer).strip().upper()
                    buffer.clear()
                    if raw and valid_sn(raw):
                        self.root.after(0, lambda value=raw: self._submit_global_scan(value))
            except Exception as exc:
                self.log(f"[SCANNER] global hook error: {exc}")

        self._ate_keyboard_listener = keyboard.Listener(on_press=on_press)
        self._ate_keyboard_listener.daemon = True
        self._ate_keyboard_listener.start()
        self.log("[SCANNER] ATE-base global keyboard hook started")

    def _submit_global_scan(self, sn):
        if sn == self._last_scan_value and time.monotonic() - self._last_scan_time < 0.8:
            return
        self.scanner_var.set(sn)
        self._handle_scan()

    def _confirm_route(self):
        if not self.route_target_batch:
            self.status.set("确认失败：请先从NG箱或NG记录中选择产品")
            speak("请先选择需要处理的不良品")
            return
        with sqlite3.connect(str(DB_PATH)) as conn:
            row = conn.execute("SELECT payload FROM fct_batches WHERE batch_id=?", (self.route_target_batch,)).fetchone()
        motherboard = json.loads(row[0]) if row else {}
        self.mes_queue.put({"type": "STATION_ROUTE_SELECTED", "stationCode": STATION_CODE,
            "payload": {"batchId": self.route_target_batch, "destination": NG_ROUTE_DESTINATION,
                        "workflowCode": NG_ROUTE_WORKFLOW,
                        "destinationLabel": NG_ROUTE_LABEL,
                        "destinationStationCode": NG_ROUTE_STATION_CODE,
                        "requestReason": NG_ROUTE_REASON,
                        "motherboard": motherboard,
                        "automatic": True,
                        "eventTime": int(time.time()*1000)}})
        self.status.set(f"{WORK_ITEM_LABEL} {self.route_target_batch} 已送往{NG_ROUTE_LABEL}，等待扫码接收")
        self.route_target_batch = ""
        self.route_button.configure(state="disabled")

    def arm_retest(self, attempt):
        if self.active_retest_batch is not None:
            self.log("A retest motherboard is already armed")
            return
        with sqlite3.connect(str(DB_PATH)) as conn:
            row = conn.execute(
                """SELECT b.batch_id,b.payload
                   FROM fct_batches b
                   WHERE EXISTS (
                     SELECT 1 FROM fct_boards n
                     WHERE n.batch_id=b.batch_id AND n.result_1='FAIL'
                       AND n.test_count=? AND n.retest_remaining>0
                   )
                   ORDER BY b.updated_at DESC LIMIT 1""",
                (attempt,),
            ).fetchone()
        if not row:
            self.log(f"No motherboard is waiting for retest {attempt}")
            return
        self.active_retest_batch = row[0]
        self.active_retest_attempt = attempt
        self.status.set(f"RETEST {attempt} ARMED")
        self.batch_text.set(
            f"Motherboard {row[0]} · next actual Excel row group is retest {attempt} · one-time bypass"
        )
        self.log(f"Retest {attempt} armed for motherboard {row[0]}")

    def _consume_retest_token_from_excel(self, group):
        """Let the first matching Excel group consume the scanner-or-Excel token."""
        if self.active_retest_batch is not None:
            return True
        if not self.retest_scan_mode:
            return False
        self.retest_scan_mode = False
        incoming = [board.get("sn", "") for board in group.get("subBoards", [])]
        with sqlite3.connect(str(DB_PATH)) as conn:
            placeholders = ",".join("?" for _ in incoming) or "?"
            row = conn.execute(
                f"""SELECT b.batch_id,b.sn,b.test_count,b.retest_remaining,f.created_at
                    FROM fct_boards b JOIN fct_batches f ON f.batch_id=b.batch_id
                    WHERE b.sn IN ({placeholders}) ORDER BY f.updated_at DESC LIMIT 1""",
                incoming or [""],
            ).fetchone()
        if not row or int(row[3] or 0) <= 0:
            self.log("[RETEST BYPASS] Excel consumed token but no eligible NG motherboard matched")
            return False
        batch_id, sn, test_count, remaining, created_at = row
        overtime = created_at and int(time.time()*1000) - int(created_at) > 2 * 3600 * 1000
        if overtime and not self.overtime_permission:
            self.status.set("超过2小时，需要主管许可")
            speak("该母板已超过两小时，需要主管许可后才能复检")
            return False
        permission_by = "LOCAL_SUPERVISOR" if overtime and self.overtime_permission else None
        ok, response = self.mes_retest.arm(
            sn, batch_id, created_at, permission_by,
            "local supervisor permission" if permission_by else None,
        )
        if not ok:
            self.status.set(f"MES复检拒绝：{response.get('code', 'MES_RETEST_DENIED')}")
            return False
        self.overtime_permission = False
        self.active_retest_batch = batch_id
        self.active_retest_attempt = int(test_count)
        self.active_retest_sn = sn
        self.status.set(f"Excel复检已启动：{batch_id}，剩余{remaining}次")
        self.log(f"[RETEST BYPASS] shared one-time token consumed by Excel; batch={batch_id}")
        return True

    def _monitor(self):
        while self.running:
            self.excel_event.wait()
            self.excel_event.clear()
            if not self.running:
                break
            try:
                path = latest_xlsx(self.watch_dir.get())
                if path:
                    if not wait_file_stable(path):
                        self.log(f"Excel still changing; deferred: {path.name}")
                        continue
                    for group in read_result_groups(path):
                        if self._already_processed(path, group):
                            continue
                        if self.active_retest_batch is None and self.retest_scan_mode:
                            self._consume_retest_token_from_excel(group)
                        if self.active_retest_batch is not None:
                            window_key = (str(path), group["testTime"], group["side"])
                            opened = self.retest_partial_windows.setdefault(window_key, time.monotonic())
                            if time.monotonic() - opened < 12.0:
                                self.ui_queue.put(("partial", group))
                                continue
                            # Rendering is driven by the tester workbook and
                            # must not wait for MES identity/network success.
                            self.ui_queue.put(("group", group))
                            self._save_group(path, group)
                            self.retest_partial_windows.pop(window_key, None)
                            continue
                        if not group["isComplete"]:
                            self.ui_queue.put(("partial", group))
                            self.mes_queue.put({"type": "FCT_PROCESS", "stationCode": STATION_CODE,
                                "payload": {"stage": "TESTING", "batchId": group["batchId"],
                                            "progress": group["discoveredCount"], "total": DISPLAY_SLOT_COUNT}})
                            continue
                        # Display the complete 12-slot result immediately.
                        # MES identification persists/retries independently.
                        self.ui_queue.put(("group", group))
                        self._save_group(path, group)
            except Exception as exc:
                self.log(f"Read retry: {exc}")

    def _show_group(self, group):
        lifecycle = group.get("lifecycle") or {}
        stable_batch_id = group.get("stableBatchId", group["batchId"])
        # Keep KPI data on the dedicated tab; the crowded monitor remains
        # focused on the motherboard slots.  Counts come from this real group.
        boards = list(group.get("subBoards") or [])
        update_station_kpi(
            self.kpi_tab,
            total=len(boards),
            passed=sum(str(board.get("result", "")).upper() in {"PASS", "OK"} for board in boards),
            ng=sum(str(board.get("result", "")).upper() in {"FAIL", "NG", "NOK"} for board in boards),
        )
        duplicate_sns = set(group.get("duplicateSns") or [])
        if SOLID_MOTHERBOARD:
            detail = f"{group['side']}1-{group['side']}12"
        else:
            detail = group["subBoards"][0].get("channel") or "single product"
        self.batch_text.set(
            f"{WORK_ITEM_LABEL} {stable_batch_id} · {detail} · "
            f"{lifecycle.get('overallResult', group['overallResult'])}"
        )
        for index, board in enumerate(group["subBoards"]):
            self.raw_tree.insert("",0,values=(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"EXCEL",
                f"rows {group.get('rowStart','?')}-{group.get('rowEnd','?')}",json.dumps(board,ensure_ascii=False),
                "PARSED",board.get("sn","")))
            is_duplicate = board["sn"] in duplicate_sns
            is_ict_ng = SHOW_UPSTREAM_NG_CLASSIFICATION and str(board["sn"]).strip().upper() in self.ict_ng_sns
            is_fct_ng = board["result"] == "FAIL"
            color = "#92400e" if is_duplicate else ("#7f1d1d" if is_fct_ng else ("#9a3412" if is_ict_ng else "#065f46"))
            border = "#fbbf24" if is_duplicate else ("#ef4444" if is_fct_ng else ("#fb923c" if is_ict_ng else "#10b981"))
            if SHOW_UPSTREAM_NG_CLASSIFICATION:
                result_marks = " + ".join(label for enabled, label in (
                    (is_ict_ng, "ICT NG"), (is_fct_ng, "FCT NG")
                ) if enabled) or "PASS"
            else:
                result_marks = "NG" if is_fct_ng else "PASS"
            display_index = index
            if INDEPENDENT_TWO_SIDED_LAYOUT:
                channel = str(board.get("channel") or "").strip().upper()
                if len(channel) >= 2 and channel[0] in ("L", "R") and channel[1:].isdigit():
                    channel_number = int(channel[1:])
                    if 1 <= channel_number <= 8:
                        display_index = channel_number - 1 + (8 if channel[0] == "R" else 0)
            self.slot_frames[display_index].configure(bg=color, highlightbackground=border)
            for child in self.slot_frames[display_index].winfo_children():
                child.configure(bg=color, fg="white")
            self.slot_vars[display_index].set(
                f"{board['channel']}\n{board['sn']}\n"
                f"{'DUPLICATE' if is_duplicate else result_marks}  {board['errorCode']}"
            )
        self.log(
            f"Discovered {len(group['subBoards'])} independent product(s): {stable_batch_id} "
            f"{lifecycle.get('overallResult', group['overallResult'])} "
            f"NG={sum(b['result'] == 'FAIL' for b in group['subBoards'])}"
        )
        self.status.set("RUNNING")
        children=self.raw_tree.get_children()
        if len(children)>1000: self.raw_tree.delete(*children[1000:])

    def _show_partial_group(self, group):
        count = group["discoveredCount"]
        self.batch_text.set(
            f"Reading motherboard · {group['side']} side · discovered {count}/12"
        )
        for index in range(12):
            if index < count:
                board = group["subBoards"][index]
                is_ict_ng = SHOW_UPSTREAM_NG_CLASSIFICATION and str(board["sn"]).strip().upper() in self.ict_ng_sns
                is_fct_ng = board["result"] == "FAIL"
                color = "#7f1d1d" if is_fct_ng else ("#9a3412" if is_ict_ng else "#065f46")
                border = "#ef4444" if is_fct_ng else ("#fb923c" if is_ict_ng else "#10b981")
                if SHOW_UPSTREAM_NG_CLASSIFICATION:
                    result_marks = " + ".join(label for enabled, label in (
                        (is_ict_ng, "ICT NG"), (is_fct_ng, "FCT NG")
                    ) if enabled) or "PASS"
                else:
                    result_marks = "NG" if is_fct_ng else "PASS"
                self.slot_frames[index].configure(bg=color, highlightbackground=border)
                for child in self.slot_frames[index].winfo_children():
                    child.configure(bg=color, fg="white")
                self.slot_vars[index].set(
                    f"{board['channel']} / Slot {index + 1}\n{board['sn']}\n"
                    f"{result_marks}  {board['errorCode']}"
                )
            else:
                self.slot_frames[index].configure(bg="#334155", highlightbackground="#64748b")
                for child in self.slot_frames[index].winfo_children():
                    child.configure(bg="#334155", fg="#cbd5e1")
                self.slot_vars[index].set(f"Slot {index + 1}\n—\nWAIT")

    def _drain_ui(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "log":
                    self.log_box.insert("end", payload + "\n")
                    self.log_box.see("end")
                elif kind == "group":
                    self._show_group(payload)
                elif kind == "partial":
                    self._show_partial_group(payload)
                elif kind == "route_required":
                    self.route_target_batch = str(payload)
                    self._confirm_route()
                elif kind == "dup_alarm":
                    self._start_duplicate_alarm(payload)
                    self.station_alarm.trigger("重码报警",payload,"发现重复编码，禁止离开本站")
                elif kind == "scanner":
                    self.scanner_var.set(payload)
                    self._handle_scan()
        except queue.Empty:
            pass
        self.root.after(100, self._drain_ui)

    def simulate(self, simulation_side=None):
        if self.sim_running:
            return
        self.sim_running = True
        simulation_count = 12 if SOLID_MOTHERBOARD else (8 if simulation_side in ("L", "R") else 1)
        active_test_button = self.right_test_button if simulation_side == "R" and self.right_test_button else self.test_button
        active_test_button.configure(state="disabled", text=f"Testing {simulation_side or WORK_ITEM_LABEL} 0/{simulation_count}...")
        if not self.running:
            self.start()
        SIM_DIR.mkdir(parents=True, exist_ok=True)
        path = SIM_DIR / f"{SIM_PRODUCT}({datetime.now():%Y-%m-%d}).xlsx"
        timestamp = datetime.now().strftime("%Y-%m-%d/%H:%M:%S")
        base = datetime.now().strftime("%H%M")
        retest_rows = None
        simulated_fail_slots = set(
            random.sample(range(1, simulation_count + 1), random.randint(1, min(4, simulation_count)))
        )
        simulation_members = None
        if self.active_retest_batch is not None:
            with sqlite3.connect(str(DB_PATH)) as conn:
                retest_rows = [row for row in conn.execute(
                    """SELECT channel,sn,COALESCE(result_3,result_2,result_1)
                       FROM fct_boards WHERE batch_id=? ORDER BY slot""",
                    (self.active_retest_batch,),
                ).fetchall() if str(row[2] or "").upper() == "FAIL"]
        elif SOLID_MOTHERBOARD:
            try:
                simulation_motherboard_id, simulation_members = mes_latest_ict_motherboard_members()
                self.log(f"Simulator uses ICT motherboard {simulation_motherboard_id}")
            except Exception as exc:
                self.sim_running = False
                active_test_button.configure(
                    state="normal", text=f"Test {WORK_ITEM_LABEL} ({simulation_count} SN)"
                )
                self.log(f"Simulator stopped: {exc}")
                return

        def writer():
            try:
                if path.exists():
                    wb = load_workbook(str(path))
                    ws = wb.active
                else:
                    wb = Workbook()
                    ws = wb.active
                    ws.title = "Sheet1"
                    ws.append(["ProgramName", "Operator", "TotalNumber", "PassRate", "ProgramFileDate", "PassNumber", "LCLROW"])
                    ws.append(["FCT-SIM.ats", "SIM", 0, 0, timestamp, 0, 12])
                    ws.append(["ChannelNo."] + list(range(1, 33)))
                    ws.append(["FailNumber"] + [0] * 32)
                    for _ in range(5, 22):
                        ws.append([])
                    ws.append(["NO.", "Result", "Channel", "BarCode", "Time", "ErrorCode", "Voltage", "FullLoad", "Ripple"])
                    ws.append([])
                    ws.append([])
                start_no = max(0, ws.max_row - 24)
                slots_to_write = range(1, len(retest_rows) + 1) if retest_rows else range(1, simulation_count + 1)
                for slot in slots_to_write:
                    if retest_rows:
                        channel, sn, result = retest_rows[slot - 1]
                    else:
                        channel = f"{simulation_side or 'L'}{slot}"
                        result = "FAIL" if slot in simulated_fail_slots else "PASS"
                        # Independent L/R banks need a 10-character simulator
                        # SN so the same parser used for equipment files accepts
                        # it: ASM + HHMM + side + slot(1-8) + suffix.
                        if simulation_side in ("L", "R"):
                            sn = f"{SIM_SN_PREFIX}{base}{simulation_side}{slot}A"
                        elif simulation_members:
                            sn = str(simulation_members[slot - 1].get("sn") or "").strip().upper()
                        else:
                            sn = f"{SIM_SN_PREFIX}{base}{slot:02d}A"
                    ws.append([start_no + slot, result, channel, sn, timestamp, "Vo" if result == "FAIL" else "0", 12.2, 12.1 if result == "PASS" else 0.0, 65.0])
                    wb.save(str(path))
                    expected_count = len(retest_rows) if retest_rows else simulation_count
                    self.log(f"Simulator wrote {channel}/{expected_count} {sn} {result}")
                    self.root.after(
                        0,
                        lambda current=slot: active_test_button.configure(
                            text=f"Testing {'retest' if retest_rows else WORK_ITEM_LABEL} {current}/{expected_count}..."
                        ),
                    )
                    time.sleep(0.10)
                wb.close()
            except Exception as exc:
                self.log(f"Simulator failed: {exc}")
            finally:
                self.sim_running = False
                self.root.after(
                    0,
                    lambda: active_test_button.configure(
                        state="normal", text=(f"测试{'右侧' if simulation_side == 'R' else '左侧'} 8 个" if simulation_side in ("L", "R") else f"Test {WORK_ITEM_LABEL} ({simulation_count} SN)")
                    ),
                )

        threading.Thread(target=writer, daemon=True, name="fct-simulator").start()


if __name__ == "__main__":
    _instance_mutex = acquire_single_instance("MANU_FCT_AGENT")
    _preview_duplicate = os.environ.get("STATION_AGENT_PREVIEW", "1").strip().lower() not in {"0", "false", "no"} and os.environ.get("STATION_AGENT_ALLOW_PREVIEW_DUPLICATE", "0").strip().lower() in {"1", "true", "yes"}
    if _instance_mutex is None and not _preview_duplicate:
        raise SystemExit("FCT Agent is already running")
    init_db()
    SIM_DIR.mkdir(parents=True, exist_ok=True)
    window = tk.Tk()
    if os.environ.get("FCT_EMBEDDED_ENGINE") == "1":
        window.withdraw()
    app = FctAgent(window)
    from station_retest import install_station_retest_panel
    install_station_retest_panel(window, STATION_CODE, MES_URL.replace("/api/pda/events", ""))
    from motherboard_search import install_motherboard_search
    motherboard_browser = install_motherboard_search(window, MES_URL, "manual")
    install_repair_workflow(window, STATION_CODE, MES_URL, "FCT")
    app.start()
    window.protocol("WM_DELETE_WINDOW", lambda: (app.stop(), window.destroy()))
    window.mainloop()
