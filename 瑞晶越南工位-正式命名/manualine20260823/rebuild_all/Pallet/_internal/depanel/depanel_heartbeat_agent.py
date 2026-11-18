# -*- coding: utf-8 -*-
"""Manual depanel scanner: heartbeat plus barcode scans; no result files."""

import json
import sqlite3
import threading
import time
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from pathlib import Path
import subprocess, base64, sys, os
import socket
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_AUTO_UI_DIR = next(
    (path for path in Path(__file__).resolve().parents[2].iterdir()
     if path.is_dir() and path.name.startswith("002-")),
    None,
)
if _AUTO_UI_DIR is not None:
    sys.path.insert(0, str(_AUTO_UI_DIR))
from station_common_bootstrap import attach_common_agent
from station_repair_workflow import install_repair_workflow

COMMON_AGENT = attach_common_agent("manu_depanel", __file__, "depanel")


MES_URL = os.environ.get("MES_API_URL", "http://192.168.6.155:8080/api/pda/events")
STATION_CODE = "manu_depanel"
HEARTBEAT_SECONDS = 5
SCANNER_TCP_PORT = int(os.environ.get("DEPANEL_SCANNER_TCP_PORT", "1003"))
SCANNER_LISTENING = False
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
SN_DB = APP_DIR / "depanel_sn.db"
NG_DB = APP_DIR / "depanel_ng.db"
QT_COMMAND_PATH = APP_DIR / "depanel_qt_command.json"
sys.path.insert(0, str(APP_DIR.parent))

# Product arrival is a mandatory gate for every SN-processing station.  Keep
# depanel's existing local SQLite flow, while adding the shared append-only
# arrival ledger and MES/offline outbox before motherboard lookup begins.
try:
    from station_arrival_core import ArrivalError, StationArrivalStore
    ARRIVAL_STORE = StationArrivalStore(SN_DB, STATION_CODE, MES_URL)
except ImportError:
    ArrivalError = RuntimeError
    ARRIVAL_STORE = None

try:
    from station_ui_primitives import install_kpi_skeleton, install_station_tabs, register_scanner_entry
except ImportError:
    def install_kpi_skeleton(_parent):
        return None
    def register_scanner_entry(_root, entry):
        return entry

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
        def __init__(self, *a, **k): pass
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
    import ctypes
    class _WindowsMutex:
        def __init__(self, handle): self.handle = handle
        def close(self):
            if self.handle:
                ctypes.windll.kernel32.CloseHandle(self.handle)
                self.handle = None
        def __del__(self): self.close()
        def __enter__(self): return self
        def __exit__(self, *_args): self.close()
    def acquire_single_instance(name):
        if os.name != "nt":
            return _WindowsMutex(None)
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(
            None, False, "Local\\RUIJING_" + str(name)
        )
        if not handle:
            return None
        if kernel32.GetLastError() == 183:
            kernel32.CloseHandle(handle)
            return None
        return _WindowsMutex(handle)

MES_SYNC = DurableMesSync(SN_DB, MES_URL, STATION_CODE)

def valid_sn(sn):
    value = str(sn or "").strip().upper()
    return len(value) == 10 and value.isalnum()

def fetch_motherboard_from_mes(sn):
    base = MES_URL.replace("/api/pda/events", "").rstrip("/")
    url = (
        f"{base}/api/station/confirmed-motherboards/identify/"
        f"{urllib.parse.quote(sn)}?line=manual"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Some MES deployments expose the same confirmed layout through the
        # search route but return 404 from identify while its projection is
        # catching up.  Depanel must still be able to display ICT/FCT results.
        if exc.code != 404:
            raise
        fallback = (
            f"{base}/api/station/confirmed-motherboards/search/"
            f"{urllib.parse.quote(sn)}?line=manual"
        )
        try:
            with urllib.request.urlopen(fallback, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as search_exc:
            if search_exc.code != 404:
                raise
            # Last-resort projection fallback: the canonical list is often
            # available while the SN search index is being refreshed.
            listing = f"{base}/api/station/confirmed-motherboards?line=manual&limit=5000"
            with urllib.request.urlopen(listing, timeout=12) as response:
                listing_data = json.loads(response.read().decode("utf-8"))
            data = next(
                (
                    item for item in (listing_data.get("items") or [])
                    if any(
                        str(board.get("sn") or "").strip().upper() == str(sn).strip().upper()
                        for board in (item.get("members") or [])
                        if isinstance(board, dict)
                    )
                ),
                None,
            )
            if not data:
                raise ValueError(f"MES motherboard not found for SN {sn}")
    batch_id = str(data.get("motherboardId") or data.get("ictBatchId") or "").strip()
    members = data.get("members") or []
    if not batch_id or not members:
        raise ValueError("MES returned incomplete motherboard identity")
    now = int(time.time() * 1000)
    with sqlite3.connect(str(NG_DB)) as conn:
        conn.execute("DELETE FROM motherboard_members WHERE batch_id=?", (batch_id,))
        for index, board in enumerate(members, 1):
            conn.execute("""INSERT INTO motherboard_members
                (batch_id,slot,sn,result,ict_ng,fct_ng,source_station,received_at)
                VALUES(?,?,?,?,?,?,?,?)""", (
                batch_id, int(board.get("slot") or index), str(board.get("sn") or "").strip().upper(),
                str(board.get("result") or "PASS").upper(), int(bool(board.get("ictNg"))),
                int(bool(board.get("fctNg"))), "mes_identity", now,
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
        conn.execute("UPDATE confirmed_ng SET ict_ng=1 WHERE source_station='manu_ict' AND ict_ng=0 AND fct_ng=0")
        conn.execute("UPDATE confirmed_ng SET fct_ng=1 WHERE source_station='manu_fct' AND ict_ng=0 AND fct_ng=0")
        conn.execute("""CREATE TABLE IF NOT EXISTS motherboard_members (
            batch_id TEXT NOT NULL, slot INTEGER NOT NULL, sn TEXT NOT NULL,
            result TEXT, ict_ng INTEGER NOT NULL DEFAULT 0,
            fct_ng INTEGER NOT NULL DEFAULT 0, source_station TEXT,
            received_at INTEGER NOT NULL, PRIMARY KEY(batch_id,slot))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_depanel_mb_sn ON motherboard_members(sn)")
        conn.execute("""CREATE TABLE IF NOT EXISTS maintenance_handover_outbox (
            event_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'PENDING', sent_at INTEGER
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS mes_confirmed_ng_guard (
            sn TEXT PRIMARY KEY, source_station TEXT, batch_id TEXT,
            ict_ng INTEGER NOT NULL DEFAULT 0, fct_ng INTEGER NOT NULL DEFAULT 0,
            mes_version INTEGER NOT NULL DEFAULT 0, payload TEXT,
            synchronized_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS motherboard_sync_versions (
            batch_id TEXT PRIMARY KEY, mes_version INTEGER NOT NULL,
            updated_at TEXT, synchronized_at INTEGER NOT NULL)""")


def queue_maintenance_handover(payload, error="MES_OFFLINE"):
    """Persist a repair handover locally; MES remains the final authority."""
    event_id = str(payload.get("eventId") or "").strip()
    if not event_id:
        raise ValueError("maintenance handover requires eventId")
    with sqlite3.connect(str(NG_DB)) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO maintenance_handover_outbox
               (event_id,payload,created_at,last_error,status)
               VALUES(?,?,?,?, 'PENDING')""",
            (event_id, json.dumps(payload, ensure_ascii=False), int(time.time() * 1000), str(error)),
        )


def maintenance_handover_outbox_worker():
    """Retry queued depanel handovers after MES recovers, idempotently."""
    endpoint = MES_URL.replace("/api/pda/events", "/api/station/maintenance-handovers")
    while True:
        try:
            with sqlite3.connect(str(NG_DB)) as conn:
                rows = conn.execute(
                    "SELECT event_id,payload,attempts FROM maintenance_handover_outbox "
                    "WHERE status='PENDING' ORDER BY created_at LIMIT 20"
                ).fetchall()
            for event_id, raw, attempts in rows:
                try:
                    request = urllib.request.Request(
                        endpoint, data=raw.encode("utf-8"),
                        headers={"Content-Type": "application/json"}, method="POST"
                    )
                    with urllib.request.urlopen(request, timeout=5) as response:
                        response.read()
                    payload = json.loads(raw)
                    sn = str(payload.get("ngSn") or "").strip().upper()
                    with sqlite3.connect(str(NG_DB)) as conn:
                        conn.execute(
                            "UPDATE maintenance_handover_outbox SET status='SENT',sent_at=?,attempts=? WHERE event_id=?",
                            (int(time.time() * 1000), int(attempts) + 1, event_id),
                        )
                        if sn:
                            conn.execute(
                                "UPDATE confirmed_ng SET status='waiting_repair_receipt' WHERE sn=? AND status IN ('waiting','picked')",
                                (sn,),
                            )
                except Exception as exc:
                    with sqlite3.connect(str(NG_DB)) as conn:
                        conn.execute(
                            "UPDATE maintenance_handover_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?",
                            (str(exc), event_id),
                        )
        except Exception:
            pass
        time.sleep(5)


def sync_merged_motherboard(event):
    """Persist one versioned MES merge; return summary or None if stale."""
    payload = event.get("payload") or {}
    batch_id = str(payload.get("motherboardId") or "").strip()
    members = payload.get("members") or []
    version = int(payload.get("version") or 0)
    if not batch_id or not members or version <= 0:
        return None
    now = int(time.time() * 1000)
    with sqlite3.connect(str(NG_DB)) as conn:
        current = conn.execute(
            "SELECT mes_version FROM motherboard_sync_versions WHERE batch_id=?",
            (batch_id,),
        ).fetchone()
        if current and int(current[0]) >= version:
            return None
        old_sns = [
            row[0] for row in conn.execute(
                "SELECT sn FROM motherboard_members WHERE batch_id=?", (batch_id,)
            ).fetchall()
        ]
        conn.execute("DELETE FROM motherboard_members WHERE batch_id=?", (batch_id,))
        if old_sns:
            placeholders = ",".join("?" for _ in old_sns)
            conn.execute(
                f"DELETE FROM confirmed_ng WHERE batch_id=? OR sn IN ({placeholders})",
                [batch_id] + old_sns,
            )
        counts = {"ICT_NG": 0, "FCT_NG": 0, "ICT_FCT_NG": 0}
        slots = {"ICT_NG": [], "FCT_NG": [], "ICT_FCT_NG": []}
        for fallback_slot, board in enumerate(members, 1):
            slot = int(board.get("slot") or fallback_slot)
            sn = str(board.get("sn") or "").strip().upper()
            ict_ng = int(bool(board.get("ictNg")))
            fct_ng = int(bool(board.get("fctNg")))
            category = "ICT_FCT_NG" if ict_ng and fct_ng else (
                "ICT_NG" if ict_ng else ("FCT_NG" if fct_ng else "PASS")
            )
            conn.execute("""INSERT INTO motherboard_members
                (batch_id,slot,sn,result,ict_ng,fct_ng,source_station,received_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (batch_id, slot, sn, category, ict_ng, fct_ng, "MES_MERGED", now))
            if category != "PASS":
                counts[category] += 1
                slots[category].append(slot)
                conn.execute("""INSERT INTO confirmed_ng
                    (sn,source_station,batch_id,status,detected_at,picked_at,ict_ng,fct_ng)
                    VALUES (?,?,?,'waiting',?,NULL,?,?)
                    ON CONFLICT(sn) DO UPDATE SET source_station=excluded.source_station,
                      batch_id=excluded.batch_id,status='waiting',
                      detected_at=excluded.detected_at,picked_at=NULL,
                      ict_ng=excluded.ict_ng,fct_ng=excluded.fct_ng""",
                    (sn, category, batch_id, now, ict_ng, fct_ng))
        conn.execute("""INSERT INTO motherboard_sync_versions
            (batch_id,mes_version,updated_at,synchronized_at) VALUES(?,?,?,?)
            ON CONFLICT(batch_id) DO UPDATE SET mes_version=excluded.mes_version,
              updated_at=excluded.updated_at,synchronized_at=excluded.synchronized_at""",
            (batch_id, version, str(payload.get("updatedAt") or ""), now))
    return {"batchId": batch_id, "version": version, "counts": counts, "slots": slots}


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
                    conn.execute("UPDATE confirmed_ng SET status='revived' WHERE sn=?", (sn,))
                    conn.execute("DELETE FROM mes_confirmed_ng_guard WHERE sn=?", (sn,))
        return

    # ── NG_DEFECT: 只处理 ICT/FCT 站的 NG 事件 ──
    if station not in ("manu_ict", "manu_fct"):
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
            ict_ng = max(int(prior[0]), int(station == "manu_ict" and board_ng))
            fct_ng = max(int(prior[1]), int(station == "manu_fct" and board_ng))
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
                  int(station == "manu_ict"), int(station == "manu_fct")))
            conn.execute(
                """UPDATE motherboard_members SET
                     ict_ng=MAX(ict_ng,?), fct_ng=MAX(fct_ng,?) WHERE sn=?""",
                (int(station == "manu_ict"), int(station == "manu_fct"), str(board["sn"]).upper()),
            )


def ng_event_listener(on_merged=None):
    url = MES_URL + "?node=depanel_scanner&types=NG_DEFECT,NG_REVIVED,STATION_NG_PICKED,MOTHERBOARD_LAYOUT_UPDATED"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        if event.get("type") == "MOTHERBOARD_LAYOUT_UPDATED":
                            summary = sync_merged_motherboard(event)
                            if summary and on_merged:
                                on_merged(summary)
                        else:
                            sync_confirmed_ng(event)
        except Exception:
            time.sleep(2)

def mes_snapshot_sync(on_merged=None):
    """Mirror the same authoritative depanel boxes rendered by the 3D line."""
    url = MES_URL.replace("/api/pda/events", "/api/station/bucket-snapshots")
    guard_url = MES_URL.replace("/api/pda/events", "/api/station/ng-guard")
    motherboard_url = MES_URL.replace(
        "/api/pda/events",
        "/api/station/confirmed-motherboards?line=manual&limit=5000",
    )
    handover_url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=manu_depanel")
    while True:
        try:
            # Motherboard lookup is the depanel station's critical path. Large
            # bucket snapshots must never prevent the canonical MES feed from
            # reaching local SQLite.
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    snapshot_body = json.loads(response.read().decode("utf-8"))
                    items = snapshot_body if isinstance(snapshot_body, list) else snapshot_body.get("items", [])
            except Exception:
                items = []
            try:
                with urllib.request.urlopen(guard_url, timeout=5) as response:
                    guard = json.loads(response.read().decode("utf-8"))
            except Exception:
                # The full ICT/FCT motherboard snapshots below are sufficient
                # to rebuild the depanel lookup database. NG guard is useful
                # enrichment, but must never block the complete sync cycle.
                guard = {"items": []}
            try:
                with urllib.request.urlopen(motherboard_url, timeout=10) as response:
                    canonical_motherboards = json.loads(
                        response.read().decode("utf-8")
                    ).get("items", [])
            except Exception:
                canonical_motherboards = []
            try:
                with urllib.request.urlopen(handover_url, timeout=5) as response:
                    handovers = json.loads(response.read().decode("utf-8")).get("items", [])
            except Exception:
                handovers = []
            records = []
            for item in items:
                if item.get("stationCode") == STATION_CODE and item.get("bucketName") in ("pending_ng", "confirmed_ng"):
                    records.extend(item.get("payload") or [])
            active = {str(record.get("sn", "")).upper() for record in records if record.get("sn")}
            now = int(time.time() * 1000)
            with sqlite3.connect(str(NG_DB)) as conn:
                # MES canonical motherboard feed includes both all-PASS and NG
                # panels. Mirror every complete layout before processing the
                # defect-only guards and boxes.
                for layout in canonical_motherboards:
                    batch_id = str(layout.get("motherboardId") or "")
                    members = layout.get("members") or []
                    if not batch_id or not members:
                        continue
                    for fallback_slot, board in enumerate(members, 1):
                        board_sn = str(board.get("sn") or "").strip().upper()
                        if not board_sn:
                            continue
                        ict_flag = int(bool(board.get("ictNg")))
                        fct_flag = int(bool(board.get("fctNg")))
                        conn.execute(
                            """INSERT INTO motherboard_members
                               (batch_id,slot,sn,result,ict_ng,fct_ng,
                                source_station,received_at)
                               VALUES(?,?,?,?,?,?,?,?)
                               ON CONFLICT(batch_id,slot) DO UPDATE SET
                                 sn=excluded.sn,result=excluded.result,
                                 ict_ng=excluded.ict_ng,
                                 fct_ng=excluded.fct_ng,
                                 source_station='MES_CANONICAL',
                                 received_at=excluded.received_at""",
                            (
                                batch_id,
                                int(board.get("slot") or fallback_slot),
                                board_sn,
                                str(board.get("result") or "PASS").upper(),
                                ict_flag,
                                fct_flag,
                                "MES_CANONICAL",
                                now,
                            ),
                        )
                # Build guard_by_sn from confirmed_ng table (SSE maintains this correctly via MAX OR)
                guard_by_sn = {}
                for row in conn.execute("SELECT sn, ict_ng, fct_ng FROM confirmed_ng"):
                    sn, ict, fct = row[0], row[1], row[2]
                    existing = guard_by_sn.get(sn, (0, 0))
                    guard_by_sn[sn] = (max(existing[0], ict), max(existing[1], fct))
                # Upsert mes_confirmed_ng_guard from confirmed_ng (preserves OR'd flags from SSE)
                for sn, (ict, fct) in guard_by_sn.items():
                    src = 'manu_ict' if ict and not fct else ('manu_fct' if fct and not ict else ('ICT+FCT' if ict and fct else ''))
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
                # Primary source: authoritative ICT/FCT bucket snapshots. They
                # contain the complete 12-member motherboard, including PASS
                # siblings, so depanel can identify the panel by any scanned SN.
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    source = str(item.get("stationCode") or "")
                    bucket = str(item.get("bucketName") or "")
                    if source not in ("manu_ict", "manu_fct"):
                        continue
                    if bucket not in ("confirmed_ng", "pending_ng", "pass"):
                        continue
                    for record in item.get("payload") or []:
                        members = record.get("subBoards") if isinstance(record, dict) else None
                        if isinstance(members, list) and members:
                            layouts.append(
                                (0 if source == "manu_ict" else 1, source, record, members)
                            )
                # Secondary enrichment source: NG guard broadcasts.
                for record in guard.get("items", []) or []:
                    if not isinstance(record, dict):
                        continue
                    source = str(record.get("sourceStationCode") or record.get("stationCode") or "")
                    members = record.get("subBoards")
                    if source in ("manu_ict", "manu_fct") and isinstance(members, list) and members:
                        layouts.append((0 if source == "manu_ict" else 1, source, record, members))
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
                        ict_flag = max(int(ict_flag), int(source == "manu_ict" and board_ng))
                        fct_flag = max(int(fct_flag), int(source == "manu_fct" and board_ng))
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
                    if str(handover.get("sourceStation", "")) != "manu_fct":
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
                             board.get("result"), int(ict_flag), fct_flag, "manu_fct", now))
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
            # Reconnect/startup compensation: render the newest canonical MES
            # motherboard without requiring a scanner read. Version rejection
            # prevents this 3-second fallback from causing repeated redraws.
            if canonical_motherboards:
                newest = max(
                    canonical_motherboards,
                    key=lambda item: str(item.get("updatedAt") or ""),
                )
                updated_text = str(newest.get("updatedAt") or "")
                try:
                    version = int(datetime.fromisoformat(
                        updated_text.replace("Z", "+00:00")
                    ).timestamp() * 1000)
                except Exception:
                    version = now
                summary = sync_merged_motherboard({
                    "type": "MOTHERBOARD_LAYOUT_UPDATED",
                    "payload": {
                        **newest,
                        "version": version,
                        "updatedAt": updated_text,
                    },
                })
                if summary and on_merged:
                    on_merged(summary)
        except Exception:
            pass
        time.sleep(3)


def post_event(event):
    payload = event.get("payload") or {}
    return MES_SYNC.send(event.get("type", "STATION_EVENT"), payload,
                         eventId=event.get("eventId"))


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
        root.title("RUIJING · PCBA DEPANEL STATION")
        # Keep the complete four-column motherboard visible on the station's
        # 1280px RDP display (Windows display scaling may be 125%).
        root.geometry("1060x760")
        root.configure(bg="#070d18")
        self.status = tk.StringVar(value="● 运行中 / RUNNING")
        self.sn = tk.StringVar()
        self._normalizing_scan = False
        self._global_scan_buffer = ""
        self._global_scan_last_key_at = 0.0
        self._last_scan_value = ""
        self._last_scan_time = 0.0
        self.sn.trace_add("write", self._keep_latest_scan)
        self.selected_batch_id = ""
        self._latest_mes_batch_id = ""
        self.pending_repair_batch = ""
        self.pending_repair_members = []
        self._last_sqlite_view_signature = None
        self._merged_alarm_active = False
        self._merged_alarm_flash = False
        self._last_announced_version = 0

        header = tk.Frame(root, bg="#0b1f35", padx=14, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="PCBA分板工位 / PCBA DEPANEL STATION", bg="#0b1f35", fg="#e0f2fe", font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Label(header, text="扫码挑出不良品 | MES同步 | 交接接收", bg="#0b1f35", fg="#7dd3fc", font=("Microsoft YaHei UI", 11)).pack(side="left", padx=18)
        tk.Label(header,text="数据源: USB/TCP扫码枪 + MES确认NG",bg="#0b1f35",fg="#a7f3d0",font=("Microsoft YaHei UI",9)).pack(side="left",padx=8)
        self.language=TrilingualController(root,header)
        self.alarm=StationAlarm(root,lambda sns: post_event({"type":"DUPLICATE_ALARM_RELEASE","stationCode":STATION_CODE,"payload":{"sns":sns,"releasedAt":int(time.time()*1000)}}),STATION_CODE,MES_URL)

        cards = tk.Frame(root, bg="#070d18", padx=10, pady=8)
        cards.pack(fill="x")
        status_card = self.status_card = tk.Frame(cards, bg="#10243b", highlightbackground="#22c55e", highlightthickness=1)
        status_card.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(status_card, text="AGENT 状态 / STATUS", bg="#10243b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(pady=(7,0))
        self.status_label = tk.Label(status_card, textvariable=self.status, bg="#10243b", fg="#22c55e", font=("Microsoft YaHei UI", 14, "bold"))
        self.status_label.pack(pady=(0,7))
        self.count_var = tk.StringVar(value="扫描 0 | 待挑出NG 0")
        count_card = tk.Frame(cards, bg="#10243b", highlightbackground="#38bdf8", highlightthickness=1)
        count_card.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(count_card, text="工位数据 / STATION DATA", bg="#10243b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(pady=(7,0))
        tk.Label(count_card, textvariable=self.count_var, bg="#10243b", fg="#38bdf8", font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(0,7))
        self.current_motherboard = tk.StringVar(
            value="当前母版 / CURRENT MOTHERBOARD: 等待扫码"
        )
        motherboard_card = tk.Frame(
            cards, bg="#10243b", highlightbackground="#f59e0b",
            highlightthickness=1
        )
        motherboard_card.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(
            motherboard_card, text="当前母版 / CURRENT MOTHERBOARD",
            bg="#10243b", fg="#fbbf24", font=("Microsoft YaHei UI", 9, "bold")
        ).pack(pady=(7, 0))
        tk.Label(
            motherboard_card, textvariable=self.current_motherboard,
            bg="#10243b", fg="#f8fafc", font=("Consolas", 14, "bold")
        ).pack(pady=(0, 7))

        scanbar = tk.Frame(root, bg="#083344", padx=8, pady=7)
        scanbar.pack(fill="x", padx=10, pady=(0,8))
        tk.Label(scanbar, text="扫码枪 / SCANNER", bg="#083344", fg="#67e8f9", font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=6)
        # Keep the retest action in the scanner bar. The shared retest panel
        # otherwise places it at the root window's top-right corner, which
        # overlaps the header/cards on Depanel.
        retest_host = tk.Frame(scanbar, bg="#083344")
        retest_host.pack(side="right", padx=(8, 0))
        self.root._retest_host = retest_host
        self.entry = tk.Entry(scanbar, textvariable=self.sn, font=("Consolas", 20), bg="#10243b", fg="white", insertbackground="white", justify="center")
        self.entry.pack(side="left", fill="x", expand=True, padx=8, ipady=5)
        register_scanner_entry(self.root, self.entry)
        # Keep the visible scanner field's behavior identical to FCT: a
        # scanner suffix or operator Enter submits through the station path.
        self.entry.bind("<Return>", self.submit)
        self._disable_ime_for_scanner()
        # Keyboard-wedge scanners are captured globally inside the station
        # window. The scan does not depend on the Entry having focus.
        self.root.bind_all("<KeyPress>", self._capture_global_scanner_key, add="+")
        notebook = self.notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0,8))
        live_tab, sn_tab, ict_ng_tab, fct_ng_tab, both_ng_tab, handover_tab, residence_tab, raw_tab, sqlite_tab, kpi_tab = (tk.Frame(notebook, bg="#0f172a") for _ in range(10))
        notebook.add(live_tab, text="实时监控 / LIVE")
        notebook.add(sn_tab, text="SN记录 / SN")
        notebook.add(ict_ng_tab, text="ICT NG")
        notebook.add(fct_ng_tab, text="FCT NG")
        notebook.add(both_ng_tab, text="ICT+FCT NG")
        notebook.add(handover_tab, text="工程交接单 / HANDOVER")
        notebook.add(residence_tab, text="工位滞留监控 / RESIDENCE")
        notebook.add(raw_tab,text="原始数据 / RAW DATA")
        notebook.add(sqlite_tab, text="本地 SQLite / LOCAL DB")
        notebook.add(kpi_tab, text="KPI / ANALYSIS")
        # Put the shared operator/maintenance tabs into Depanel's existing
        # workspace notebook.  Creating them before this notebook produces a
        # second tab bar above the LIVE view; ICT uses this single-notebook
        # layout as the common station pattern.
        install_station_tabs(root)
        install_kpi_skeleton(kpi_tab)
        self.sqlite_tab = sqlite_tab
        # Depanel operator view is intentionally minimal: scanner + calculated
        # motherboard only. Diagnostic tables remain instantiated for support
        # code but are not exposed in the production UI.
        for hidden_tab in (sn_tab, handover_tab, residence_tab, raw_tab):
            notebook.hide(hidden_tab)
        self.raw_tree=ttk.Treeview(raw_tab,columns=("time","source","location","raw","status","sn"),show="headings")
        for key,label in (("time","接收时间"),("source","数据源"),("location","设备/接口"),("raw","原始内容"),("status","解析状态"),("sn","关联SN")): self.raw_tree.heading(key,text=label)
        self.raw_tree.column("raw",width=390); self.raw_tree.pack(fill="both",expand=True,padx=8,pady=8)
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
            callback = lambda _event, tab_index=index+2: notebook.select(tab_index)
            canvas.bind("<Button-1>", callback)
            self.product_box_canvases.append((canvas, count_item))
        self.motherboard_title = tk.StringVar(value="等待母版扫码 / WAITING FOR MOTHERBOARD")
        board_panel = tk.Frame(live_tab, bg="#0b1728", padx=8, pady=7)
        board_panel.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(board_panel, textvariable=self.motherboard_title, bg="#0b1728", fg="#7dd3fc",
                 font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))
        self.board_slot_vars, self.board_slot_frames = [], []
        for slot in range(1, 13):
            row, column = 1 + (slot - 1) // 4, (slot - 1) % 4
            frame = tk.Frame(board_panel, bg="#334155", highlightbackground="#64748b",
                             highlightthickness=2, width=180, height=62)
            frame.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)
            frame.grid_propagate(False)
            value = tk.StringVar(value=f"槽位 {slot} / SLOT {slot}\n—\nWAIT")
            tk.Label(frame, textvariable=value, bg="#334155", fg="#cbd5e1",
                     font=("Consolas", 9, "bold"), justify="center").pack(fill="both", expand=True)
            self.board_slot_vars.append(value); self.board_slot_frames.append(frame)
            board_panel.grid_columnconfigure(column, weight=1)
        self.log_box = scrolledtext.ScrolledText(live_tab, bg="#020617", fg="#cbd5e1", font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)
        self.log_box.pack_forget()
        # NG routing is owned by the shared MES repair component.  Do not
        # expose a duplicate manual send button in the depanel main view.
        self.send_repair_button = None
        self.sn_tree = ttk.Treeview(sn_tab, columns=("sn","first","last","count"), show="headings")
        for key,label in (("sn","SN"),("first","首次扫描"),("last","最近扫描"),("count","次数")): self.sn_tree.heading(key,text=label)
        self.sn_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.ng_trees = []
        for parent in (ict_ng_tab, fct_ng_tab, both_ng_tab):
            tree = ttk.Treeview(
                parent,
                columns=(
                    "sn", "source", "batch", "status", "detected", "picked",
                    "layout", "ng_count", "synced",
                ),
                displaycolumns=("batch", "layout", "ng_count", "synced"),
                show="headings",
            )
            for key,label in (("sn","SN"),("source","来源"),("batch","母板号"),("status","状态"),("detected","发现时间"),("picked","挑出时间")): tree.heading(key,text=label)
            for key, label, width in (
                ("batch", "母版号 / MOTHERBOARD", 160),
                ("layout", "12槽结构 / 12-SLOT LAYOUT", 610),
                ("ng_count", "NG数", 65),
                ("synced", "同步时间", 145),
            ):
                tree.heading(key, text=label)
                tree.column(key, width=width, anchor="center")
            tree.pack(fill="both", expand=True, padx=8, pady=8)
            self.ng_trees.append(tree)
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

        sqlite_tools = tk.Frame(sqlite_tab, bg="#0f172a", padx=8, pady=8)
        sqlite_tools.pack(fill="x")
        tk.Label(
            sqlite_tools, text="SN / 母版号", bg="#0f172a", fg="#cbd5e1",
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(side="left")
        self.sqlite_filter = tk.StringVar()
        sqlite_entry = tk.Entry(
            sqlite_tools, textvariable=self.sqlite_filter, width=28,
            bg="#10243b", fg="white", insertbackground="white",
            font=("Consolas", 11),
        )
        sqlite_entry.pack(side="left", padx=8, ipady=3)
        sqlite_entry.bind("<Return>", lambda _event: self.refresh_local_sqlite())
        tk.Button(
            sqlite_tools, text="查询 / REFRESH", command=self.refresh_local_sqlite,
            bg="#0284c7", fg="white", activebackground="#0369a1",
            activeforeground="white", relief="flat", padx=14, pady=4,
        ).pack(side="left")
        self.sqlite_summary = tk.StringVar(value="点击查询查看本地 SQLite")
        tk.Label(
            sqlite_tools, textvariable=self.sqlite_summary, bg="#0f172a",
            fg="#7dd3fc", font=("Microsoft YaHei UI", 10),
        ).pack(side="right")
        # History uses the same 4 x 3 motherboard structure as ICT and FCT.
        history_layout = tk.Frame(sqlite_tab, bg="#07111f")
        history_layout.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self.sqlite_layout_canvas = tk.Canvas(
            history_layout, bg="#07111f", height=330, highlightthickness=0
        )
        history_scroll = ttk.Scrollbar(
            history_layout, orient="vertical", command=self.sqlite_layout_canvas.yview
        )
        self.sqlite_layout_canvas.configure(yscrollcommand=history_scroll.set)
        history_scroll.pack(side="right", fill="y")
        self.sqlite_layout_canvas.pack(side="left", fill="both", expand=True)
        self.sqlite_layout_content = tk.Frame(self.sqlite_layout_canvas, bg="#07111f")
        self.sqlite_layout_window = self.sqlite_layout_canvas.create_window(
            (0, 0), window=self.sqlite_layout_content, anchor="nw"
        )
        self.sqlite_layout_content.bind(
            "<Configure>",
            lambda _e: self.sqlite_layout_canvas.configure(
                scrollregion=self.sqlite_layout_canvas.bbox("all")
            ),
        )
        self.sqlite_layout_canvas.bind(
            "<Configure>",
            lambda e: self.sqlite_layout_canvas.itemconfigure(
                self.sqlite_layout_window, width=e.width
            ),
        )
        sqlite_columns = (
            "batch", "slot", "sn", "result", "ict", "fct", "source", "received"
        )
        self.sqlite_tree = ttk.Treeview(
            sqlite_tab, columns=sqlite_columns, show="headings"
        )
        for key, label, width in (
            ("batch", "母版号 / MOTHERBOARD", 150),
            ("slot", "槽位", 50),
            ("sn", "SN", 130),
            ("result", "结果", 65),
            ("ict", "ICT NG", 60),
            ("fct", "FCT NG", 60),
            ("source", "数据源", 110),
            ("received", "同步时间", 145),
        ):
            self.sqlite_tree.heading(key, text=label)
            self.sqlite_tree.column(key, width=width, anchor="center")
        sqlite_scroll = ttk.Scrollbar(
            sqlite_tab, orient="vertical", command=self.sqlite_tree.yview
        )
        self.sqlite_tree.configure(yscrollcommand=sqlite_scroll.set)
        sqlite_scroll.pack(side="right", fill="y", pady=(0, 8))
        self.sqlite_tree.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)
        self.root.after(3000, self._refresh_sqlite_tab_if_visible)
        self.entry.focus_set()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        threading.Thread(target=self.scanner_tcp_loop, daemon=True,
                         name="depanel-scanner-tcp").start()
        threading.Thread(
            target=ng_event_listener,
            args=(lambda summary: self.root.after(0, self._apply_merged_layout, summary),),
            daemon=True,
            name="depanel-mes-merged-layout",
        ).start()
        threading.Thread(
            target=mes_snapshot_sync,
            args=(lambda summary: self.root.after(0, self._apply_merged_layout, summary),),
            daemon=True,
            name="depanel-mes-snapshot",
        ).start()
        threading.Thread(target=self._qt_command_worker, daemon=True).start()
        start_sync_worker(STATION_CODE, MES_URL)

    def _on_notebook_tab_changed(self, _event=None):
        selected = self.notebook.select()
        if selected == str(self.sqlite_tab):
            self.refresh_local_sqlite()

    def _refresh_sqlite_tab_if_visible(self):
        if self.notebook.select() == str(self.sqlite_tab):
            self.refresh_local_sqlite()
        self.root.after(3000, self._refresh_sqlite_tab_if_visible)

    def refresh_local_sqlite(self):
        """Read-only operator view of the depanel station's local SQLite."""
        keyword = self.sqlite_filter.get().strip().upper()
        for row in self.sqlite_tree.get_children():
            self.sqlite_tree.delete(row)
        for widget in self.sqlite_layout_content.winfo_children():
            widget.destroy()
        try:
            with sqlite3.connect(str(NG_DB)) as conn:
                conn.row_factory = sqlite3.Row
                where = ""
                params = []
                if keyword:
                    where = "WHERE UPPER(batch_id) LIKE ? OR UPPER(sn) LIKE ?"
                    pattern = f"%{keyword}%"
                    params = [pattern, pattern]
                rows = conn.execute(
                    f"""SELECT batch_id,slot,sn,result,ict_ng,fct_ng,
                               source_station,received_at
                        FROM motherboard_members {where}
                        ORDER BY received_at DESC,batch_id DESC,slot
                        LIMIT 5000""",
                    params,
                ).fetchall()
                board_count = conn.execute(
                    f"""SELECT COUNT(DISTINCT batch_id)
                        FROM motherboard_members {where}""",
                    params,
                ).fetchone()[0]
            for row in rows:
                received = ""
                if row["received_at"]:
                    received = time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime(int(row["received_at"]) / 1000),
                    )
                self.sqlite_tree.insert("", "end", values=(
                    row["batch_id"], row["slot"], row["sn"], row["result"],
                    "NG" if row["ict_ng"] else "-",
                    "NG" if row["fct_ng"] else "-",
                    row["source_station"] or "", received,
                ))
            layouts = {}
            for row in rows:
                layouts.setdefault(str(row["batch_id"]), {})[int(row["slot"])] = row
            for batch_id, members in layouts.items():
                card = tk.Frame(
                    self.sqlite_layout_content, bg="#0b1b2d",
                    highlightbackground="#334155", highlightthickness=1,
                    padx=8, pady=7,
                )
                card.pack(fill="x", padx=7, pady=6)
                ng_count = sum(1 for member in members.values() if member["ict_ng"] or member["fct_ng"])
                tk.Label(
                    card, text=f"母版 {batch_id} · 12 SLOTS · NG {ng_count}",
                    bg="#0b1b2d", fg="#7dd3fc", font=("Consolas", 11, "bold"),
                ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))
                for slot in range(1, 13):
                    member = members.get(slot)
                    ict_ng = bool(member and member["ict_ng"])
                    fct_ng = bool(member and member["fct_ng"])
                    result = str(member["result"] or "EMPTY").upper() if member else "EMPTY"
                    if ict_ng and fct_ng:
                        state, bg, border = "ICT+FCT NG", "#581c87", "#c084fc"
                    elif ict_ng:
                        state, bg, border = "ICT NG", "#7c2d12", "#fb923c"
                    elif fct_ng:
                        state, bg, border = "FCT NG", "#7f1d1d", "#ef4444"
                    elif result in ("PASS", "OK"):
                        state, bg, border = "PASS", "#064e3b", "#22c55e"
                    else:
                        state, bg, border = result, "#1e293b", "#475569"
                    slot_card = tk.Frame(card, bg=bg, highlightbackground=border,
                                         highlightthickness=2, width=220, height=57)
                    slot_card.grid(row=1 + (slot - 1) // 4, column=(slot - 1) % 4,
                                   sticky="nsew", padx=3, pady=3)
                    slot_card.grid_propagate(False)
                    sn = str(member["sn"] or "—") if member else "—"
                    tk.Label(slot_card, text=f"#{slot}  {state}\n{sn}", bg=bg, fg="white",
                             font=("Consolas", 9, "bold"), justify="left", anchor="w").pack(
                                 fill="both", expand=True, padx=7)
                    card.grid_columnconfigure((slot - 1) % 4, weight=1)
            self.sqlite_summary.set(
                f"母版 {board_count} · 槽位记录 {len(rows)} · {NG_DB.name}"
            )
        except Exception as exc:
            self.sqlite_summary.set(f"读取失败：{exc}")

    def _flash_merged_alarm(self):
        # Match the automatic-line depanel UI: never flash continuously.
        # Motherboards may wait in SQLite for a long time, so an MES sync is
        # not an operator alarm.  The scanned motherboard remains stable.
        self._merged_alarm_active = False
        self._merged_alarm_flash = False
        self.status_card.configure(bg="#10243b", highlightbackground="#22c55e")
        self.status_label.configure(bg="#10243b", fg="#22c55e")

    def _apply_merged_layout(self, summary):
        """Persist MES state without changing the operator's scanned view."""
        self._merged_alarm_active = False
        if int(summary["version"]) <= self._last_announced_version:
            return
        self._latest_mes_batch_id = str(summary["batchId"])
        counts = summary["counts"]
        total_ng = sum(int(value) for value in counts.values())
        if total_ng:
            self.status.set(
                f"MES已同步母板 {self._latest_mes_batch_id} · 请扫码显示 · NG {total_ng}"
            )
        else:
            self._merged_alarm_active = False
            self.status.set(
                f"MES已同步母板 {self._latest_mes_batch_id} · 请扫码显示 · 全部通过"
            )
        self._last_announced_version = int(summary["version"])

    def _keep_latest_scan(self, *_args):
        if self._normalizing_scan:
            return
        value = self.sn.get().strip().upper()
        # If the scanner appends a second 10-character SN, discard the first
        # one immediately and retain only the newest scan.
        if len(value) > 10:
            self._normalizing_scan = True
            self.sn.set(value[-10:])
            self._normalizing_scan = False

    def _disable_ime_for_scanner(self):
        """Prevent an active IME from composing keyboard-wedge scanner data."""
        if os.name != "nt":
            return
        try:
            import ctypes
            self.root.update_idletasks()
            imm32 = ctypes.windll.imm32
            user32 = ctypes.windll.user32
            for widget in (self.root, self.entry):
                imm32.ImmAssociateContext(int(widget.winfo_id()), 0)
            english = user32.LoadKeyboardLayoutW("00000409", 1)
            user32.ActivateKeyboardLayout(english, 0)
        except Exception:
            pass

    def _capture_global_scanner_key(self, event):
        """Collect scanner keystrokes from any widget and submit on Enter."""
        now = time.monotonic()
        if now - self._global_scan_last_key_at > 1.0:
            self._global_scan_buffer = ""
        self._global_scan_last_key_at = now
        if event.keysym in ("Return", "KP_Enter"):
            # A manually typed or pasted SN is already present in the Entry.
            # Prefer it over the keyboard-wedge buffer and submit exactly once.
            entry_value = self.sn.get().strip().upper()
            if valid_sn(entry_value):
                self._global_scan_buffer = ""
                self.sn.set(entry_value)
                self.submit()
                return "break"
            value = self._global_scan_buffer[-10:].upper()
            self._global_scan_buffer = ""
            if valid_sn(value):
                self.sn.set(value)
                self.submit()
                return "break"
            return None
        # Use the physical key symbol, not event.char. On production PCs a
        # Chinese/Vietnamese IME can transform scanner keystrokes into composed
        # text (for example "5G7M01631A" became Chinese characters), while the
        # key symbol remains the scanner's original A-Z/0-9 value.
        key = str(event.keysym or "").upper()
        if len(key) == 1 and key.isalnum():
            self._global_scan_buffer = (self._global_scan_buffer + key)[-10:]
        return None

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
                        tabs = {"show_sn_sqlite": 1, "show_ict_ng_sqlite": 2,
                                "show_fct_ng_sqlite": 3, "show_both_ng_sqlite": 4}
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
            except Exception:
                pass
            time.sleep(0.2)

    def heartbeat_loop(self):
        while True:
            try:
                event = {
                    "type": "AGENT_HEARTBEAT", "stationCode": STATION_CODE,
                    "eventId": "heartbeat-%s-%d" % (STATION_CODE, int(time.time() * 1000)),
                    "payload": {"agent": "depanel_scanner", "agentVersion": "3.1-heartbeat",
                                "status": "running", "sourceType": "SCANNER",
                                "scannerTcpPort": SCANNER_TCP_PORT,
                                "scannerListening": SCANNER_LISTENING,
                                "sourceConnected": True, "timestamp": int(time.time() * 1000)},
                }
                request = urllib.request.Request(
                    MES_URL, data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(request, timeout=3) as response:
                    response.read()
            except Exception:
                pass
            time.sleep(HEARTBEAT_SECONDS)

    def _start_ate_keyboard_hook(self):
        """System-wide ATE-base keyboard-wedge listener for Depanel."""
        try:
            from pynput import keyboard
        except ImportError:
            self.log("[SCANNER] pynput unavailable; global hook disabled")
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
        self.sn.set(sn)
        self.submit()

    def scanner_tcp_loop(self):
        global SCANNER_LISTENING
        while True:
            server = None
            try:
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(("0.0.0.0", SCANNER_TCP_PORT))
                server.listen(5)
                server.settimeout(1.0)
                SCANNER_LISTENING = True
                while True:
                    try:
                        client, _address = server.accept()
                    except socket.timeout:
                        continue
                    with client:
                        raw = client.recv(4096).decode("utf-8", errors="ignore")
                        compact = "".join(ch for ch in raw.upper() if ch.isalnum())
                        sn = compact[-10:] if len(compact) >= 10 else compact
                        if valid_sn(sn):
                            self.root.after(
                                0, lambda value=sn: (
                                    self.sn.set(value), self.submit()
                                )
                            )
                            client.sendall(b"OK\r\n")
                        else:
                            client.sendall(b"INVALID\r\n")
            except Exception:
                SCANNER_LISTENING = False
                time.sleep(2)
            finally:
                SCANNER_LISTENING = False
                if server is not None:
                    try:
                        server.close()
                    except Exception:
                        pass

    def refresh_tables(self):
        try:
            with sqlite3.connect(str(SN_DB)) as conn:
                sns = conn.execute("SELECT sn,first_scanned_at,last_scanned_at,scan_count FROM all_sns ORDER BY last_scanned_at DESC LIMIT 1000").fetchall()
            with sqlite3.connect(str(NG_DB)) as conn:
                ngs = conn.execute("""SELECT sn,source_station,batch_id,status,detected_at,picked_at,ict_ng,fct_ng
                    FROM confirmed_ng WHERE status IN ('waiting','picked')
                    ORDER BY detected_at DESC LIMIT 1000""").fetchall()
                # MES synchronization updates SQLite only. The motherboard
                # canvas remains blank/current until the operator scans an SN.
                latest_batch = ((self.selected_batch_id,)
                                if self.selected_batch_id else None)
                motherboard = conn.execute(
                    "SELECT slot,sn,result,ict_ng,fct_ng FROM motherboard_members WHERE batch_id=? ORDER BY slot",
                    (latest_batch[0],),
                ).fetchall() if latest_batch else []
                motherboard_version = conn.execute(
                    "SELECT COUNT(*),COALESCE(MAX(received_at),0) FROM motherboard_members"
                ).fetchone()
            # Polling is only for detecting new SQLite records. Rebuilding the
            # Tk widgets with identical data causes visible flashing, so leave
            # the current operator view completely untouched until the local
            # data snapshot actually changes.
            sqlite_view_signature = (
                tuple(sns),
                tuple(ngs),
                latest_batch[0] if latest_batch else "",
                tuple(motherboard),
                tuple(motherboard_version),
            )
            if sqlite_view_signature == self._last_sqlite_view_signature:
                return
            self._last_sqlite_view_signature = sqlite_view_signature
            self.sn_tree.delete(*self.sn_tree.get_children())
            for tree in self.ng_trees: tree.delete(*tree.get_children())
            for row in sns: self.sn_tree.insert("","end",values=row)
            counts = [0, 0, 0]
            for row in ngs:
                category = 2 if row[6] and row[7] else (0 if row[6] else 1)
                self.ng_trees[category].insert("","end",values=row[:6])
                if row[3] in ("waiting", "picked"): counts[category] += 1
            for index, value in enumerate(counts):
                self.box_count_vars[index].set(str(value))
                if index < len(self.product_box_canvases):
                    canvas, count_item = self.product_box_canvases[index]
                    canvas.itemconfigure(count_item, text=str(value))
            self.count_var.set(f"扫描 {len(sns)} | ICT NG {counts[0]} | FCT NG {counts[1]} | ICT+FCT NG {counts[2]}")
            handover_url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=manu_depanel")
            with urllib.request.urlopen(handover_url, timeout=5) as response:
                handovers = json.loads(response.read().decode("utf-8")).get("items", [])
            self.handover_tree.delete(*self.handover_tree.get_children())
            for row in handovers:
                self.handover_tree.insert("","end",values=(row.get("transferId",""),row.get("batchId",""),
                    row.get("sourceStation",""),row.get("destinationStation",""),row.get("memberCount",""),
                    row.get("status",""),row.get("sentAt",""),row.get("receivedAt",""),row.get("acceptedBy","")))
            residence_url = MES_URL.replace("/api/pda/events", "/api/station/residence-stats?stationCode=manu_depanel")
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

    def refresh_motherboard_boxes(self):
        """Render every local motherboard as a compact 12-slot structure."""
        with sqlite3.connect(str(NG_DB)) as conn:
            rows = conn.execute(
                """SELECT batch_id,slot,sn,result,ict_ng,fct_ng,received_at
                     FROM motherboard_members
                    ORDER BY received_at DESC,batch_id DESC,slot"""
            ).fetchall()
        grouped = {}
        for row in rows:
            grouped.setdefault(str(row[0]), []).append(row)
        for tree in self.ng_trees:
            tree.delete(*tree.get_children())
        category_counts = [0, 0, 0]
        for batch_id, members in grouped.items():
            members = sorted(members, key=lambda row: int(row[1] or 0))
            categories = set()
            tokens = []
            newest = 0
            for _batch, slot, sn, result, ict_ng, fct_ng, received_at in members:
                newest = max(newest, int(received_at or 0))
                if ict_ng and fct_ng:
                    mark = "BOTH"
                    categories.add(2)
                    category_counts[2] += 1
                elif ict_ng:
                    mark = "ICT"
                    categories.add(0)
                    category_counts[0] += 1
                elif fct_ng:
                    mark = "FCT"
                    categories.add(1)
                    category_counts[1] += 1
                else:
                    mark = "OK"
                tokens.append(f"{int(slot):02d}:{str(sn)[-6:]}:{mark}")
            if not categories:
                continue
            layout = " | ".join(tokens)
            synced = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(newest / 1000))
                if newest else ""
            )
            for category in categories:
                ng_count = sum(
                    1 for row in members
                    if (
                        (category == 0 and row[4] and not row[5])
                        or (category == 1 and row[5] and not row[4])
                        or (category == 2 and row[4] and row[5])
                    )
                )
                values = ("", "", batch_id, "", "", "", layout, ng_count, synced)
                self.ng_trees[category].insert("", "end", values=values)
        for index, value in enumerate(category_counts):
            self.box_count_vars[index].set(str(value))
            if index < len(self.product_box_canvases):
                canvas, count_item = self.product_box_canvases[index]
                canvas.itemconfigure(count_item, text=str(value))

    def _render_motherboard(self, batch_id, members):
        self.current_motherboard.set(
            str(batch_id) if batch_id else "等待扫码 / WAITING FOR SCAN"
        )
        self.motherboard_title.set(
            f"母版结构：{batch_id} · 12 SLOTS · ICT/FCT 最终状态" if batch_id
            else "等待母版扫码 / WAITING FOR MOTHERBOARD"
        )
        by_slot = {int(row[0]): row for row in members}
        for slot in range(1, 13):
            row = by_slot.get(slot)
            if not row:
                text, color, border = f"槽位 {slot} / SLOT {slot}\n—\nWAIT", "#334155", "#64748b"
            else:
                _slot, sn, result, ict_ng, fct_ng = row
                marks = " + ".join(label for enabled, label in ((ict_ng, "ICT NG"), (fct_ng, "FCT NG")) if enabled) or "PASS"
                color = "#581c87" if ict_ng and fct_ng else ("#9a3412" if ict_ng else ("#991b1b" if fct_ng else "#065f46"))
                border = "#c084fc" if ict_ng and fct_ng else ("#fb923c" if ict_ng else ("#ef4444" if fct_ng else "#10b981"))
                text = f"槽位 {slot} / SLOT {slot}\n{sn}\n{marks}"
            frame = self.board_slot_frames[slot - 1]
            frame.configure(bg=color, highlightbackground=border)
            for child in frame.winfo_children(): child.configure(bg=color, fg="white")
            self.board_slot_vars[slot - 1].set(text)

    def _refresh_ng_boxes_for_search(self):
        """Refresh the three NG boxes only as part of an explicit SN search."""
        with sqlite3.connect(str(NG_DB)) as conn:
            ngs = conn.execute(
                """SELECT sn,source_station,batch_id,status,detected_at,picked_at,
                          ict_ng,fct_ng
                     FROM confirmed_ng
                    WHERE status IN ('waiting','picked')
                    ORDER BY detected_at DESC LIMIT 200"""
            ).fetchall()
        for tree in self.ng_trees:
            tree.delete(*tree.get_children())
        counts = [0, 0, 0]
        for row in ngs:
            category = 2 if row[6] and row[7] else (0 if row[6] else 1)
            self.ng_trees[category].insert("", "end", values=row[:6])
            counts[category] += 1
        for index, value in enumerate(counts):
            self.box_count_vars[index].set(str(value))
            canvas, count_item = self.product_box_canvases[index]
            canvas.itemconfigure(count_item, text=str(value))

    def submit(self, _event=None):
        sn = self.sn.get().strip().upper()
        self._last_scan_value = sn
        self._last_scan_time = time.monotonic()
        # Keep the last scanned SN visible for the operator. The StringVar
        # trace replaces it automatically when the scanner sends the next SN.
        self.sn.set(sn)
        self.raw_tree.insert("",0,values=(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"SCANNER","USB/TCP",sn,"RECEIVED",sn))
        children=self.raw_tree.get_children()
        if len(children)>1000:self.raw_tree.delete(*children[1000:])
        if not valid_sn(sn):
            return
        if False and ARRIVAL_STORE is not None:
            try:
                arrival = ARRIVAL_STORE.record_arrival(sn, "SCANNER", "USB/TCP")
            except ArrivalError as exc:
                message = f"ARRIVAL BLOCKED / 到达拦截: {exc}"
                self.status.set(message)
                self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] [ARRIVAL] {message}\n")
                self.log_box.see("end")
                speak("到达校验失败")
                self.entry.focus_set()
                return
            if not arrival.get("sequence_valid", True):
                message = f"SEQUENCE JUMP / 站点跳跃: {arrival.get('sequence_detail', '')}"
                self.status.set(message)
                self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] [ARRIVAL] {message}\n")
                self.log_box.see("end")
                speak("站点跳跃，禁止继续")
                self.entry.focus_set()
                return
        # Scanning never registers or mutates a production SN. MES is the
        # Local SQLite is the fast scan path. MES is confirmation/fallback only;
        # never block the operator's keyboard event on a network lookup.
        try:
            row = None
            mes_lookup_error = ""
            # The background MES/local mirror already owns synchronization.
            # Never retry SQLite reads on the Tk event thread: one scan must
            # paint immediately instead of waiting through five 200 ms sleeps.
            for attempt in range(1, 2):
                with sqlite3.connect(str(NG_DB)) as conn:
                    row = conn.execute(
                        """SELECT m.batch_id,m.slot,m.sn,m.result,m.ict_ng,m.fct_ng,
                                  COALESCE(c.status,'') AS ng_status
                           FROM motherboard_members m
                           LEFT JOIN confirmed_ng c ON c.sn=m.sn
                           WHERE m.sn=?
                           ORDER BY m.received_at DESC LIMIT 1""",
                        (sn,),
                    ).fetchone()
                if row:
                    break
            if not row:
                # Do not block the Tk event thread on MES. The local database
                # has already been checked across newest and older records;
                # confirm remotely in the background and let the next local
                # refresh/scan display any returned record.
                threading.Thread(
                    target=self._confirm_missing_scan_in_mes,
                    args=(sn,),
                    daemon=True,
                    name="manual-depanel-mes-confirm",
                ).start()
            with sqlite3.connect(str(NG_DB)) as conn:
                if not row:
                    ng_only = conn.execute(
                        """SELECT sn,source_station,ict_ng,fct_ng,status
                           FROM confirmed_ng WHERE sn=? LIMIT 1""",
                        (sn,),
                    ).fetchone()
                    if ng_only:
                        source = "ICT+FCT" if ng_only[2] and ng_only[3] else ("ICT" if ng_only[2] else "FCT")
                        message = f"SN {sn} · {source} NG · 状态 {ng_only[4]} · 未找到母板槽位"
                    else:
                        message = f"SN {sn} · 本地 SQLite 无记录"
                    self.status.set(message)
                    self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] [只读查询] {message}\n")
                    self.log_box.see("end")
                    speak("未找到")
                    # A failed scan does not switch to an unscanned MES board.
                    # Keep the current operator-selected display unchanged.
                    self.entry.focus_set()
                    return
                batch_id, slot, board_sn, result, ict_ng, fct_ng, ng_status = row
                members = conn.execute(
                    """SELECT slot,sn,result,ict_ng,fct_ng
                       FROM motherboard_members
                       WHERE batch_id=? ORDER BY slot""",
                    (batch_id,),
                ).fetchall()
            self.selected_batch_id = str(batch_id)
            ng_type = "ICT+FCT NG" if ict_ng and fct_ng else ("ICT NG" if ict_ng else ("FCT NG" if fct_ng else "PASS"))
            self._render_motherboard(str(batch_id), members)
            # Defer the table redraw so the scan/merge result is committed to
            # the visible motherboard immediately, even with a large NG list.
            self.root.after(0, self._refresh_ng_boxes_for_search)
            if ARRIVAL_STORE is not None:
                threading.Thread(
                    target=self._record_arrival_background,
                    args=(sn,), daemon=True, name="manual-depanel-arrival-mes"
                ).start()
            ng_members = [item for item in members if item[3] or item[4]]
            self.pending_repair_batch = str(batch_id)
            self.pending_repair_members = list(ng_members)
            ng_count = sum(1 for item in members if item[3] or item[4])
            message = (
                f"SN {board_sn} · 母板 {batch_id} · 槽位 {slot} · {ng_type} · "
                f"整板 {len(members)} 槽 / NG {ng_count}"
            )
            self.status.set(message)
            self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] [只读查询] {message}\n")
            self.log_box.see("end")
            speak("NG" if ng_count else "全部通过")
        except Exception as exc:
            self.status.set(f"本地查询失败 / LOOKUP FAILED: {exc}")
        self.entry.focus_set()
        return

    def _record_arrival_background(self, sn):
        try:
            ARRIVAL_STORE.record_arrival(sn, "SCANNER", "USB/TCP")
        except Exception as exc:
            self.root.after(0, lambda: self.log_box.insert(
                "end", f"[{datetime.now():%H:%M:%S}] [ARRIVAL/MES background] {exc}\n"
            ))

    def _confirm_missing_scan_in_mes(self, sn):
        """Confirm a locally missing SN without delaying the scan display."""
        try:
            fetch_motherboard_from_mes(sn)
            self.root.after(0, lambda: self.log_box.insert(
                "end", f"[{datetime.now():%H:%M:%S}] MES confirmation completed for {sn}; local cache updated.\n"
            ))
        except Exception as exc:
            self.root.after(0, lambda: self.log_box.insert(
                "end", f"[{datetime.now():%H:%M:%S}] MES confirmation pending for {sn}: {exc}\n"
            ))

        # Identify an NG scan, but do not stop motherboard lookup. At depanel
        # this information is exactly what the operator needs to pick the bad
        # daughterboard out of the physical panel.
        scanned_ng = None
        with sqlite3.connect(str(NG_DB)) as conn_ng:
            ng_row = conn_ng.execute(
                """SELECT sn, source_station, ict_ng, fct_ng FROM confirmed_ng
                   WHERE sn=? AND status IN ('waiting','picked') LIMIT 1""",
                (sn,),
            ).fetchone()
            if not ng_row:
                # MES ng-guard 表使用 sourceStationCode 区分 ICT/FCT，没有 ict_ng/fct_ng 列
                mes_guard = conn_ng.execute(
                    "SELECT sn, source_station FROM mes_confirmed_ng_guard WHERE sn=? LIMIT 1",
                    (sn,),
                ).fetchone()
                if mes_guard:
                    # 将 sourceStationCode 转换为 ict_ng/fct_ng 标志
                    src = mes_guard[1] or ''
                    ict = 1 if 'ict' in src.lower() else 0
                    fct = 1 if 'fct' in src.lower() else 0
                    ng_row = (mes_guard[0], src, ict, fct)
            if ng_row and (ng_row[2] or ng_row[3]):   # ict_ng or fct_ng
                src = ng_row[1]
                if not src:
                    src = ('ICT' if ng_row[2] else '') + ('和FCT' if (ng_row[2] and ng_row[3]) else ('FCT' if ng_row[3] else ''))
                scanned_ng = src
                self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] [NG识别] {sn} — 来源 {src}\n")
                self.log_box.see("end")
        try:
            with sqlite3.connect(str(NG_DB)) as conn:
                batch = conn.execute(
                    """SELECT batch_id FROM motherboard_members
                       WHERE sn=?
                       ORDER BY received_at DESC LIMIT 1""", (sn,)
                ).fetchone()
                if not batch:
                    try:
                        batch = (fetch_motherboard_from_mes(sn),)
                    except Exception as exc:
                        self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] MES identity lookup failed: {exc}\n")
                if not batch:
                    self.status.set(f"未找到该板所属FCT母板：{sn}")
                    speak("没有找到该板所属母板")
                    return
                batch_id = str(batch[0])
                self.selected_batch_id = batch_id
                members = conn.execute(
                    "SELECT slot,sn,result,ict_ng,fct_ng FROM motherboard_members WHERE batch_id=? ORDER BY slot",
                    (batch_id,),
                ).fetchall()
                ng_members = [row for row in members if row[3] or row[4]]
            self._render_motherboard(batch_id, members)
            self.pending_repair_batch = batch_id
            self.pending_repair_members = list(ng_members)
            self.status.set(f"已显示母板 {batch_id} · {len(members)}槽 · NG {len(ng_members)} · 扫码仅查询")
            layout = "，".join(
                f"槽位{row[0]}，{'ICT和FCT不良' if row[3] and row[4] else ('ICT不良' if row[3] else 'FCT不良')}"
                for row in ng_members
            )
            message = f"已识别母板 {batch_id}，NG {len(ng_members)}片"
            self.status.set(message)
            self.log_box.insert("end", f"[{datetime.now():%H:%M:%S}] {message}\n")
            self.log_box.see("end")
            if scanned_ng:
                speak(f"扫描板为{scanned_ng}不良。已识别母板，{layout}，请直接挑出不良品")
            else:
                speak(f"已识别母板，{layout}，请直接挑出不良品" if layout else "已识别母板，本盘没有不良品")
            self.refresh_tables()
        except Exception as exc:
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
                 WHERE c.status IN ('waiting','picked')
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
        queued_sns = []
        try:
            for parent_batch, slot, ng_sn, first_detected_at, _result, ict_ng, fct_ng in staged:
                first_detected_at = int(first_detected_at or sent_at)
                category = "ICT_FCT_NG" if ict_ng and fct_ng else ("ICT_ONLY_NG" if ict_ng else "FCT_ONLY_NG")
                return_stations = (["manu_ict", "manu_fct"] if ict_ng and fct_ng
                                   else ["manu_ict"] if ict_ng else ["manu_fct"])
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
                        "clickedAt": sent_at,
                        "eventId": f"{transfer_batch_id}:{ng_sn}"}
                request = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        created.append(json.loads(response.read().decode("utf-8")))
                except Exception as exc:
                    queue_maintenance_handover(body, str(exc))
                    queued_sns.append(ng_sn)
                    self.log_box.insert("end", f"[MES OFFLINE] queued handover {body['eventId']}\\n")
            with sqlite3.connect(str(NG_DB)) as conn:
                sns = [str(row[2]) for row in staged if str(row[2]).upper() not in set(queued_sns)]
                placeholders = ",".join("?" for _ in sns)
                if sns:
                    conn.execute(f"UPDATE confirmed_ng SET status='waiting_repair_receipt' WHERE sn IN ({placeholders})", sns)
            self.status.set(
                f"{confirmer_role} {confirmer_id} 已确认发送 {len(created)} 个NG；"
                "等待维修站15分钟内扫码接收"
            )
            speak(f"已生成{len(created)}个维修工单，请送往回修站，等待扫码接收")
            self.pending_repair_batch = ""; self.pending_repair_members = []
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
    threading.Thread(target=maintenance_handover_outbox_worker, daemon=True,
                     name="maintenance-handover-outbox").start()
    app = tk.Tk()
    if os.environ.get("DEPANEL_EMBEDDED_ENGINE") == "1": app.withdraw()
    scanner = DepanelScanner(app)
    install_station_retest_panel(app, STATION_CODE, MES_URL.replace('/pda/events',''), test_station=False, announcer=speak)
    from motherboard_search import install_motherboard_search
    motherboard_browser = install_motherboard_search(app, MES_URL, "manual")
    # Keep the standard repair component visible for history, SLA and MES
    # supervision. Its generic dispatch action is locked by station policy;
    # the three physical NG boxes above remain the single dispatch entry.
    # Repair workflow performs synchronous MES reads during construction.
    # Defer it so the depanel visualization and scanner open immediately.
    def _install_repair_panel_later():
        try:
            install_repair_workflow(app, STATION_CODE, MES_URL, "PCBA分板")
        except Exception as exc:
            scanner.log(f"[REPAIR] deferred panel unavailable: {exc}")
    app.after(5000, _install_repair_panel_later)
    app.mainloop()
