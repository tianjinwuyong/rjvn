# -*- coding: utf-8 -*-
"""Manual depanel scanner: heartbeat plus barcode scans; no result files."""

import json
import socket
import sqlite3
import threading
import time
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from pathlib import Path
import subprocess, base64, sys, os
from datetime import datetime

try:
    import cv2
except ImportError:
    cv2 = None


MES_URL = os.environ.get("MES_API_URL", "http://192.168.6.155:8080/api/pda/events")
STATION_CODE = "auto_depanel"
HEARTBEAT_SECONDS = 5
SCANNER_TCP_HOST = os.environ.get("STATION_SCANNER_HOST", "0.0.0.0")
SCANNER_TCP_PORT = int(os.environ.get("STATION_SCANNER_PORT", "1003"))
CAMERA_QR_ENABLED = False
CAMERA_INDEX = int(os.environ.get("DEPANEL_CAMERA_INDEX", "0"))
CAMERA_REARM_SECONDS = float(os.environ.get("DEPANEL_CAMERA_REARM_SECONDS", "2.0"))
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
SN_DB = APP_DIR / "depanel_sn.db"
NG_DB = APP_DIR / "depanel_ng.db"
QT_COMMAND_PATH = APP_DIR / "depanel_qt_command.json"
sys.path.insert(0, str(APP_DIR.parent))
MANUAL_LINE_DIR = APP_DIR.parent.parent / "002-自动线"
if str(MANUAL_LINE_DIR) not in sys.path and MANUAL_LINE_DIR.exists():
    sys.path.insert(1, str(MANUAL_LINE_DIR))
from station_resource_startup import start_first_install_resource_read
start_first_install_resource_read(APP_DIR)
from station_ui_primitives import configure_tk_station, update_station_kpi, register_scanner_entry

try:
    from station_scrap_workflow import request_direct_scrap, start_sync_worker
except ImportError:
    def request_direct_scrap(*a, **k): pass
    def start_sync_worker(*a, **k): pass

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
    from station_data_sync import DurableMesSync, mes_scan_gate
except ImportError:
    class _DummyMesSync:
        def sync_once(self, *a, **k): return 0
        def flush(self): pass
        @property
        def ng_guard(self): return {}
    DurableMesSync = _DummyMesSync
    class _DummyGate:
        def get(self, *a, **k): return None
    mes_scan_gate = _DummyGate

try:
    from station_retest import install_station_retest_panel
except ImportError:
    def install_station_retest_panel(*a, **k): pass

try:
    from station_runtime_safety import acquire_single_instance
except ImportError:
    class _DummyMutex:
        def __init__(self, name): self.name = name
        def __enter__(self): return self
        def __exit__(self, *a): pass
    def acquire_single_instance(name):
        return _DummyMutex(name)

MES_SYNC = DurableMesSync(SN_DB, MES_URL, STATION_CODE)

def valid_sn(sn):
    value = str(sn or "").strip().upper()
    # Camera software may send either a daughterboard SN or the motherboard QR.
    return (len(value) == 10 and value.isalnum()) or (
        len(value) == 14 and value.isdigit()
    )

def fetch_motherboard_from_mes(sn):
    base = MES_URL.replace("/api/pda/events", "").rstrip("/")
    url = (
        f"{base}/api/station/confirmed-motherboards/identify/"
        f"{urllib.parse.quote(sn)}?line=auto"
    )
    with urllib.request.urlopen(url, timeout=8) as response:
        data = json.loads(response.read().decode("utf-8"))
    batch_id = str(data.get("motherboardId") or data.get("ictBatchId") or "").strip()
    members = data.get("members") or []
    if not batch_id or len(members) != 6:
        raise ValueError("MES returned incomplete motherboard identity")
    now = int(time.time() * 1000)
    with sqlite3.connect(str(NG_DB)) as conn:
        for index, board in enumerate(members, 1):
            slot = int(board.get("slot") or index)
            sn_value = str(board.get("sn") or "").strip().upper()
            result_value = str(board.get("result") or "PASS").upper()
            ict_value = int(bool(board.get("ictNg")))
            fct_value = int(bool(board.get("fctNg")))
            conn.execute("""INSERT INTO motherboard_members
                (batch_id,slot,sn,result,ict_ng,fct_ng,source_station,received_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(batch_id,slot) DO UPDATE SET
                  sn=excluded.sn,result=excluded.result,ict_ng=excluded.ict_ng,
                  fct_ng=excluded.fct_ng,source_station=excluded.source_station,
                  received_at=excluded.received_at""", (
                batch_id, slot, sn_value, result_value, ict_value,
                fct_value, "mes_identity", now,
            ))
            conn.execute("""INSERT INTO motherboard_member_history
                (batch_id,slot,sn,result,ict_ng,fct_ng,source_station,attempt_no,recorded_at,payload)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (
                batch_id, slot, sn_value, result_value, ict_value, fct_value,
                "mes_identity", int(board.get("testCount") or 1), now,
                json.dumps(board, ensure_ascii=False),
            ))
    return batch_id

def speak(text):
    script = f'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{str(text).replace(chr(34), "")}")'
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def init_databases():
    with sqlite3.connect(str(SN_DB)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS all_sns (
                sn TEXT PRIMARY KEY,
                first_scanned_at INTEGER NOT NULL,
                last_scanned_at INTEGER NOT NULL,
                scan_count INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_event_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sn TEXT NOT NULL,
                source TEXT NOT NULL,
                raw_value TEXT NOT NULL,
                received_at INTEGER NOT NULL,
                occurrence_no INTEGER NOT NULL,
                is_duplicate INTEGER NOT NULL DEFAULT 0,
                processing_status TEXT NOT NULL DEFAULT 'RECEIVED',
                motherboard_id TEXT,
                mes_event_id TEXT,
                mes_uploaded_at INTEGER,
                error_detail TEXT
            )
        """)
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_depanel_scan_history_sn_time
            ON scan_event_history(sn, received_at DESC)""")
        conn.execute(
            "DELETE FROM scan_event_history WHERE received_at < ?",
            (int(time.time() * 1000) - 30 * 24 * 60 * 60 * 1000,),
        )
    with sqlite3.connect(str(NG_DB)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS confirmed_ng (
                sn TEXT PRIMARY KEY,
                source_station TEXT NOT NULL,
                batch_id TEXT,
                status TEXT NOT NULL DEFAULT 'waiting',
                detected_at INTEGER NOT NULL,
                picked_at INTEGER,
                ict_ng INTEGER NOT NULL DEFAULT 0,
                fct_ng INTEGER NOT NULL DEFAULT 0
            )
        """)
        for column in ("ict_ng INTEGER NOT NULL DEFAULT 0", "fct_ng INTEGER NOT NULL DEFAULT 0"):
            try:
                conn.execute(f"ALTER TABLE confirmed_ng ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass
        conn.execute("UPDATE confirmed_ng SET ict_ng=1 WHERE source_station='auto_ict' AND ict_ng=0 AND fct_ng=0")
        conn.execute("UPDATE confirmed_ng SET fct_ng=1 WHERE source_station='auto_fct' AND ict_ng=0 AND fct_ng=0")
        conn.execute("""CREATE TABLE IF NOT EXISTS motherboard_members (
            batch_id TEXT NOT NULL, slot INTEGER NOT NULL, sn TEXT NOT NULL,
            result TEXT, ict_ng INTEGER NOT NULL DEFAULT 0,
            fct_ng INTEGER NOT NULL DEFAULT 0, source_station TEXT,
            received_at INTEGER NOT NULL, PRIMARY KEY(batch_id,slot))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_depanel_mb_sn ON motherboard_members(sn)")
        conn.execute("""CREATE TABLE IF NOT EXISTS motherboard_member_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL, slot INTEGER NOT NULL, sn TEXT NOT NULL,
            result TEXT, ict_ng INTEGER NOT NULL DEFAULT 0,
            fct_ng INTEGER NOT NULL DEFAULT 0, source_station TEXT NOT NULL,
            attempt_no INTEGER NOT NULL DEFAULT 1, recorded_at INTEGER NOT NULL,
            payload TEXT NOT NULL
        )""")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_depanel_mb_history
            ON motherboard_member_history(batch_id,sn,attempt_no,recorded_at)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mes_confirmed_ng_guard (
            sn TEXT PRIMARY KEY, source_station TEXT, batch_id TEXT,
            ict_ng INTEGER NOT NULL DEFAULT 0, fct_ng INTEGER NOT NULL DEFAULT 0,
            mes_version INTEGER NOT NULL DEFAULT 0, payload TEXT,
            synchronized_at INTEGER NOT NULL)""")


def save_scan(sn):
    now = int(time.time() * 1000)
    with sqlite3.connect(str(SN_DB)) as conn:
        conn.execute("""
            INSERT INTO all_sns (sn,first_scanned_at,last_scanned_at,scan_count)
            VALUES (?,?,?,1)
            ON CONFLICT(sn) DO UPDATE SET
              last_scanned_at=excluded.last_scanned_at,
              scan_count=all_sns.scan_count+1
        """, (sn, now, now))


def record_scan_event(sn, source, raw_value=None):
    """Append one immutable row for every scan, including duplicates."""
    now = int(time.time() * 1000)
    with sqlite3.connect(str(SN_DB)) as conn:
        previous = conn.execute(
            "SELECT COUNT(*) FROM scan_event_history WHERE sn=?", (sn,)
        ).fetchone()[0]
        cursor = conn.execute("""INSERT INTO scan_event_history
            (sn,source,raw_value,received_at,occurrence_no,is_duplicate,processing_status)
            VALUES(?,?,?,?,?,?,?)""", (
                sn, str(source or "UNKNOWN"), str(raw_value or sn), now,
                int(previous) + 1, int(previous > 0),
                "DUPLICATE_RECEIVED" if previous > 0 else "RECEIVED",
            ))
        return int(cursor.lastrowid), int(previous) + 1, bool(previous)


def update_scan_event(event_row_id, status, motherboard_id=None, mes_event_id=None, error_detail=None):
    uploaded_at = int(time.time() * 1000) if mes_event_id else None
    with sqlite3.connect(str(SN_DB)) as conn:
        conn.execute("""UPDATE scan_event_history SET
            processing_status=?, motherboard_id=COALESCE(?,motherboard_id),
            mes_event_id=COALESCE(?,mes_event_id),
            mes_uploaded_at=COALESCE(?,mes_uploaded_at), error_detail=?
            WHERE id=?""", (
                status, motherboard_id, mes_event_id, uploaded_at,
                str(error_detail)[:2000] if error_detail else None, event_row_id,
            ))


def mark_ng_picked(sn):
    now = int(time.time() * 1000)
    with sqlite3.connect(str(NG_DB)) as conn:
        row = conn.execute("SELECT source_station,batch_id FROM confirmed_ng WHERE sn=? AND status='waiting'", (sn,)).fetchone()
        if row:
            conn.execute("UPDATE confirmed_ng SET status='picked',picked_at=? WHERE sn=?", (now, sn))
        return row


def sync_confirmed_ng(event):
    event_type = event.get("type") or ""
    station = event.get("stationCode") or event.get("payload", {}).get("stationCode") or ""
    payload = event.get("payload") or {}
    now = int(time.time() * 1000)

    # ── STATION_NG_PICKED: 板被取出维修，更新本地状态为 picked ──
    if event_type == "STATION_NG_PICKED":
        sn = str(payload.get("sn") or "").strip().upper()
        if sn:
            mark_ng_picked(sn)
        return

    # ── NG_REVIVED: 维修完成，板回到产线，移除本地拦截记录 ──
    if event_type == "NG_REVIVED":
        sns = payload.get("sns") or []
        if payload.get("sn"):
            sns.append(payload["sn"])
        sns = [str(s).strip().upper() for s in sns if s]
        if sns:
            with sqlite3.connect(str(NG_DB)) as conn:
                for sn in sns:
                    conn.execute("DELETE FROM confirmed_ng WHERE sn=?", (sn,))
                    conn.execute("DELETE FROM mes_confirmed_ng_guard WHERE sn=?", (sn,))
        return

    # ── NG_DEFECT: 只处理 ICT/FCT 站的 NG 事件 ──
    if station not in ("auto_ict", "auto_fct"):
        return

    with sqlite3.connect(str(NG_DB)) as conn:
        # Preserve the complete incoming motherboard. Good siblings remain
        # visible, while defect marks are merged by SN across ICT and FCT.
        for fallback_slot, board in enumerate(payload.get("subBoards") or [], 1):
            if not board.get("sn"):
                continue
            board_sn = str(board["sn"]).upper()
            prior = conn.execute(
                "SELECT ict_ng,fct_ng FROM confirmed_ng WHERE sn=?", (board_sn,)
            ).fetchone() or (0, 0)
            board_ng = bool(board.get("isConfirmedNG")) or str(board.get("result", "")).upper() in {"NG", "CONFIRMED_NG"}
            ict_ng = max(int(prior[0]), int(station == "auto_ict" and board_ng))
            fct_ng = max(int(prior[1]), int(station == "auto_fct" and board_ng))
            conn.execute("""INSERT INTO motherboard_members
                (batch_id,slot,sn,result,ict_ng,fct_ng,source_station,received_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(batch_id,slot) DO UPDATE SET
                  sn=excluded.sn,result=excluded.result,
                  ict_ng=MAX(motherboard_members.ict_ng,excluded.ict_ng),
                  fct_ng=MAX(motherboard_members.fct_ng,excluded.fct_ng),
                  source_station=excluded.source_station,received_at=excluded.received_at""",
                (str(payload.get("batchId") or ""), int(board.get("slot") or fallback_slot),
                 board_sn, board.get("result"), ict_ng, fct_ng, station, now))
        for board in payload.get("subBoards") or []:
            if not board.get("isConfirmedNG") or not board.get("sn"):
                continue
            conn.execute("""
                INSERT INTO confirmed_ng (sn,source_station,batch_id,status,detected_at,picked_at,ict_ng,fct_ng)
                VALUES (?,?,?,'waiting',?,NULL,?,?)
                ON CONFLICT(sn) DO UPDATE SET
                  source_station=excluded.source_station,
                  batch_id=excluded.batch_id,
                  status='waiting',detected_at=excluded.detected_at,picked_at=NULL,
                  ict_ng=MAX(confirmed_ng.ict_ng,excluded.ict_ng),
                  fct_ng=MAX(confirmed_ng.fct_ng,excluded.fct_ng)
            """, (str(board["sn"]).upper(), station, payload.get("batchId"), now,
                  int(station == "auto_ict"), int(station == "auto_fct")))
            conn.execute(
                """UPDATE motherboard_members SET
                     ict_ng=MAX(ict_ng,?), fct_ng=MAX(fct_ng,?) WHERE sn=?""",
                (int(station == "auto_ict"), int(station == "auto_fct"), str(board["sn"]).upper()),
            )


def ng_event_listener():
    url = MES_URL + "?node=depanel_scanner&types=NG_DEFECT,NG_REVIVED,STATION_NG_PICKED"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if line.startswith("data: "):
                        sync_confirmed_ng(json.loads(line[6:]))
        except Exception:
            time.sleep(2)

def mes_snapshot_sync():
    """Mirror the same authoritative depanel boxes rendered by the 3D line."""
    url = MES_URL.replace("/api/pda/events", "/api/station/bucket-snapshots")
    guard_url = MES_URL.replace("/api/pda/events", "/api/station/ng-guard")
    handover_url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=auto_depanel")
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                snapshot_body = json.loads(response.read().decode("utf-8"))
                items = snapshot_body if isinstance(snapshot_body, list) else snapshot_body.get("items", [])
            with urllib.request.urlopen(guard_url, timeout=5) as response:
                guard = json.loads(response.read().decode("utf-8"))
            with urllib.request.urlopen(handover_url, timeout=5) as response:
                handovers = json.loads(response.read().decode("utf-8")).get("items", [])
            records = []
            for item in items:
                if item.get("stationCode") == STATION_CODE and item.get("bucketName") in ("pending_ng", "confirmed_ng"):
                    records.extend(item.get("payload") or [])
            active = {str(record.get("sn", "")).upper() for record in records if record.get("sn")}
            now = int(time.time() * 1000)
            with sqlite3.connect(str(NG_DB)) as conn:
                # Build guard_by_sn from confirmed_ng table (SSE maintains this correctly via MAX OR)
                guard_by_sn = {}
                for row in conn.execute("SELECT sn, ict_ng, fct_ng FROM confirmed_ng"):
                    sn, ict, fct = row[0], row[1], row[2]
                    existing = guard_by_sn.get(sn, (0, 0))
                    guard_by_sn[sn] = (max(existing[0], ict), max(existing[1], fct))
                # Upsert mes_confirmed_ng_guard from confirmed_ng (preserves OR'd flags from SSE)
                for sn, (ict, fct) in guard_by_sn.items():
                    src = 'auto_ict' if ict and not fct else ('auto_fct' if fct and not ict else ('ICT+FCT' if ict and fct else ''))
                    conn.execute("""INSERT INTO mes_confirmed_ng_guard (sn,source_station,ict_ng,fct_ng,synchronized_at)
                        VALUES(?,?,?,?,?)
                        ON CONFLICT(sn) DO UPDATE SET
                          ict_ng=MAX(mes_confirmed_ng_guard.ict_ng,excluded.ict_ng),
                          fct_ng=MAX(mes_confirmed_ng_guard.fct_ng,excluded.fct_ng),
                          source_station=excluded.source_station,
                          synchronized_at=excluded.synchronized_at""",
                        (sn, src, ict, fct, now))
                # MES sends authoritative ICT/FCT motherboard snapshots before
                # the physical product reaches depanel. Merge layouts by shared
                # daughterboard SNs and mirror them into local SQLite. A scanner
                # observation still confirms the physical position separately.
                layouts = []
                for record in guard.get("items", []) or []:
                    if not isinstance(record, dict):
                        continue
                    source = str(record.get("sourceStationCode") or record.get("stationCode") or "")
                    members = record.get("subBoards")
                    if source in ("auto_ict", "auto_fct") and isinstance(members, list) and len(members) == 6:
                        layouts.append((0 if source == "auto_ict" else 1, source, record, members))
                for _order, source, record, members in sorted(layouts, key=lambda row: row[0]):
                    member_sns = [str(board.get("sn") or "").strip().upper()
                                  for board in members if isinstance(board, dict) and board.get("sn")]
                    canonical_batch = str(record.get("batchId") or "")
                    if member_sns:
                        placeholders = ",".join("?" for _ in member_sns)
                        matched = conn.execute(
                            f"""SELECT batch_id,COUNT(*) AS overlap FROM motherboard_members
                                WHERE sn IN ({placeholders}) GROUP BY batch_id
                                HAVING COUNT(*)>=2 ORDER BY overlap DESC,MAX(received_at) DESC LIMIT 1""",
                            member_sns,
                        ).fetchone()
                        if matched:
                            canonical_batch = str(matched[0])
                    if not canonical_batch:
                        continue
                    for fallback_slot, board in enumerate(members, 1):
                        if not isinstance(board, dict) or not board.get("sn"):
                            continue
                        board_sn = str(board["sn"]).strip().upper()
                        board_ng = bool(board.get("isConfirmedNG")) or str(board.get("result") or "").upper() in {
                            "FAIL", "NG", "CONFIRMED_NG"
                        }
                        ict_flag, fct_flag = guard_by_sn.get(board_sn, (0, 0))
                        ict_flag = max(int(ict_flag), int(source == "auto_ict" and board_ng))
                        fct_flag = max(int(fct_flag), int(source == "auto_fct" and board_ng))
                        conn.execute("""INSERT INTO motherboard_members
                            (batch_id,slot,sn,result,ict_ng,fct_ng,source_station,received_at)
                            VALUES(?,?,?,?,?,?,?,?)
                            ON CONFLICT(batch_id,slot) DO UPDATE SET
                              sn=excluded.sn,result=excluded.result,
                              ict_ng=MAX(motherboard_members.ict_ng,excluded.ict_ng),
                              fct_ng=MAX(motherboard_members.fct_ng,excluded.fct_ng),
                              source_station='MES_MERGED',received_at=excluded.received_at""",
                            (canonical_batch, int(board.get("slot") or fallback_slot), board_sn,
                             board.get("result"), ict_flag, fct_flag, "MES_MERGED", now))
                # Rebuild complete FCT motherboards from MES handover payloads.
                # This makes layout recovery independent of live SSE delivery.
                for handover in handovers:
                    if str(handover.get("sourceStation", "")) != "auto_fct":
                        continue
                    motherboard = handover.get("motherboard") or {}
                    if isinstance(motherboard, str):
                        try: motherboard = json.loads(motherboard)
                        except Exception: motherboard = {}
                    members = motherboard.get("subBoards") or []
                    batch_id = str(handover.get("batchId") or motherboard.get("batchId") or "")
                    for fallback_slot, board in enumerate(members, 1):
                        if not isinstance(board, dict) or not board.get("sn"):
                            continue
                        board_sn = str(board["sn"]).upper()
                        ict_flag, global_fct_flag = guard_by_sn.get(board_sn, (0, 0))
                        fct_flag = max(int(global_fct_flag), int(bool(board.get("isConfirmedNG"))))
                        conn.execute("""INSERT INTO motherboard_members
                            (batch_id,slot,sn,result,ict_ng,fct_ng,source_station,received_at)
                            VALUES(?,?,?,?,?,?,?,?)
                            ON CONFLICT(batch_id,slot) DO UPDATE SET
                              sn=excluded.sn,result=excluded.result,
                              ict_ng=MAX(motherboard_members.ict_ng,excluded.ict_ng),
                              fct_ng=MAX(motherboard_members.fct_ng,excluded.fct_ng),
                              source_station=excluded.source_station,received_at=excluded.received_at""",
                            (batch_id, int(board.get("slot") or fallback_slot), board_sn,
                             board.get("result"), int(ict_flag), fct_flag, "auto_fct", now))
                for record in records:
                    sn = str(record.get("sn", "")).upper()
                    if not sn: continue
                    code = str(record.get("defectCode", ""))
                    ict_ng = int(code in ("ICT_ONLY_NG", "ICT_FCT_NG"))
                    fct_ng = int(code in ("FCT_ONLY_NG", "ICT_FCT_NG"))
                    conn.execute("""INSERT INTO confirmed_ng
                      (sn,source_station,batch_id,status,detected_at,picked_at,ict_ng,fct_ng)
                      VALUES(?,?,?,'waiting',?,NULL,?,?)
                      ON CONFLICT(sn) DO UPDATE SET source_station=excluded.source_station,
                       batch_id=excluded.batch_id,
                       status=CASE WHEN confirmed_ng.status='picked' THEN 'picked' ELSE 'waiting' END,
                       picked_at=CASE WHEN confirmed_ng.status='picked' THEN confirmed_ng.picked_at ELSE NULL END,
                      ict_ng=excluded.ict_ng,fct_ng=excluded.fct_ng""",
                      (sn, record.get("sourceStationCode") or record.get("originStationCode") or "MES",
                       record.get("batchId"), now, ict_ng, fct_ng))
        except Exception:
            pass
        time.sleep(3)


def post_event(event):
    body = json.dumps(event, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(MES_URL, data=body,
        headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=4) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def reconcile_local_inventory():
    while True:
        try:
            with sqlite3.connect(str(SN_DB)) as db:
                sns = [{"sn": row[0]} for row in db.execute("SELECT sn FROM all_sns ORDER BY sn")]
            with sqlite3.connect(str(NG_DB)) as db:
                ngs = [{"sn": row[0]} for row in db.execute(
                    "SELECT sn FROM confirmed_ng WHERE status='waiting' ORDER BY sn")]
            version = int(time.time() * 1000)
            MES_SYNC.reconcile("sn_records", sns, version, "sn")
            MES_SYNC.reconcile("confirmed_ng", ngs, version, "sn")
        except Exception:
            pass
        time.sleep(60)


class DepanelScanner:
    def __init__(self, root):
        self.root = root
        configure_tk_station(root)
        root.title("RUIJING · PCBA DEPANEL STATION")
        root.geometry("1060x760")
        root.configure(bg="#070d18")
        self.status = tk.StringVar(value="● 运行中 / RUNNING")
        self.sn = tk.StringVar()
        self.mes_motherboard_id = tk.StringVar(value="MES 母版号: —")
        self.selected_batch_id = ""
        self.pending_repair_batch = ""
        self.pending_repair_members = []

        header = tk.Frame(root, bg="#0b1f35", padx=14, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="PCBA分板工位 / PCBA DEPANEL STATION", bg="#0b1f35", fg="#e0f2fe", font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Label(header, text="扫码挑出不良品 | MES同步 | 交接接收", bg="#0b1f35", fg="#7dd3fc", font=("Microsoft YaHei UI", 11)).pack(side="left", padx=18)
        tk.Label(header,text="数据源: USB/TCP扫码枪 + MES确认NG",bg="#0b1f35",fg="#a7f3d0",font=("Microsoft YaHei UI",9)).pack(side="left",padx=8)
        self.language=TrilingualController(root,header)
        self.alarm=StationAlarm(root,lambda sns: post_event({"type":"DUPLICATE_ALARM_RELEASE","stationCode":STATION_CODE,"payload":{"sns":sns,"releasedAt":int(time.time()*1000)}}),STATION_CODE,MES_URL)

        cards = tk.Frame(root, bg="#070d18", padx=10, pady=8)
        cards.pack(fill="x")
        status_card = tk.Frame(cards, bg="#10243b", highlightbackground="#22c55e", highlightthickness=1)
        status_card.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(status_card, text="AGENT 状态 / STATUS", bg="#10243b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(pady=(7,0))
        tk.Label(status_card, textvariable=self.status, bg="#10243b", fg="#22c55e", font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(0,7))
        self.count_var = tk.StringVar(value="扫描 0 | 待挑出NG 0")
        count_card = tk.Frame(cards, bg="#10243b", highlightbackground="#38bdf8", highlightthickness=1)
        count_card.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(count_card, text="工位数据 / STATION DATA", bg="#10243b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(pady=(7,0))
        tk.Label(count_card, textvariable=self.count_var, bg="#10243b", fg="#38bdf8", font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(0,7))
        mother_card = tk.Frame(cards, bg="#10243b", highlightbackground="#fbbf24", highlightthickness=2)
        mother_card.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(mother_card, text="当前扫码母版 / CURRENT MOTHERBOARD", bg="#10243b",
                 fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(pady=(7, 0))
        tk.Label(mother_card, textvariable=self.mes_motherboard_id, bg="#10243b",
                 fg="#fbbf24", font=("Consolas", 15, "bold")).pack(pady=(0, 7))

        scanbar = tk.Frame(root, bg="#083344", padx=8, pady=7)
        scanbar.pack(fill="x", padx=10, pady=(0,8))
        tk.Label(scanbar, text="扫码枪 / SCANNER", bg="#083344", fg="#67e8f9", font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=6)
        self.entry = tk.Entry(scanbar, textvariable=self.sn, font=("Consolas", 20), bg="#10243b", fg="white", insertbackground="white", justify="center")
        self.entry.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        self.entry.bind("<Return>", self.submit)
        register_scanner_entry(self.root, self.entry)
        self.send_repair_button = tk.Button(
            scanbar, text="确认NG发往回修站", command=self.confirm_send_to_repair,
            state="disabled", bg="#c2410c", fg="white",
            font=("Microsoft YaHei UI", 11, "bold"), padx=12,
        )
        self.send_repair_button.pack(side="left", padx=4)
        tk.Button(scanbar, text="申请报废", command=lambda: request_direct_scrap(self.root, STATION_CODE, MES_URL, self.sn.get()), bg="#b91c1c", fg="white", font=("Microsoft YaHei UI", 11, "bold"), padx=12).pack(side="left", padx=4)

        notebook = self.notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0,8))
        live_tab, sn_tab, ict_ng_tab, fct_ng_tab, both_ng_tab, handover_tab, residence_tab, raw_tab, motherboard_history_tab = (tk.Frame(notebook, bg="#0f172a") for _ in range(9))
        notebook.add(live_tab, text="实时监控 / LIVE")
        notebook.add(motherboard_history_tab, text="母板历史 / MOTHERBOARDS")
        notebook.add(sn_tab, text="SN记录 / SN")
        notebook.add(ict_ng_tab, text="ICT NG")
        notebook.add(fct_ng_tab, text="FCT NG")
        notebook.add(both_ng_tab, text="ICT+FCT NG")
        notebook.add(handover_tab, text="工程交接单 / HANDOVER")
        notebook.add(residence_tab, text="工位滞留监控 / RESIDENCE")
        notebook.add(raw_tab,text="原始数据 / RAW DATA")
        tk.Button(scanbar, text="查看 SN SQLite", command=lambda: notebook.select(2),
                  bg="#0e7490", fg="white", font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=3)
        tk.Button(scanbar, text="ICT NG SQLite", command=lambda: notebook.select(3),
                  bg="#c2410c", fg="white", font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=3)
        tk.Button(scanbar, text="FCT NG SQLite", command=lambda: notebook.select(4),
                  bg="#b91c1c", fg="white", font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=3)
        tk.Button(scanbar, text="ICT+FCT SQLite", command=lambda: notebook.select(5),
                  bg="#7e22ce", fg="white", font=("Microsoft YaHei UI", 9, "bold")).pack(side="left", padx=3)
        self.raw_tree=ttk.Treeview(raw_tab,columns=("time","source","location","raw","status","sn"),show="headings")
        for key,label in (("time","接收时间"),("source","数据源"),("location","设备/接口"),("raw","原始内容"),("status","解析状态"),("sn","关联SN")): self.raw_tree.heading(key,text=label)
        self.raw_tree.column("raw",width=390); self.raw_tree.pack(fill="both",expand=True,padx=8,pady=8)
        history_header = tk.Frame(motherboard_history_tab, bg="#0b1f35", padx=12, pady=8)
        history_header.pack(fill="x")
        tk.Label(
            history_header, text="母板整体布局历史 · ICT/FCT 合并结果",
            bg="#0b1f35", fg="#7dd3fc",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).pack(side="left")
        self.motherboard_history_summary = tk.StringVar(value="等待母板数据")
        tk.Label(
            history_header, textvariable=self.motherboard_history_summary,
            bg="#0b1f35", fg="#cbd5e1",
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(side="right")
        self.motherboard_history_canvas = tk.Canvas(
            motherboard_history_tab, bg="#07111f", highlightthickness=0
        )
        history_scroll = ttk.Scrollbar(
            motherboard_history_tab, orient="vertical",
            command=self.motherboard_history_canvas.yview,
        )
        self.motherboard_history_content = tk.Frame(
            self.motherboard_history_canvas, bg="#07111f"
        )
        self.motherboard_history_content.bind(
            "<Configure>",
            lambda _event: self.motherboard_history_canvas.configure(
                scrollregion=self.motherboard_history_canvas.bbox("all")
            ),
        )
        self.motherboard_history_canvas.create_window(
            (0, 0), window=self.motherboard_history_content,
            anchor="nw", width=1010,
        )
        self.motherboard_history_canvas.configure(yscrollcommand=history_scroll.set)
        self.motherboard_history_canvas.pack(
            side="left", fill="both", expand=True, padx=(8, 0), pady=8
        )
        history_scroll.pack(side="right", fill="y", pady=8)
        self.box_count_vars = [tk.StringVar(value="0") for _ in range(3)]
        self.product_box_canvases = []
        box_row = tk.Frame(live_tab, bg="#07111f", padx=8, pady=8)
        box_row.pack(fill="x", padx=8, pady=8)
        for index, (title, color) in enumerate((("ICT NG", "#f97316"), ("FCT NG", "#ef4444"), ("ICT+FCT NG", "#a855f7"))):
            # The product tote itself is the button, matching the 3D-line box.
            canvas = tk.Canvas(box_row, width=172, height=46, bg="#10243b",
                               highlightthickness=0, cursor="hand2")
            canvas.pack(side="left", fill="x", expand=True, padx=6)
            canvas.create_rectangle(1, 1, 170, 44, outline=color, width=2)
            # Compact tote icon: the same product-box identity without a huge drawing.
            canvas.create_polygon(10, 15, 37, 15, 33, 20, 14, 20,
                                  fill="#07111f", outline=color, width=2)
            canvas.create_polygon(14, 20, 33, 20, 31, 34, 16, 34,
                                  fill="#0b1b2d", outline=color, width=2)
            canvas.create_text(46, 23, text=title, fill=color, anchor="w",
                               font=("Segoe UI", 9, "bold"))
            canvas.create_oval(142, 10, 164, 32, fill=color, outline="")
            count_item = canvas.create_text(153, 21, text="0", fill="white",
                                            font=("Segoe UI", 9, "bold"))
            callback = lambda _event, tab_index=index+3: notebook.select(tab_index)
            canvas.bind("<Button-1>", callback)
            self.product_box_canvases.append((canvas, count_item))
        self.motherboard_title = tk.StringVar(value="等待 FCT confirmed NG 母板 / WAITING")
        board_panel = tk.Frame(live_tab, bg="#0b1728", padx=8, pady=7)
        board_panel.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(board_panel, textvariable=self.motherboard_title, bg="#0b1728", fg="#7dd3fc",
                 font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        self.board_slot_vars, self.board_slot_frames = [], []
        for slot in range(1, 7):
            row, column = 1 + (slot - 1) // 3, (slot - 1) % 3
            frame = tk.Frame(board_panel, bg="#334155", highlightbackground="#64748b",
                             highlightthickness=2, width=240, height=62)
            frame.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)
            frame.grid_propagate(False)
            value = tk.StringVar(value=f"槽位 {slot} / SLOT {slot}\n—\nWAIT")
            tk.Label(frame, textvariable=value, bg="#334155", fg="#cbd5e1",
                     font=("Consolas", 9, "bold"), justify="center").pack(fill="both", expand=True)
            self.board_slot_vars.append(value); self.board_slot_frames.append(frame)
            board_panel.grid_columnconfigure(column, weight=1)
        self.log_box = scrolledtext.ScrolledText(live_tab, bg="#020617", fg="#cbd5e1", font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
        self.sn_tree = ttk.Treeview(sn_tab, columns=("sn","first","last","count"), show="headings")
        for key,label in (("sn","SN"),("first","首次扫描"),("last","最近扫描"),("count","次数")): self.sn_tree.heading(key,text=label)
        self.sn_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.ng_bucket_views = []
        for parent, title in zip(
            (ict_ng_tab, fct_ng_tab, both_ng_tab),
            ("ICT NG 母板布局", "FCT NG 母板布局", "ICT+FCT NG 母板布局"),
        ):
            header = tk.Frame(parent, bg="#0b1f35", padx=12, pady=8)
            header.pack(fill="x")
            tk.Label(
                header, text=title, bg="#0b1f35", fg="#7dd3fc",
                font=("Microsoft YaHei UI", 14, "bold"),
            ).pack(side="left")
            summary = tk.StringVar(value="0 块母板")
            tk.Label(
                header, textvariable=summary, bg="#0b1f35", fg="#cbd5e1",
                font=("Microsoft YaHei UI", 10, "bold"),
            ).pack(side="right")
            canvas = tk.Canvas(parent, bg="#07111f", highlightthickness=0)
            scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
            content = tk.Frame(canvas, bg="#07111f")
            content.bind(
                "<Configure>",
                lambda _event, c=canvas: c.configure(scrollregion=c.bbox("all")),
            )
            canvas.create_window((0, 0), window=content, anchor="nw", width=1010)
            canvas.configure(yscrollcommand=scroll.set)
            canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
            scroll.pack(side="right", fill="y", pady=8)
            self.ng_bucket_views.append((content, summary))
        self.handover_tree = ttk.Treeview(handover_tab,
            columns=("id","batch","source","destination","members","status","sent","received","accepted"), show="headings")
        for key,label in (("id","交接单号"),("batch","整盘编号"),("source","来源工位"),("destination","目标工位"),
                          ("members","SN数量"),("status","状态"),("sent","送出时间"),("received","接收时间"),("accepted","接收人/扫码枪")):
            self.handover_tree.heading(key,text=label)
        self.handover_tree.pack(fill="both",expand=True,padx=8,pady=8)
        self.residence_tree = ttk.Treeview(residence_tab,
            columns=("sn","batch","state","ng","entered","seconds","alarm"), show="headings")
        for key,label in (("sn","SN"),("batch","整盘编号"),("state","当前状态"),("ng","NG"),
                          ("entered","入站时间"),("seconds","滞留时间"),("alarm","报警状态")):
            self.residence_tree.heading(key,text=label)
        self.residence_tree.pack(fill="both",expand=True,padx=8,pady=8)
        notebook.bind("<<NotebookTabChanged>>", lambda _e: self.refresh_tables())
        def refresh_mes_pages():
            self.refresh_tables()
        self.root.after(500, refresh_mes_pages)
        self.root.after(800, self._refresh_kpi)
        self.entry.focus_set()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        threading.Thread(target=ng_event_listener, daemon=True).start()
        threading.Thread(target=mes_snapshot_sync, daemon=True).start()
        threading.Thread(target=self._qt_command_worker, daemon=True).start()
        threading.Thread(target=self._scanner_tcp_server, daemon=True).start()
        if CAMERA_QR_ENABLED:
            threading.Thread(
                target=self._camera_qr_worker,
                daemon=True,
                name="depanel-camera-qr",
            ).start()
        start_sync_worker(STATION_CODE, MES_URL)

    def _refresh_kpi(self):
        try:
            with sqlite3.connect(str(SN_DB)) as conn:
                scanned = conn.execute("SELECT COUNT(*) FROM all_sns").fetchone()[0]
            with sqlite3.connect(str(NG_DB)) as conn:
                ng = conn.execute(
                    "SELECT COUNT(*) FROM confirmed_ng WHERE status IN ('waiting','picked')"
                ).fetchone()[0]
            update_station_kpi(self.root, total=scanned, passed=max(0, scanned - ng), ng=ng)
        except Exception as exc:
            print(f"[KPI] refresh deferred: {exc}")
        self.root.after(2000, self._refresh_kpi)

    def _camera_qr_worker(self):
        """Continuously decode motherboard/daughterboard QR from USB camera."""
        if cv2 is None:
            self.root.after(
                0, lambda: self.status.set("Camera QR unavailable: OpenCV missing")
            )
            return
        detector = cv2.QRCodeDetector()
        last_code = ""
        last_seen = 0.0
        while True:
            camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
            if not camera.isOpened():
                self.root.after(
                    0,
                    lambda: self.status.set(
                        f"Camera {CAMERA_INDEX} unavailable or occupied; retrying"
                    ),
                )
                camera.release()
                time.sleep(5)
                continue
            self.root.after(
                0, lambda: self.status.set(f"Camera {CAMERA_INDEX} QR reading")
            )
            try:
                while camera.isOpened():
                    ok, frame = camera.read()
                    if not ok:
                        break
                    decoded, _points, _straight = detector.detectAndDecode(frame)
                    code = "".join(str(decoded or "").split()).upper()
                    now = time.monotonic()
                    if valid_sn(code):
                        if code != last_code or now - last_seen >= CAMERA_REARM_SECONDS:
                            if self._queue_external_sn(code):
                                last_code = code
                                self.root.after(
                                    0,
                                    lambda value=code: self.status.set(
                                        f"Camera QR received: {value}"
                                    ),
                                )
                        last_seen = now
                    elif now - last_seen >= CAMERA_REARM_SECONDS:
                        last_code = ""
            except Exception as exc:
                self.root.after(
                    0,
                    lambda message=str(exc): self.status.set(
                        f"Camera QR retry: {message}"
                    ),
                )
            finally:
                camera.release()
            time.sleep(2)

    def _scanner_tcp_server(self):
        """Accept scanner-compatible SN lines from local or LAN applications."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((SCANNER_TCP_HOST, SCANNER_TCP_PORT))
                server.listen(8)
                while True:
                    connection, _address = server.accept()
                    threading.Thread(
                        target=self._scanner_tcp_client,
                        args=(connection,),
                        daemon=True,
                    ).start()
        except Exception as exc:
            self.root.after(
                0,
                lambda message=str(exc): self.status.set(
                    f"TCP {SCANNER_TCP_PORT} unavailable: {message}"
                ),
            )

    def _scanner_tcp_client(self, connection):
        with connection:
            connection.settimeout(30)
            pending = b""
            while True:
                try:
                    chunk = connection.recv(1024)
                except socket.timeout:
                    break
                if not chunk:
                    if pending.strip():
                        self._queue_external_sn(
                            pending.decode("utf-8", "ignore"),
                            source=f"TCP:{SCANNER_TCP_PORT}",
                        )
                    break
                pending += chunk
                while b"\n" in pending or b"\r" in pending:
                    split_at = min(
                        index for index in (pending.find(b"\n"), pending.find(b"\r"))
                        if index >= 0
                    )
                    line, pending = pending[:split_at], pending[split_at + 1:]
                    pending = pending.lstrip(b"\r\n")
                    sn = line.decode("utf-8", "ignore").strip().upper()
                    if not sn:
                        continue
                    if self._queue_external_sn(sn, source=f"TCP:{SCANNER_TCP_PORT}"):
                        connection.sendall(b"OK QUEUED\r\n")
                    else:
                        connection.sendall(b"ERROR INVALID_SN\r\n")

    def _queue_external_sn(self, value, source="EXTERNAL"):
        sn = str(value or "").strip().upper()
        if not valid_sn(sn):
            return False
        self.root.after(
            0,
            lambda code=sn, scan_source=source: (
                self.sn.set(code),
                self.submit(source=scan_source),
            ),
        )
        return True

    def _qt_command_worker(self):
        last_request = ""
        while True:
            try:
                if QT_COMMAND_PATH.exists():
                    payload = json.loads(QT_COMMAND_PATH.read_text(encoding="utf-8"))
                    QT_COMMAND_PATH.unlink(missing_ok=True)
                    request_id = str(payload.get("requestId") or "")
                    if request_id and request_id != last_request:
                        last_request = request_id
                        tabs = {"show_sn_sqlite": 2, "show_ict_ng_sqlite": 3,
                                "show_fct_ng_sqlite": 4, "show_both_ng_sqlite": 5}
                        action = payload.get("command")
                        if action in tabs:
                            index = tabs[action]
                            self.root.after(0, lambda i=index: (self.root.deiconify(), self.notebook.select(i), self.root.lift()))
                        elif action == "release_duplicate_alarm":
                            post_event({"type":"DUPLICATE_ALARM_RELEASE","stationCode":STATION_CODE,
                                        "payload":{"releasedAt":int(time.time()*1000)}})
                        elif action == "scan_sn":
                            sn = str(payload.get("sn") or "").strip().upper()
                            if sn:
                                self.root.after(0, lambda value=sn: (self.sn.set(value), self.submit()))
                        elif action == "send_to_repair":
                            self.root.after(0, self.confirm_send_to_repair)
                        elif action == "request_scrap":
                            self.root.after(0, lambda: request_direct_scrap(
                                self.root, STATION_CODE, MES_URL, self.sn.get()))
            except Exception:
                pass
            time.sleep(0.2)

    def heartbeat_loop(self):
        while True:
            try:
                post_event({
                    "type": "AGENT_HEARTBEAT", "stationCode": STATION_CODE,
                    "payload": {"agent": "depanel_scanner", "status": "running", "timestamp": int(time.time() * 1000)},
                })
            except Exception:
                pass
            time.sleep(HEARTBEAT_SECONDS)

    def refresh_tables(self):
        try:
            with sqlite3.connect(str(SN_DB)) as conn:
                sns = conn.execute("SELECT sn,first_scanned_at,last_scanned_at,scan_count FROM all_sns ORDER BY last_scanned_at DESC LIMIT 1000").fetchall()
            with sqlite3.connect(str(NG_DB)) as conn:
                ngs = conn.execute("""SELECT sn,source_station,batch_id,status,detected_at,picked_at,ict_ng,fct_ng
                    FROM confirmed_ng WHERE status IN ('waiting','picked')
                    ORDER BY detected_at DESC LIMIT 1000""").fetchall()
                # MES may synchronize many waiting motherboards. Do not switch
                # the operator display until a child SN is scanned.
                latest_batch = ((self.selected_batch_id,) if self.selected_batch_id else None)
                motherboard = conn.execute(
                    "SELECT slot,sn,result,ict_ng,fct_ng FROM motherboard_members WHERE batch_id=? ORDER BY slot",
                    (latest_batch[0],),
                ).fetchall() if latest_batch else []
                motherboard_history = conn.execute(
                    """SELECT batch_id,slot,sn,result,ict_ng,fct_ng
                       FROM motherboard_members
                       ORDER BY received_at DESC,batch_id DESC,slot
                       LIMIT 600"""
                ).fetchall()
            self.sn_tree.delete(*self.sn_tree.get_children())
            for row in sns: self.sn_tree.insert("","end",values=row)
            counts = [0, 0, 0]
            bucket_batches = [set(), set(), set()]
            for row in ngs:
                category = 2 if row[6] and row[7] else (0 if row[6] else 1)
                if row[3] in ("waiting", "picked"):
                    counts[category] += 1
                    if row[2]:
                        bucket_batches[category].add(str(row[2]))
            for index, value in enumerate(counts):
                self.box_count_vars[index].set(str(value))
                if index < len(self.product_box_canvases):
                    canvas, count_item = self.product_box_canvases[index]
                    canvas.itemconfigure(count_item, text=str(value))
            self.count_var.set(f"扫描 {len(sns)} | ICT NG {counts[0]} | FCT NG {counts[1]} | ICT+FCT NG {counts[2]}")
            self._render_motherboard_history(motherboard_history)
            for index, batch_ids in enumerate(bucket_batches):
                bucket_rows = [row for row in motherboard_history if str(row[0]) in batch_ids]
                self._render_ng_bucket(index, bucket_rows)
            handover_url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=auto_depanel")
            with urllib.request.urlopen(handover_url, timeout=5) as response:
                handovers = json.loads(response.read().decode("utf-8")).get("items", [])
            self.handover_tree.delete(*self.handover_tree.get_children())
            for row in handovers:
                self.handover_tree.insert("","end",values=(row.get("transferId",""),row.get("batchId",""),
                    row.get("sourceStation",""),row.get("destinationStation",""),row.get("memberCount",""),
                    row.get("status",""),row.get("sentAt",""),row.get("receivedAt",""),row.get("acceptedBy","")))
            residence_url = MES_URL.replace("/api/pda/events", "/api/station/residence-stats?stationCode=auto_depanel")
            with urllib.request.urlopen(residence_url, timeout=5) as response:
                residence = json.loads(response.read().decode("utf-8"))
            threshold = int(residence.get("thresholdMinutes",30)) * 60
            self.residence_tree.delete(*self.residence_tree.get_children())
            for row in residence.get("current",[]):
                seconds = int(row.get("seconds",0))
                self.residence_tree.insert("","end",values=(row.get("sn",""),row.get("batchId",""),
                    row.get("productState",""),"是" if row.get("isNg") else "否",row.get("enteredAt",""),
                    f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}","超时" if seconds >= threshold else "正常"))
        except Exception:
            pass

    def _render_ng_bucket(self, index, rows):
        content, summary = self.ng_bucket_views[index]
        self._render_motherboard_cards(
            content, summary, rows, empty_text="当前 bucket 没有 NG 母板"
        )

    def _render_motherboard_history(self, rows):
        """Render every cached motherboard as one 3x2 six-slot layout card."""
        self._render_motherboard_cards(
            self.motherboard_history_content,
            self.motherboard_history_summary,
            rows,
            empty_text="暂无母板布局记录",
        )

    def _render_motherboard_cards(self, content, summary, rows, empty_text):
        for child in content.winfo_children():
            child.destroy()
        layouts = {}
        for batch_id, slot, sn, result, ict_ng, fct_ng in rows:
            layouts.setdefault(str(batch_id), {})[int(slot)] = (
                str(sn or ""), str(result or "PASS").upper(),
                bool(ict_ng), bool(fct_ng),
            )
        summary.set(
            f"{len(layouts)} 块母板 / {sum(len(items) for items in layouts.values())} 个子板"
        )
        if not layouts:
            tk.Label(
                content, text=empty_text, bg="#07111f", fg="#64748b",
                font=("Microsoft YaHei UI", 15, "bold"), pady=70,
            ).pack(fill="x")
            return
        for batch_id, members in layouts.items():
            card = tk.Canvas(
                content, height=180, bg="#0b1b2d",
                highlightbackground="#334155", highlightthickness=1,
            )
            card.pack(fill="x", padx=7, pady=6)
            ng_count = sum(1 for _sn, _result, ict_ng, fct_ng in members.values()
                           if ict_ng or fct_ng)
            card.create_text(
                12, 15, text=f"母板 {batch_id} · 3×2 · NG {ng_count}",
                anchor="w", fill="#7dd3fc", font=("Consolas", 11, "bold"),
            )
            for slot in range(1, 7):
                sn, result, ict_ng, fct_ng = members.get(
                    slot, ("—", "EMPTY", False, False)
                )
                state = (
                    "ICT+FCT NG" if ict_ng and fct_ng else
                    "ICT NG" if ict_ng else
                    "FCT NG" if fct_ng else
                    "PASS" if result not in ("EMPTY", "") else "EMPTY"
                )
                background = (
                    "#581c87" if ict_ng and fct_ng else
                    "#9a3412" if ict_ng else
                    "#991b1b" if fct_ng else
                    "#065f46" if state == "PASS" else "#334155"
                )
                border = (
                    "#c084fc" if ict_ng and fct_ng else
                    "#fb923c" if ict_ng else
                    "#ef4444" if fct_ng else
                    "#10b981" if state == "PASS" else "#64748b"
                )
                column, row_index = (slot - 1) % 3, (slot - 1) // 3
                x1, y1 = 10 + column * 247, 32 + row_index * 63
                x2, y2 = x1 + 238, y1 + 56
                card.create_rectangle(
                    x1, y1, x2, y2, fill=background, outline=border, width=2
                )
                card.create_text(
                    x1 + 7, y1 + 10, text=f"槽位 {slot} · {state}",
                    anchor="w", fill="white", font=("Microsoft YaHei UI", 9, "bold"),
                )
                card.create_text(
                    x1 + 7, y1 + 34, text=sn,
                    anchor="w", fill="#e2e8f0", font=("Consolas", 9),
                )

    def _render_motherboard(self, batch_id, members):
        self.mes_motherboard_id.set(f"MES 母版号: {batch_id}" if batch_id else "MES 母版号: —")
        self.motherboard_title.set(
            f"FCT confirmed NG 母板：{batch_id} · NG种类与槽位" if batch_id
            else "等待 FCT confirmed NG 母板 / WAITING"
        )
        by_slot = {int(row[0]): row for row in members}
        for slot in range(1, 7):
            row = by_slot.get(slot)
            if not row:
                text, color, border = f"槽位 {slot} / SLOT {slot}\n—\nWAIT", "#334155", "#64748b"
            else:
                _slot, sn, result, ict_ng, fct_ng = row
                marks = " + ".join(label for enabled, label in ((ict_ng, "ICT NG"), (fct_ng, "FCT NG")) if enabled) or "GOOD"
                color = "#581c87" if ict_ng and fct_ng else ("#9a3412" if ict_ng else ("#991b1b" if fct_ng else "#065f46"))
                border = "#c084fc" if ict_ng and fct_ng else ("#fb923c" if ict_ng else ("#ef4444" if fct_ng else "#10b981"))
                text = f"槽位 {slot} / SLOT {slot}\n{sn}\n{marks}"
            frame = self.board_slot_frames[slot - 1]
            frame.configure(bg=color, highlightbackground=border)
            for child in frame.winfo_children(): child.configure(bg=color, fg="white")
            self.board_slot_vars[slot - 1].set(text)

    def submit(self, _event=None, source="SCANNER"):
        sn = self.sn.get().strip().upper()
        self.sn.set("")
        source = str(source or "SCANNER")
        self.raw_tree.insert("",0,values=(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),source,"USB/TCP",sn,"RECEIVED",sn))
        children=self.raw_tree.get_children()
        if len(children)>1000:self.raw_tree.delete(*children[1000:])
        if not valid_sn(sn):
            return
        save_scan(sn)
        scan_event_id, occurrence_no, is_duplicate = record_scan_event(sn, source, sn)
        # Keep the scan path responsive: the local record is written first,
        # while MES upload runs independently and is retained on failure.
        mes_event_id = None
        threading.Thread(
            target=self._upload_scan_to_mes,
            args=(sn, source, scan_event_id, occurrence_no, is_duplicate),
            daemon=True,
            name="depanel-scan-upload",
        ).start()
        try:
            with sqlite3.connect(str(NG_DB)) as conn:
                # MES owns the canonical ICT motherboard identity. Local SQLite
                # can contain an older FCT-derived alias for the same daughter
                # SN, so always refresh from MES first and use SQLite only as an
                # offline fallback.
                batch = None
                batch = conn.execute(
                    """SELECT batch_id FROM motherboard_members
                       WHERE sn=? OR batch_id=?
                       ORDER BY
                         CASE WHEN LENGTH(batch_id)=14
                                    AND batch_id NOT GLOB '*[^0-9]*'
                              THEN 0 ELSE 1 END,
                         received_at DESC
                       LIMIT 1""", (sn, sn)
                ).fetchone()
                if not batch:
                    update_scan_event(
                        scan_event_id,
                        "MOTHERBOARD_NOT_FOUND",
                        mes_event_id=mes_event_id,
                        error_detail="motherboard identity not found locally or in MES",
                    )
                    self.status.set(f"未找到该板所属FCT母板：{sn}")
                    speak("没有找到该板所属母板")
                    return
                batch_id = str(batch[0])
                self.selected_batch_id = batch_id
                update_scan_event(
                    scan_event_id,
                    "DUPLICATE_MOTHERBOARD_FOUND" if is_duplicate else "MOTHERBOARD_FOUND",
                    motherboard_id=batch_id,
                    mes_event_id=mes_event_id,
                )
                members = conn.execute(
                    "SELECT slot,sn,result,ict_ng,fct_ng FROM motherboard_members WHERE batch_id=? ORDER BY slot",
                    (batch_id,),
                ).fetchall()
                ng_members = [row for row in members if row[3] or row[4]]
            self._render_motherboard(batch_id, members)
            self.pending_repair_batch = batch_id
            self.pending_repair_members = list(ng_members)
            self.send_repair_button.configure(state="normal" if ng_members else "disabled")
            if ng_members:
                ng_sns = [str(row[1]) for row in ng_members if str(row[1]).strip()]
                self.alarm.trigger(
                    "分板 NG 报警", ng_sns,
                    "立即取出标红的 NG 子板；确认取出后解除报警，MES 保留处理时长",
                )
            elif is_duplicate:
                self.alarm.trigger("重码报警", [sn], "分板扫码发现重复 SN，禁止继续流转")
            self.status.set(f"已显示母板 {batch_id} · 6槽 · NG {len(ng_members)} · 扫码仅查询")
            layout = "，".join(
                f"槽位{row[0]}，{'ICT和FCT不良' if row[3] and row[4] else ('ICT不良' if row[3] else 'FCT不良')}"
                for row in ng_members
            )
            message = f"已识别母板 {batch_id}，NG {len(ng_members)}片"
            self.status.set(message)
            self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] {message}\n")
            self.log_box.see("end")
            speak(f"已识别母板，{layout}，请直接挑出不良品" if layout else "已识别母板，本盘没有不良品")
            self.refresh_tables()
        except Exception as exc:
            update_scan_event(scan_event_id, "LOOKUP_FAILED", error_detail=exc)
            self.status.set(f"本地查询失败 / LOOKUP FAILED: {exc}")
        self.entry.focus_set()

    def confirm_send_to_repair(self):
        role_choice = messagebox.askyesnocancel(
            "确认送往维修站 / CONFIRM TRANSFER",
            "请选择确认人角色：\n\n是 / YES = 操作员 OPERATOR\n"
            "否 / NO = 品质 QC\n取消 / CANCEL = 不发送",
            parent=self.root,
        )
        if role_choice is None:
            return
        confirmer_role = "OPERATOR" if role_choice else "QC"
        confirmer_id = simpledialog.askstring(
            "人员确认 / PERSONNEL CONFIRMATION",
            f"请输入{('操作员' if confirmer_role == 'OPERATOR' else '品质人员')}工号：",
            parent=self.root,
        )
        confirmer_id = str(confirmer_id or "").strip().upper()
        if not confirmer_id:
            messagebox.showwarning("未发送 / NOT SENT", "必须输入确认人工号。", parent=self.root)
            return
        # Commit exactly what is physically staged in the three depanel NG
        # boxes at click time.  `picked` means the operator has scanned and
        # separated the daughterboard; already submitted items have status
        # `waiting_repair_receipt` and are therefore never submitted twice.
        with sqlite3.connect(str(NG_DB)) as conn:
            staged = conn.execute("""
                SELECT c.batch_id, COALESCE(m.slot, 0), c.sn,
                       c.detected_at, COALESCE(m.result, 'FAIL'),
                       c.ict_ng, c.fct_ng
                  FROM confirmed_ng c
                  LEFT JOIN motherboard_members m
                    ON m.batch_id=c.batch_id AND m.sn=c.sn
                 WHERE c.status='picked'
                 ORDER BY c.batch_id, COALESCE(m.slot, 0), c.sn
            """).fetchall()
        if not staged:
            self.status.set("三个NG箱中没有等待送修的产品")
            return
        sent_at = int(time.time() * 1000)
        transfer_batch_id = f"DEPANEL-NG-{sent_at}"
        oldest_ng_detected_at = min(int(row[3] or sent_at) for row in staged)
        dispatch_deadline_at = oldest_ng_detected_at + 20 * 60 * 1000
        repair_deadline_at = oldest_ng_detected_at + 120 * 60 * 1000
        endpoint = MES_URL.replace("/api/pda/events", "/api/station/maintenance-handovers")
        created = []
        try:
            for parent_batch, slot, ng_sn, first_detected_at, _result, ict_ng, fct_ng in staged:
                first_detected_at = int(first_detected_at or sent_at)
                category = "ICT_FCT_NG" if ict_ng and fct_ng else ("ICT_ONLY_NG" if ict_ng else "FCT_ONLY_NG")
                return_stations = (["auto_ict", "auto_fct"] if ict_ng and fct_ng
                                   else ["auto_ict"] if ict_ng else ["auto_fct"])
                board = {"slot": slot, "sn": ng_sn, "result": "FAIL", "defectCode": category,
                         "ngCategory": category, "detectedAt": first_detected_at,
                         "firstDetectedAt": first_detected_at,
                         "oldestNgDetectedAt": oldest_ng_detected_at,
                         "dispatchDeadlineAt": dispatch_deadline_at,
                         "repairDeadlineAt": repair_deadline_at,
                         "returnStations": return_stations, "parentBatchId": parent_batch}
                body = {"sourceStation": STATION_CODE, "sourceStationName": "PCBA分板工位",
                        "batchId": ng_sn, "parentBatchId": parent_batch,
                        "ngSn": ng_sn, "ngCategory": category,
                        "detectedAt": first_detected_at,
                        "firstDetectedAt": first_detected_at,
                        "transferBatchId": transfer_batch_id,
                        "oldestNgDetectedAt": oldest_ng_detected_at,
                        "dispatchDeadlineAt": dispatch_deadline_at,
                        "repairDeadlineAt": repair_deadline_at,
                        "receiptDeadlineMinutes": 15, "turnaroundDeadlineMinutes": 120,
                        "returnStations": return_stations, "members": [board],
                        "motherboard": {"batchId": ng_sn, "parentBatchId": self.pending_repair_batch,
                                        "split": True, "subBoards": [board]},
                        "submittedBy": confirmer_id, "submittedRole": confirmer_role,
                        "confirmedBy": confirmer_id, "confirmedRole": confirmer_role,
                        "clickedAt": sent_at}
                request = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(request, timeout=10) as response:
                    created.append(json.loads(response.read().decode("utf-8")))
            with sqlite3.connect(str(NG_DB)) as conn:
                sns = [str(row[2]) for row in staged]
                placeholders = ",".join("?" for _ in sns)
                conn.execute(f"UPDATE confirmed_ng SET status='waiting_repair_receipt' WHERE sn IN ({placeholders})", sns)
            self.status.set(
                f"{confirmer_role} {confirmer_id} 已确认发送 {len(created)} 个NG；"
                "等待维修站15分钟内扫码接收"
            )
            speak(f"已生成{len(created)}个维修工单，请送往回修站，等待扫码接收")
            self.pending_repair_batch = ""; self.pending_repair_members = []
            self.send_repair_button.configure(state="disabled")
            self.refresh_tables()
        except Exception as exc:
            self.status.set(f"维修WO生成失败：{exc}")
            speak("维修工单生成失败，请检查MES连接")


if __name__ == "__main__":
    _instance_mutex = acquire_single_instance("MANU_DEPANEL_AGENT")
    if _instance_mutex is None: raise SystemExit("Depanel Agent is already running")
    init_databases()
    threading.Thread(target=reconcile_local_inventory, daemon=True,
                     name="depanel-inventory-reconcile").start()
    app = tk.Tk()
    if os.environ.get("DEPANEL_EMBEDDED_ENGINE") == "1": app.withdraw()
    DepanelScanner(app)
    from motherboard_search import install_motherboard_search
    install_motherboard_search(app, MES_URL, "auto")
    retest_button = install_station_retest_panel(
        app, STATION_CODE, MES_URL.replace('/pda/events', ''),
        test_station=False, announcer=speak,
    )
    # The language selector occupies the top-right corner. Keep Confirm Retest
    # immediately to its left so both controls remain independently clickable.
    if retest_button is not None:
        retest_button.place_configure(relx=1.0, x=-170, y=12, anchor="ne")
    from station_repair_workflow import install_repair_workflow
    install_repair_workflow(app, STATION_CODE, MES_URL, "PCBA分板")
    app.mainloop()
