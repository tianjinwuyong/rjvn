# -*- coding: utf-8 -*-
"""
Manual Line ICT Agent  —  CSV primary, Scanner auxiliary
- CSV PASS/FAIL 是数据源
- Scanner 只是操作员手动确认，不查重，不管重复
- NG 全生命周期 SSE 实时推送
- confirmed NG 额外 POST MES（统计用）

MES target: http://192.168.6.155:8080/api/pda/events
Runs on: 192.168.6.91 (ICT工站电脑)
"""
import os, sys, json, time, threading, socket, queue, sqlite3, subprocess, re, csv, random, uuid

def log(message):
    # Early-startup logger; the full station logger is installed below.
    print(str(message), flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AUTO_COMMON_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "002-自动线"))
if os.path.isdir(_AUTO_COMMON_DIR) and _AUTO_COMMON_DIR not in sys.path:
    sys.path.insert(0, _AUTO_COMMON_DIR)
# ICT uses the proven ATE-base hook below; avoid a second Common Agent hook.
os.environ.setdefault("STATION_DISABLE_COMMON_SCANNER", "1")
from station_common_bootstrap import attach_common_agent
COMMON_AGENT = attach_common_agent("manu_ict", __file__, "ict")
from datetime import datetime
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from station_resource_viewer import build_resource_view, render_resource_view
try:
    from station_ui_primitives import register_scanner_entry
except ImportError:
    register_scanner_entry = None

# ── Voice (TTS) ─────────────────────────────────────────────────────────
_voice_lock = threading.Lock()


def speak(text):
    """Windows TTS via PowerShell - thread-safe, works with Chinese."""
    def _do():
        try:
            import subprocess
            import codecs
            # Use -EncodedCommand to avoid all encoding/escaping issues
            cmd_bytes = f'Add-Type -AssemblyName System.Speech; $tts = New-Object System.Speech.Synthesis.SpeechSynthesizer; $tts.Speak("{text}")'
            import base64
            encoded = base64.b64encode(cmd_bytes.encode('utf-16le')).decode('ascii')
            subprocess.Popen(['powershell', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-EncodedCommand', encoded],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        except Exception as e:
            log(f"[TTS] error: {e}")
    threading.Thread(target=_do, daemon=True).start()


def speak_ng(slot):
    """Speak NG alert: '发现不良品，第{n}个槽位'"""
    speak(f"发现不良品，第{slot}个槽位")

# ── Station config ─────────────────────────────────────────────────────
STATION_CODE = "manu_ict"
SCRAP_REASONS = {
    "S01": "PCB断裂、缺角或严重变形", "S02": "PCB烧焦、碳化、分层或起泡",
    "S03": "焊盘、线路或金手指严重脱落", "S04": "关键元器件损坏且无法更换",
    "S05": "连接器、端子或接口不可修复", "S06": "外壳破裂、残缺或尺寸严重超差",
    "S07": "进水、腐蚀或严重污染", "S08": "高压、绝缘等安全缺陷不可修复",
    "S09": "多次维修或复测仍不合格", "S10": "已用完规定复测机会且无维修价值",
    "S11": "维修成本超过允许标准", "S12": "SN、板码或产品身份无法追溯",
    "S13": "工艺异常导致无法进入后续工序", "S14": "存在不可接受的可靠性风险",
    "S15": "工程变更、客户要求或质量指令报废", "S16": "人为破坏",
    "S17": "操作不当", "S18": "测试设备不良", "S19": "机械撞击", "S99": "其他原因",
}
STATION_LABEL = "手动线-ICT测试"
# Keep deployment settings beside the EXE. In a PyInstaller one-file build,
# __file__ points to a temporary extraction folder and must not hold the DB.
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "ict_config.json")
_DEFAULT_CONFIG = {
    "mes_url": "http://192.168.6.155:8080/api/pda/events",
    "watch_dir": r"D:\SRC",
    "scanner_tcp_port": 1003,
    "enable_simulator": False,
    "confirm_after_fail_count": 3,
}
try:
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as _config_file:
        _station_config = dict(_DEFAULT_CONFIG, **json.load(_config_file))
except FileNotFoundError:
    _station_config = dict(_DEFAULT_CONFIG)
except Exception as _config_error:
    print(f"[CONFIG] Cannot read {CONFIG_PATH}: {_config_error}; using defaults")
    _station_config = dict(_DEFAULT_CONFIG)

MES_URL = os.environ.get("MES_API_URL", str(_station_config["mes_url"])).strip()
WATCH_DIR = os.environ.get("ICT_WATCH_DIR", str(_station_config["watch_dir"])).strip()
TCP_PORT = int(os.environ.get("ICT_SCANNER_TCP_PORT", _station_config["scanner_tcp_port"]))
ENABLE_SIMULATOR = bool(_station_config.get("enable_simulator", False))
CONFIRM_AFTER_FAIL_COUNT = max(1, int(_station_config.get("confirm_after_fail_count", 1)))
APP_VERSION = "2026.07.18-safety1"

# ── NG tuning ──────────────────────────────────────────────────────────
MAX_RETEST = max(0, CONFIRM_AFTER_FAIL_COUNT - 1)
AGING_HOURS = 2       # ≥2h no PASS → Aged NG

# ── NG tracking ────────────────────────────────────────────────────────
# {sn: {firstFailTime, testCount}}
_ng_tracking = {}

# ── SQLite ──────────────────────────────────────────────────────────────
NG_DB = os.path.join(APP_DIR, "ict_ng.db")

sys.path.insert(0, os.path.dirname(APP_DIR))
_AUTO_COMMON_DIR = os.path.abspath(os.path.join(APP_DIR, "..", "..", "002-自动线"))
if os.path.isdir(_AUTO_COMMON_DIR) and _AUTO_COMMON_DIR not in sys.path:
    sys.path.insert(0, _AUTO_COMMON_DIR)

try:
    from station_data_sync import reconcile_inventory, mes_scan_gate
except ImportError:
    def reconcile_inventory(*a, **k): pass
    class _DummyGate:
        def get(self, *a, **k): return None
    mes_scan_gate = _DummyGate()

try:
    from station_runtime_safety import wait_file_stable, run_diagnostics
except ImportError:
    def wait_file_stable(*a, **k): return True
    def run_diagnostics(*a, **k): return {}

def _inventory_reconcile_worker():
    while True:
        try:
            with sqlite3.connect(NG_DB) as conn:
                sn_rows = conn.execute(
                    "SELECT sn,scan_time,batch_id,slot,result FROM all_sns WHERE sn IS NOT NULL ORDER BY scan_time,sn"
                ).fetchall()
                batch_rows = conn.execute(
                    "SELECT sn_obj FROM ng_batches WHERE sn_obj IS NOT NULL ORDER BY created_at,batch_id"
                ).fetchall()
                sns = [{"sn": row[0], "testTime": row[1], "batchId": row[2],
                        "slot": row[3], "result": row[4]} for row in sn_rows]
                passed = [{"sn": row[0], "time": row[1], "batchId": row[2],
                           "slot": row[3], "result": row[4]} for row in sn_rows
                          if str(row[4] or "").upper() == "PASS"]
                pending, confirmed = [], []
                for (raw,) in batch_rows:
                    try:
                        motherboard = json.loads(raw)
                    except Exception:
                        continue
                    failed = [board for board in motherboard.get("subBoards", [])
                              if str(board.get("result", "")).upper() == "FAIL"]
                    if not failed:
                        continue
                    if any(bool(board.get("isConfirmedNG")) for board in failed):
                        confirmed.append(motherboard)
                    else:
                        pending.append(motherboard)
            version = int(time.time() * 1000)
            reconcile_inventory(MES_URL, STATION_CODE, "sn_records", sns, version, "sn")
            base = MES_URL.replace("/api/pda/events", "").rstrip("/")
            snapshots = {
                "pending_ng": pending,
                "confirmed_ng": confirmed,
                "pass": passed,
                "stats": [{"pass": len(passed), "ng": len(pending),
                           "confirmedNg": len(confirmed), "dup": 0,
                           "updatedAt": version}],
            }
            for bucket_name, payload in snapshots.items():
                body = json.dumps({"payload": payload}, ensure_ascii=False).encode("utf-8")
                request = urllib.request.Request(
                    f"{base}/api/station/bucket-snapshots/{STATION_CODE}/{bucket_name}",
                    data=body, method="PUT", headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=8) as response:
                    response.read()
        except Exception as exc:
            log(f"[INVENTORY] reconcile deferred: {exc}")
        time.sleep(60)

def init_ng_db():
    """Create tables if not exist. Handles first-time and migration."""
    with sqlite3.connect(NG_DB) as conn:
        # NG batches - summary of each test batch
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ng_batches (
                batch_id   TEXT PRIMARY KEY,
                main_sn    TEXT,
                sn_obj     TEXT,
                batch_start INTEGER,
                created_at INTEGER,
                member_count INTEGER DEFAULT 12,
                ng_count INTEGER DEFAULT 0,
                overall_result TEXT,
                last_test_time INTEGER
            )
        """)
        for column_sql in (
            "ALTER TABLE ng_batches ADD COLUMN member_count INTEGER DEFAULT 12",
            "ALTER TABLE ng_batches ADD COLUMN ng_count INTEGER DEFAULT 0",
            "ALTER TABLE ng_batches ADD COLUMN overall_result TEXT",
            "ALTER TABLE ng_batches ADD COLUMN last_test_time INTEGER",
        ):
            try:
                conn.execute(column_sql)
            except sqlite3.OperationalError:
                pass

        # NG boards - each slot's test results (never deleted)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ng_boards (
                batch_id       TEXT,
                slot           INTEGER,
                sn             TEXT,
                result_1       TEXT,
                result_2       TEXT,
                result_3       TEXT,
                final_result   TEXT,
                repair_result  TEXT,
                test_count     INTEGER,
                retest_remaining INTEGER,
                is_confirmed   INTEGER,
                test_time_1    INTEGER,
                test_time_2    INTEGER,
                test_time_3    INTEGER,
                last_test_time INTEGER,
                PRIMARY KEY (batch_id, slot)
            )
        """)

        # Migration: add new columns if they don't exist
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN result_1 TEXT")
            log("[DB] Migrated: added result_1 column")
        except:
            pass
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN result_2 TEXT")
            log("[DB] Migrated: added result_2 column")
        except:
            pass
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN result_3 TEXT")
            log("[DB] Migrated: added result_3 column")
        except:
            pass
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN final_result TEXT")
            log("[DB] Migrated: added final_result column")
        except:
            pass
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN repair_result TEXT")
            log("[DB] Migrated: added repair_result column")
        except:
            pass
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN test_time_1 INTEGER")
            log("[DB] Migrated: added test_time_1 column")
        except:
            pass
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN test_time_2 INTEGER")
            log("[DB] Migrated: added test_time_2 column")
        except:
            pass
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN test_time_3 INTEGER")
            log("[DB] Migrated: added test_time_3 column")
        except:
            pass
        try:
            conn.execute("ALTER TABLE ng_boards ADD COLUMN last_test_time INTEGER")
        except:
            pass

        # All SNs - for duplicate SN detection
        conn.execute("""
            CREATE TABLE IF NOT EXISTS all_sns (
                sn         TEXT,
                scan_time  INTEGER,
                batch_id   TEXT,
                slot       INTEGER,
                result     TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sn_time ON all_sns(sn, scan_time)")

        # Maintenance NG - confirmed NG boards (after 2 retests fail)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_ng (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id        TEXT,
                main_sn         TEXT,
                slot            INTEGER,
                sn              TEXT,
                confirm_time    INTEGER,
                status          TEXT DEFAULT 'pending'
            )
        """)

        # Aged NG - batches > 2 hours old without retest
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aged_ng (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id        TEXT,
                main_sn         TEXT,
                aged_time       INTEGER,
                status          TEXT DEFAULT 'pending'
            )
        """)
        conn.execute("""CREATE TABLE IF NOT EXISTS mes_event_outbox (
            event_id TEXT PRIMARY KEY, event_json TEXT NOT NULL,
            created_at INTEGER NOT NULL, retry_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT, last_attempt INTEGER, status TEXT NOT NULL DEFAULT 'PENDING')""")
        # Local, append-only repair WO projection. MES remains authoritative
        # for status; this table preserves the latest received status while
        # offline and supports history/Outbox inspection at the station.
        conn.execute("""CREATE TABLE IF NOT EXISTS repair_work_orders (
            repair_wo_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL UNIQUE,
            sn TEXT NOT NULL,
            source_station TEXT NOT NULL,
            destination_station TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            mes_status TEXT NOT NULL,
            status_source TEXT NOT NULL DEFAULT 'MES',
            manager_notice TEXT,
            issued_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            raw_json TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_repair_wo_status ON repair_work_orders(mes_status, updated_at)")

def seed_preview_repair_work_orders():
    """Seed the authorized 3-NG preview into local SQLite only."""
    if os.environ.get("ICT_CREATE_SIM_MOTHERBOARD") != "1":
        return
    now = int(time.time() * 1000)
    rows = []
    for index in (2, 5, 8):
        payload = {
            "repairWoId": f"SIM-RW-{index:03d}",
            "eventId": f"SIM-EVENT-{index:03d}",
            "sn": f"SIM-MB-{index:03d}",
            "sourceStation": STATION_CODE,
            "destinationStation": "repair_station",
            "quantity": 1,
            "mesStatus": "WAITING_REPAIR",
            "statusSource": "MES",
            "managerNotice": "PENDING_PICKUP_ACK",
            "issuedAt": now,
            "updatedAt": now,
        }
        rows.append((payload["repairWoId"], payload["eventId"], payload["sn"],
                     payload["sourceStation"], payload["destinationStation"],
                     payload["quantity"], payload["mesStatus"], payload["statusSource"],
                     payload["managerNotice"], now, now, json.dumps(payload, ensure_ascii=False)))
    with sqlite3.connect(NG_DB) as conn:
        conn.executemany("""INSERT OR REPLACE INTO repair_work_orders
            (repair_wo_id, event_id, sn, source_station, destination_station,
             quantity, mes_status, status_source, manager_notice, issued_at,
             updated_at, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", rows)
    log("[DB] Seeded 3 isolated preview repair WOs; MES status is authoritative")

def save_ng_batch(sn_obj, batch_start_ms):
    """Persist a NG batch to SQLite - tracks full test lifecycle."""
    members = list(sn_obj.get("subBoards", []))
    if not members:
        raise ValueError("NG motherboard has no members")
    ng_count = sum(1 for board in members if str(board.get("result", "")).upper() == "FAIL")
    if ng_count <= 0:
        return
    with sqlite3.connect(NG_DB) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO ng_batches
            (batch_id, main_sn, sn_obj, batch_start, created_at, member_count, ng_count, overall_result, last_test_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sn_obj["batchId"], sn_obj["mainSn"],
              json.dumps(sn_obj, ensure_ascii=False),
              batch_start_ms, int(time.time() * 1000), len(members), ng_count,
              sn_obj.get("overallResult", "FAIL"),
              max((max(board.get("testTimes", []) or [0]) for board in members), default=0)))
        # Save ALL subBoards (PASS and FAIL) to preserve full test history
        for b in members:
            # Get all test results and timestamps for this slot
            results = b.get("results", [])  # list of results in order
            test_times = b.get("testTimes", [])  # list of timestamps in order
            result_1 = results[0] if len(results) > 0 else None
            result_2 = results[1] if len(results) > 1 else None
            result_3 = results[2] if len(results) > 2 else None
            test_time_1 = test_times[0] if len(test_times) > 0 else None
            test_time_2 = test_times[1] if len(test_times) > 1 else None
            test_time_3 = test_times[2] if len(test_times) > 2 else None
            final_result = b.get("result")
            is_confirmed = 1 if b.get("isConfirmedNG") else 0

            conn.execute("""
                INSERT OR REPLACE INTO ng_boards
                (batch_id, slot, sn, result_1, result_2, result_3, final_result,
                 test_count, retest_remaining, is_confirmed,
                 test_time_1, test_time_2, test_time_3, last_test_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sn_obj["batchId"], b["slot"], b["sn"],
                  result_1, result_2, result_3, final_result,
                  b.get("testCount", 1), b.get("retestRemaining", 0),
                  is_confirmed,
                  test_time_1, test_time_2, test_time_3,
                  max(test_times) if test_times else None))

def remove_ng_batch(batch_id):
    """Delete a NG batch from SQLite (after aged or confirmed-pass)."""
    with sqlite3.connect(NG_DB) as conn:
        conn.execute("DELETE FROM ng_boards WHERE batch_id = ?", (batch_id,))
        conn.execute("DELETE FROM ng_batches WHERE batch_id = ?", (batch_id,))

def save_confirmed_ng(main_sn, batch_id, slot, sn):
    """Save confirmed NG board to maintenance table."""
    with sqlite3.connect(NG_DB) as conn:
        conn.execute("""
            INSERT INTO maintenance_ng (batch_id, main_sn, slot, sn, confirm_time, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (batch_id, main_sn, slot, sn, int(time.time() * 1000)))
        log(f"[MAINT] Confirmed NG: {sn} slot {slot}")

def update_repair_result(batch_id, slot, repair_result):
    """Update repair result for a slot after maintenance."""
    with sqlite3.connect(NG_DB) as conn:
        conn.execute("""
            UPDATE ng_boards SET repair_result = ? WHERE batch_id = ? AND slot = ?
        """, (repair_result, batch_id, slot))
        conn.execute("""
            UPDATE maintenance_ng SET status = ? WHERE batch_id = ? AND slot = ?
        """, (repair_result, batch_id, slot))
        log(f"[REPAIR] Updated: batch={batch_id} slot={slot} result={repair_result}")

def save_aged_ng(batch_id, main_sn):
    """Save aged NG batch to aged_ng table."""
    with sqlite3.connect(NG_DB) as conn:
        conn.execute("""
            INSERT INTO aged_ng (batch_id, main_sn, aged_time, status)
            VALUES (?, ?, ?, 'pending')
        """, (batch_id, main_sn, int(time.time() * 1000)))
        log(f"[AGED] Saved aged NG: {main_sn} batch={batch_id}")

def save_sn(sn, batch_id, slot, result):
    """Save SN to track all scanned SNs."""
    with sqlite3.connect(NG_DB) as conn:
        if _test_mode_enabled:
            updated = conn.execute(
                """UPDATE all_sns SET scan_time=?,batch_id=?,slot=?,result=?
                   WHERE UPPER(sn)=UPPER(?)""",
                (int(time.time() * 1000), batch_id, slot, result, sn),
            ).rowcount
            if updated:
                return
        conn.execute("""
            INSERT INTO all_sns (sn, scan_time, batch_id, slot, result)
            VALUES (?, ?, ?, ?, ?)
        """, (sn, int(time.time() * 1000), batch_id, slot, result))

def mes_sn_is_duplicate(sn):
    """MES factory SN master is authoritative for normal (non-retest) CSVs."""
    base = MES_URL.replace("/api/pda/events", "").rstrip("/")
    url = f"{base}/api/station/sn-guard/check/{urllib.parse.quote(str(sn).strip().upper())}"
    with urllib.request.urlopen(url, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    return bool(data.get("duplicate"))

def mes_source_time(batch_timestamp):
    """Convert ICT YYYYMMDDhhmmss into an unambiguous Vietnam ISO time."""
    value = str(batch_timestamp or "").strip()
    parsed = datetime.strptime(value, "%Y%m%d%H%M%S")
    return parsed.strftime("%Y-%m-%dT%H:%M:%S+07:00")

def load_pending_ng_batches():
    """Restore pending NG batches from SQLite into _pending_ng_batches on startup."""
    pending = {}
    try:
        with sqlite3.connect(NG_DB) as conn:
            rows = conn.execute(
                "SELECT batch_id, main_sn, sn_obj, batch_start FROM ng_batches"
            ).fetchall()
        for batch_id, main_sn, sn_obj_json, _batch_start_ms in rows:
            try:
                sn_obj = json.loads(sn_obj_json)
                # New format: use (prefix, batch_id) as key
                # We don't have prefix in SQLite, so use a placeholder
                prefix = sn_obj.get("stationCode", "ICT")
                batch_key = (prefix, batch_id)
                # Restore sub_boards from sn_obj
                sub_boards = {}
                child_sns = {}
                for b in sn_obj.get("subBoards", []):
                    slot = b.get("slot")
                    if slot:
                        results = b.get("results", [])
                        test_times = b.get("testTimes", [])
                        history = [(test_times[i], results[i]) for i in range(len(results)) if i < len(test_times)]
                        if not history:
                            history = [(0, b.get("result", "UNKNOWN"))]
                        sub_boards[slot] = history
                        child_sns[slot] = b.get("sn", main_sn)
                batch_start_str = sn_obj.get("batchStart", batch_id)
                batch_end_str = sn_obj.get("batchEnd", batch_id)
                try:
                    batch_start_int = int(batch_start_str)
                    batch_end_int = int(batch_end_str)
                except:
                    batch_start_int = batch_start_str
                    batch_end_int = batch_end_str
                pending[batch_key] = {
                    "main_sn": main_sn,
                    "sn_obj": sn_obj,
                    "batch_start": batch_start_int,
                    "batch_end": batch_end_int,
                    "sub_boards": sub_boards,
                    "child_sns": child_sns,
                    "is_pushed": True,
                }
            except Exception:
                pass
    except Exception:
        pass
    return pending

# ── MES bridge ──────────────────────────────────────────────────────────
_event_queue = queue.Queue()
_send_thread = None


_log_lock = threading.Lock()
_tk_log_win = None   # set by bootstrap
_tk_log_queue = queue.Queue()

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    txt = f"[{ts}] {msg}"
    print(txt, flush=True)
    os.makedirs(WATCH_DIR, exist_ok=True)
    with open(os.path.join(WATCH_DIR, "ict_agent.log"), "a", encoding="utf-8") as f:
        f.write(txt + "\n")
    # Tk is not thread-safe. Worker/watcher threads enqueue text and the main
    # UI loop drains it; calling widget.after() here can deadlock simulation.
    if _tk_log_win is not None:
        _tk_log_queue.put(txt)


def now_ms():
    return int(time.time() * 1000)


def build_ng_object(sn):
    """Build NG payload for SSE (3D real-time display)."""
    info = _ng_tracking.get(sn, {"firstFailTime": now_ms(), "testCount": 1})
    born_ms = info["firstFailTime"]
    test_count = info["testCount"]

    age_ms = now_ms() - born_ms
    age_hours = age_ms / 3_600_000
    is_confirmed = test_count >= MAX_RETEST + 1
    is_aged = age_hours >= AGING_HOURS

    if is_aged:
        label = "Aged NG"
    elif is_confirmed:
        label = "NG Pool"
    else:
        label = "NG"

    return {
        "sn": sn,
        "birthTime": born_ms,
        "birthStation": STATION_CODE,
        "birthPlace": STATION_LABEL,
        "mainboard": "",
        "slot": "",
        "totalSlots": 12,
        "operator": "ICT操作员",
        "retestRemaining": max(0, MAX_RETEST - (test_count - 1)),
        "ageHours": round(age_hours, 2),
        "isConfirmed": is_confirmed,
        "isAged": is_aged,
        "label": label,
        "testCount": test_count,
    }


# ── MES bridge ─────────────────────────────────────────────────────────
def _mes_worker():
    """Durable MES sender: SQLite first, retry until the MES acknowledges."""
    log("[MES] Worker started")
    while True:
        item = None
        try:
            item = _event_queue.get(timeout=1.0)
        except queue.Empty:
            pass
        if item is not None:
            item.setdefault("eventId", f"ict-{uuid.uuid4()}")
            with sqlite3.connect(NG_DB) as conn:
                conn.execute("INSERT OR IGNORE INTO mes_event_outbox(event_id,event_json,created_at) VALUES(?,?,?)",
                             (item["eventId"], json.dumps(item, ensure_ascii=False), now_ms()))
        with sqlite3.connect(NG_DB) as conn:
            row = conn.execute("SELECT event_id,event_json FROM mes_event_outbox WHERE status='PENDING' ORDER BY created_at LIMIT 1").fetchone()
        if not row:
            continue
        event_id, event_json = row
        item = json.loads(event_json)
        log(f"[MES] Dequeued: {item.get('type')}")
        try:
            body = json.dumps(item, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                MES_URL,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            with sqlite3.connect(NG_DB) as conn:
                conn.execute("DELETE FROM mes_event_outbox WHERE event_id=?", (event_id,))
            log(f"[MES] {item.get('type')} → {item.get('sn', '')} OK")
        except urllib.error.HTTPError as e:
            # A rejected payload (4xx) will never become valid by retrying it.
            # Quarantine it so one old/bad event cannot block every later NG.
            try:
                response_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                response_text = ""
            error_text = f"HTTP {e.code}: {response_text or e.reason}"
            if 400 <= int(e.code) < 500:
                try:
                    rejected = json.loads(response_text) if response_text else {}
                except Exception:
                    rejected = {}
                rejection_code = str(rejected.get("code", "")).upper()
                rejected_sn = str(rejected.get("sn") or item.get("payload", {}).get("sn") or "").strip().upper()
                if rejected_sn and "DUPLICATE" in rejection_code:
                    # MES won the atomic duplicate race. Undo the optimistic
                    # local registration and raise the station duplicate alarm.
                    with sqlite3.connect(NG_DB) as conn:
                        conn.execute("DELETE FROM all_sns WHERE UPPER(sn)=UPPER(?)", (rejected_sn,))
                    _duplicate_alarm_queue.put(rejected_sn)
                with sqlite3.connect(NG_DB) as conn:
                    conn.execute(
                        "UPDATE mes_event_outbox SET retry_count=retry_count+1,last_error=?,last_attempt=?,status='REJECTED' WHERE event_id=?",
                        (error_text, now_ms(), event_id),
                    )
                log(f"[MES REJECTED] {item.get('type')} {item.get('sn', '')}: {error_text}")
                continue
            with sqlite3.connect(NG_DB) as conn:
                conn.execute("UPDATE mes_event_outbox SET retry_count=retry_count+1,last_error=?,last_attempt=? WHERE event_id=?",
                             (error_text, now_ms(), event_id))
            log(f"[MES ERR] {item.get('type')} {item.get('sn', '')}: {error_text}")
            time.sleep(2)
        except Exception as e:
            with sqlite3.connect(NG_DB) as conn:
                conn.execute("UPDATE mes_event_outbox SET retry_count=retry_count+1,last_error=?,last_attempt=? WHERE event_id=?",
                             (str(e), now_ms(), event_id))
            log(f"[MES ERR] {item.get('type')} {item.get('sn', '')}: {e}")
            time.sleep(2)


def _enqueue(event_type, sn, extra=None):
    inner = {"sn": sn}
    if extra:
        inner.update(extra)
    payload = {
        "type": event_type,
        "stationCode": STATION_CODE,
        "payload": inner,
    }
    _event_queue.put(payload)

def _sync_ict_process(stage, batch_id="", progress=0, **extra):
    """Publish the operator-visible ICT lifecycle to the MES authority."""
    payload = {
        "stage": stage, "batchId": str(batch_id or ""),
        "progress": int(progress or 0), "total": 6,
        "eventTime": int(time.time() * 1000), **extra,
    }
    _event_queue.put({"type": "ICT_PROCESS", "priority": "info", "stationCode": STATION_CODE, "payload": payload})


def post_sn_scan(sn):
    global _active_retest_batch, _scan_retest_mode, _overtime_retest_permit, _explicit_retest_grant
    """SN scanned at station — drives WIP flow in 3D."""
    # Auxiliary scanner is local-only. CSV reports are the sole ICT data
    # source sent to MES/3D.
    log(f"[SCANNER LOCAL] {sn}")
    _scanner_ui_queue.put((sn, datetime.now().strftime("%H:%M:%S")))
    # The button grants exactly one scanner bypass. Consume it immediately,
    # even when the scanned code is invalid or does not belong to an NG board,
    # so an accidental scan can never leave duplicate checking disabled.
    retest_scan_authorized = bool(_scan_retest_mode)
    if retest_scan_authorized:
        _scan_retest_mode = False
        log(f"[RETEST BYPASS] one scanner duplicate check consumed by {sn}")
    try:
        with sqlite3.connect(NG_DB) as conn:
            match = conn.execute(
                "SELECT batch_id FROM ng_boards WHERE sn=? ORDER BY rowid DESC LIMIT 1", (sn,)
            ).fetchone()
            source = "NG"
            if match:
                batch_id = str(match[0])
                scanned_board = conn.execute(
                    "SELECT slot,final_result,retest_remaining,test_count FROM ng_boards "
                    "WHERE batch_id=? AND sn=? LIMIT 1", (batch_id, sn)
                ).fetchone()
                rows = conn.execute(
                    "SELECT slot,sn,final_result,retest_remaining,test_count "
                    "FROM ng_boards WHERE batch_id=? ORDER BY slot", (batch_id,)
                ).fetchall()
            else:
                scanned_board = None
                match = conn.execute(
                    "SELECT batch_id FROM all_sns WHERE sn=? ORDER BY scan_time DESC LIMIT 1", (sn,)
                ).fetchone()
                source = "SN"
                if match:
                    batch_id = str(match[0])
                    rows = conn.execute(
                        "SELECT slot,sn,result,2,1 FROM all_sns WHERE batch_id=? "
                        "GROUP BY slot ORDER BY slot", (batch_id,)
                    ).fetchall()
                else:
                    rows = []
        if match and rows:
            if source != "NG" and not retest_scan_authorized:
                log(f"[DUP] Scanner duplicate detected after one-time bypass restored: {sn}")
                _duplicate_alarm_queue.put(sn)
                _enqueue("DUPLICATE_SN", sn, {
                    "pcbSerial": sn, "batchId": str(batch_id),
                    "eventType": "ict_scanner_duplicate",
                })
                return
            slots_info = [
                (int(slot), str(result or "PASS").upper(), int(retest_left or 0), str(board_sn))
                for slot, board_sn, result, retest_left, _test_count in rows
            ]
            duplicate_counts = {
                int(slot): int(test_count) for slot, _board_sn, _result, _left, test_count in rows
                if int(test_count or 1) > 1
            }
            _ui_update_queue.put((batch_id, slots_info, duplicate_counts))
            _scanner_batch_queue.put((sn, batch_id, len(rows), source))
            log(f"[SCANNER BOARD] {sn} -> batch={batch_id} members={len(rows)} source={source}")
            if source == "NG" and scanned_board:
                scanned_slot = int(scanned_board[0])
                fail_rows = [row for row in rows if str(row[2] or "").upper() == "FAIL"]
                remaining = max((int(row[3] or 0) for row in fail_rows), default=0)
                if remaining > 0:
                    speak(f"母板号{batch_id}，还有{remaining}次复检机会，请开始测试")
                else:
                    speak("没有复检机会，确认不良，整盘自动送往FCT")
                log(f"[SCANNER RETEST] {sn}: batch={batch_id} remaining={remaining}")
                if retest_scan_authorized:
                    selected_key = next((
                        key for key, info in _pending_ng_batches.items()
                        if str((info.get("sn_obj") or {}).get("batchId", key[1])) == batch_id
                    ), None)
                    if selected_key is not None and _explicit_retest_grant:
                        # Confirmed NG has no automatic allowance, but every
                        # explicit button action authorizes this selected batch.
                        remaining = max(1, remaining)
                    selected_info = _pending_ng_batches.get(selected_key, {}) if selected_key else {}
                    try:
                        started = datetime.strptime(
                            str(selected_info.get("batch_start", selected_key[1])), "%Y%m%d%H%M%S"
                        )
                        overtime = (datetime.now() - started).total_seconds() > AGING_HOURS * 3600
                    except Exception:
                        overtime = False
                    if remaining > 0 and selected_key is not None and overtime and not _overtime_retest_permit:
                        _retest_scan_ui_queue.put(("NEED_PERMISSION", batch_id, remaining, scanned_slot, sn))
                        _sync_ict_process("OVERTIME_PERMISSION_REQUIRED", batch_id, 12, remaining=remaining)
                        speak("该母板已超过两小时，需要主管许可后才能复检")
                        log(f"[RETEST SCAN] blocked overtime batch={batch_id}; permission required")
                    elif remaining > 0 and selected_key is not None:
                        _active_retest_batch = selected_key
                        _explicit_retest_grant = False
                        if overtime:
                            _overtime_retest_permit = False
                        _sync_ict_process("RETEST_ARMED", batch_id, 0, remaining=remaining, overtime=overtime)
                        _retest_scan_ui_queue.put(("ARMED", batch_id, remaining, scanned_slot, sn))
                        log(f"[RETEST SCAN] armed batch={batch_id} by sn={sn}")
                    elif remaining <= 0:
                        _retest_scan_ui_queue.put(("NO_CHANCE", batch_id, remaining, scanned_slot, sn))
                    else:
                        _retest_scan_ui_queue.put(("NOT_LOADED", batch_id, remaining, scanned_slot, sn))
            elif source != "NG":
                speak(f"母板号{batch_id}，请开始测试")
                if retest_scan_authorized:
                    _retest_scan_ui_queue.put(("NOT_LOADED", batch_id, 0, 0, sn))
        else:
            _scanner_batch_queue.put((sn, "", 0, "NOT_FOUND"))
            if retest_scan_authorized:
                _retest_scan_ui_queue.put(("NOT_LOADED", "", 0, 0, sn))
            log(f"[SCANNER BOARD] {sn} -> motherboard not found")
    except Exception as error:
        _scanner_batch_queue.put((sn, "", 0, "ERROR"))
        log(f"[SCANNER BOARD ERR] {sn}: {error}")


def post_ng_defect(sn):
    """NG event — drives 3D station NG display (all state changes)."""
    ng_obj = build_ng_object(sn)
    ng_obj["sn"] = sn
    ng_obj["defectCode"] = "ICT_FAIL"
    payload = {
        "type": "NG_DEFECT",
        "stationCode": STATION_CODE,
        "payload": ng_obj,
    }
    _event_queue.put(payload)


def post_ng_to_mes(sn):
    """Confirmed NG only — for MES statistics (sent once per confirmed NG)."""
    info = _ng_tracking.get(sn, {"firstFailTime": now_ms(), "testCount": 1})
    ng_obj = build_ng_object(sn)
    payload = {
        "type": "NG_DEFECT",
        "sn": sn,
        "stationCode": STATION_CODE,
        "defectCode": "ICT_FAIL",
        "payload": ng_obj,
    }
    _enqueue("NG_CONFIRMED", sn, {"payload": ng_obj})


# ── Scanner capture ────────────────────────────────────────────────────
import urllib.request  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402

_kb_buf = ""
_kb_lock = threading.Lock()
_kb_listener = None
_tcp_running = False
_ict_root_ref = [None]
_scanner_entry_ref = [None]
_scanner_submit_ref = [None]


def _ict_window_is_foreground(root):
    """Avoid double-capturing when the visible Tk SN field owns the keyboard."""
    try:
        user32 = ctypes.windll.user32
        foreground = int(user32.GetForegroundWindow())
        root_hwnd = int(root.winfo_id())
        while foreground:
            if foreground == root_hwnd:
                return True
            foreground = int(user32.GetParent(foreground))
    except Exception:
        return False
    return False


def is_valid_scanner_sn(value):
    """Accept keyboard-wedge SNs used by ICT and the upstream ATE stations."""
    return bool(re.fullmatch(r"[A-Z0-9]{3,64}", (value or "").strip().upper()))


def classify_scanned_sn(sn):
    """Read local SQLite before processing the scan: NG takes precedence over duplicate."""
    try:
        with sqlite3.connect(NG_DB) as conn:
            ng = conn.execute(
                "SELECT 1 FROM ng_boards WHERE UPPER(sn)=UPPER(?) "
                "AND UPPER(COALESCE(final_result,'')) IN ('FAIL','NG') LIMIT 1", (sn,)
            ).fetchone()
            if ng:
                return "NG"
            dup = conn.execute(
                "SELECT 1 FROM all_sns WHERE UPPER(sn)=UPPER(?) LIMIT 1", (sn,)
            ).fetchone()
            return "DUP" if dup else "NEW"
    except Exception as exc:
        log(f"[SCAN CLASSIFY ERR] {sn}: {exc}")
        return "UNKNOWN"


def _start_keyboard_hook():
    """USB barcode scanner as keyboard input — hook Enter to commit."""
    global _kb_listener, _kb_buf
    try:
        from pynput import keyboard
    except ImportError:
        log("[SCANNER] pynput not installed — keyboard hook disabled")
        return

    def on_press(key):
        global _kb_buf
        try:
            ch = key.char.upper() if hasattr(key, 'char') and key.char else None
            if ch and ch.isalnum():
                with _kb_lock:
                    _kb_buf += ch
            elif key == keyboard.Key.enter:
                with _kb_lock:
                    sn = _kb_buf.strip()
                    _kb_buf = ""
                if is_valid_scanner_sn(sn):
                    log(f"[ATE-BASE GLOBAL SCAN] {sn}")
                    root = _ict_root_ref[0]
                    submit = _scanner_submit_ref[0]
                    if root is not None and submit is not None:
                        def deliver_global_scan(value=sn):
                            # If the visible Entry already received this
                            # wedge, its <Return> handler has submitted it.
                            # This prevents TESTSNTESTSN double submissions.
                            try:
                                current = _scanner_entry_ref[0].get().strip().upper()
                            except Exception:
                                current = ""
                            if current == value or current.endswith(value):
                                return
                            submit(value)
                        root.after(0, deliver_global_scan)
                    else:
                        post_sn_scan(sn)
        except Exception:
            pass

    _kb_listener = keyboard.Listener(on_press=on_press)
    _kb_listener.start()
    log("[SCANNER] Keyboard hook started")


def _start_tcp_server():
    """TCP server on port 1003 — receives scans from TCP-enabled devices."""
    global _tcp_running
    if _tcp_running:
        return
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", TCP_PORT))
        srv.listen(5)
        _tcp_running = True
        log(f"[SCANNER] TCP server started on port {TCP_PORT}")
    except Exception as e:
        log(f"[SCANNER] TCP server failed: {e}")
        return

    def accept_loop():
        while _tcp_running:
            try:
                srv.settimeout(1.0)
                client, addr = srv.accept()
                threading.Thread(target=_handle_tcp, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break

    threading.Thread(target=accept_loop, name="tcp-server", daemon=True).start()


def _handle_tcp(client):
    """Handle one TCP client — accumulate bytes, split on newline."""
    try:
        client.settimeout(5.0)
        buf = b""
        while True:
            chunk = client.recv(256)
            if not chunk:
                break
            buf += chunk
            lines = buf.decode("utf-8", errors="replace").split("\n")
            for line in lines[:-1]:
                line = line.strip()
                if line:
                    log(f"[tcp] {line}")
                    if line.upper() == "PING":
                        client.sendall((json.dumps({
                            "ok": True,
                            "reply": "PONG",
                            "stationCode": STATION_CODE,
                            "mesUrl": MES_URL,
                            "watchDir": WATCH_DIR,
                            "timestamp": now_ms(),
                        }, ensure_ascii=False) + "\n").encode("utf-8"))
                    elif line.upper() == "RETEST":
                        result = arm_latest_retest()
                        client.sendall((json.dumps(result, ensure_ascii=False) + "\n").encode("utf-8"))
                    elif is_valid_scanner_sn(line):
                        post_sn_scan(line)
            buf = lines[-1].encode("utf-8") if lines[-1] else b""
        client.close()
    except Exception:
        try:
            client.close()
        except Exception:
            pass


# ── Batch state ────────────────────────────────────────────────────────
# Key: (main_sn, batch_ts) → already finalized (sent SSE)
_processed_batches = set()
MAX_RETEST = max(0, CONFIRM_AFTER_FAIL_COUNT - 1)
AGING_HOURS = 2.0  # hours before NG becomes Aged

# Pending: batch_key → {
#   main_sn, batch_start, batch_end, sub_boards: {slot: [(ts_int, result), ...]}, is_pushed: bool
# }
_pending_ng_batches = {}
_active_retest_batch = None  # batch_key explicitly armed from the UI
_scan_retest_mode = False     # operator pressed retest and must scan one NG child SN
_explicit_retest_grant = False  # one manual opportunity; automatic retests remain zero
_overtime_retest_permit = False  # one complete >2-hour retest; consumed when armed
_route_target_batch = ""
_ui_update_queue = queue.Queue()
_duplicate_alarm_queue = queue.Queue()
_scanner_ui_queue = queue.Queue()
_scanner_batch_queue = queue.Queue()
_retest_scan_ui_queue = queue.Queue()
_aging_warning_sent = set()
_simulation_sns = set()       # UI test button only; never triggers DUP blocking
_test_mode_enabled = bool(_station_config.get("test_mode_enabled", False))


def _persist_test_mode(enabled):
    """Lock the operator-selected mode across restarts."""
    config = dict(_station_config)
    config["test_mode_enabled"] = bool(enabled)
    temp_path = CONFIG_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as config_file:
        json.dump(config, config_file, ensure_ascii=False, indent=2)
        config_file.flush()
        os.fsync(config_file.fileno())
    os.replace(temp_path, CONFIG_PATH)
    _station_config["test_mode_enabled"] = bool(enabled)


def _find_local_motherboard_id(child_sn):
    """Return the original motherboard ID already assigned to this SN."""
    with sqlite3.connect(NG_DB) as conn:
        row = conn.execute(
            """SELECT batch_id FROM all_sns
               WHERE UPPER(sn)=UPPER(?) ORDER BY scan_time DESC LIMIT 1""",
            (child_sn,),
        ).fetchone()
        if not row:
            row = conn.execute(
                """SELECT batch_id FROM ng_boards
                   WHERE UPPER(sn)=UPPER(?) ORDER BY rowid DESC LIMIT 1""",
                (child_sn,),
            ).fetchone()
    return str(row[0]) if row and row[0] else ""


def _load_local_motherboard(batch_key, batch_id):
    """Load the last SQLite result for an existing motherboard into memory."""
    if batch_key in _pending_ng_batches:
        return
    with sqlite3.connect(NG_DB) as conn:
        rows = conn.execute(
            """SELECT slot,sn,result,scan_time FROM all_sns
               WHERE batch_id=? ORDER BY slot,scan_time DESC""",
            (batch_id,),
        ).fetchall()
    latest_by_slot = {}
    for slot, sn, result, scan_time in rows:
        latest_by_slot.setdefault(
            int(slot), (str(sn), str(result or "PASS").upper(), int(scan_time or now_ms()))
        )
    if not latest_by_slot:
        return
    _pending_ng_batches[batch_key] = {
        "main_sn": latest_by_slot[min(latest_by_slot)][0],
        "batch_start": min(item[2] for item in latest_by_slot.values()),
        "batch_end": max(item[2] for item in latest_by_slot.values()),
        "sub_boards": {
            slot: [(item[2], item[1])] for slot, item in latest_by_slot.items()
        },
        "child_sns": {
            slot: item[0] for slot, item in latest_by_slot.items()
        },
        "is_pushed": False,
        "test_count": 1,
        "_batch_key": batch_key,
    }


def arm_latest_retest():
    """Arm the newest unresolved NG batch for one scanned, partial-board retest."""
    global _active_retest_batch
    candidates = []
    for key, info in _pending_ng_batches.items():
        obj = info.get("sn_obj") or {}
        failed = [b for b in obj.get("subBoards", [])
                  if b.get("result") == "FAIL" and b.get("retestRemaining", 0) > 0]
        if failed:
            candidates.append((str(info.get("batch_end", key[1])), key, failed))
    if not candidates:
        return {"ok": False, "message": "No unresolved NG batch with retests remaining"}

    _, key, failed = sorted(candidates, reverse=True)[0]
    _active_retest_batch = key
    available_before = min(b.get("retestRemaining", 0) for b in failed)
    remaining_after = max(0, available_before - 1)
    attempt_number = MAX_RETEST - available_before + 1
    failed_slots = [b.get("slot") for b in failed]
    announcement = (
        f"开始第{attempt_number}次复测，批次{key[1]}，"
        f"不良槽位{'、'.join(str(s) for s in failed_slots)}，"
        f"剩余{remaining_after}次复测机会"
    )
    speak(announcement)
    log(f"[RETEST] {announcement}; waiting for 1 or more child-board CSV files")
    return {
        "ok": True,
        "batchKey": list(key),
        "batchId": str(key[1]),
        "attempt": attempt_number,
        "remaining": remaining_after,
        "failedSlots": failed_slots,
        "message": announcement,
    }

# Tracks batch_keys that have already been pushed via SSE (prevents bootstrap duplicate)
_finalized_batches = set()

# Duplicate SN detection flag (重码)


# ── Incremental slot update ────────────────────────────────────────────
def _update_or_create_slot(batch_key, child_sn, result, ts_int, slot_hint=None):
    """
    当新CSV到达时：增量更新pending的某个slot。
    batch_key: (prefix, batch_ts) tuple - groups all 12 files of same mother board
    child_sn: unique child board SN from filename
    """
    if batch_key not in _pending_ng_batches:
        _pending_ng_batches[batch_key] = {
            "main_sn": child_sn,  # First child's SN as proxy for batch
            "batch_start": ts_int,
            "batch_end": ts_int,
            "sub_boards": {},     # child_sn → [(ts_int, result), ...]
            "child_sns": {},      # slot → child_sn mapping
            "is_pushed": False,
            "test_count": 1,
            "_batch_key": batch_key,
        }
    else:
        p = _pending_ng_batches[batch_key]
        if ts_int < p["batch_start"]:
            p["batch_start"] = ts_int
        if ts_int > p["batch_end"]:
            p["batch_end"] = ts_int

    p = _pending_ng_batches[batch_key]

    # Determine slot number - use existing slot if this child_sn already exists
    slot = None
    for s, cs in p["child_sns"].items():
        if cs == child_sn:
            slot = s
            break
    if slot is None:
        slot = int(slot_hint) if slot_hint is not None else len(p["child_sns"]) + 1
        p["child_sns"][slot] = child_sn

    if _test_mode_enabled:
        # Test mode is a current-state workflow: replace the previous value.
        p["sub_boards"][slot] = [(ts_int, result)]
    else:
        if slot not in p["sub_boards"]:
            p["sub_boards"][slot] = []
        p["sub_boards"][slot].append((ts_int, result))

    return True  # always signal "ready to finalize"


def _push_partial_batch_to_ui(batch_key):
    """Reflect every accepted CSV immediately on the 12-slot GUI panel."""
    p = _pending_ng_batches.get(batch_key)
    if not p:
        return
    slots_info = []
    duplicate_counts = {}
    for slot in sorted(p.get("sub_boards", {})):
        history = sorted(p["sub_boards"][slot])
        if not history:
            continue
        result = history[-1][1]
        test_count = len(history)
        retest_remaining = max(0, MAX_RETEST - (test_count - 1))
        sn = p.get("child_sns", {}).get(slot, "")
        slots_info.append((slot, result, retest_remaining, sn))
        if test_count > 1:
            duplicate_counts[slot] = test_count
    _ui_update_queue.put(
        (p.get("main_sn", str(batch_key[1])), slots_info, duplicate_counts)
    )
    _sync_ict_process("TESTING", batch_key[1], len(slots_info))


def _finalize_batch(batch_key):
    """
    计算sub_boards详细信息，推SSE，记SQLite。
    batch_key: (prefix, batch_ts) tuple
    - NG batch：保留在 _pending_ng_batches（等待retest或aging）
    - PASS batch：从 _pending_ng_batches 删除
    """
    p = _pending_ng_batches.get(batch_key)
    if not p:
        return
    main_sn = p["main_sn"]  # First child's SN as batch identifier
    # Keep one stable batch ID throughout initial test and all retests.
    batch_ts_str = str(batch_key[1])
    batch_start = p["batch_start"]
    batch_end = p["batch_end"]

    sub_boards = []
    has_fail = False
    confirmed_ng_count = 0

    for slot in sorted(p["sub_boards"].keys()):
        history = sorted(p["sub_boards"][slot])
        test_count = len(history)
        final_result = history[-1][1]
        results = [r for _, r in history]
        test_times = [t for t, _ in history]
        child_sn = p["child_sns"].get(slot, main_sn)

        retest_remaining = max(0, MAX_RETEST - (test_count - 1))
        is_confirmed_ng = (final_result == "FAIL" and test_count >= MAX_RETEST + 1)

        sub_boards.append({
            "sn": child_sn,
            "slot": slot,
            "result": final_result,
            "results": results,
            "testTimes": test_times,
            "testCount": test_count,
            "retestRemaining": retest_remaining,
            "isConfirmedNG": is_confirmed_ng,
        })

        if final_result == "FAIL":
            has_fail = True
        if is_confirmed_ng:
            confirmed_ng_count += 1
            try:
                save_confirmed_ng(main_sn, batch_ts_str, slot, child_sn)
            except Exception as e:
                log(f"[DB ERR] save_confirmed_ng: {e}")

    overall = "CONFIRMED_NG" if confirmed_ng_count > 0 else ("FAIL" if has_fail else "PASS")

    try:
        from datetime import datetime
        bs_str = str(batch_start)
        if len(bs_str) == 14:
            batch_start_dt = datetime.strptime(bs_str, "%Y%m%d%H%M%S")
            batch_start_ms = int(batch_start_dt.timestamp() * 1000)
        else:
            batch_start_ms = int(bs_str) * 1000
        age_ms = now_ms() - batch_start_ms
    except Exception:
        batch_start_ms = int(time.time() * 1000)
        age_ms = 0
    age_hours = age_ms / 3_600_000
    is_aged = age_hours >= 2.0

    sn_obj = {
        "batchId": batch_ts_str,
        "mainSn": main_sn,
        "subBoards": sub_boards,
        "overallResult": overall,
        "slotCount": len(sub_boards),
        "confirmedNgCount": confirmed_ng_count,
        "stationCode": STATION_CODE,
        "batchStart": str(batch_start),
        "batchEnd": str(batch_end),
        "retestMax": MAX_RETEST,
        "ageHours": round(age_hours, 2),
        "isAged": is_aged,
        "isAgedLabel": "Aged" if is_aged else "",
    }

    # Push the finalized lifecycle state to the Tkinter motherboard panel.
    # The registered wrapper schedules the actual widget update on Tk's thread.
    try:
        ui_slots = [
            (b["slot"], b["result"], b["retestRemaining"], b["sn"])
            for b in sub_boards
        ]
        duplicate_counts = {
            b["slot"]: b["testCount"] for b in sub_boards if b["testCount"] > 1
        }
        # The motherboard display must show the stable motherboard/batch ID.
        # main_sn is the first daughter SN and belongs only in the slot view.
        _ui_update_queue.put((batch_ts_str, ui_slots, duplicate_counts))
    except Exception as e:
        log(f"[UI ERR] motherboard update: {e}")

    import json as _json
    fail_boards = [b for b in sub_boards if b["result"] == "FAIL"]
    fail_slots = [(b["slot"], b["sn"], b["testCount"], b["retestRemaining"]) for b in fail_boards]
    from datetime import datetime as _dt
    start_str = _dt.strptime(str(batch_start), "%Y%m%d%H%M%S").strftime("%H:%M:%S") if batch_start else "?"
    log("[NG] mainSn=%s start=%s age=%sh confirmed=%d/%d fail_slots=%s isAged=%s" % (
        main_sn, start_str, round(age_hours, 1), confirmed_ng_count, len(fail_boards), fail_slots, is_aged))
    log("[NG] OBJ=" + _json.dumps(sn_obj, ensure_ascii=False))

    if _test_mode_enabled:
        # Test mode has no retry ceiling and no production duplicate/NG alarm
        # lifecycle. SQLite and MES both receive one current motherboard state.
        for board in sub_boards:
            save_sn(board["sn"], batch_ts_str, board["slot"], board["result"])
        p["sn_obj"] = sn_obj
        p["is_pushed"] = True
        _sync_ict_process(
            "TEST_MODE_RESULT", batch_ts_str, len(sub_boards),
            overallResult=overall, testMode=True, latestResultOnly=True,
            motherboardId=batch_ts_str,
            ictBatchId=batch_ts_str,
            mainSn=main_sn,
            subBoards=sub_boards,
            slotCount=len(sub_boards),
            canonicalMotherboardMerge=True,
            sourceStation=STATION_CODE,
            sourceStationCode=STATION_CODE,
        )
        _event_queue.put({
            "type": "STATION_TEST_RESULT",
            "priority": "info",
            "stationCode": STATION_CODE,
            "payload": {
                **sn_obj,
                "sn": main_sn,
                "pcbSerial": main_sn,
                "testMode": True,
                "latestResultOnly": True,
                "result": "FAIL" if has_fail else "PASS",
            },
        })
        message = (
            f"测试模式，母板号{batch_ts_str}，"
            f"最后结果{'不良' if has_fail else '通过'}"
        )
        speak(message)
        log(f"[TEST MODE] Latest motherboard result saved locally and queued to MES: {batch_ts_str}")
        return

    if overall in ("FAIL", "CONFIRMED_NG"):
        _sync_ict_process(overall, batch_ts_str, 12, overallResult=overall)
        p["sn_obj"] = sn_obj
        p["batch_start_str"] = str(batch_start)
        p["is_pushed"] = True
        try:
            save_ng_batch(sn_obj, batch_start_ms)
        except Exception as e:
            log("[DB ERR] save_ng_batch: " + str(e))
        fail_boards = [b for b in sub_boards if b["result"] == "FAIL"]
        if fail_boards:
            slots_text = "，".join(str(b["slot"]) for b in fail_boards)
            # A motherboard can only be retested while every failed member still
            # has an opportunity, so announce the minimum remaining count.
            total_chances = min(int(b.get("retestRemaining", 0)) for b in fail_boards)
            if total_chances > 0:
                message = (
                    f"母板号{batch_ts_str}，本盘不良槽位：{slots_text}，"
                    f"剩余复检机会{total_chances}次"
                )
            else:
                message = (
                    f"母板号{batch_ts_str}，本盘不良槽位：{slots_text}，"
                    "没有复检机会，确认不良，整盘自动送往FCT"
                )
                # Confirmed ICT NG is transferred as the complete 12-board
                # motherboard directly to FCT. No operator destination choice.
                _event_queue.put({
                    "type": "ICT_ROUTE_SELECTED", "priority": "critical", "stationCode": STATION_CODE,
                    "payload": {"batchId": batch_ts_str, "destination": "FCT",
                                "destinationStationCode": "manu_fct", "destinationLabel": "FCT",
                                "motherboard": sn_obj, "automatic": True,
                                "eventTime": int(time.time() * 1000)},
                })
                message = f"母板号{batch_ts_str}，没有复检机会，确认不良，整盘自动送往FCT"
            speak(message)
            log(f"[VOICE] Batch result: {message}")
        payload = {
            "type": "NG_DEFECT",
            "priority": "critical",
            "stationCode": STATION_CODE,
            "payload": sn_obj,
        }
        _event_queue.put(payload)
    else:
        _sync_ict_process("PASS", batch_ts_str, 12, overallResult="PASS")
        message = f"母板号{batch_ts_str}，本盘测试通过，无不良槽位"
        speak(message)
        log(f"[VOICE] Batch result: {message}")
        _pending_ng_batches.pop(batch_key, None)
        payload = {
            "type": "SN_SCAN",
            "priority": "critical",
            "stationCode": STATION_CODE,
            "payload": {
                "sn": main_sn,
                "pcbSerial": main_sn,
                "batchId": batch_ts_str,
                "subBoards": sub_boards,
                "overallResult": overall,
                "slotCount": len(sub_boards),
                "batchStart": str(batch_start),
                "batchEnd": str(batch_end),
            },
        }
        _event_queue.put(payload)

def _parse_batch_from_fname(fname):
    """
    Parse filename: PREFIX_{childSN}_{timestamp}_{result}.CSV
    New format (no slot suffix): NBT-(26V5060)EPS18R1G-36-ICT_1G6N00901A_20260717074544_PASS.CSV
    Returns (child_sn, prefix, batch_ts, result, timestamp_int) or None.
    """
    try:
        base = fname.upper().replace(".CSV", "")
        parts = base.split("_")
        if len(parts) < 4:
            return None
        result = parts[-1]
        ts_str = parts[-2]
        child_sn = parts[-3]
        # Production station must never ingest or transmit simulator serials,
        # including SIM CSV files left behind by an older installation.
        if child_sn.startswith("SIM") and not ENABLE_SIMULATOR:
            return None
        prefix = parts[0]  # e.g., NBT-(26V5060)EPS18R1G-36-ICT
        try:
            ts_int = int(ts_str)
        except:
            ts_int = 0
        return child_sn, prefix, ts_str, result, ts_int
    except Exception:
        return None


def _read_csv_summary(path):
    """Read and validate the two-row ICT report summary (GBK/GB18030)."""
    if not wait_file_stable(path):
        raise OSError(f"ICT CSV is still changing after 12 seconds: {path}")
    last_error = None
    for _ in range(5):
        try:
            with open(path, "r", encoding="gb18030", newline="") as report:
                rows = csv.reader(report)
                header = next(rows)
                values = next(rows)
            if len(values) < 7:
                raise ValueError("ICT summary row has fewer than 7 columns")
            return {
                "test_name": values[0].strip(),
                "result": values[1].strip().upper(),
                "sn": values[2].strip().upper(),
                "start_time": values[3].strip(),
                "end_time": values[4].strip(),
                "slot": int(values[5].strip()),
                "slot_count": int(values[6].strip()),
            }
        except (OSError, StopIteration) as error:
            last_error = error
            time.sleep(0.2)
    if last_error:
        raise last_error
    raise ValueError("Cannot read ICT CSV summary")


def process_batch(batch_key, collected):
    """
    collected: list of (child_sn, result, ts_int) tuples for all files in batch.
    batch_key: (prefix, batch_ts_str)
    """
    if batch_key in _processed_batches:
        return
    _processed_batches.add(batch_key)

    prefix, batch_ts = batch_key

    # Group by child_sn, sort by timestamp
    from collections import defaultdict
    by_sn = defaultdict(list)
    for child_sn, result, ts_int in collected:
        by_sn[child_sn].append((ts_int, result))

    sub_boards = []
    has_fail = False
    batch_start = None
    batch_end = None

    # Use first child_sn as main_sn for the batch
    main_sn = sorted(by_sn.keys())[0] if by_sn else prefix

    for slot_idx, child_sn in enumerate(sorted(by_sn.keys()), start=1):
        tests = sorted(by_sn[child_sn])
        test_count = len(tests)
        final_result = tests[-1][1]

        if batch_start is None:
            batch_start = tests[0][0]
        if batch_end is None:
            batch_end = tests[-1][0]

        retest_remaining = max(0, MAX_RETEST - (test_count - 1))
        is_confirmed_ng = (final_result == "FAIL" and test_count >= MAX_RETEST + 1)

        results = [r for _, r in tests]
        test_times = [t for t, _ in tests]

        board = {
            "sn": child_sn,
            "slot": slot_idx,
            "result": final_result,
            "results": results,
            "testTimes": test_times,
            "testCount": test_count,
            "retestRemaining": retest_remaining,
            "isConfirmedNG": is_confirmed_ng,
        }
        sub_boards.append(board)

        if final_result == "FAIL":
            has_fail = True

    confirmed_ng_count = sum(1 for b in sub_boards if b.get("isConfirmedNG", False))
    overall = "CONFIRMED_NG" if confirmed_ng_count > 0 else ("FAIL" if has_fail else "PASS")

    try:
        from datetime import datetime
        bs_str = str(batch_start)
        if len(bs_str) == 14:
            batch_start_dt = datetime.strptime(bs_str, "%Y%m%d%H%M%S")
            batch_start_ms = int(batch_start_dt.timestamp() * 1000)
        else:
            batch_start_ms = int(bs_str) * 1000
        age_ms = now_ms() - batch_start_ms
    except Exception:
        batch_start_ms = int(time.time() * 1000)
        age_ms = 0
    age_hours = age_ms / 3_600_000
    is_aged = age_hours >= 2.0

    sn_obj = {
        "batchId": batch_ts,
        "mainSn": main_sn,
        "subBoards": sub_boards,
        "overallResult": overall,
        "slotCount": len(sub_boards),
        "confirmedNgCount": confirmed_ng_count,
        "stationCode": STATION_CODE,
        "batchStart": batch_start,
        "batchEnd": batch_end,
        "retestMax": MAX_RETEST,
        "ageHours": round(age_hours, 2),
        "isAged": is_aged,
        "isAgedLabel": "Aged" if is_aged else "",
    }

    # Rebuild sub_boards dict with child_sns mapping for _finalize_batch
    sub_boards_dict = {}
    child_sns_map = {}
    for b in sub_boards:
        sub_boards_dict[b["slot"]] = [(0, b["result"])]
        child_sns_map[b["slot"]] = b["sn"]

    _pending_ng_batches[batch_key] = {
        "main_sn": main_sn,
        "batch_start": batch_start,
        "batch_start_str": str(batch_start),
        "batch_end": batch_end,
        "sub_boards": sub_boards_dict,
        "child_sns": child_sns_map,
        "sn_obj": sn_obj,
        "is_pushed": True,
    }

    if overall in ("FAIL", "CONFIRMED_NG"):
        try:
            save_ng_batch(sn_obj, batch_start_ms)
        except Exception as e:
            log("[DB ERR] save_ng_batch: " + str(e))
    else:
        _pending_ng_batches.pop(batch_key, None)


def _aging_checker():
    """Background thread: check pending NG batches every 60s for aging."""
    while True:
        time.sleep(60)
        try:
            from datetime import datetime
            now = now_ms()
            expired_keys = []
            warning_keys = []

            for batch_key, info in list(_pending_ng_batches.items()):
                batch_start = info["batch_start"]
                try:
                    bs_str = str(batch_start)
                    if len(bs_str) == 14:
                        batch_start_dt = datetime.strptime(bs_str, "%Y%m%d%H%M%S")
                        batch_start_ms = int(batch_start_dt.timestamp() * 1000)
                    else:
                        batch_start_ms = int(bs_str) * 1000
                except Exception:
                    batch_start_ms = now

                age_ms = now - batch_start_ms
                age_hours = age_ms / 3_600_000
                remaining = AGING_HOURS - age_hours  # hours until aged

                if remaining <= 0:
                    expired_keys.append(batch_key)
                elif remaining <= 20 / 60:  # ≤20 min left
                    warning_keys.append((batch_key, info))

            # Fire aging alert (20 min warning)
            for batch_key, info in warning_keys:
                if info.get("_suppress_aging_events") or batch_key in _aging_warning_sent:
                    continue
                sn_obj = info["sn_obj"]
                sn_obj_copy = dict(sn_obj)
                sn_obj_copy["isAgingWarning"] = True
                sn_obj_copy["agingRemainingMinutes"] = round(remaining * 60, 1)
                sn_obj_copy["ageHours"] = round(age_hours, 2)
                payload = {
                    "type": "NG_DEFECT",
                    "stationCode": STATION_CODE,
                    "payload": sn_obj_copy,
                }
                _event_queue.put(payload)
                _aging_warning_sent.add(batch_key)
                log(f"[AGING] 20min warning: {batch_key[0]} batch={batch_key[1]} remain={round(remaining*60,1)}min")

            # Fire aged event - KEEP records in SQLite, don't delete
            for batch_key in expired_keys:
                info = _pending_ng_batches.pop(batch_key, None)
                if info is None:
                    continue
                _finalized_batches.discard(batch_key)
                sn_obj = info["sn_obj"]
                sn_obj_copy = dict(sn_obj)
                sn_obj_copy["isAged"] = True
                sn_obj_copy["isAgedLabel"] = "Aged"
                sn_obj_copy["ageHours"] = round(AGING_HOURS, 2)
                payload = {
                    "type": "NG_DEFECT",
                    "stationCode": STATION_CODE,
                    "payload": sn_obj_copy,
                }
                if not info.get("_suppress_aging_events"):
                    _event_queue.put(payload)
                # Save to aged_ng table - DO NOT delete ng_batches/ng_boards records
                try:
                    save_aged_ng(sn_obj["batchId"], sn_obj["mainSn"])
                except Exception as e:
                    log(f"[DB ERR] aged save: {e}")
                log(f"[AGING] Aged: {batch_key[0]} batch={batch_key[1]} - records KEPT in SQLite")

        except Exception as e:
            log(f"[AGING ERR] {e}")


class CSVHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._seen = set()
        self._seen_lock = threading.Lock()

    def mark_existing(self):
        """Mark the bootstrap files so the safety scan does not replay them."""
        try:
            with self._seen_lock:
                self._seen.update(
                    f for f in os.listdir(WATCH_DIR) if f.upper().endswith(".CSV")
                )
        except Exception as e:
            log(f"[CSV MARK ERR] {e}")

    def reconcile(self):
        """Safety net for a watchdog thread that stops delivering events."""
        try:
            files = [f for f in os.listdir(WATCH_DIR) if f.upper().endswith(".CSV")]
        except Exception as e:
            log(f"[CSV RECONCILE ERR] {e}")
            return
        for fname in sorted(files):
            with self._seen_lock:
                if fname in self._seen:
                    continue
                # Claim first. If processing fails, release it for the next scan.
                self._seen.add(fname)
            try:
                self._handle_path(os.path.join(WATCH_DIR, fname))
            except Exception as e:
                with self._seen_lock:
                    self._seen.discard(fname)
                log(f"[CSV PROCESS ERR] {fname}: {e}")

    def on_created(self, event):
        if event.is_directory:
            return
        fname = os.path.basename(event.src_path)
        with self._seen_lock:
            if fname in self._seen:
                return
            self._seen.add(fname)
        try:
            self._handle_path(event.src_path)
        except Exception as e:
            with self._seen_lock:
                self._seen.discard(fname)
            log(f"[CSV PROCESS ERR] {fname}: {e}")

    def _handle_path(self, src_path):
        fname = os.path.basename(src_path)
        if not fname.upper().endswith(".CSV"):
            return
        parsed = _parse_batch_from_fname(fname)
        if not parsed:
            log(f"[CSV] Unknown format: {fname}")
            return

        child_sn, prefix, batch_ts, result, ts_int = parsed
        summary = _read_csv_summary(src_path)
        validation_errors = []
        if summary["sn"] != child_sn:
            validation_errors.append(f"SN file={child_sn} csv={summary['sn']}")
        if summary["result"] != result:
            validation_errors.append(f"result file={result} csv={summary['result']}")
        if summary["start_time"] != batch_ts:
            validation_errors.append(f"start file={batch_ts} csv={summary['start_time']}")
        if summary["result"] not in ("PASS", "FAIL"):
            validation_errors.append(f"invalid result={summary['result']}")
        if summary["slot_count"] < 1 or not 1 <= summary["slot"] <= summary["slot_count"]:
            validation_errors.append(
                f"invalid group={summary['slot']}/{summary['slot_count']}"
            )
        if validation_errors:
            log(f"[CSV REJECT] {fname}: {'; '.join(validation_errors)}")
            return

        # CSV summary is authoritative after it agrees with the filename.
        child_sn = summary["sn"]
        result = summary["result"]
        slot_hint = summary["slot"]
        declared_slot_count = summary["slot_count"]
        batch_key = (prefix, batch_ts)

        # Test mode reuses the motherboard identity created by the first test.
        # If the SN is new, the incoming batch timestamp becomes its permanent
        # motherboard ID. Existing SQLite data is loaded before it is updated.
        if _test_mode_enabled:
            existing_batch_id = _find_local_motherboard_id(child_sn)
            if existing_batch_id:
                batch_key = (prefix, existing_batch_id)
                _load_local_motherboard(batch_key, existing_batch_id)
                log(f"[TEST MODE] Existing motherboard {existing_batch_id} found for {child_sn}")
            else:
                log(f"[TEST MODE] New motherboard {batch_ts} created for {child_sn}")

        # A repeated SN is a retest only after the operator explicitly arms an
        # unresolved NG batch. Other duplicate SNs are silently ignored.
        global _active_retest_batch, _scan_retest_mode, _overtime_retest_permit, _explicit_retest_grant
        # One retest-button token is shared by scanner and CSV (OR semantics).
        # If a matching CSV arrives before a handheld scan, that CSV consumes
        # the token and identifies/arms its motherboard directly.
        if _active_retest_batch is None and _scan_retest_mode:
            selected_key = next((
                key for key, info in _pending_ng_batches.items()
                if child_sn in set(info.get("child_sns", {}).values())
            ), None)
            selected_info = _pending_ng_batches.get(selected_key, {}) if selected_key else {}
            selected_board = next((
                board for board in (selected_info.get("sn_obj") or {}).get("subBoards", [])
                if str(board.get("sn", "")).upper() == child_sn
            ), None)
            remaining = int((selected_board or {}).get("retestRemaining", 0) or 0)
            if selected_key is not None and _explicit_retest_grant:
                remaining = max(1, remaining)
            if selected_key is not None and remaining > 0:
                try:
                    started = datetime.strptime(
                        str(selected_info.get("batch_start", selected_key[1])), "%Y%m%d%H%M%S"
                    )
                    overtime = (datetime.now() - started).total_seconds() > AGING_HOURS * 3600
                except Exception:
                    overtime = False
                if overtime and not _overtime_retest_permit:
                    _scan_retest_mode = False
                    _retest_scan_ui_queue.put(("NEED_PERMISSION", str(selected_key[1]), remaining, 0, child_sn))
                    log(f"[RETEST BYPASS] CSV token rejected: overtime permission required for {child_sn}")
                    return
                _scan_retest_mode = False
                _active_retest_batch = selected_key
                _explicit_retest_grant = False
                if overtime:
                    _overtime_retest_permit = False
                log(f"[RETEST BYPASS] shared one-time token consumed by CSV {child_sn}")
            else:
                _scan_retest_mode = False
                log(f"[RETEST BYPASS] CSV token consumed but no eligible NG board: {child_sn}")
                return

        is_retest_csv = False
        if _active_retest_batch is not None:
            target = _pending_ng_batches.get(_active_retest_batch)
            target_sns = set(target.get("child_sns", {}).values()) if target else set()
            if target and child_sn in target_sns:
                batch_key = _active_retest_batch
                is_retest_csv = True
        from station_retest import is_unlimited_retest
        if not is_retest_csv and not _test_mode_enabled and not is_unlimited_retest(STATION_CODE):
            try:
                is_simulation = child_sn in _simulation_sns
                duplicate = None
                if not is_simulation:
                    with sqlite3.connect(NG_DB) as conn:
                        duplicate = conn.execute(
                            "SELECT 1 FROM all_sns WHERE sn = ? LIMIT 1", (child_sn,)
                        ).fetchone()
                    if not duplicate:
                        try:
                            duplicate = (1,) if mes_sn_is_duplicate(child_sn) else None
                        except Exception as exc:
                            # Offline fallback: local registry continues to
                            # protect the station; MES performs the final atomic
                            # check when the durable event is delivered.
                            log(f"[DUP CHECK] MES unavailable, local fallback: {exc}")
                if duplicate:
                    log(f"[DUP] Duplicate SN detected: {child_sn}")
                    _duplicate_alarm_queue.put(child_sn)
                    _enqueue("DUPLICATE_SN", child_sn, {
                        "pcbSerial": child_sn,
                        "batchId": batch_ts,
                        "result": result,
                        "eventType": "ict_duplicate",
                    })
                    return
                if is_simulation:
                    log(f"[TEST] DUP check bypassed for simulated SN: {child_sn}")
            except Exception:
                pass

        # UI-FIRST PIPELINE: render every valid CSV immediately. Persistence,
        # MES delivery and directory bookkeeping must never delay the board UI.
        _update_or_create_slot(batch_key, child_sn, result, ts_int, slot_hint)
        _push_partial_batch_to_ui(batch_key)

        # Collect all files with same prefix+timestamp (same mother board batch)
        batch_files = []
        try:
            all_files = os.listdir(WATCH_DIR)
            for f in all_files:
                p = _parse_batch_from_fname(f)
                if p and (p[1], p[2]) == (prefix, batch_ts):
                    batch_files.append(p)
        except Exception as e:
            log(f"[CSV DIR ERR] {e}")

        log(f"[CSV] {fname} → batch {batch_ts} has {len(batch_files)}/{declared_slot_count} files")

        # Update or create pending entry keyed by batch_key
        current_count = len(_pending_ng_batches[batch_key].get("child_sns", {}))
        log(f"[CSV DISPLAY] {fname} -> batch {batch_ts} {current_count}/{declared_slot_count}")
        try:
            slot = next((s for s, sn in _pending_ng_batches[batch_key]["child_sns"].items()
                         if sn == child_sn), 0)
            if not is_retest_csv:
                # Only the initial scan belongs in the unique-SN registry.
                # Retest reads update ng_boards history but must not create
                # additional all_sns rows or affect duplicate statistics.
                save_sn(child_sn, str(batch_key[1]), slot, result)
                _enqueue("STATION_TEST_RESULT" if _test_mode_enabled else "SN_SCAN", child_sn, {
                    "pcbSerial": child_sn,
                    "batchId": str(batch_key[1]),
                    "slot": slot,
                    "result": result,
                    "eventType": "ict_csv",
                    "testTime": mes_source_time(batch_ts),
                    "testMode": bool(_test_mode_enabled),
                    "latestResultOnly": bool(_test_mode_enabled),
                })
            else:
                log(f"[RETEST] SN registry bypass: {child_sn}")
        except Exception as e:
            log(f"[DB ERR] save_sn: {e}")

        # Track files for this batch. A normal test is a complete 12-board
        # motherboard. A scanner-armed retest may contain only the one or few
        # child boards actually placed on the tester; collect those reports for
        # 12 seconds from the first CSV and then close this single retest.
        p = _pending_ng_batches.get(batch_key)
        if p:
            if p.get("_current_batch_ts") != batch_ts:
                p["_current_batch_ts"] = batch_ts
                p["_current_batch_files"] = 0
                is_partial_retest = is_retest_csv
                p["_expected_files"] = None if is_partial_retest else declared_slot_count
                p["_declared_slot_count"] = declared_slot_count
                p["_current_test_started"] = True
                p["is_pushed"] = False
                p["test_count"] = p.get("test_count", 0) + 1
                if is_partial_retest:
                    threading.Timer(
                        12.0, self._finalize_partial_retest,
                        args=(batch_key, batch_ts),
                    ).start()
                    log(f"[RETEST] 12-second CSV collection opened for batch {batch_key[1]}")
            p["_current_batch_files"] = p.get("_current_batch_files", 0) + 1

        # Finalize when all files for this batch have arrived
        p = _pending_ng_batches.get(batch_key)
        if p:
            expected_files = p.get("_expected_files", 12)
            actual_files = p.get("_current_batch_files", 0)
            if expected_files is not None and actual_files >= expected_files and not p.get("is_pushed"):
                p["is_pushed"] = True
                _finalize_batch(batch_key)
                if is_retest_csv and _active_retest_batch == batch_key:
                    _active_retest_batch = None
                    log(f"[RETEST] Batch {batch_key[1]} retest completed")

    @staticmethod
    def _finalize_partial_retest(batch_key, report_batch_ts):
        """Finish one scanner-armed partial retest after its 12-second window."""
        global _active_retest_batch
        p = _pending_ng_batches.get(batch_key)
        if not p or p.get("_current_batch_ts") != report_batch_ts or p.get("is_pushed"):
            return
        received = int(p.get("_current_batch_files", 0))
        if received <= 0:
            return
        p["is_pushed"] = True
        _finalize_batch(batch_key)
        if _active_retest_batch == batch_key:
            _active_retest_batch = None
        log(f"[RETEST] Partial retest completed: batch={batch_key[1]}, CSV={received}")


# ── Bootstrap ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import tkinter as tk
    from tkinter import scrolledtext, ttk, messagebox, simpledialog
    from station_i18n import TrilingualController

    # OS-level single-instance guard. The previous tasklist check cannot see
    # Python/EXE command lines reliably and allowed duplicate agents.
    import ctypes
    _instance_mutex = ctypes.windll.kernel32.CreateMutexW(
        None, False, "Global\\Ruijing_MANUAL_ICT_Agent_Station91"
    )
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(
            None, "ICT Agent 已经在运行。", "ICT Agent", 0x40
        )
        sys.exit(0)

    # Kill existing agent instances (only one allowed)
    import subprocess
    try:
        result = subprocess.run(['tasklist'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'python' in line.lower() and 'ict_agent' in line.lower():
                pid = int(line.split()[1])
                if pid == os.getpid():
                    continue
                try:
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
                    print(f"Killed existing agent PID {pid}")
                except:
                    pass
    except:
        pass

    root = tk.Tk()
    _ict_root_ref[0] = root
    # Route every system-wide scanner event into the ICT station handler.
    # The common listener observes keyboard-wedge scanners without stealing
    # input from the operator's active application.
    COMMON_AGENT.bind_ui_root(
        root,
        lambda value, scanner_id="common-scanner": post_sn_scan(str(value)),
    )
    print(f"[COMMON_AGENT] {COMMON_AGENT.identity()}")
    # When supervised by the Qt/WebGL station shell, keep the proven Tk event
    # loop alive for production callbacks but do not expose the legacy flat UI.
    # CSV, scanner, SQLite, alarms and MES outbox continue independently.
    if os.environ.get("ICT_EMBEDDED_ENGINE", "").strip() == "1":
        root.withdraw()
    root.title(f"ICT Agent — {STATION_CODE}")
    root.geometry("1280x720")
    root.minsize(900, 620)
    root.configure(bg="#070d18")
    top_banner = tk.Frame(root, bg="#0b1f35", height=64)
    top_banner.pack(fill="x")
    top_banner.pack_propagate(False)
    # Keep shared controls visible in the ICT toolbar. Otherwise the repair
    # component is packed below the expanding workspace and can be invisible.
    root._repair_host = top_banner
    ui_language = {"code": "zh"}
    language_bridge = {"controller": None}
    UI_TEXT = {
        "zh": {"subtitle": "CSV实时检测 | 12片母板 | MES同步", "status": "AGENT 状态", "mother": "母板编号", "scanner": "扫码枪：等待扫描", "mirror": "ICT · 3D 实时同步", "dup_title": "发现重复编码", "dup_ban": "禁止重复编码离开本站", "release": "解除报警"},
        "en": {"subtitle": "LIVE CSV | 12-BOARD PANEL | MES SYNC", "status": "AGENT STATUS", "mother": "MOTHERBOARD", "scanner": "SCANNER: WAITING", "mirror": "ICT · 3D LIVE SYNC", "dup_title": "DUPLICATE CODE FOUND", "dup_ban": "DUPLICATE PRODUCT MUST NOT LEAVE", "release": "QUICK RELEASE"},
        "vi": {"subtitle": "CSV THỜI GIAN THỰC | BO 12 MẠCH | ĐỒNG BỘ MES", "status": "TRẠNG THÁI AGENT", "mother": "MÃ BO MẸ", "scanner": "MÁY QUÉT: ĐANG CHỜ", "mirror": "ICT · ĐỒNG BỘ 3D", "dup_title": "PHÁT HIỆN MÃ TRÙNG", "dup_ban": "CẤM SẢN PHẨM TRÙNG RỜI TRẠM", "release": "TẮT CẢNH BÁO"},
    }
    def _T(key): return UI_TEXT[ui_language["code"]].get(key, key)
    tk.Label(top_banner, text="RUIJING  ·  ICT STATION",
             font=("Segoe UI", 20, "bold"), bg="#0b1f35", fg="#e0f2fe").pack(side="left", padx=20)
    _heartbeat_label = tk.Label(top_banner, text="♥ OFFLINE", font=("Segoe UI", 11, "bold"),
                                     bg="#0b1f35", fg="#ef4444")
    _heartbeat_label.pack(side="left", padx=12)
    language_frame = tk.Frame(top_banner, bg="#0b1f35")
    language_frame.place(relx=1.0, x=-10, y=14, anchor="ne")
    def _set_language(code):
        ui_language["code"] = code if code in UI_TEXT else "zh"
        banner_subtitle.config(text=_T("subtitle"))
        status_title_label.config(text=_T("status"))
        mother_title_label.config(text=_T("mother"))
        scanner_var.set(_T("scanner"))
        try:
            mirror_title_label.config(text=_T("mirror"))
        except Exception:
            pass
        if language_bridge["controller"] is not None:
            language_bridge["controller"].set(ui_language["code"])
    for language_code, language_text in (("zh", "中"), ("en", "EN"), ("vi", "VI")):
        tk.Button(language_frame, text=language_text,
                  command=lambda code=language_code: _set_language(code),
                  font=("Segoe UI", 9, "bold"), bg="#164e63", fg="white",
                  activebackground="#0891b2", relief="flat", padx=7, pady=3
                  ).pack(side="left", padx=2)
    banner_subtitle = tk.Label(top_banner, text=_T("subtitle"),
             font=("Microsoft YaHei UI", 11), bg="#0b1f35", fg="#7dd3fc")
    banner_subtitle.pack(side="right", padx=165)

    status_cards = tk.Frame(root, bg="#070d18", padx=8, pady=7)
    status_cards.pack(fill="x")

    # Status bar
    status_var = tk.StringVar(value="⚡ 运行中")
    status_card = tk.Frame(status_cards, bg="#10243b", highlightbackground="#22c55e", highlightthickness=1)
    status_card.pack(side="left", fill="both", expand=True, padx=4)
    status_title_label = tk.Label(status_card, text=_T("status"), font=("Segoe UI", 9, "bold"), bg="#10243b", fg="#94a3b8")
    status_title_label.pack(pady=(6, 0))
    tk.Label(status_card, textvariable=status_var, font=("Microsoft YaHei UI", 14, "bold"), bg="#10243b", fg="#22c55e").pack(pady=(0, 6))

    # Mother board ID - BIG and prominent
    mother_board_var = tk.StringVar(value="无主板")
    mother_card = tk.Frame(status_cards, bg="#10243b", highlightbackground="#fbbf24", highlightthickness=1)
    mother_card.pack(side="left", fill="both", expand=True, padx=4)
    mother_title_label = tk.Label(mother_card, text=_T("mother"), font=("Segoe UI", 9, "bold"), bg="#10243b", fg="#94a3b8")
    mother_title_label.pack(pady=(6, 0))
    mother_board_label = tk.Label(mother_card, textvariable=mother_board_var, font=("Consolas", 16, "bold"),
                                  fg="#fbbf24", bg="#0f172a", padx=20, pady=5)
    mother_board_label.pack(pady=(0, 5))

    # Board info (batch)
    board_var = tk.StringVar(value="")
    tk.Label(root, textvariable=board_var, font=("Arial", 10),
             fg="#38bdf8").pack()

    scanner_var = tk.StringVar(value="扫码枪：等待扫描")
    scanner_label = tk.Label(
        status_cards, textvariable=scanner_var, font=("Microsoft YaHei UI", 13, "bold"),
        fg="#67e8f9", bg="#083344", padx=16, pady=6,
        relief="groove", bd=1,
    )
    scanner_label.pack(side="left", fill="both", expand=True, padx=4)

    # Match the useful part of the 3D shell: an operator-visible scanner field
    # and a clear MES authority indicator. This remains an auxiliary identity
    # scan only; CSV files are still the sole source of ICT test results.
    scan_control = tk.LabelFrame(
        root, text=" SN DATA / 扫描 SN ",
        bg="#083344", fg="#e0f2fe", bd=1, relief="solid",
        font=("Microsoft YaHei UI", 10, "bold"),
    )
    scan_control.pack(fill="x", padx=12, pady=(0, 6))
    from station_arrival_ui import ProductGateComponent
    product_gate = ProductGateComponent(root, enabled=False, backend_note="ICT arrival/route backend not integrated")
    tk.Label(scan_control, text="扫码 SN / SCAN SN", bg="#083344", fg="#67e8f9",
             font=("Microsoft YaHei UI", 10, "bold")).pack(side="left", padx=(10, 6))
    visible_scan_var = tk.StringVar()
    visible_scan_entry = tk.Entry(
        scan_control, textvariable=visible_scan_var,
        font=("Consolas", 15, "bold"), justify="center",
        bg="#fff7c2", fg="#111827", insertbackground="#111827",
        relief="solid", bd=1,
    )
    visible_scan_entry.pack(side="left", fill="x", expand=True, padx=5, pady=6, ipady=3)
    if register_scanner_entry is not None:
        register_scanner_entry(root, visible_scan_entry)

    def _submit_visible_scan(_event=None):
        raw_value = _event if isinstance(_event, str) else visible_scan_var.get()
        sn = str(raw_value or "").strip().upper()
        visible_scan_var.set(sn)
        if sn:
            board_var.set(f"SN DATA: {sn}")
            classification = classify_scanned_sn(sn)
            if classification == "NG":
                scanner_var.set(f"NG / 不良: {sn}")
                scanner_label.config(bg="#991b1b", fg="white")
            elif classification == "DUP":
                scanner_var.set(f"DUPLICATE / 重复: {sn}")
                scanner_label.config(bg="#92400e", fg="white")
            elif classification == "NEW":
                scanner_var.set(f"NEW SN / 新码: {sn}")
                scanner_label.config(bg="#065f46", fg="white")
            scanner_var.set(f"SCAN RECEIVED / 已收到: {sn}")
        if not is_valid_scanner_sn(sn):
            scanner_var.set(f"扫码无效：{sn or 'EMPTY'} · 需要10位产品SN")
            scanner_label.config(bg="#7f1d1d", fg="white")
        else:
            allowed, verdict = mes_scan_gate(MES_URL, STATION_CODE, sn,
                event_type="ict_physical_scanner", retestAuthorized=bool(_scan_retest_mode))
            # MES outage must not prevent the station from accepting a local
            # scanner input.  Local SQLite still performs NG/DUP detection;
            # the MES outbox retries synchronization when the API returns.
            code = str(verdict.get("code") or "") if isinstance(verdict, dict) else ""
            if allowed or code == "MES_GUARD_UNAVAILABLE":
                if not allowed:
                    log(f"[MES OFFLINE] local scan accepted for SQLite NG/DUP handling: {sn}")
                post_sn_scan(sn)
            else:
                code = code or "MES_GUARD_REJECTED"
                scanner_var.set(f"MES禁止扫码：{code} · {sn}")
                scanner_label.config(bg="#7f1d1d", fg="white")
                log(f"[MES FAIL-CLOSED] scanner block {sn}: {verdict}")
        visible_scan_entry.focus_set()

    visible_scan_entry.bind("<Return>", _submit_visible_scan)
    visible_scan_entry.bind("<KP_Enter>", _submit_visible_scan)
    _scanner_entry_ref[0] = visible_scan_entry
    _scanner_submit_ref[0] = _submit_visible_scan
    root.after(300, visible_scan_entry.focus_set)
    tk.Button(scan_control, text="确认扫码", command=_submit_visible_scan,
              bg="#0369a1", fg="white", font=("Microsoft YaHei UI", 10, "bold"),
              padx=12).pack(side="left", padx=6, pady=5)
    mes_authority_var = tk.StringVar(value="● MES 正在连接")
    mes_authority_label = tk.Label(scan_control, textvariable=mes_authority_var,
                                   bg="#083344", fg="#fbbf24",
                                   font=("Microsoft YaHei UI", 10, "bold"))
    mes_authority_label.pack(side="right", padx=12)

    # Retest remaining for whole mother board
    retest_var = tk.StringVar(value="")
    retest_label = tk.Label(root, textvariable=retest_var, font=("Arial", 12, "bold"),
                            fg="#fbbf24", bg="#0f172a")
    retest_label.pack(pady=(0, 5))

    # Keep station actions in one compact horizontal toolbar.
    controls_frame = tk.Frame(root, bg="#0b1728", highlightbackground="#1e3a5f", highlightthickness=1)
    controls_frame.pack(fill="x", padx=8, pady=(0, 8))

    test_mode_var = tk.StringVar(value="取消测试模式（当前：测试模式）")

    def _toggle_test_mode():
        global _test_mode_enabled, _active_retest_batch, _scan_retest_mode
        _test_mode_enabled = not _test_mode_enabled
        _active_retest_batch = None
        _scan_retest_mode = False
        try:
            _persist_test_mode(_test_mode_enabled)
        except Exception as exc:
            log(f"[TEST MODE] Cannot persist selected mode: {exc}")
        if _test_mode_enabled:
            test_mode_var.set("取消测试模式（当前：测试模式）")
            test_mode_button.configure(bg="#16a34a", activebackground="#15803d")
            retest_var.set("测试模式已开启：不检查重码，只保存最后结果")
            log("[TEST MODE] Enabled: unlimited tests, DUP disabled, latest result wins")
        else:
            test_mode_var.set("开启测试模式（当前：正常模式）")
            test_mode_button.configure(bg="#475569", activebackground="#334155")
            retest_var.set("正常生产模式：首次测试 + 最多两次复测")
            log("[TEST MODE] Disabled: normal production rules restored")

    test_mode_button = tk.Button(
        controls_frame, textvariable=test_mode_var, command=_toggle_test_mode,
        bg="#16a34a", activebackground="#15803d", fg="white",
        font=("Microsoft YaHei UI", 10, "bold"), relief="flat",
        padx=12, pady=5,
    )
    test_mode_button.pack(side="left", padx=4, pady=5)

    mes_box_cache = {}
    embedded_detail_views = {}
    def _show_mes_box(title, cache_key):
        if cache_key in embedded_detail_views:
            _render_embedded_motherboards(cache_key)
            workspace_notebook.select(embedded_detail_views[cache_key]["tab"])
            return
        rows = list(mes_box_cache.get(cache_key, []))
        window = tk.Toplevel(root)
        window.title(f"{title} · MES 母板详情")
        window.geometry("1080x650")
        window.configure(bg="#07111f")

        layouts = {}
        for row in rows:
            children = next((row.get(key) for key in ("subBoards", "members", "boards")
                             if isinstance(row.get(key), list)), None)
            children = children or [row]
            batch_id = str(row.get("batchId") or row.get("mainSn") or "")
            for child in children:
                child_batch = str(child.get("batchId") or batch_id or child.get("mainSn") or "UNKNOWN")
                layouts.setdefault(child_batch, {})[int(child.get("slot") or len(layouts.get(child_batch, {})) + 1)] = child

        summary = tk.Frame(window, bg="#0b1f35", padx=16, pady=11)
        summary.pack(fill="x")
        tk.Label(summary, text=title, bg="#0b1f35", fg="#7dd3fc",
                 font=("Microsoft YaHei UI", 18, "bold")).pack(side="left")
        tk.Label(summary, text=f"{len(layouts)} 块母板 / {sum(len(v) for v in layouts.values())} 个子板",
                 bg="#0b1f35", fg="#cbd5e1", font=("Microsoft YaHei UI", 11, "bold")).pack(side="right")

        canvas = tk.Canvas(window, bg="#07111f", highlightthickness=0)
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="#07111f")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", width=1040)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

        if not layouts:
            tk.Label(content, text="暂无 MES 母板记录", bg="#07111f", fg="#64748b",
                     font=("Microsoft YaHei UI", 16, "bold"), pady=80).pack(fill="x")
        for batch_id, members in layouts.items():
            card = tk.Canvas(content, height=244, bg="#0b1b2d", highlightbackground="#334155",
                             highlightthickness=1)
            card.pack(fill="x", padx=8, pady=7)
            card.create_text(13, 16, text=f"母板 {batch_id}", anchor="w", fill="#7dd3fc",
                             font=("Consolas", 12, "bold"))
            for slot in range(1, 13):
                member = members.get(slot, {})
                result = str(member.get("result") or member.get("overallResult") or "EMPTY").upper()
                failed = result in ("FAIL", "NG", "CONFIRMED_NG")
                passed = result in ("PASS", "OK")
                background = "#7f1d1d" if failed else ("#064e3b" if passed else "#1e293b")
                border = "#ef4444" if failed else ("#22c55e" if passed else "#475569")
                column, row_index = (slot - 1) % 4, (slot - 1) // 4
                x1, y1 = 12 + column * 252, 36 + row_index * 68
                x2, y2 = x1 + 242, y1 + 60
                card.create_rectangle(x1, y1, x2, y2, fill=background, outline=border, width=2)
                card.create_text(x1 + 8, y1 + 10, text=f"#{slot}   {result}", anchor="w",
                                 fill="white", font=("Consolas", 9, "bold"))
                card.create_text(x1 + 8, y1 + 29, text=str(member.get("sn") or "—"), anchor="w",
                                 fill="#e2e8f0", font=("Consolas", 9))
                card.create_text(x1 + 8, y1 + 47,
                                 text=f"测试 {member.get('testCount', 0)} · 剩余 {member.get('retestRemaining', 0)}",
                                 anchor="w", fill="#cbd5e1", font=("Microsoft YaHei UI", 8))

    def _bind_box_contents(widget, title, cache_key):
        callback = lambda _event, name=title, key=cache_key: _show_mes_box(name, key)
        widget.bind("<Button-1>", callback)
        widget.configure(cursor="hand2")
        for child in widget.winfo_children():
            child.bind("<Button-1>", callback)
            child.configure(cursor="hand2")

    def _compact_box(parent, title, color, count_var, cache_key):
        box = tk.Frame(parent, bg="#10243b", highlightbackground=color,
                       highlightthickness=2, padx=7, pady=5)
        box.pack(side="left", fill="x", expand=True, padx=3)
        tk.Label(box, text="▦", bg="#10243b", fg=color,
                 font=("Segoe UI Symbol", 16, "bold")).pack(side="left", padx=(0, 5))
        tk.Label(box, text=title, bg="#10243b", fg=color,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(box, textvariable=count_var, bg=color, fg="white", width=3,
                 font=("Segoe UI", 9, "bold")).pack(side="right", padx=(5, 0))
        _bind_box_contents(box, title, cache_key)

    def _is_ict_repair_revival_order(row):
        """ICT handover UI only receives revival orders returned by maintenance."""
        destination_type = str(row.get("destinationType", "")).strip().upper()
        source_station = str(row.get("sourceStation", "")).strip().lower()
        destination_station = str(row.get("destinationStation", "")).strip().lower()
        return (
            destination_type == "REPAIR_RETURN"
            and destination_station == STATION_CODE.lower()
            and source_station in {"manu_rework", "maintenance", "repair", "repair_center"}
        )

    def _show_handover_sheet():
        window = tk.Toplevel(root)
        window.title("维修复活接收单 / REPAIR REVIVAL ORDER")
        window.geometry("1080x540")
        tree = ttk.Treeview(window, columns=("id","batch","source","destination","members","status","sent","received","accepted"), show="headings")
        labels = (("id","交接单号"),("batch","整盘编号"),("source","来源工位"),("destination","目标工位"),
                  ("members","SN数量"),("status","交接状态"),("sent","送出时间"),("received","接收时间"),("accepted","接收人/扫码枪"))
        for key, label in labels: tree.heading(key, text=label)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        try:
            url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=manu_ict")
            with urllib.request.urlopen(url, timeout=5) as response:
                rows = [
                    row for row in json.loads(response.read().decode("utf-8")).get("items", [])
                    if _is_ict_repair_revival_order(row)
                ]
            for row in rows:
                tree.insert("", "end", values=(row.get("transferId",""), row.get("batchId",""), row.get("sourceStation",""),
                    row.get("destinationStation",""), row.get("memberCount",""), row.get("status",""),
                    row.get("sentAt",""), row.get("receivedAt",""), row.get("acceptedBy","")))
        except Exception as exc:
            tree.insert("", "end", values=("MES连接失败", str(exc), "", "", "", "", "", "", ""))

    ict_box_vars = {key: tk.StringVar(value="0") for key in ("ng", "first_retest", "pass", "confirmed", "aged")}
    ict_boxes = tk.Frame(root, bg="#07111f", padx=8, pady=5)
    ict_boxes.pack(fill="x", padx=8, pady=(0, 7))
    # ICT has no physical box workflow. Show only motherboard result groups;
    # retest/confirmed/aged classifications remain MES audit attributes.
    for key, title, color in (("pass", "PASS 母板", "#22c55e"),
                              ("confirmed", "NG 母板", "#ef4444")):
        _compact_box(ict_boxes, title, color, ict_box_vars[key], f"ict:{key}")

    depanel_box_vars = {key: tk.StringVar(value="0") for key in ("ICT_ONLY_NG", "FCT_ONLY_NG", "ICT_FCT_NG")}
    # Depanel classification is MES-owned and is intentionally not rendered at
    # ICT. The variables remain so the background synchronization contract is
    # unchanged and the depanel station can display its own three NG classes.

    # Compact station-side mirror of the authoritative MES/3D ICT data.
    # It never calculates a competing copy; it reads station_bucket_snapshots
    # from the same API used by every 3D browser.
    ict_mirror = tk.Toplevel(root)
    ict_mirror.title("3D ICT 同步窗口")
    ict_mirror.geometry("460x390+20+40")
    ict_mirror.minsize(420, 340)
    ict_mirror.configure(bg="#07111f")
    ict_mirror.attributes("-topmost", False)
    ict_mirror.protocol("WM_DELETE_WINDOW", ict_mirror.withdraw)
    ict_mirror.withdraw()

    mirror_status_var = tk.StringVar(value="● 正在连接 MES...")
    mirror_counts = {
        "pass": tk.StringVar(value="0"),
        "pending": tk.StringVar(value="0"),
        "confirmed": tk.StringVar(value="0"),
        "dup": tk.StringVar(value="0"),
    }
    mirror_latest_var = tk.StringVar(value="等待 ICT 数据")
    mirror_header = tk.Frame(ict_mirror, bg="#0b1f35", padx=14, pady=10)
    mirror_header.pack(fill="x")
    mirror_title_label = tk.Label(mirror_header, text=_T("mirror"), font=("Microsoft YaHei UI", 18, "bold"),
             bg="#0b1f35", fg="#e0f2fe")
    mirror_title_label.pack(anchor="w")
    tk.Label(mirror_header, text=f"数据源 / SOURCE: CSV · {WATCH_DIR}", font=("Consolas", 9),
             bg="#0b1f35", fg="#a7f3d0").pack(anchor="w", pady=(2,0))
    mirror_status_label = tk.Label(mirror_header, textvariable=mirror_status_var,
                                   font=("Microsoft YaHei UI", 10, "bold"),
                                   bg="#0b1f35", fg="#fbbf24")
    mirror_status_label.pack(anchor="w", pady=(3, 0))

    mirror_drag = {"x": 0, "y": 0}
    def _mirror_drag_start(event):
        mirror_drag["x"] = event.x_root - ict_mirror.winfo_x()
        mirror_drag["y"] = event.y_root - ict_mirror.winfo_y()

    def _mirror_drag_move(event):
        x = event.x_root - mirror_drag["x"]
        y = event.y_root - mirror_drag["y"]
        max_x = max(0, ict_mirror.winfo_screenwidth() - ict_mirror.winfo_width())
        max_y = max(0, ict_mirror.winfo_screenheight() - ict_mirror.winfo_height())
        ict_mirror.geometry(f"+{min(max(x, 0), max_x)}+{min(max(y, 0), max_y)}")

    for drag_widget in (mirror_header, *mirror_header.winfo_children()):
        drag_widget.bind("<ButtonPress-1>", _mirror_drag_start)
        drag_widget.bind("<B1-Motion>", _mirror_drag_move)

    cards = tk.Frame(ict_mirror, bg="#07111f", padx=10, pady=10)
    cards.pack(fill="x")
    for index, (key, title, color) in enumerate((
        ("pass", "PASS", "#22c55e"),
        ("pending", "待复测 NG", "#f59e0b"),
        ("confirmed", "确认 NG", "#ef4444"),
        ("dup", "重码", "#a855f7"),
    )):
        card = tk.Frame(cards, bg="#10243b", highlightbackground=color, highlightthickness=1,
                        padx=8, pady=8)
        card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=5, pady=5)
        tk.Label(card, text=title, font=("Microsoft YaHei UI", 10, "bold"),
                 bg="#10243b", fg="#cbd5e1").pack()
        tk.Label(card, textvariable=mirror_counts[key], font=("Segoe UI", 26, "bold"),
                 bg="#10243b", fg=color).pack()
    cards.grid_columnconfigure(0, weight=1)
    cards.grid_columnconfigure(1, weight=1)

    latest_card = tk.Frame(ict_mirror, bg="#10243b", padx=12, pady=10)
    latest_card.pack(fill="both", expand=True, padx=15, pady=(0, 12))
    tk.Label(latest_card, text="3D ICT BOX · 最新内容", font=("Microsoft YaHei UI", 11, "bold"),
             bg="#10243b", fg="#7dd3fc").pack(anchor="w")
    tk.Label(latest_card, textvariable=mirror_latest_var, justify="left", anchor="nw",
             font=("Consolas", 10), bg="#10243b", fg="#e2e8f0", wraplength=410
             ).pack(fill="both", expand=True, pady=(7, 0))

    def _show_ict_mirror():
        ict_mirror.deiconify()
        ict_mirror.lift()

    _removed_mirror_button = tk.Button(controls_frame, text="3D ICT 同步窗口", command=_show_ict_mirror,
              font=("Microsoft YaHei UI", 10, "bold"), bg="#0369a1", fg="white",
              activebackground="#075985", relief="flat", padx=10, pady=5
              )

    def _apply_mirror_snapshot(items):
        buckets = {item.get("bucketName"): item.get("payload", []) for item in items
                   if item.get("stationCode") == STATION_CODE}
        passed = buckets.get("pass", []) or []
        pending = buckets.get("pending_ng", []) or []
        confirmed = buckets.get("confirmed_ng", []) or []
        stats_rows = buckets.get("stats", []) or []
        stats = stats_rows[0] if stats_rows else {}
        mirror_counts["pass"].set(str(len(passed)))
        mirror_counts["pending"].set(str(len(pending)))
        mirror_counts["confirmed"].set(str(len(confirmed)))
        mirror_counts["dup"].set(str(int(stats.get("dup", 0) or 0)))
        # Aging is an additional warning state, not a reason to remove a
        # motherboard from its operational NG/retest box.
        ict_box_vars["ng"].set(str(sum(1 for row in pending if int(row.get("testCount", 1) or 1) <= 1)))
        ict_box_vars["first_retest"].set(str(sum(1 for row in pending if int(row.get("testCount", 1) or 1) == 2)))
        ict_box_vars["pass"].set(str(len({str(row.get('batchId') or row.get('mainSn') or row.get('sn')) for row in passed})))
        ict_box_vars["confirmed"].set(str(len({str(row.get('batchId') or row.get('mainSn') or row.get('sn')) for row in confirmed})))
        ict_box_vars["aged"].set(str(sum(1 for row in pending + confirmed if row.get("isAged"))))
        mes_box_cache["ict:ng"] = [row for row in pending if int(row.get("testCount", 1) or 1) <= 1]
        mes_box_cache["ict:first_retest"] = [row for row in pending if int(row.get("testCount", 1) or 1) == 2]
        mes_box_cache["ict:pass"] = passed
        mes_box_cache["ict:confirmed"] = confirmed
        mes_box_cache["ict:aged"] = [row for row in pending + confirmed if row.get("isAged")]
        recent = sorted(
            [(row.get("time", 0), "PASS", row.get("sn", "")) for row in passed] +
            [(row.get("time", 0), "NG", row.get("sn", "")) for row in pending] +
            [(row.get("time", 0), "CONFIRMED", row.get("sn", "")) for row in confirmed],
            reverse=True,
        )[:8]
        mirror_latest_var.set("\n".join(f"{kind:<10} {sn}" for _, kind, sn in recent) or "暂无 ICT 数据")
        mirror_status_var.set("● MES 已连接 · 与3D数据一致")
        mirror_status_label.config(fg="#22c55e")
        mes_authority_var.set("● MES 已接管 · 2D/3D 同步")
        mes_authority_label.config(fg="#22c55e")
        depanel_pending = next((item.get("payload", []) for item in items
                                if item.get("stationCode") == "manu_depanel" and item.get("bucketName") == "pending_ng"), []) or []
        for code, variable in depanel_box_vars.items():
            matching = [row for row in depanel_pending if row.get("defectCode") == code]
            variable.set(str(len(matching)))
            mes_box_cache[f"depanel:{code}"] = matching

    _mes_box_updates = queue.Queue(maxsize=2)

    def _queue_mes_snapshot(rows):
        while not _mes_box_updates.empty():
            try:
                _mes_box_updates.get_nowait()
            except queue.Empty:
                break
        try:
            _mes_box_updates.put_nowait(rows)
        except queue.Full:
            pass

    def _mirror_worker():
        snapshot_url = MES_URL.replace("/api/pda/events", "/api/station/bucket-snapshots")
        while True:
            try:
                with urllib.request.urlopen(snapshot_url, timeout=4) as response:
                    data = json.loads(response.read().decode("utf-8"))
                _queue_mes_snapshot(data.get("items", []))
            except Exception:
                root.after(0, lambda: (
                    mirror_status_var.set("● MES 离线 · 保留最后数据"),
                    mirror_status_label.config(fg="#ef4444"),
                    mes_authority_var.set("● MES 离线 · 禁止交接放行"),
                    mes_authority_label.config(fg="#ef4444"),
                ))
            time.sleep(3)

    def _mes_push_worker():
        """Receive MES bucket broadcasts; polling remains the reconnect fallback."""
        stream_url = MES_URL + "?node=manu_ict_agent&types=BUCKET_SNAPSHOT_UPDATE&replay=0"
        while True:
            try:
                with urllib.request.urlopen(stream_url, timeout=45) as stream:
                    for raw_line in stream:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data:"):
                            continue
                        event = json.loads(line[5:].strip())
                        if event.get("type") != "BUCKET_SNAPSHOT_UPDATE":
                            continue
                        payload = event.get("payload") or {}
                        if payload.get("stationCode") != STATION_CODE:
                            continue
                        snapshot_url = MES_URL.replace("/api/pda/events", "/api/station/bucket-snapshots")
                        with urllib.request.urlopen(snapshot_url, timeout=4) as response:
                            data = json.loads(response.read().decode("utf-8"))
                        _queue_mes_snapshot(data.get("items", []))
            except Exception as exc:
                log(f"[MES PUSH] reconnecting: {exc}")
                time.sleep(2)

    def _drain_mes_box_updates():
        try:
            rows = _mes_box_updates.get_nowait()
            _apply_mirror_snapshot(rows)
        except queue.Empty:
            pass
        root.after(250, _drain_mes_box_updates)

    # The former ICT/3D mirror window is retired, but the station-side box
    # counters still use the same authoritative MES snapshots. Keep the data
    # worker running without showing the retired window.
    def _refresh_local_ict_boxes():
        """ICT owns its boxes locally; MES only receives their snapshots."""
        try:
            with sqlite3.connect(NG_DB) as conn:
                raw_batches = conn.execute(
                    "SELECT sn_obj FROM ng_batches WHERE sn_obj IS NOT NULL ORDER BY created_at,batch_id"
                ).fetchall()
                pass_rows = conn.execute(
                    "SELECT sn,scan_time,batch_id,slot,result FROM all_sns WHERE UPPER(result)='PASS' ORDER BY scan_time,sn"
                ).fetchall()
            pending, first_retest, confirmed, aged = [], [], [], []
            for (raw,) in raw_batches:
                try:
                    board = json.loads(raw)
                except Exception:
                    continue
                failed = [item for item in board.get("subBoards", [])
                          if str(item.get("result", "")).upper() == "FAIL"]
                if not failed:
                    continue
                if board.get("isAged"):
                    aged.append(board)
                if any(bool(item.get("isConfirmedNG")) for item in failed):
                    confirmed.append(board)
                elif max(int(item.get("testCount", 1) or 1) for item in failed) >= 2:
                    first_retest.append(board)
                else:
                    pending.append(board)
            passed = [{"sn": row[0], "time": row[1], "batchId": row[2],
                       "slot": row[3], "result": row[4]} for row in pass_rows]
            local_sets = {"ng": pending, "first_retest": first_retest,
                          "pass": passed, "confirmed": confirmed, "aged": aged}
            for key, records in local_sets.items():
                if key in ("pass", "confirmed"):
                    count = len({str(row.get("batchId") or row.get("mainSn") or row.get("sn")) for row in records})
                else:
                    count = len(records)
                ict_box_vars[key].set(str(count))
                mes_box_cache[f"ict:{key}"] = records
        except Exception as exc:
            log(f"[LOCAL BOX] refresh failed: {exc}")
        root.after(1000, _refresh_local_ict_boxes)

    root.after(100, _refresh_local_ict_boxes)

    # Duplicate alarm is local to the ICT station and remains active until the
    # operator explicitly releases it. Releasing only silences the alarm; it
    # never removes the duplicate record or allows the CSV to be accepted.
    duplicate_alarm_active = {"value": False, "flash": False, "sns": []}
    ng_alarm_active = {"value": False, "sns": []}
    active_alarm_window = {"window": None, "flash_job": None, "voice_job": None, "flash_on": False}
    duplicate_alarm_var = tk.StringVar(value="")
    duplicate_alarm_label = tk.Label(
        root, textvariable=duplicate_alarm_var,
        font=("Microsoft YaHei UI", 14, "bold"),
        fg="white", bg="#0f172a", padx=12, pady=6,
    )
    duplicate_alarm_label.pack(fill="x", padx=8, pady=(0, 5))

    def _close_alarm_window():
        for job_name in ("flash_job", "voice_job"):
            job = active_alarm_window.get(job_name)
            if job is not None:
                try:
                    root.after_cancel(job)
                except Exception:
                    pass
                active_alarm_window[job_name] = None
        win = active_alarm_window.get("window")
        if win is not None:
            try:
                if win.winfo_exists():
                    win.destroy()
            except Exception:
                pass
        active_alarm_window["window"] = None
        active_alarm_window["flash_on"] = False

    def _show_alarm_window(kind, sns, release_command):
        """Large, topmost ATE-style alarm with a clean grouped-SN layout."""
        _close_alarm_window()
        sns = [str(sn).strip() for sn in sns if str(sn).strip()]
        win = tk.Toplevel(root)
        active_alarm_window["window"] = win
        is_dup = kind == "DUP"
        title = _T("dup_title") if is_dup else "NG"
        warning = _T("dup_ban") if is_dup else "NG"
        accent = "#f59e0b" if is_dup else "#ef4444"
        win.title(title)
        win.attributes("-topmost", True)
        win.attributes("-fullscreen", True)
        win.configure(bg="#160b12")
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{sw}x{sh}+0+0")
        win.bind("<F11>", lambda _event: win.attributes("-fullscreen", not win.attributes("-fullscreen")))
        win.protocol("WM_DELETE_WINDOW", lambda: None)

        header = tk.Frame(win, bg=accent, height=112)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⚠", font=("Segoe UI Symbol", 50, "bold"),
                 bg=accent, fg="white").pack(side="left", padx=(28, 12))
        title_box = tk.Frame(header, bg=accent)
        title_box.pack(side="left", fill="y")
        tk.Label(title_box, text=title, font=("Microsoft YaHei UI", 34, "bold"),
                 bg=accent, fg="white").pack(anchor="w", pady=(18, 0))
        tk.Label(title_box, text="ICT STATION  ·  CSV REAL-TIME DETECTION",
                 font=("Segoe UI", 12, "bold"), bg=accent, fg="#fff7ed").pack(anchor="w")

        body = tk.Frame(win, bg="#160b12")
        body.pack(fill="both", expand=True, padx=32, pady=24)
        tk.Label(body, text=warning, font=("Microsoft YaHei UI", 24, "bold"),
                 bg="#160b12", fg="#fecaca").pack(pady=(0, 14))

        sn_card = tk.Frame(body, bg="#2b1119", highlightbackground=accent,
                           highlightthickness=2, padx=18, pady=14)
        sn_card.pack(fill="both", expand=True)
        tk.Label(sn_card, text=f"检测数量  {len(sns)}", font=("Microsoft YaHei UI", 13, "bold"),
                 bg="#2b1119", fg="#fda4af").pack(anchor="w", pady=(0, 8))
        sn_text = tk.Text(sn_card, height=8, wrap="word", font=("Consolas", 19, "bold"),
                          bg="#12090d", fg="#ffffff", insertbackground="#ffffff",
                          relief="flat", padx=14, pady=12, spacing1=4, spacing3=4)
        sn_text.pack(fill="both", expand=True)
        rows = ["    ".join(sns[i:i + 3]) for i in range(0, len(sns), 3)]
        sn_text.insert("1.0", "\n".join(rows) if rows else "-")
        sn_text.config(state="disabled")

        footer = tk.Frame(win, bg="#0f070a", height=92)
        footer.pack(fill="x")
        footer.pack_propagate(False)
        tk.Label(footer, text="确认现场产品后解除报警  /  Verify product before release",
                 font=("Microsoft YaHei UI", 12), bg="#0f070a", fg="#cbd5e1").pack(side="left", padx=32)
        tk.Button(footer, text=_T("release"), command=release_command,
                  font=("Microsoft YaHei UI", 22, "bold"), bg="#16a34a", fg="white",
                  activebackground="#15803d", activeforeground="white", relief="flat",
                  padx=34, pady=10, cursor="hand2").pack(side="right", padx=32, pady=14)

        def _flash_modal():
            if active_alarm_window.get("window") is not win or not win.winfo_exists():
                return
            active_alarm_window["flash_on"] = not active_alarm_window["flash_on"]
            on = active_alarm_window["flash_on"]
            flash_color = "#ffffff" if on else accent
            header.config(bg=flash_color)
            for child in header.winfo_children():
                try:
                    child.config(bg=flash_color, fg=accent if on else "white")
                    for grandchild in child.winfo_children():
                        grandchild.config(bg=flash_color, fg=accent if on else "white")
                except Exception:
                    pass
            sn_card.config(highlightbackground="#ffffff" if on else accent)
            active_alarm_window["flash_job"] = root.after(420, _flash_modal)

        def _repeat_voice():
            if active_alarm_window.get("window") is not win or not win.winfo_exists():
                return
            voice_text = {
                "zh": "发现重复编码，禁止离开本站",
                "en": "Duplicate code detected. Product must not leave this station.",
                "vi": "Phát hiện mã trùng. Cấm sản phẩm rời khỏi trạm.",
            }.get(ui_language["code"], "发现重复编码，禁止离开本站")
            if not is_dup:
                voice_text = "发现不良品，需要处理"
            speak(voice_text)
            active_alarm_window["voice_job"] = root.after(4500, _repeat_voice)

        _flash_modal()
        _repeat_voice()
        win.lift()
        win.focus_force()

    def _flash_duplicate_alarm():
        if not duplicate_alarm_active["value"]:
            duplicate_alarm_label.config(bg="#0f172a")
            return
        duplicate_alarm_active["flash"] = not duplicate_alarm_active["flash"]
        duplicate_alarm_label.config(
            bg="#dc2626" if duplicate_alarm_active["flash"] else "#facc15",
            fg="white" if duplicate_alarm_active["flash"] else "#111827",
        )
        root.after(350, _flash_duplicate_alarm)

    def _start_duplicate_alarm(sn):
        sn = str(sn or "").strip()
        if sn and sn not in duplicate_alarm_active["sns"]:
            duplicate_alarm_active["sns"].append(sn)
        duplicate_alarm_var.set(
            "发现重复编码，禁止离开本站：" + "  |  ".join(duplicate_alarm_active["sns"])
        )
        if not duplicate_alarm_active["value"]:
            duplicate_alarm_active["value"] = True
            duplicate_alarm_active["flash"] = False
            _flash_duplicate_alarm()
        _show_alarm_window("DUP", duplicate_alarm_active["sns"], _release_duplicate_alarm)

    def _release_duplicate_alarm():
        released_sns = list(duplicate_alarm_active["sns"])
        duplicate_alarm_active["value"] = False
        duplicate_alarm_active["flash"] = False
        duplicate_alarm_active["sns"].clear()
        duplicate_alarm_var.set("")
        duplicate_alarm_label.config(bg="#0f172a", fg="white")
        _close_alarm_window()
        _enqueue("DUPLICATE_ALARM_RELEASE", released_sns[0] if released_sns else "", {
            "eventType": "ict_duplicate_alarm_release",
            "sns": released_sns,
            "released": True,
        })
        log("[DUP] Duplicate alarm released by operator")

    def _start_ng_alarm(info):
        sns = list((info or {}).get("sns") or [])
        if sns:
            speak(f"发现不良品，{len(sns)}个产品需要处理")
        # ICT test NG is evidence, not a line-stop alarm. Keep the red board
        # state and publish a mark-only event for MES/3D; duplicate and route
        # violations continue to use the blocking alarm workflow.
        ng_alarm_active["value"] = bool(sns)
        ng_alarm_active["sns"] = sns
        for marked_sn in sns:
            _event_queue.put({
                "type": "NG_MARKED",
                "priority": "warning",
                "stationCode": STATION_CODE,
                "payload": {
                    "sn": marked_sn,
                    "reason": "ICT_FAIL",
                    "markedAt": int(time.time() * 1000),
                    "status": "MARK_ONLY",
                },
            })
        if sns:
            _show_alarm_window("NG", sns, _release_ng_alarm)
        log(f"[NG ALARM] ICT marked {len(sns)} SN(s); full-screen warning shown")

    def _release_ng_alarm():
        ng_alarm_active["value"] = False
        ng_alarm_active["sns"].clear()
        _close_alarm_window()
        log("[NG] NG alarm released by operator")

    tk.Button(
        controls_frame, text="解除重码报警", command=_release_duplicate_alarm,
        font=("Microsoft YaHei UI", 12, "bold"), bg="#facc15", fg="#111827",
        activebackground="#fde047", relief="raised", padx=14, pady=5,
    ).pack(side="right", padx=4)

    def _arm_retest_bypass_ui():
        """Bypass duplicate detection for exactly the next complete retest batch."""
        result = arm_latest_retest()
        if result.get("ok"):
            retest_var.set(
                f"BYPASS已启动：第{result['attempt']}次，"
                f"读取实际复检子板后自动恢复正常，剩余{result['remaining']}次"
            )
        else:
            retest_var.set("没有可复测的NG母板")

    def _enable_retest_scan_mode():
        global _scan_retest_mode, _explicit_retest_grant
        _scan_retest_mode = True
        _explicit_retest_grant = True
        retest_var.set("复检扫码已启动：请扫描需要复检的NG板码")
        speak("请扫描需要复检的板码")
        log("[RETEST SCAN] waiting for NG child-board scan")

    # F6 invokes the same one-shot retest action as the visible Retest button.
    root.bind("<F6>", lambda _event: _enable_retest_scan_mode())

    def _grant_overtime_retest_permission():
        global _overtime_retest_permit
        if not messagebox.askyesno(
            "超时复检许可",
            "确认授权一次超过2小时的整盘复检？\n许可在扫码成功后自动失效。",
            icon="warning",
        ):
            return
        _overtime_retest_permit = True
        _sync_ict_process("OVERTIME_PERMISSION_GRANTED", "", 0)
        retest_var.set("已授权一次超时复检：请点击复检扫码并扫描板码")
        speak("超时复检已许可，请扫描板码")
        log("[RETEST PERMISSION] one overtime retest granted")

    tk.Button(
        controls_frame, text="确认复测", command=_enable_retest_scan_mode,
        font=("Microsoft YaHei UI", 12, "bold"), bg="#7c3aed", fg="white",
        activebackground="#6d28d9", relief="raised", padx=14, pady=5,
    ).pack(side="left", padx=4)

    route_var = tk.StringVar(value="FCT")
    route_selector = ttk.Combobox(
        controls_frame, textvariable=route_var, values=("FCT",),
        state="disabled", width=9, font=("Microsoft YaHei UI", 10),
    )
    # ICT confirmed NG has one fixed route; do not show a destination selector.

    def _confirm_ng_route():
        global _route_target_batch
        if not _route_target_batch:
            retest_var.set("当前没有等待选择去向的母板")
            return
        destination = "FCT"
        route_info = next((info for key, info in _pending_ng_batches.items()
                           if str((info.get("sn_obj") or {}).get("batchId", key[1])) == _route_target_batch), {})
        request_reason = ""
        if destination == "SCRAP_APPROVAL":
            reason_menu = "\n".join(f"{code}  {label}" for code, label in SCRAP_REASONS.items())
            reason_code = (simpledialog.askstring("MES 直接报废单",
                f"请选择并输入报废原因代码：\n\n{reason_menu}", parent=root) or "").strip().upper()
            if reason_code not in SCRAP_REASONS:
                retest_var.set("报废申请已取消：必须选择有效报废原因")
                return
            detail = ""
            if reason_code in {"S16", "S17", "S18", "S19", "S99"}:
                detail = (simpledialog.askstring("报废原因说明",
                    "请输入责任人、设备编号、发生过程及详细说明（必填）：", parent=root) or "").strip()
                if not detail:
                    retest_var.set("报废申请已取消：该原因必须填写详细说明")
                    return
            request_reason = f"{reason_code} {SCRAP_REASONS[reason_code]}" + (f"：{detail}" if detail else "")
        _event_queue.put({
            "type": "ICT_ROUTE_SELECTED", "priority": "critical", "stationCode": STATION_CODE,
            "payload": {"batchId": _route_target_batch, "destination": destination,
                        "destinationStationCode": "manu_fct", "destinationLabel": "FCT",
                        "requestReason": request_reason,
                        "motherboard": route_info.get("sn_obj") or {},
                        "eventTime": int(time.time() * 1000)},
        })
        retest_var.set(f"整盘 {_route_target_batch} 已自动送往FCT")
        speak("该母板自动送往FCT")
        log(f"[ROUTE] batch={_route_target_batch} destination={destination}")
        _route_target_batch = ""
        route_selector.config(state="disabled")
        route_confirm_button.config(state="disabled")

    route_confirm_button = tk.Button(
        controls_frame, text="确认去向", command=_confirm_ng_route, state="disabled",
        font=("Microsoft YaHei UI", 10, "bold"), bg="#0e7490", fg="white",
        relief="raised", padx=9, pady=5,
    )
    # Fixed route is submitted automatically; do not show a confirmation button.

    # ATE-style tabbed workspace: live monitor + local SQLite records.
    workspace_style = ttk.Style()
    workspace_style.configure("ICT.TNotebook", background="#070d18", borderwidth=0)
    workspace_style.configure("ICT.TNotebook.Tab", font=("Microsoft YaHei UI", 8, "bold"), padding=(6, 3))
    workspace_notebook = ttk.Notebook(root, style="ICT.TNotebook")
    workspace_notebook.pack(fill="both", expand=True, padx=8, pady=(0, 6))
    monitor_tab = tk.Frame(workspace_notebook, bg="#070d18")
    pass_motherboard_tab = tk.Frame(workspace_notebook, bg="#07111f")
    ng_motherboard_tab = tk.Frame(workspace_notebook, bg="#07111f")
    sn_records_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    ng_records_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    handover_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    resources_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    professional_user_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    operator_manual_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    maintenance_manual_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    sop_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    daily_check_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    operation_report_tab = tk.Frame(workspace_notebook, bg="#0f172a")
    workspace_notebook.add(monitor_tab, text="实时监控 / LIVE")
    workspace_notebook.add(pass_motherboard_tab, text="PASS 母板")
    workspace_notebook.add(ng_motherboard_tab, text="NG 母板")
    workspace_notebook.add(sn_records_tab, text="SN记录 / SN")
    workspace_notebook.add(ng_records_tab, text="NG记录 / NG")
    workspace_notebook.add(handover_tab, text="维修复活令 / REPAIR RETURN")
    workspace_notebook.add(resources_tab, text="资源查看 / RESOURCES")

    for _tab, _title, _body in ((operator_manual_tab, "操作手册", "操作员登录、扫码、确认测试结果、处理PASS/NG。\n所有工站必须按MES发布版本执行。"), (maintenance_manual_tab, "维修手册", "维护人员查看设备状态、故障、SQLite证据和MES连接。\n维修动作必须记录并等待MES授权闭环。"), (sop_tab, "SOP", "当前工站SOP、版本、发布日期和确认状态。\n生产前必须确认已加载MES发布版本。"), (daily_check_tab, "日检", "□ 操作员授权\n□ 设备与安全状态\n□ SOP版本\n□ SQLite可用\n□ MES连接\n□ Outbox队列\n□ Agent心跳"), (operation_report_tab, "操作报告", "记录特殊事件、停机、设备异常、质量风险和处理措施。\n报告先保存本地SQLite，再发送MES。"), (professional_user_tab, "专业用户", "维修、质量、诊断、SOP确认和MES路由审核。")):
        workspace_notebook.add(_tab, text=_title)
        tk.Label(_tab, text=_title, bg="#0f172a", fg="#e2e8f0", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        tk.Label(_tab, text=_body, justify="left", bg="#0f172a", fg="#cbd5e1", font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=18)
    for _tab_index, _tab_label in enumerate(["实时监控", "合格母板", "NG母板", "SN记录", "NG记录", "维修复活令", "资源查看", "操作手册", "维修手册", "SOP", "日检", "操作报告", "专业用户"]):
        workspace_notebook.tab(_tab_index, text=_tab_label)

    _tab_labels = {
        "zh": ["实时监控", "合格母板", "NG母板", "SN记录", "NG记录", "维修复活令", "资源查看", "操作手册", "维修手册", "SOP", "日检", "操作报告", "专业用户"],
        "en": ["Live Monitor", "Pass Boards", "NG Boards", "SN Records", "NG Records", "Repair Return", "Resources", "Operator Manual", "Maintenance Manual", "SOP", "Daily Check", "Operation Report", "Professional User"],
        "vi": ["Giám sát", "Bo mạch đạt", "Bo mạch NG", "Bản ghi SN", "Bản ghi NG", "Trả sửa chữa", "Tài nguyên", "Hướng dẫn vận hành", "Hướng dẫn bảo trì", "SOP", "Kiểm tra ngày", "Báo cáo vận hành", "Người dùng chuyên môn"]
    }
    def _update_workspace_tabs():
        for _tab_index, _tab_label in enumerate(_tab_labels.get(ui_language["code"], _tab_labels["zh"])):
            workspace_notebook.tab(_tab_index, text=_tab_label)
    _update_workspace_tabs()

    resource_view = {"tables": []}
    resource_split = tk.PanedWindow(resources_tab, orient="horizontal", bg="#0f172a", sashwidth=6)
    resource_split.pack(fill="both", expand=True, padx=8, pady=(8, 0))
    resource_table_list = ttk.Treeview(resource_split, columns=("rows",), show="headings", height=18)
    resource_table_list.heading("rows", text="TABLE / 表")
    resource_table_list.column("rows", width=230, anchor="w")
    resource_text = tk.Text(resource_split, wrap="none", font=("Consolas", 10),
                            bg="#0b1220", fg="#e2e8f0")
    resource_split.add(resource_table_list, minsize=230)
    resource_split.add(resource_text, minsize=600)

    def _show_resource_table(_event=None):
        selected = resource_table_list.selection()
        if not selected:
            return
        table = resource_view.get("tables", [])[resource_table_list.index(selected[0])]
        lines = [f"TABLE / 表: {table.get('name','-')}", f"ROWS / 行数: {table.get('rows',0)}",
                 "COLUMNS / 列: " + ", ".join(table.get("columns", [])), ""]
        for row in table.get("preview", []):
            lines.append(" | ".join(f"{key}={value}" for key, value in row.items()))
        resource_text.configure(state="normal")
        resource_text.delete("1.0", "end")
        resource_text.insert("1.0", "\n".join(lines))
        resource_text.configure(state="disabled")

    resource_table_list.bind("<<TreeviewSelect>>", _show_resource_table)

    def _refresh_resources():
        global resource_view
        resource_view = build_resource_view(NG_DB)
        for item in resource_table_list.get_children():
            resource_table_list.delete(item)
        for table in resource_view.get("tables", []):
            resource_table_list.insert("", "end", values=(f"{table.get('name','-')} ({table.get('rows',0)})",))
        if resource_view.get("tables"):
            first = resource_table_list.get_children()[0]
            resource_table_list.selection_set(first)
            resource_table_list.focus(first)
            _show_resource_table()
        else:
            resource_text.configure(state="normal")
            resource_text.delete("1.0", "end")
            resource_text.insert("1.0", render_resource_view(resource_view))
            resource_text.configure(state="disabled")

    tk.Button(resources_tab, text="刷新 / REFRESH", command=_refresh_resources,
              bg="#2563eb", fg="white", relief="flat", padx=14, pady=6).pack(pady=8)
    _refresh_resources()

    def _build_embedded_detail(tab, title, cache_key, tone):
        header = tk.Frame(tab, bg="#0b1f35", padx=14, pady=9)
        header.pack(fill="x")
        tk.Label(header, text=title, bg="#0b1f35", fg=tone,
                 font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        summary_var = tk.StringVar(value="等待 MES 数据")
        tk.Label(header, textvariable=summary_var, bg="#0b1f35", fg="#cbd5e1",
                 font=("Microsoft YaHei UI", 10, "bold")).pack(side="right")
        canvas = tk.Canvas(tab, bg="#07111f", highlightthickness=0)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg="#07111f")
        content.bind("<Configure>", lambda _event, c=canvas: c.configure(scrollregion=c.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", width=1010)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll.pack(side="right", fill="y", pady=8)
        embedded_detail_views[cache_key] = {
            "tab": tab, "content": content, "summary": summary_var, "title": title,
        }

    _build_embedded_detail(pass_motherboard_tab, "PASS 母板历史", "ict:pass", "#22c55e")
    _build_embedded_detail(ng_motherboard_tab, "NG 母板历史", "ict:confirmed", "#ef4444")

    def _render_embedded_motherboards(cache_key):
        view = embedded_detail_views[cache_key]
        content = view["content"]
        for child in content.winfo_children():
            child.destroy()
        layouts = {}
        for record in list(mes_box_cache.get(cache_key, [])):
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

    def _make_record_tree(parent, columns, widths):
        shell = tk.Frame(parent, bg="#0f172a", padx=10, pady=10)
        shell.pack(fill="both", expand=True)
        tree = ttk.Treeview(shell, columns=columns, show="headings")
        for column, width in zip(columns, widths):
            tree.heading(column, text=column)
            tree.column(column, width=width, anchor="center")
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return tree

    sn_tab_tree = _make_record_tree(
        sn_records_tab,
        ("SN", "母板批次", "槽位", "结果", "扫码时间"),
        (190, 210, 80, 100, 190),
    )
    ng_tab_tree = _make_record_tree(
        ng_records_tab,
        ("批次", "槽位", "SN", "最终结果", "测试次数", "剩余复测", "最后测试时间", "确认NG"),
        (170, 60, 170, 100, 80, 90, 150, 80),
    )
    handover_tree = _make_record_tree(
        handover_tab,
        ("交接单号", "整盘编号", "来源工位", "目标工位", "SN数量", "交接状态", "送出时间", "接收时间", "接收人/扫码枪"),
        (90, 150, 120, 120, 70, 110, 165, 165, 140),
    )

    def _refresh_record_tabs(_event=None):
        try:
            with sqlite3.connect(NG_DB) as conn:
                sn_rows = conn.execute(
                    "SELECT sn,batch_id,slot,result,scan_time FROM all_sns ORDER BY scan_time DESC LIMIT 1000"
                ).fetchall()
                ng_rows = conn.execute(
                    "SELECT batch_id,slot,sn,final_result,test_count,retest_remaining,last_test_time,is_confirmed FROM ng_boards ORDER BY rowid DESC LIMIT 1000"
                ).fetchall()
            sn_tab_tree.delete(*sn_tab_tree.get_children())
            ng_tab_tree.delete(*ng_tab_tree.get_children())
            for row in sn_rows:
                sn_tab_tree.insert("", "end", values=row)
            for row in ng_rows:
                values = list(row)
                values[-1] = "是" if values[-1] else "否"
                ng_tab_tree.insert("", "end", values=values)
            url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=manu_ict")
            with urllib.request.urlopen(url, timeout=5) as response:
                handovers = [
                    row for row in json.loads(response.read().decode("utf-8")).get("items", [])
                    if _is_ict_repair_revival_order(row)
                ]
            handover_tree.delete(*handover_tree.get_children())
            for row in handovers:
                handover_tree.insert("", "end", values=(row.get("transferId",""), row.get("batchId",""),
                    row.get("sourceStation",""), row.get("destinationStation",""), row.get("memberCount",""),
                    row.get("status",""), row.get("sentAt",""), row.get("receivedAt",""), row.get("acceptedBy","")))
        except Exception as error:
            log(f"[TAB REFRESH ERR] {error}")

    workspace_notebook.bind("<<NotebookTabChanged>>", _refresh_record_tabs)

    # Main workspace: motherboard on the left, live activity log on the right.
    content_frame = tk.Frame(monitor_tab, bg="#0f172a")
    content_frame.pack(fill="both", expand=True, padx=8, pady=5)

    # 3D Board Canvas (12 slots) - 3 rows x 4 cols
    board_frame = tk.Frame(content_frame, bg="#1e293b", width=840, height=520)
    board_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
    board_frame.pack_propagate(False)

    canvas = tk.Canvas(board_frame, width=840, height=520, bg="#1e293b", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    kpi_frame = tk.Frame(content_frame, bg="#10243b", width=250)
    kpi_frame.pack(side="right", fill="y", padx=(8, 0))
    kpi_frame.pack_propagate(False)
    tk.Label(kpi_frame, text="ANALYSIS / KPI", bg="#10243b", fg="#7dd3fc",
             font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(14, 10))
    kpi_vars = {}
    for key, label, color in (("total", "TOTAL SLOTS", "#38bdf8"), ("pass", "PASS", "#22c55e"),
                              ("ng", "NG", "#ef4444"), ("retest", "RETEST LEFT", "#f59e0b")):
        card = tk.Frame(kpi_frame, bg="#0b1728", highlightbackground=color, highlightthickness=2)
        card.pack(fill="x", padx=10, pady=6)
        tk.Label(card, text=label, bg="#0b1728", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
        var = tk.StringVar(value="0")
        kpi_vars[key] = var
        tk.Label(card, textvariable=var, bg="#0b1728", fg=color, font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=10, pady=(0, 7))
    kpi_chart = tk.Canvas(kpi_frame, height=190, bg="#0b1728", highlightthickness=0)
    kpi_chart.pack(fill="x", padx=10, pady=(12, 10))

    # Slot states: slot_num -> {'result': 'PASS'/'FAIL', 'sn': str}
    _slot_states = {}
    _mother_board_id = ""
    _batch_retest_left = 2

    def draw_board():
        canvas.delete("all")
        total = len(_slot_states)
        passed = sum(1 for value in _slot_states.values() if str(value.get("result", "")).upper() in ("PASS", "OK"))
        failed = sum(1 for value in _slot_states.values() if str(value.get("result", "")).upper() in ("FAIL", "NG"))
        remaining = max(0, min((int(value.get("retest_remaining", 0) or 0) for value in _slot_states.values()), default=0))
        kpi_vars["total"].set(str(total)); kpi_vars["pass"].set(str(passed)); kpi_vars["ng"].set(str(failed)); kpi_vars["retest"].set(str(remaining))
        kpi_chart.delete("all")
        chart_w = max(210, kpi_chart.winfo_width())
        chart_h = 190
        kpi_chart.create_text(8, 10, text="YIELD / RESULT MIX", anchor="w", fill="#cbd5e1", font=("Segoe UI", 9, "bold"))
        denom = max(1, passed + failed)
        pass_angle = 360 * passed / denom
        kpi_chart.create_oval(chart_w - 102, 28, chart_w - 18, 112, fill="#22c55e", outline="")
        if failed:
            kpi_chart.create_arc(chart_w - 102, 28, chart_w - 18, 112, start=pass_angle, extent=360 - pass_angle, fill="#ef4444", outline="")
        kpi_chart.create_oval(chart_w - 78, 52, chart_w - 42, 88, fill="#0b1728", outline="")
        bar_x, bar_y, bar_w, bar_h = 18, 42, max(90, chart_w - 140), 22
        kpi_chart.create_rectangle(bar_x, bar_y, bar_x + bar_w, bar_y + bar_h, fill="#334155", outline="")
        if passed:
            kpi_chart.create_rectangle(bar_x, bar_y, bar_x + bar_w * passed / denom, bar_y + bar_h, fill="#22c55e", outline="")
        if failed:
            kpi_chart.create_rectangle(bar_x + bar_w * passed / denom, bar_y, bar_x + bar_w, bar_y + bar_h, fill="#ef4444", outline="")
        kpi_chart.create_text(bar_x, 78, text=f"PASS {passed}", anchor="w", fill="#86efac", font=("Consolas", 9, "bold"))
        kpi_chart.create_text(bar_x, 98, text=f"NG {failed}", anchor="w", fill="#fca5a5", font=("Consolas", 9, "bold"))

        # Draw 3D board background
        canvas.create_polygon([20,20, 780,20, 800,50, 800,450, 780,480, 20,480, 0,450, 0,50],
                             fill="#334155", outline="#475569", width=2)
        canvas.create_polygon([20,20, 780,20, 800,50, 0,50],
                             fill="#475569", outline="#64748b", width=1)
        canvas.create_polygon([780,20, 800,50, 800,450, 780,480],
                             fill="#1e293b", outline="#334155", width=1)

        # Draw slots (4 cols x 3 rows, slots fill top-to-bottom per column)
        # Column 0: 1,2,3 | Column 1: 4,5,6 | Column 2: 7,8,9 | Column 3: 10,11,12
        slot_size = 100
        start_x = 45
        start_y = 40
        cols = 4
        for i in range(12):
            row = i % 3        # 0,1,2,0,1,2,0,1,2,0,1,2
            col = i // 3        # 0,0,0,1,1,1,2,2,2,3,3,3
            x = start_x + col * (slot_size + 45)
            y = start_y + row * (slot_size + 45)
            slot_num = i + 1

            state = _slot_states.get(slot_num, {})
            result = state.get('result', 'FAIL')
            retest_left = state.get('retest_left', 2)
            sn = state.get('sn', '')

            if result == "PASS":
                color = "#166534"  # green
                text_color = "#4ade80"
            else:  # FAIL
                if retest_left > 0:
                    color = "#dc2626"  # bright red
                    text_color = "#ffffff"
                else:
                    color = "#991b1b"  # dark red - no more chances
                    text_color = "#fca5a5"

            # Draw 3D slot box
            canvas.create_polygon([x,y, x+slot_size,y, x+slot_size+10,y-10, x+10,y-10],
                                 fill="#475569", outline="#64748b")
            canvas.create_polygon([x+slot_size,y, x+slot_size+10,y-10, x+slot_size+10,y+slot_size-10, x+slot_size,y+slot_size],
                                 fill="#1e293b", outline="#334155")
            canvas.create_polygon([x,y, x+10,y-10, x+slot_size+10,y-10, x+slot_size,y],
                                 fill="#64748b", outline="#94a3b8")
            # Slot face
            canvas.create_rectangle(x+5, y-5, x+slot_size+5, y+slot_size-5,
                                  fill=color, outline=text_color, width=2)
            # Slot number (top)
            canvas.create_text(x+slot_size//2+5, y+18, text=f"S{slot_num:02d}",
                             fill=text_color, font=("Arial", 12, "bold"))
            # SN (middle) - full SN
            if sn:
                if result == "PASS":
                    sn_color = "#4ade80"  # green
                else:
                    sn_color = "#f87171"  # red
                canvas.create_text(x+slot_size//2+5, y+slot_size//2+2, text=sn,
                                 fill=sn_color, font=("Courier", 8, "bold"))
            # Status (bottom)
            test_count = state.get('test_count', 1)
            if result == "FAIL":
                if test_count > 1:
                    canvas.create_text(x+slot_size//2+5, y+slot_size-20,
                                     text=f"x{test_count}",
                                     fill="#fbbf24", font=("Arial", 9, "bold"))
                else:
                    canvas.create_text(x+slot_size//2+5, y+slot_size-20,
                                     text="FAIL",
                                     fill="#ffffff", font=("Arial", 10, "bold"))
            elif result == "PASS":
                if test_count > 1:
                    canvas.create_text(x+slot_size//2+5, y+slot_size-20,
                                     text=f"PASS x{test_count}",
                                     fill="#4ade80", font=("Arial", 9, "bold"))
                else:
                    canvas.create_text(x+slot_size//2+5, y+slot_size-20,
                                     text="PASS",
                                     fill="#4ade80", font=("Arial", 10, "bold"))
        # The source geometry remains legible at large displays, while this
        # scaled render keeps all twelve blocks visible on compact monitors.
        canvas.scale("all", 0, 0, 0.8, 0.8)
        canvas.configure(scrollregion=(0, 0, 640, 384))

    def update_board(main_sn, slots_info, dup_slots=None):
        """Update board display with current batch info.
        slots_info: list of (slot_num, result, retest_left, sn)
        dup_slots: dict of slot_num -> test_count (for slots tested multiple times)
        """
        global _mother_board_id, _batch_retest_left

        mother_board_var.set(f"母版: {main_sn}")
        board_var.set(f"母版: {main_sn}")

        # Find batch retest count from slots
        batch_retest = 2
        _slot_states.clear()
        for item in slots_info:
            if len(item) == 4:
                slot_num, result, retest_left, sn = item
            else:
                slot_num, result, retest_left = item
                sn = ''
            _slot_states[slot_num] = {'result': result, 'sn': sn}
            if retest_left < batch_retest:
                batch_retest = retest_left

        _batch_retest_left = batch_retest
        if batch_retest > 0:
            retest_var.set(f"剩余复测次数: {batch_retest}")
        else:
            retest_var.set("等待确认复测")

        if dup_slots:
            for slot_num, test_count in dup_slots.items():
                if slot_num in _slot_states:
                    _slot_states[slot_num]['test_count'] = test_count
        draw_board()
        log(f"[TEST] Board updated: {main_sn}")

    # Create a complete 12-file motherboard through the normal CSV pipeline.
    simulator_state = {"running": False, "forced_fail_slots": None}

    def _create_mother_board_test():
        if simulator_state["running"]:
            return
        simulator_state["running"] = True
        create_mb_button.config(state="disabled", text="正在模拟整盘测试...")

        def _write_test_batch():
            try:
                os.makedirs(WATCH_DIR, exist_ok=True)
                batch_ts = datetime.now().strftime("%Y%m%d%H%M%S")
                serial_seed = datetime.now().strftime("%H%M%S")
                prefix = "NBT-(26V5060)EPS18R1G-36-ICT"
                retest_info = _pending_ng_batches.get(_active_retest_batch) if _active_retest_batch else None
                retest_sns = dict(retest_info.get("child_sns", {})) if retest_info else {}
                prior_results = {
                    int(board.get("slot")): str(board.get("result", "PASS")).upper()
                    for board in ((retest_info.get("sn_obj") or {}).get("subBoards", []) if retest_info else [])
                }
                # A newly created test motherboard contains 1-4 FAIL boards at
                # random slots. A retest creates CSVs only for the failed child
                # boards actually being retested, never all 12 siblings.
                forced_fail_slots = simulator_state.pop("forced_fail_slots", None)
                simulated_fail_slots = set() if retest_info else set(
                    forced_fail_slots
                    if forced_fail_slots
                    else random.sample(range(1, 13), random.randint(1, 4))
                )
                if simulated_fail_slots:
                    log(f"[TEST] Random FAIL slots: {sorted(simulated_fail_slots)}")
                test_slots = (
                    sorted(slot for slot, value in prior_results.items() if value == "FAIL")
                    if retest_info else list(range(1, 13))
                )
                for slot in test_slots:
                    sn = retest_sns.get(slot) or retest_sns.get(str(slot)) or f"T{serial_seed}{slot:02d}A"
                    _simulation_sns.add(sn)
                    result = prior_results.get(slot, "FAIL" if slot in simulated_fail_slots else "PASS")
                    name = f"{prefix}_{sn}_{batch_ts}_{result}.CSV"
                    final_path = os.path.join(WATCH_DIR, name)
                    temp_path = final_path + ".tmp"
                    with open(temp_path, "w", encoding="gb18030", newline="") as report:
                        report.write("test_name,test_result,barcode,start_time,end_time,group_no,group_count,\n")
                        report.write(f"{prefix},{result},{sn},{batch_ts},{batch_ts},{slot},12,\n")
                        report.write("group_no,step_no,component,result\n")
                    os.replace(temp_path, final_path)
                    log(f"[TEST] Motherboard {batch_ts}: slot {slot}/12 {sn} {result}")
                    time.sleep(0.10)
                mode_label = "partial retest" if retest_info else "normal"
                log(f"[TEST] Motherboard created: {batch_ts}; {mode_label} CSV pipeline active; files={len(test_slots)}")
            except Exception as error:
                log(f"[TEST] Motherboard creation failed: {error}")
            finally:
                simulator_state["running"] = False
                root.after(0, lambda: create_mb_button.config(state="normal", text="模拟测试母板"))

        threading.Thread(target=_write_test_batch, daemon=True, name="motherboard-test").start()

    if os.environ.get("ICT_CREATE_SIM_MOTHERBOARD", "").strip() == "1":
        root.after(1200, _create_mother_board_test)

    # Retest button - for when this is a retest batch
    def _do_retest():
        global _batch_retest_left, _active_retest_batch
        candidates = []
        for key, info in _pending_ng_batches.items():
            obj = info.get("sn_obj") or {}
            failed = [b for b in obj.get("subBoards", [])
                      if b.get("result") == "FAIL"
                      and b.get("testCount", 1) == 1
                      and b.get("retestRemaining", 0) > 0]
            if failed:
                candidates.append((str(info.get("batch_end", key[1])), key, failed))
        if not candidates:
            retest_var.set("没有可复测的NG批次")
            return
        _, key, failed = sorted(candidates, reverse=True)[0]
        _active_retest_batch = key
        available_before = min(b.get("retestRemaining", 0) for b in failed)
        _batch_retest_left = max(0, available_before - 1)
        attempt_number = MAX_RETEST - available_before + 1
        failed_slots = "、".join(str(b.get("slot")) for b in failed)
        retest_var.set(
            f"第{attempt_number}次复测已启动: {key[1]}，剩余 {_batch_retest_left} 次"
        )
        announcement = (
            f"开始第{attempt_number}次复测，批次{key[1]}，"
            f"不良槽位{failed_slots}，剩余{_batch_retest_left}次复测机会"
        )
        # Move the affected boards into the First Retest bucket immediately.
        # Actual results are still recorded only after all 12 new CSVs arrive.
        try:
            import copy
            preview = copy.deepcopy((_pending_ng_batches[key].get("sn_obj") or {}))
            failed_sns = {b.get("sn") for b in failed}
            for board in preview.get("subBoards", []):
                if board.get("sn") in failed_sns:
                    board["testCount"] = 2
                    board["retestRemaining"] = 1
                    board["isConfirmedNG"] = False
                    board["retestInProgress"] = True
            preview["retestInProgress"] = True
            preview["retestAttempt"] = 1
            _event_queue.put({
                "type": "NG_DEFECT",
                "priority": "critical",
                "stationCode": STATION_CODE,
                "payload": preview,
            })
        except Exception as e:
            log(f"[RETEST] Failed to push first-retest preview: {e}")
        speak(announcement)
        log(f"[RETEST] {announcement}; waiting for 12 new CSV files")

    def _do_second_retest():
        global _batch_retest_left, _active_retest_batch
        candidates = []
        for key, info in _pending_ng_batches.items():
            obj = info.get("sn_obj") or {}
            failed = [
                b for b in obj.get("subBoards", [])
                if b.get("result") == "FAIL"
                and b.get("testCount", 1) == 2
                and b.get("retestRemaining", 0) == 1
            ]
            if failed:
                candidates.append((str(info.get("batch_end", key[1])), key, failed))
        if not candidates:
            retest_var.set("没有等待第二次复测的NG批次")
            return

        _, key, failed = sorted(candidates, reverse=True)[0]
        _active_retest_batch = key
        _batch_retest_left = 0
        failed_slots = "、".join(str(b.get("slot")) for b in failed)
        retest_var.set(f"第二次复测已启动: {key[1]}，剩余 0 次")
        announcement = (
            f"开始第二次复测，批次{key[1]}，"
            f"不良槽位{failed_slots}，本次为最后一次复测机会"
        )
        speak(announcement)
        log(f"[RETEST] {announcement}; waiting for 12 new CSV files")

    # Replace the older vertically packed action buttons with compact toolbar
    # versions. Keeping the callbacks unchanged avoids changing test logic.
    for _widget in list(root.pack_slaves()):
        if isinstance(_widget, tk.Button) and _widget.cget("bg") in (
            "#3b82f6", "#10b981", "#8b5cf6", "#dc2626"
        ):
            _widget.pack_forget()

    create_mb_button = tk.Button(
        controls_frame, text="模拟测试母板", command=_create_mother_board_test,
        font=("Microsoft YaHei UI", 10, "bold"), bg="#10b981", fg="white",
        relief="flat", padx=10, pady=5,
    )
    create_mb_button.pack(side="left", padx=4)

    # Local command bridge used by the visible Qt/WebGL shell. Commands are
    # one-shot files on the same station; no MES or central 3D control path is
    # involved. The existing simulation callback still creates real CSV files
    # and lets the normal 12-second ingestion pipeline process them.
    # Frozen PyInstaller apps extract __file__ into a temporary _MEI folder.
    # Commands are written beside the installed EXE in D:\stations, so always
    # use the already-resolved application directory.
    _qt_command_path = os.path.join(APP_DIR, "ict_qt_command.json")

    def _poll_qt_commands():
        try:
            if os.path.exists(_qt_command_path):
                with open(_qt_command_path, "r", encoding="utf-8") as command_file:
                    command = json.load(command_file)
                os.remove(_qt_command_path)
                if command.get("command") == "simulate_motherboard":
                    mode = str(command.get("mode", "normal_simulation"))
                    simulator_state["forced_fail_slots"] = [
                        int(slot) for slot in command.get("failSlots", [])
                        if 1 <= int(slot) <= 12
                    ]
                    log(
                        f"[QT COMMAND] simulate motherboard request={command.get('requestId', '')} "
                        f"mode={mode}; generated simulation SNs only bypass DUP"
                    )
                    _create_mother_board_test()
                elif command.get("command") == "arm_retest_scan":
                    log(f"[QT COMMAND] arm one-shot retest scan request={command.get('requestId', '')}")
                    _enable_retest_scan_mode()
                elif command.get("command") == "scan_sn":
                    sn = str(command.get("sn") or "").strip().upper()
                    if sn: post_sn_scan(sn)
                elif command.get("command") == "release_duplicate_alarm":
                    _release_duplicate_alarm()
                elif command.get("command") == "show_sn_sqlite":
                    _show_sn_viewer()
                elif command.get("command") == "show_ng_sqlite":
                    _show_ng_viewer()
                elif command.get("command") == "grant_overtime_retest":
                    _grant_overtime_retest_permission()
                elif command.get("command") == "show_handover_sheet":
                    _show_handover_sheet()
                elif command.get("command") == "confirm_route":
                    _confirm_ng_route()
                elif command.get("command") == "run_self_test":
                    _run_self_test()
                elif command.get("command") == "clear_local_sqlite":
                    _clear_all_ict_data()
        except Exception as error:
            log(f"[QT COMMAND ERR] {error}")
            try:
                os.remove(_qt_command_path)
            except OSError:
                pass
        root.after(250, _poll_qt_commands)

    root.after(250, _poll_qt_commands)

    def _clear_all_ict_data():
        global _active_retest_batch, _mother_board_id, _batch_retest_left
        confirmed = messagebox.askyesno(
            "清空 ICT 本地 SQLite",
            "确认清空 ict_ng.db 中的全部业务记录？\n\n"
            "表结构会保留；不会删除 D:\\SRC 原始 CSV，"
            "也不会删除 MES 或 3D 数据。此操作不能撤销。",
            icon="warning",
        )
        if not confirmed:
            return
        try:
            # MES must receive the complete ICT SN ledger before any local
            # business rows can be cleared.  The periodic reconciler runs once
            # per minute, so without this synchronous final handoff an operator
            # could clear newly parsed SNs before their next upload cycle.
            with sqlite3.connect(NG_DB) as conn:
                pending_mes_rows = conn.execute(
                    "SELECT sn,scan_time,batch_id,slot,result FROM all_sns "
                    "WHERE sn IS NOT NULL ORDER BY scan_time,sn"
                ).fetchall()
            pending_mes_sns = [
                {"sn": row[0], "testTime": row[1], "batchId": row[2],
                 "slot": row[3], "result": row[4]}
                for row in pending_mes_rows
            ]
            if pending_mes_sns:
                synchronized = reconcile_inventory(
                    MES_URL, STATION_CODE, "sn_records", pending_mes_sns,
                    int(time.time() * 1000), "sn", reported_by="ICT_PRE_CLEAR",
                    unchanged_resend_seconds=0,
                )
                if not synchronized:
                    raise RuntimeError(
                        "MES未确认完整ICT SN履历；已取消清空 / "
                        "MES did not confirm the complete ICT SN ledger; clear cancelled"
                    )
            with sqlite3.connect(NG_DB) as conn:
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
            _ng_tracking.clear()
            _pending_ng_batches.clear()
            _processed_batches.clear()
            # Clear the already-triggered UI alarm and any duplicate SNs that
            # were queued before the operator cleared the local database.
            while True:
                try:
                    _duplicate_alarm_queue.get_nowait()
                except queue.Empty:
                    break
            _release_duplicate_alarm()
            _active_retest_batch = None
            _mother_board_id = ""
            _batch_retest_left = MAX_RETEST
            _slot_states.clear()
            mother_board_var.set("无主板")
            board_var.set("")
            retest_var.set("")
            draw_board()
            _refresh_local_ict_boxes()
            _refresh_record_tabs()
            log(f"[CLEAR] ICT local SQLite cleared: {len(tables)} tables")
            messagebox.showinfo(
                "清空完成",
                f"ICT 本地 SQLite 已清空（{len(tables)} 个表）。\n"
                "原始 CSV、MES 和 3D 数据未删除。",
            )
        except Exception as error:
            log(f"[CLEAR ERR] {error}")
            messagebox.showerror("清空失败", str(error))

    def _run_self_test():
        results = run_diagnostics(MES_URL, WATCH_DIR, TCP_PORT, (NG_DB,))
        lines = [f"{'通过' if ok else '失败'} · {name} · {detail}" for name, ok, detail in results]
        lines.insert(0, f"ICT v{APP_VERSION} · 首次确认阈值 {CONFIRM_AFTER_FAIL_COUNT}")
        messagebox.showinfo("ICT 系统自检", "\n".join(lines))

    tk.Button(
        controls_frame, text="系统自检", command=_run_self_test,
        font=("Microsoft YaHei UI", 10, "bold"), bg="#0369a1", fg="white",
        relief="flat", padx=10, pady=5,
    ).pack(side="right", padx=4)
    # Maintenance self-test remains callable internally but is not shown to operators.
    for _widget in controls_frame.winfo_children():
        if isinstance(_widget, tk.Button) and ("self-test" in str(_widget.cget("text")).lower() or _widget.cget("bg") == "#0369a1"):
            _widget.pack_forget()
    draw_board()  # Initial draw

    # Main-view diagnostics: keep the operational failures visible without a
    # console, while retaining the detailed scrollable event log underneath.
    diagnostics_panel = tk.Frame(content_frame, bg="#0b1728", width=430)
    diagnostics_panel.pack(side="right", fill="both", expand=True, padx=(8, 0))
    tk.Label(diagnostics_panel, text="运行诊断 / LIVE DIAGNOSTICS", bg="#0b1728", fg="#7dd3fc",
             font=("Microsoft YaHei UI", 12, "bold"), anchor="w").pack(fill="x", padx=8, pady=(6, 2))
    diagnostic_vars = {}
    for key, label in (("heartbeat", "MES heartbeat"), ("handover", "Handover sync"),
                       ("tabs", "Record refresh"), ("inventory", "Inventory reconcile")):
        var = tk.StringVar(value=f"{label}: waiting")
        diagnostic_vars[key] = var
        tk.Label(diagnostics_panel, textvariable=var, bg="#0b1728", fg="#cbd5e1",
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=10, pady=1)
    log_win = scrolledtext.ScrolledText(diagnostics_panel, height=8, font=("Courier", 9),
                                        bg="#0f172a", fg="#e2e8f0")
    log_win.pack(side="top", fill="both", expand=True, padx=6, pady=(6, 6))
    log_win.pack_forget()
    diagnostics_panel.pack_forget()
    _tk_log_win = log_win

    def _drain_tk_log_queue():
        try:
            while True:
                line = _tk_log_queue.get_nowait()
                _tk_log_win.insert("end", line + "\n")
                if "[HEARTBEAT ERR]" in line:
                    diagnostic_vars["heartbeat"].set("MES heartbeat: ERROR / timed out")
                elif "[HEARTBEAT]" in line:
                    diagnostic_vars["heartbeat"].set("MES heartbeat: OK")
                if "[HANDOVER SYNC]" in line:
                    diagnostic_vars["handover"].set("Handover sync: ERROR / timed out")
                if "[TAB REFRESH ERR]" in line:
                    diagnostic_vars["tabs"].set("Record refresh: ERROR / timed out")
                if "[INVENTORY]" in line:
                    diagnostic_vars["inventory"].set("Inventory reconcile: ERROR / deferred")
        except queue.Empty:
            pass
        _tk_log_win.see("end")
        root.after(100, _drain_tk_log_queue)

    root.after(100, _drain_tk_log_queue)

    # Store update function globally
    import __main__
    __main__.update_board = update_board

    _latest_ict_view_signature = {"value": None}

    def _refresh_latest_motherboard_view():
        """Restore the newest completed ICT motherboard from local SQLite."""
        try:
            with sqlite3.connect(NG_DB) as conn:
                newest = conn.execute(
                    """SELECT batch_id,MAX(scan_time)
                       FROM all_sns
                       WHERE batch_id IS NOT NULL AND batch_id<>''
                       GROUP BY batch_id
                       ORDER BY MAX(scan_time) DESC LIMIT 1"""
                ).fetchone()
                if not newest:
                    return
                signature = (str(newest[0]), int(newest[1] or 0))
                if signature == _latest_ict_view_signature["value"]:
                    return
                rows = conn.execute(
                    """SELECT slot,sn,result,scan_time
                       FROM all_sns WHERE batch_id=?
                       ORDER BY slot,scan_time DESC""",
                    (newest[0],),
                ).fetchall()
            latest_by_slot = {}
            for slot, sn, result, _scan_time in rows:
                latest_by_slot.setdefault(
                    int(slot), (int(slot), str(result or "PASS").upper(), 2, str(sn or ""))
                )
            if latest_by_slot:
                update_board(str(newest[0]), list(latest_by_slot.values()))
                _latest_ict_view_signature["value"] = signature
        except Exception as exc:
            log(f"[UI RESTORE] {exc}")
        finally:
            root.after(2000, _refresh_latest_motherboard_view)

    root.after(350, _refresh_latest_motherboard_view)

    def _drain_ui_updates():
        try:
            while True:
                scan_state, batch_id, remaining, slot, scanned_sn = _retest_scan_ui_queue.get_nowait()
                if scan_state == "ARMED":
                    retest_var.set(f"复检已启动：整盘 {batch_id}，剩余 {remaining} 次")
                elif scan_state == "NO_CHANCE":
                    retest_var.set(f"槽位{slot}没有复检机会，整盘自动送往FCT")
                elif scan_state == "NEED_PERMISSION":
                    retest_var.set(f"整盘 {batch_id} 已超过2小时，需要主管许可")
                elif scan_state == "ROUTE_REQUIRED":
                    global _route_target_batch
                    _route_target_batch = str(batch_id)
                    retest_var.set(f"整盘 {batch_id} 没有复检机会，自动送往FCT")
                    _confirm_ng_route()
                else:
                    retest_var.set(f"整盘 {batch_id} 未加载，无法启动复检")
        except queue.Empty:
            pass
        try:
            while True:
                scanned_sn, batch_id, member_count, source = _scanner_batch_queue.get_nowait()
                if batch_id:
                    scanner_var.set(
                        f"扫码枪：{scanned_sn}  →  整盘 {batch_id}  ({member_count}/12)"
                    )
                    scanner_label.config(bg="#166534" if member_count == 12 else "#92400e", fg="white")
                elif source == "NOT_FOUND":
                    scanner_var.set(f"扫码枪：{scanned_sn}  →  未找到所属母板")
                    scanner_label.config(bg="#7f1d1d", fg="white")
                else:
                    scanner_var.set(f"扫码枪：{scanned_sn}  →  查询失败")
                    scanner_label.config(bg="#7f1d1d", fg="white")
        except queue.Empty:
            pass
        try:
            while True:
                _scanner_ui_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            while True:
                _start_duplicate_alarm(_duplicate_alarm_queue.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                main_sn, slots_info, dup_slots = _ui_update_queue.get_nowait()
                update_board(main_sn, slots_info, dup_slots)
        except queue.Empty:
            pass
        root.after(100, _drain_ui_updates)

    root.after(100, _drain_ui_updates)

    # SQLite Viewer Button - All SNs
    def _show_sn_viewer():
        """Show a window with all_sns table data"""
        viewer = tk.Toplevel(root)
        viewer.title("📋 all_sns 表 - SN记录")
        viewer.geometry("900x500")
        viewer.configure(bg="#0f172a")

        # Treeview for data
        cols = ("SN", "扫描时间", "批次ID", "槽位", "结果")
        tree = ttk.Treeview(viewer, columns=cols, show="headings", height=20)

        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=180)

        # Scrollbar
        scrollbar = ttk.Scrollbar(viewer, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

        # Load data
        try:
            import datetime
            with sqlite3.connect(NG_DB) as conn:
                cur = conn.execute("""
                    SELECT sn, scan_time, batch_id, slot, result
                    FROM all_sns
                    ORDER BY scan_time DESC
                    LIMIT 500
                """)
                for row in cur.fetchall():
                    try:
                        dt = datetime.datetime.fromtimestamp(row[1] / 1000)
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        time_str = str(row[1])
                    tree.insert("", "end", values=(row[0], time_str, row[2], row[3], row[4]))
        except Exception as e:
            tk.Label(viewer, text=f"Error: {e}", fg="red", bg="#0f172a").pack()

        tk.Button(viewer, text="刷新", command=_show_sn_viewer,
                 font=("Arial", 10), bg="#3b82f6", fg="white",
                 relief="flat", padx=15, pady=5).pack(pady=5)

    # SQLite Viewer Button - NG Batches
    def _show_ng_viewer():
        """Show a window with ng_batches and ng_boards data"""
        viewer = tk.Toplevel(root)
        viewer.title("📋 NG批次记录")
        viewer.geometry("1000x600")
        viewer.configure(bg="#0f172a")

        # Notebook for tabs
        notebook = ttk.Notebook(viewer)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: ng_batches
        frame1 = tk.Frame(viewer, bg="#0f172a")
        notebook.add(frame1, text=" ng_batches ")

        cols1 = ("批次ID", "主板SN", "批次开始", "创建时间")
        tree1 = ttk.Treeview(frame1, columns=cols1, show="headings")

        for col in cols1:
            tree1.heading(col, text=col)
            tree1.column(col, width=200)

        scrollbar1 = ttk.Scrollbar(frame1, orient="vertical", command=tree1.yview)
        tree1.configure(yscrollcommand=scrollbar1.set)
        tree1.pack(side="left", fill="both", expand=True)
        scrollbar1.pack(side="right", fill="y")

        # Tab 2: ng_boards
        frame2 = tk.Frame(viewer, bg="#0f172a")
        notebook.add(frame2, text=" ng_boards ")

        cols2 = ("批次ID", "槽位", "SN", "第1结果", "第1时间", "第2结果", "第2时间", "第3结果", "第3时间", "最终", "次数", "剩余", "已确认", "维修结果")
        tree2 = ttk.Treeview(frame2, columns=cols2, show="headings")

        # Set column widths - narrower for 14 columns
        col_widths = [110, 40, 100, 55, 85, 55, 85, 55, 85, 50, 40, 40, 55, 70]
        for i, col in enumerate(cols2):
            tree2.heading(col, text=col)
            tree2.column(col, width=col_widths[i])

        scrollbar2 = ttk.Scrollbar(frame2, orient="vertical", command=tree2.yview)
        tree2.configure(yscrollcommand=scrollbar2.set)
        tree2.pack(side="left", fill="both", expand=True)
        scrollbar2.pack(side="right", fill="y")

        # Tab 3: maintenance_ng
        frame3 = tk.Frame(viewer, bg="#0f172a")
        notebook.add(frame3, text=" 维修NG ")

        cols3 = ("ID", "批次ID", "主板SN", "槽位", "SN", "确认时间", "状态")
        tree3 = ttk.Treeview(frame3, columns=cols3, show="headings")

        for col in cols3:
            tree3.heading(col, text=col)
            tree3.column(col, width=120)

        scrollbar3 = ttk.Scrollbar(frame3, orient="vertical", command=tree3.yview)
        tree3.configure(yscrollcommand=scrollbar3.set)
        tree3.pack(side="left", fill="both", expand=True)
        scrollbar3.pack(side="right", fill="y")

        # Tab 4: aged_ng
        frame4 = tk.Frame(viewer, bg="#0f172a")
        notebook.add(frame4, text=" 老化NG ")

        cols4 = ("ID", "批次ID", "主板SN", "老化时间", "状态")
        tree4 = ttk.Treeview(frame4, columns=cols4, show="headings")

        for col in cols4:
            tree4.heading(col, text=col)
            tree4.column(col, width=150)

        scrollbar4 = ttk.Scrollbar(frame4, orient="vertical", command=tree4.yview)
        tree4.configure(yscrollcommand=scrollbar4.set)
        tree4.pack(side="left", fill="both", expand=True)
        scrollbar4.pack(side="right", fill="y")

        # Load data
        try:
            import datetime
            with sqlite3.connect(NG_DB) as conn:
                # Load ng_batches
                cur1 = conn.execute("""
                    SELECT batch_id, main_sn, batch_start, created_at
                    FROM ng_batches
                    ORDER BY created_at DESC
                    LIMIT 100
                """)
                for row in cur1.fetchall():
                    try:
                        dt1 = datetime.datetime.fromtimestamp(row[2] / 1000)
                        t1 = dt1.strftime("%Y-%m-%d %H:%M")
                        dt2 = datetime.datetime.fromtimestamp(row[3] / 1000)
                        t2 = dt2.strftime("%Y-%m-%d %H:%M")
                    except:
                        t1, t2 = str(row[2]), str(row[3])
                    tree1.insert("", "end", values=(row[0], row[1], t1, t2))

                # Load ng_boards - full lifecycle with timestamps
                cur2 = conn.execute("""
                    SELECT batch_id, slot, sn,
                           result_1, test_time_1,
                           result_2, test_time_2,
                           result_3, test_time_3,
                           final_result, test_count, retest_remaining, is_confirmed, repair_result
                    FROM ng_boards
                    ORDER BY batch_id, slot
                    LIMIT 500
                """)
                for row in cur2.fetchall():
                    confirmed = "是" if row[12] == 1 else "否"
                    repair = row[13] if row[13] else "-"
                    # Format timestamps
                    def fmt_time(ts):
                        if ts is None:
                            return "-"
                        try:
                            return datetime.datetime.fromtimestamp(ts / 1000).strftime("%m-%d %H:%M")
                        except:
                            return str(ts)
                    tree2.insert("", "end", values=(
                        row[0], row[1], row[2],
                        row[3], fmt_time(row[4]),
                        row[5], fmt_time(row[6]),
                        row[7], fmt_time(row[8]),
                        row[9], row[10], row[11], confirmed, repair
                    ))

                # Load maintenance_ng
                cur3 = conn.execute("""
                    SELECT id, batch_id, main_sn, slot, sn, confirm_time, status
                    FROM maintenance_ng
                    ORDER BY confirm_time DESC
                    LIMIT 200
                """)
                for row in cur3.fetchall():
                    try:
                        dt = datetime.datetime.fromtimestamp(row[5] / 1000)
                        t = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        t = str(row[5])
                    tree3.insert("", "end", values=(row[0], row[1], row[2], row[3], row[4], t, row[6]))

                # Load aged_ng
                cur4 = conn.execute("""
                    SELECT id, batch_id, main_sn, aged_time, status
                    FROM aged_ng
                    ORDER BY aged_time DESC
                    LIMIT 200
                """)
                for row in cur4.fetchall():
                    try:
                        dt = datetime.datetime.fromtimestamp(row[3] / 1000)
                        t = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        t = str(row[3])
                    tree4.insert("", "end", values=(row[0], row[1], row[2], t, row[4]))

        except Exception as e:
            tk.Label(viewer, text=f"Error: {e}", fg="red", bg="#0f172a").pack()

        tk.Button(viewer, text="刷新", command=_show_ng_viewer,
                 font=("Arial", 10), bg="#3b82f6", fg="white",
                 relief="flat", padx=15, pady=5).pack(pady=5)

    tk.Button(root, text="📋 SN记录", command=_show_sn_viewer,
             font=("Arial", 10), bg="#3b82f6", fg="white",
             relief="flat", padx=12, pady=3).pack(pady=(0, 5))

    tk.Button(root, text="📋 NG记录", command=_show_ng_viewer,
             font=("Arial", 10), bg="#f59e0b", fg="white",
             relief="flat", padx=12, pady=3).pack(pady=(0, 5))

    for _widget in root.pack_slaves():
        if isinstance(_widget, tk.Button) and _widget.cget("bg") == "#f59e0b":
            _widget.pack_forget()

    def _on_close():
        status_var.set("⏹  已停止")
        log("[AGENT] Stopped by user")
        root.after(500, root.destroy)

    root.protocol("WM_DELETE_WINDOW", _on_close)

    # Init SQLite + restore pending NG batches
    init_ng_db()
    seed_preview_repair_work_orders()
    log("[DB] Initialized")
    restored = load_pending_ng_batches()
    # Restored SQLite history must not be replayed into a freshly cleared 3D
    # line. It remains available locally and can still be updated by retests.
    for _restored_info in restored.values():
        _restored_info["_suppress_aging_events"] = True
    _pending_ng_batches.update(restored)
    log(f"[DB] Restored {len(restored)} pending NG batches from SQLite")

    # Start sender only after its durable outbox table exists.
    _send_thread = threading.Thread(target=_mes_worker, daemon=True, name="mes-bridge")
    _send_thread.start()
    log("[MES] Bridge started")

    def _handover_completion_sync():
        """Release completed motherboards from RAM; SQLite remains audit history."""
        while True:
            try:
                url = MES_URL.replace("/api/pda/events", "/api/station/handovers?stationCode=manu_ict&status=COMPLETED")
                with urllib.request.urlopen(url, timeout=5) as response:
                    completed = json.loads(response.read().decode("utf-8")).get("items", [])
                completed_ids = {str(item.get("batchId", "")) for item in completed}
                for key in list(_pending_ng_batches):
                    if str(key[1]) in completed_ids:
                        _pending_ng_batches.pop(key, None)
                        log(f"[HANDOVER] Completed batch {key[1]} released from memory")
            except Exception as error:
                log(f"[HANDOVER SYNC] {error}")
            time.sleep(10)

    threading.Thread(target=_handover_completion_sync, daemon=True, name="handover-sync").start()

    # Heartbeat — SSE to 3D
    _heartbeat_ok = [False]  # use list to allow closure modification

    def _refresh_heartbeat_indicator():
        """Keep a clear, always-visible heartbeat badge in the station banner."""
        if _heartbeat_label:
            online = bool(_heartbeat_ok[0])
            _heartbeat_label.config(
                text="● ONLINE · HEARTBEAT" if online else "● OFFLINE · HEARTBEAT",
                fg="#22c55e" if online else "#ef4444",
            )
        root.after(1000, _refresh_heartbeat_indicator)

    root.after(0, _refresh_heartbeat_indicator)
    def _heartbeat():
        while True:
            try:
                body = json.dumps({"type": "AGENT_HEARTBEAT", "stationCode": STATION_CODE,
                    "payload": {"ts": now_ms(), "label": STATION_LABEL,
                    "watchDir": WATCH_DIR}}).encode("utf-8")
                request = urllib.request.Request(MES_URL, data=body, method="POST",
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=3) as response:
                    response.read()
                _heartbeat_ok[0] = True
                root.after(0, lambda: _heartbeat_label.config(text="♥ ONLINE", fg="#22c55e") if _heartbeat_label else None)
                log(f"[HEARTBEAT] {STATION_CODE}")
            except Exception as error:
                _heartbeat_ok[0] = False
                root.after(0, lambda: _heartbeat_label.config(text="♥ OFFLINE", fg="#ef4444") if _heartbeat_label else None)
                log(f"[HEARTBEAT ERR] {error}")
            time.sleep(30)

    threading.Thread(target=_heartbeat, daemon=True, name="heartbeat").start()
    threading.Thread(target=_inventory_reconcile_worker, daemon=True,
                     name="ict-inventory-reconcile").start()
    threading.Thread(target=_aging_checker, daemon=True, name="aging").start()

    # Use the proven ATE-base global keyboard/TCP scanner for ICT.  The common
    # Agent remains responsible for SQLite/MES projection; ICT owns the
    # station-specific result and NG workflow.
    # Global keyboard-wedge capture is provided by the shared scanner
    # component registered on the visible SN entry above.
    _start_tcp_server()

    csv_handler = CSVHandler()
    # Deployment safety: files already present in D:\SRC belong to an earlier
    # production period.  Establish the baseline before starting watchdog so
    # installing/restarting the agent never replays old CSVs as new tests and
    # raises a false duplicate alarm.  Files created after this point are still
    # discovered by watchdog and the independent reconciler.
    csv_handler.mark_existing()
    observer = PollingObserver(timeout=2)
    observer.schedule(csv_handler, WATCH_DIR, recursive=False)
    observer.start()

    # Watchdog can remain alive at process level while its event thread has
    # stopped. A small independent scan makes CSV discovery self-healing.
    def _csv_reconciler():
        while True:
            time.sleep(2)
            csv_handler.reconcile()

    threading.Thread(target=_csv_reconciler, daemon=True,
                     name="csv-reconciler").start()
    log(f"[WATCH] {WATCH_DIR}")
    log(f"[AGENT] Running")

    from motherboard_search import install_motherboard_search
    motherboard_browser = install_motherboard_search(root, MES_URL, "manual")
    # The manual ICT source does not contain the auto-line adapter module.
    # Load the shared repair implementation directly so the UI can start.
    _shared_repair_dir = os.path.abspath(os.path.join(
        APP_DIR, "..", "..", "002-自动线", "(03)ICT", "dist", "manual_repair"
    ))
    if os.path.isdir(_shared_repair_dir) and _shared_repair_dir not in sys.path:
        sys.path.insert(0, _shared_repair_dir)
    from station_repair_workflow import install_repair_workflow
    repair_panel = install_repair_workflow(root, STATION_CODE, MES_URL, "ICT")
    # Make the shared repair component visible for station verification; it
    # remains a read-only preview until an MES-authorized action is selected.
    if repair_panel is not None:
        root.after(500, repair_panel.open)
    if repair_panel is not None and os.environ.get("ICT_OPEN_HISTORY", "").strip() == "1":
        root.after(900, repair_panel.open_history)
    # Keep the existing ICT language buttons, but route them through the same
    # complete widget/StringVar translator used by FCT and depanel.
    language_bridge["controller"] = TrilingualController(
        root, top_banner, show_buttons=False
    )
    language_bridge["controller"].set(ui_language["code"])
    root.mainloop()
