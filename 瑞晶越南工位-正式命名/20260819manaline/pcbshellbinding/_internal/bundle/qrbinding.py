"""
QR码绑定系统 - QR Code Binding System
PCBA主板与外壳二维码绑定 | 越南瑞晶工厂内部工具
"""

import tkinter as tk
from tkinter import scrolledtext, ttk, simpledialog, messagebox
import datetime
import time
import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys
import sqlite3
import re
import subprocess
import threading
import queue
import socket
import winreg
import asyncio
import tempfile
import ctypes
from typing import Optional, List, Tuple
from enum import Enum
import csv
import uuid

# ── Windows console cp1252 workaround (no longer needed, kept for safety) ──
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass

APP_VERSION = "2.0.0-mes-atomic"

# WebSocket 服务器
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("[WS] websockets not installed. WebSocket broadcast disabled.", flush=True)


def app_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_FILE = os.path.join(app_root(), "config.json")


def _ensure_config():
    """config.json不存在时创建带规则的默认配置"""
    if os.path.exists(CONFIG_FILE):
        return
    default = {
        "sn_rules": {
            "_note": "empty patterns disable validation; regex patterns enable validation",
            "pcba": {
                "patterns": [
                    "^5G[A-Z0-9]{8}$"
                ],
                "prefix": "",
                "min_length": 10,
                "max_length": 10,
                "description": "PCBA版规则: 5G+8位字母或数字"
            },
            "shell": {
                "patterns": [
                    "^NV18A[A-Z0-9]{9}$"
                ],
                "prefix": "",
                "min_length": 14,
                "max_length": 14,
                "description": "外壳规则: NV18A+9位字母或数字"
            }
        },
        "voice": {
            "enabled": True,
            "prompts": {
                "scan_pcba": "请扫版码",
                "scan_shell": "请扫壳码",
                "binding": "绑定",
                "violation": "违规",
                "success": "绑定成功"
            }
        },
        "binding_rules": {
            "prevent_duplicate_pcba": True,
            "prevent_duplicate_shell": True,
            "auto_bind": True
        }
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_ensure_config()


# ================================================================
# 端口与路径配置
# ================================================================
LOCAL_PORT = int(os.environ.get("STATION_LOCAL_PORT", "8090"))
WS_PORT = int(os.environ.get("STATION_WS_PORT", "11006"))
SYNC_PORT = 8089
API_KEY = os.environ.get("STATION_API_KEY", "VN-FACTORY-2024")
APP_FOLDER = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(APP_FOLDER))
MANUAL_LINE_DIR = os.path.join(os.path.dirname(os.path.dirname(APP_FOLDER)), "002-自动线")
if str(MANUAL_LINE_DIR) not in sys.path and os.path.isdir(MANUAL_LINE_DIR):
    sys.path.insert(1, str(MANUAL_LINE_DIR))
from station_resource_startup import start_first_install_resource_read
start_first_install_resource_read(APP_FOLDER)
from station_ui_primitives import install_station_tabs, register_scanner_entry
from station_scrap_workflow import request_direct_scrap, start_sync_worker
from station_alarm import StationAlarm
from station_i18n import TrilingualController
from station_data_sync import reconcile_inventory, ExpectedSnManifest
from station_retest import install_station_retest_panel
from station_runtime_safety import acquire_single_instance

# MES配置（通过环境变量覆盖）
MES_NEW_API = os.environ.get("MES_NEW_API", "http://127.0.0.1:8765/api")
MES_NG_CHECK_API = os.environ.get("MES_NG_CHECK_API", "http://127.0.0.1:8765/api/mes/ng-check")
NGM_NG_CHECK_API = os.environ.get("NGM_NG_CHECK_API", "http://127.0.0.1:8089/ng_check")  # QR sync NG check
NGM_API = os.environ.get("NGM_API", "http://127.0.0.1:5002/api/interception")  # Flask拦截记录API
MES_NEW_STATION = os.environ.get("MES_NEW_STATION", "auto_shellbinding")  # smt-factory manual-line station code
# Keep alarm/UI station identity defined in every packaged QR-binding build.
STATION_CODE = MES_NEW_STATION
MES_NEW_OPERATOR = os.environ.get("MES_NEW_OPERATOR", "BIND_OPERATOR")
MES_NEW_ENABLED = os.environ.get("MES_NEW_ENABLED", "1") == "1"
PDA_EVENT_URL = os.environ.get("PDA_EVENT_URL", "http://127.0.0.1:8765/api/pda/events")
MES_OFFLINE_ALLOWED = os.environ.get("MES_ALLOW_OFFLINE_BINDING", "0").lower() in ("1", "true", "yes", "on")
MES_LOCAL_FIRST_BINDING = os.environ.get("MES_LOCAL_FIRST_BINDING", "1").lower() in ("1", "true", "yes", "on")
HEARTBEAT_SECONDS = 5
BINDING_GUARD_DB = os.path.join(APP_FOLDER, "binding_guard.db")
STATION_ACTIVITY_DB = os.path.join(APP_FOLDER, "station_activity.db")
STATION_ACTIVITY_API = os.environ.get("STATION_ACTIVITY_API", "http://127.0.0.1:8765/api/station/activity")
ACTIVITY_TABLE_VERSION = 1

def binding_inventory_reconcile_worker():
    while True:
        try:
            with sqlite3.connect(BINDING_GUARD_DB) as conn:
                bindings = [{"sn": row[0], "codeType": row[1], "pairedSn": row[2], "boundAt": row[3]}
                            for row in conn.execute("SELECT sn,code_type,paired_sn,bound_at FROM all_sns ORDER BY sn")]
                ngs = [{"sn": row[0], "sourceStation": row[1], "batchId": row[2]}
                       for row in conn.execute("SELECT sn,source_station,batch_id FROM confirmed_ng ORDER BY sn")]
            version = int(time.time() * 1000)
            reconcile_inventory(PDA_EVENT_URL, MES_NEW_STATION, "bindings", bindings, version, "sn")
            reconcile_inventory(PDA_EVENT_URL, MES_NEW_STATION, "confirmed_ng", ngs, version, "sn")
        except Exception:
            pass
        time.sleep(60)

# MES事件桥接队列
_mes_new_lock = threading.Lock()
_mes_new_queue = queue.Queue()
_mes_new_thread = None


def init_binding_guard_db():
    with sqlite3.connect(BINDING_GUARD_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS all_sns (
                sn TEXT PRIMARY KEY, code_type TEXT NOT NULL, paired_sn TEXT,
                bound_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS confirmed_ng (
                sn TEXT PRIMARY KEY, source_station TEXT NOT NULL, batch_id TEXT,
                detected_at INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE TABLE IF NOT EXISTS duplicate_events (id INTEGER PRIMARY KEY AUTOINCREMENT, sn TEXT NOT NULL, code_type TEXT NOT NULL, detected_at INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS ng_detection_events (id INTEGER PRIMARY KEY AUTOINCREMENT, sn TEXT NOT NULL, source_station TEXT, batch_id TEXT, detected_at INTEGER NOT NULL)")


def init_station_activity_db():
    with sqlite3.connect(STATION_ACTIVITY_DB) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS table_versions (table_name TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at INTEGER NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS activity_log (event_id TEXT PRIMARY KEY, action TEXT NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL, synced_at INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS outbox (event_id TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, next_retry_at INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(event_id) REFERENCES activity_log(event_id))")
        conn.execute("INSERT OR REPLACE INTO table_versions VALUES ('activity_log',?,?)", (ACTIVITY_TABLE_VERSION, int(time.time() * 1000)))


def record_station_activity(action, payload=None):
    event_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    with sqlite3.connect(STATION_ACTIVITY_DB) as conn:
        conn.execute("INSERT INTO activity_log VALUES (?,?,?,?,NULL)", (event_id, action, json.dumps(payload or {}, ensure_ascii=False), now))
        conn.execute("INSERT INTO outbox (event_id,next_retry_at) VALUES (?,0)", (event_id,))
    return event_id


def station_activity_sync_worker():
    while True:
        try:
            with sqlite3.connect(STATION_ACTIVITY_DB) as conn:
                row = conn.execute("""
                    SELECT a.event_id,a.action,a.payload,a.created_at,o.attempts
                    FROM outbox o JOIN activity_log a ON a.event_id=o.event_id
                    WHERE o.next_retry_at<=? ORDER BY a.created_at LIMIT 1
                """, (int(time.time() * 1000),)).fetchone()
            if not row:
                time.sleep(1)
                continue
            event_id, action, payload_text, created_at, attempts = row
            body = {
                "eventId": event_id, "stationCode": MES_NEW_STATION,
                "tableName": "activity_log", "tableVersion": ACTIVITY_TABLE_VERSION,
                "action": action, "payload": json.loads(payload_text), "createdAt": created_at,
            }
            request = urllib.request.Request(STATION_ACTIVITY_API, data=json.dumps(body).encode("utf-8"), method="POST", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read()
            with sqlite3.connect(STATION_ACTIVITY_DB) as conn:
                conn.execute("UPDATE activity_log SET synced_at=? WHERE event_id=?", (int(time.time() * 1000), event_id))
                conn.execute("DELETE FROM outbox WHERE event_id=?", (event_id,))
        except Exception as exc:
            if 'event_id' in locals():
                delay = min(60000, 1000 * (2 ** min(int(attempts) + 1, 6)))
                with sqlite3.connect(STATION_ACTIVITY_DB) as conn:
                    conn.execute("UPDATE outbox SET attempts=attempts+1,last_error=?,next_retry_at=? WHERE event_id=?", (str(exc)[:500], int(time.time() * 1000) + delay, event_id))
            time.sleep(1)


def binding_guard_duplicate(sn):
    with sqlite3.connect(BINDING_GUARD_DB) as conn:
        return conn.execute("SELECT 1 FROM all_sns WHERE sn=?", (sn.strip().upper(),)).fetchone() is not None


def binding_guard_ng(sn):
    with sqlite3.connect(BINDING_GUARD_DB) as conn:
        return conn.execute("SELECT source_station,batch_id FROM confirmed_ng WHERE sn=?", (sn.strip().upper(),)).fetchone()


def binding_guard_save_pair(pcba_sn, shell_sn):
    now = int(time.time() * 1000)
    with sqlite3.connect(BINDING_GUARD_DB) as conn:
        conn.execute("INSERT OR REPLACE INTO all_sns VALUES (?,?,?,?)", (pcba_sn.upper(), "PCBA", shell_sn.upper(), now))
        conn.execute("INSERT OR REPLACE INTO all_sns VALUES (?,?,?,?)", (shell_sn.upper(), "SHELL", pcba_sn.upper(), now))


def binding_guard_record_duplicate(sn, code_type):
    with sqlite3.connect(BINDING_GUARD_DB) as conn:
        conn.execute("INSERT INTO duplicate_events (sn,code_type,detected_at) VALUES (?,?,?)", (sn.strip().upper(), code_type, int(time.time() * 1000)))


def binding_guard_record_ng_hit(sn, source_station="", batch_id=""):
    with sqlite3.connect(BINDING_GUARD_DB) as conn:
        conn.execute("INSERT INTO ng_detection_events (sn,source_station,batch_id,detected_at) VALUES (?,?,?,?)", (sn.strip().upper(), source_station, batch_id, int(time.time() * 1000)))


def shellbinding_ng_listener():
    url = PDA_EVENT_URL + "?node=shellbinding_agent&types=NG_DEFECT"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    station = event.get("stationCode") or event.get("payload", {}).get("stationCode") or ""
                    if station not in ("auto_ict", "auto_fct"):
                        continue
                    payload = event.get("payload") or {}
                    now = int(time.time() * 1000)
                    with sqlite3.connect(BINDING_GUARD_DB) as conn:
                        for board in payload.get("subBoards") or []:
                            if board.get("isConfirmedNG") and board.get("sn"):
                                conn.execute(
                                    "INSERT OR REPLACE INTO confirmed_ng VALUES (?,?,?,?)",
                                    (str(board["sn"]).upper(), station, payload.get("batchId"), now),
                                )
        except Exception:
            time.sleep(2)


# ================================================================
# MES事件推送到新MES平台
# ================================================================
def mes_bridge_event(sn, result, event_type="bind_scan", error_code=None, pcba_sn="", shell_sn=""):
    """推送扫码/绑定事件到MES看板"""
    if not MES_NEW_ENABLED:
        return
    payload = {
        "action": event_type,
        "payload": {
            "pcbSerial": sn or f"{pcba_sn}/{shell_sn}",
            "stationCode": MES_NEW_STATION,
            "operator": MES_NEW_OPERATOR,
            "eventType": event_type,
            "result": result,
        },
    }
    if error_code:
        payload["payload"]["errorCode"] = error_code
    if pcba_sn:
        payload["payload"]["pcbaSn"] = pcba_sn
    if shell_sn:
        payload["payload"]["shellSn"] = shell_sn
    with _mes_new_lock:
        try:
            _mes_new_queue.put_nowait(payload)
        except queue.Full:
            pass


def _mes_new_worker():
    """后台线程：把队列里的事件POST到MES"""
    while True:
        item = None
        with _mes_new_lock:
            if not _mes_new_queue.empty():
                item = _mes_new_queue.get_nowait()
        if item is None:
            time.sleep(1.0)
            continue
        try:
            import urllib.request, urllib.error, urllib.parse
            url = f"{MES_NEW_API}/mes/events"
            body = json.dumps(item).encode("utf-8")
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                r.read()
        except Exception as e:
            print(f"[mes-bridge] POST failed: {e}")
        time.sleep(0.5)


def start_mes_bridge():
    global _mes_new_thread
    if _mes_new_thread is None or not _mes_new_thread.is_alive():
        _mes_new_thread = threading.Thread(target=_mes_new_worker, daemon=True, name="mes-bridge")
        _mes_new_thread.start()
        print(f"[mes-bridge] started -> {MES_NEW_API}")


def shellbinding_heartbeat_worker():
    """Keep the manual shell-binding station online in the 3D line."""
    while True:
        try:
            event = {
                "type": "AGENT_HEARTBEAT",
                "stationCode": MES_NEW_STATION,
                "payload": {
                    "agent": "qrbinding",
                    "status": "running",
                    "timestamp": int(time.time() * 1000),
                },
            }
            req = urllib.request.Request(
                PDA_EVENT_URL,
                data=json.dumps(event).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                response.read()
        except Exception:
            pass
        time.sleep(HEARTBEAT_SECONDS)


def shellbinding_3d_event(event_type, sn="", result="READ", **extra):
    """Send scanner/binding/guard events to the same 3D bus used by ICT/FCT."""
    try:
        payload = {"sn": sn, "result": result, "eventType": "shellbinding_scan", **extra}
        event = {"type": event_type, "stationCode": MES_NEW_STATION, "payload": payload}
        req = urllib.request.Request(
            PDA_EVENT_URL, data=json.dumps(event).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            response.read()
    except Exception:
        pass


# ================================================================
# MES NG历史查询（拦截上游ICT/FCT漏检的NG板用）
# ================================================================
def check_mes_ng(sn):
    """查询MES ng_defect_records表，返回NG记录列表（空列表=无NG）。
    先查Flask本地NG面板（快速，无JWT），再查MES后端（备用）。
    只拦截 pending/scrapped 状态的NG，已修复的repaired板不拦截。"""
    # ── 第一步：查本地Flask NG面板（推荐） ──
    try:
        url = f"{NGM_NG_CHECK_API}?sn={urllib.parse.quote(sn.strip())}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("found") == True:
                records = data.get("records", [])
                for rec in records:
                    station = rec.get("station_code", "?")
                    status = rec.get("repair_status", "?")
                    defect = rec.get("defect_code", rec.get("error_code", "?"))
                    print(f"[NG拦截] SN={sn} station={station} status={status} defect={defect}")
                return records
    except Exception as e:
        print(f"[NG检查-Flask] {NGM_NG_CHECK_API} 失败: {e}，尝试MES后端...")

    # ── 第二步：查MES后端（备用） ──
    try:
        url = f"{MES_NG_CHECK_API}?sn={urllib.parse.quote(sn.strip())}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("found") == True:
                return data.get("records", [])
            return []
    except Exception as e:
        print(f"[NG检查-MES] {MES_NG_CHECK_API} 失败: {e}")
        return None


def mes_scan_guard(sn, phase):
    """Obtain the authoritative MES verdict for every scanner observation.

    SCAN_GUARD_CHECK is deliberately excluded from the formal production SN
    ledger by the MES API.  Any non-2xx response or unavailable MES blocks the
    station action; local guards remain the first, fast protection layer.
    """
    body = json.dumps({
        "from": "auto_shellbinding",
        "to": "mes",
        "type": "SCAN_GUARD_CHECK",
        "stationCode": MES_NEW_STATION,
        "priority": "critical",
        "payload": {"sn": sn.strip().upper(), "result": "READ", "bindingPhase": phase},
    }).encode("utf-8")
    request = urllib.request.Request(PDA_EVENT_URL, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8") or "{}")
            if result.get("blocked") or result.get("ok") is False:
                return False, str(result.get("code") or "MES_SCAN_BLOCKED"), result
            return True, "CLEAR", result
    except urllib.error.HTTPError as exc:
        try:
            result = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            result = {}
        if MES_OFFLINE_ALLOWED and exc.code >= 500:
            return True, "MES_OFFLINE", {"offline": True, "error": f"HTTP_{exc.code}"}
        return False, str(result.get("code") or f"MES_HTTP_{exc.code}"), result
    except Exception as exc:
        if MES_OFFLINE_ALLOWED:
            return True, "MES_OFFLINE", {"offline": True, "error": str(exc)}
        return False, "MES_GUARD_UNAVAILABLE", {"error": str(exc)}


def mes_binding_commit(pcba_sn, shell_sn):
    """Atomically reserve and bind both codes in MES before local persistence."""
    base = PDA_EVENT_URL.replace("/api/pda/events", "")
    body = json.dumps({
        "stationCode": MES_NEW_STATION,
        "operator": MES_NEW_OPERATOR,
        "pcbaSn": pcba_sn.strip().upper(),
        "shellSn": shell_sn.strip().upper(),
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base + "/api/station/shell-bindings/commit", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8") or "{}")
        if result.get("blocked") or result.get("ok") is False:
            return False, str(result.get("code") or "MES_BINDING_REJECTED"), result
        return True, str(result.get("acknowledgementId") or result.get("eventId") or "MES_ACK"), result
    except urllib.error.HTTPError as exc:
        try:
            result = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            result = {}
        if MES_OFFLINE_ALLOWED and exc.code >= 500:
            return True, "MES_OFFLINE_PENDING", {"offline": True, "error": f"HTTP_{exc.code}"}
        return False, str(result.get("code") or f"MES_HTTP_{exc.code}"), result
    except Exception as exc:
        if MES_OFFLINE_ALLOWED:
            return True, "MES_OFFLINE_PENDING", {"offline": True, "error": str(exc)}
        return False, "MES_BINDING_UNAVAILABLE", {"error": str(exc)}


def offline_sync_worker(store):
    """Retry locally accepted offline bindings after MES becomes reachable."""
    while not _shutdown_event.wait(10):
        for queue_id, board, shell, _attempts in store.pending_offline():
            ok, ack, detail = mes_binding_commit(board, shell)
            if ok and not str(ack).startswith("MES_OFFLINE"):
                store.mark_offline_sent(queue_id)
                record_station_activity("MES_OFFLINE_SYNC_SUCCESS", {"boardSn": board, "shellSn": shell, "ack": ack})
            else:
                store.mark_offline_retry(queue_id, detail or ack)


def report_interception(sn, upstream_station="", upstream_error_code=""):
    """上报拦截记录到Flask NG管理面板"""
    try:
        payload = json.dumps({
            "sn": sn,
            "station_code": "auto_shellbinding",
            "station_name": "PCBA外壳绑码",
            "upstream_station": upstream_station,
            "upstream_error_code": upstream_error_code,
            "interception_type": "MES_NG_BLOCK",
            "operator": "AUTO"
        }).encode("utf-8")
        req = urllib.request.Request(
            NGM_API,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3):
            pass
    except Exception as e:
        print(f"[interception] 上报失败: {e}")


# ================================================================
# WebSocket服务器（扫码/绑定事件实时广播）
# ================================================================
_shutdown_event = threading.Event()
_ws_clients = set()
_ws_broadcast_queue = queue.Queue()


def ws_broadcast(msg: str):
    """广播扫码结果给所有WebSocket客户端"""
    if not WEBSOCKETS_AVAILABLE:
        return
    try:
        _ws_broadcast_queue.put_nowait(msg)
    except queue.Full:
        pass


async def _ws_handler(websocket, path):
    global _ws_clients
    _ws_clients.add(websocket)
    cid = id(websocket)
    print(f"[WS] Client connected: {cid}")
    try:
        async for msg in websocket:
            pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)


async def _ws_broadcast_loop():
    while not _shutdown_event.is_set():
        try:
            msg = await asyncio.get_event_loop().run_in_executor(
                None, _ws_broadcast_queue.get, True, 0.5
            )
            if _ws_clients:
                await asyncio.gather(
                    *[ws.send(msg) for ws in list(_ws_clients)],
                    return_exceptions=True
                )
        except queue.Empty:
            pass
        except Exception as e:
            print(f"[WS] broadcast error: {e}")


async def _ws_server_main():
    print(f"[WS] WebSocket started: ws://0.0.0.0:{WS_PORT}")
    broadcast_task = asyncio.create_task(_ws_broadcast_loop())
    async with websockets.serve(_ws_handler, "0.0.0.0", WS_PORT):
        await _shutdown_event.wait()
    broadcast_task.cancel()


def start_ws_server():
    if not WEBSOCKETS_AVAILABLE:
        print("[WS] websockets not installed, skipping")
        return
    def ws_loop():
        asyncio.run(_ws_server_main())
    t = threading.Thread(target=ws_loop, daemon=True, name="WS-Server")
    t.start()
    print(f"[WS] WebSocket server thread started (port={WS_PORT})")


# ================================================================
# 看门狗（Watchdog）—— 崩溃自动重启
# ================================================================
WATCHDOG_MARKER_FILE = os.path.join(tempfile.gettempdir(), "qrbinding_watchdog.json")
CRASH_MARKER = os.path.join(tempfile.gettempdir(), "qrbinding_crash.json")
# This marker must be shared by the frozen watchdog and worker.  Using the
# extraction directory is unreliable for one-file PyInstaller builds because
# each process can have a different temporary extraction path.
SHUTDOWN_FILE = os.path.join(tempfile.gettempdir(), "qrbinding.shutdown")


def write_watchdog_marker(restart_count: int):
    try:
        with open(WATCHDOG_MARKER_FILE, "w") as f:
            json.dump({"restart_count": restart_count, "watchdog_pid": os.getpid()}, f)
    except Exception:
        pass


def read_watchdog_marker():
    try:
        with open(WATCHDOG_MARKER_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"restart_count": 0, "watchdog_pid": 0}


def run_watchdog():
    """看门狗进程：启动工作子进程，崩溃后自动重启"""
    write_watchdog_marker(0)
    print("=" * 50)
    print("  Watchdog started -- worker process will auto-restart on crash")
    print("=" * 50)
    try:
        while not _shutdown_event.is_set():
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--worker"]
                sout = subprocess.DEVNULL
                serr = subprocess.DEVNULL
            else:
                cmd = [sys.executable, __file__, "--worker"]
                sout = None
                serr = None
            proc = subprocess.Popen(cmd, stdout=sout, stderr=serr)
            print(f"[WATCHDOG] Worker process started (PID: {proc.pid})")
            proc.wait()
            if _shutdown_event.is_set():
                break
            # The worker requested a normal operator shutdown.  Do not let
            # the watchdog immediately resurrect it.
            if os.path.exists(SHUTDOWN_FILE):
                try:
                    os.remove(SHUTDOWN_FILE)
                except OSError:
                    pass
                print("[WATCHDOG] Normal shutdown requested")
                break
            if proc.returncode == 0:
                print("[WATCHDOG] Worker process exited normally")
                break
            if proc.returncode == 42:
                for _ in range(2):
                    if _shutdown_event.is_set():
                        return
                    time.sleep(1)
                continue
            write_watchdog_marker(read_watchdog_marker().get("restart_count", 0) + 1)
            print(f"[WATCHDOG] Worker process crashed (code: {proc.returncode}), restarting in 3s")
            for _ in range(3):
                if _shutdown_event.is_set():
                    return
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown_event.set()


# ================================================================
# 自动启动（Windows注册表）
# ================================================================
AUTO_START_NAME = "QRBindingAutoStart"


def set_auto_start(enabled: bool):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, AUTO_START_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, AUTO_START_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[auto-start] set failed: {e}")


def get_auto_start():
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, AUTO_START_NAME)
            winreg.CloseKey(key)
            return bool(val)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


# ================================================================
# station_config SQLite（工位/产线/操作员配置）
# ================================================================
def _get_db_path():
    return os.path.join(APP_FOLDER, "qrbinding_config.db")


def init_station_config():
    try:
        conn = sqlite3.connect(_get_db_path())
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS station_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
        """)
        cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('station', 'PACK-BIND-01')")
        cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('line_name', 'AUTO-LINE-1')")
        cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('operator', '')")
        conn.commit()
        conn.close()
        print("[station_config] Initialization complete")
    except Exception as e:
        print(f"[station_config] init error: {e}")


def get_station_config():
    try:
        conn = sqlite3.connect(_get_db_path())
        rows = conn.execute("SELECT key, value FROM station_config").fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def save_station_config(cfg: dict):
    try:
        conn = sqlite3.connect(_get_db_path())
        for key in ("station", "line_name", "operator"):
            if key in cfg:
                conn.execute("INSERT OR REPLACE INTO station_config (key, value) VALUES (?, ?)", (key, cfg[key]))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[station_config] save error: {e}")


# ================================================================
# IP注册 + 打开浏览器
# ================================================================
def get_local_ips():
    ips = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            primary = s.getsockname()[0]
            if primary and primary != "127.0.0.1":
                ips.append(primary)
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for addr in socket.getaddrinfo(hostname, None):
            ip = addr[4][0]
            if ip and not ip.startswith("127.") and ":" not in ip:
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    return ips


def register_ip_to_mes():
    try:
        cfg = get_station_config()
        station_code = cfg.get("station", "PACK-BIND-01")
        ips = get_local_ips()
        ip = ips[0] if ips else "127.0.0.1"
        payload = json.dumps({"ip_address": ip}).encode("utf-8")
        req = urllib.request.Request(
            f"{MES_NEW_API}/mes/stations/{station_code}/ip",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        print(f"[IP REGISTER] reported {ip} for station {station_code}")
    except Exception as e:
        print(f"[IP REGISTER] failed: {e}")


def open_browser():
    def _open():
        time.sleep(1.5)
        url = f"http://localhost:{LOCAL_PORT}/"
        print(f"[browser] Opening: {url}")
        try:
            subprocess.Popen(["msedge", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            try:
                edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                subprocess.Popen([edge_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[browser] Failed: {e}")
    threading.Thread(target=_open, daemon=True).start()


# ================================================================
# SN校验规则
# ================================================================
class SNRule:

    def __init__(self, pattern, prefix='', min_length=1, max_length=100, description=''):
        self.pattern = re.compile(pattern)
        self.prefix = prefix
        self.min_length = min_length
        self.max_length = max_length
        self.description = description

    def validate(self, sn: str) -> Tuple[bool, str]:
        sn = sn.strip()
        if not sn:
            return (False, 'SN为空')
        if len(sn) < self.min_length:
            return (False, f"过短({len(sn)}<{self.min_length})")
        if len(sn) > self.max_length:
            return (False, f"过长({len(sn)}>{self.max_length})")
        if self.prefix and not sn.startswith(self.prefix):
            return (False, f"应以{self.prefix}开头")
        # A scanner may deliver a long code in chunks. Prefix matching would
        # accept and submit a partial SN; only an exact complete rule match is
        # allowed to proceed.
        if self.pattern.fullmatch(sn):
            return (True, 'OK')
        return (False, f"格式不匹配: {self.description}")


class SNValidator:

    def __init__(self, config_path: Optional[str] = None):
        self.pcba_rules = []
        self.shell_rules = []
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

    def _load_config(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f).get("sn_rules", {})
            for key, rules_list, cfg_key in [
                ("pcba", self.pcba_rules, cfg.get("pcba", {})),
                ("shell", self.shell_rules, cfg.get("shell", {}))
            ]:
                rules_list.clear()
                for p in cfg_key.get("patterns", []):
                    if p and p.strip():
                        try:
                            re.compile(p.strip())
                        except re.error:
                            print(f"Invalid regex skipped: {p}")
                            continue
                        rules_list.append(SNRule(
                            pattern=p.strip(),
                            prefix=cfg_key.get("prefix", ""),
                            min_length=cfg_key.get("min_length", 1),
                            max_length=cfg_key.get("max_length", 100),
                            description=cfg_key.get("description", "")
                        ))
        except Exception as e:
            print(f"Rule load failed: {e}")

    def _check(self, rules: List[SNRule], sn: str, label: str) -> Tuple[bool, str]:
        sn = sn.strip()
        if not sn:
            return (False, 'SN为空')
        if not rules:
            return (True, f"{label}规则未设置, 自动通过")
        for r in rules:
            ok, msg = r.validate(sn)
            if ok:
                return (True, f"{label}通过: {r.description}")
        return (False, f"{label}规则不匹配")

    def validate_pcba(self, sn: str) -> Tuple[bool, str]:
        return self._check(self.pcba_rules, sn, "PCBA")

    def validate_shell(self, sn: str) -> Tuple[bool, str]:
        return self._check(self.shell_rules, sn, "外壳")

    def pcba_rules_desc(self) -> List[str]:
        if self.pcba_rules:
            return [r.description for r in self.pcba_rules]
        return ["未设置规则, 不校验"]

    def shell_rules_desc(self) -> List[str]:
        if self.shell_rules:
            return [r.description for r in self.shell_rules]
        return ["未设置规则, 不校验"]


class VoiceEngine:

    def __init__(self, config_path: Optional[str] = None):
        self.enabled = True
        self.language = "zh"
        self.prompt_sets = {
            "zh": {"scan_pcba": "请扫板码", "scan_shell": "请扫壳码", "binding": "绑定", "violation": "违规", "success": "绑定成功"},
            "en": {"scan_pcba": "Please scan board QR", "scan_shell": "Please scan shell QR", "binding": "Binding", "violation": "Violation", "success": "Binding successful"},
            "vi": {"scan_pcba": "Vui lòng quét mã QR bo mạch", "scan_shell": "Vui lòng quét mã QR vỏ", "binding": "Đang liên kết", "violation": "Vi phạm", "success": "Liên kết thành công"},
        }
        self.prompts = {
            "scan_pcba": "请扫版码",
            "scan_shell": "请扫壳码",
            "binding": "绑定",
            "violation": "违规",
            "success": "绑定成功"
        }
        if config_path and os.path.exists(config_path):
            try:
                vc = json.load(open(config_path, "r", encoding="utf-8")).get("voice", {})
                self.enabled = vc.get("enabled", True)
                self.prompts.update(vc.get("prompts", {}))
            except Exception:
                pass

    def _speak(self, text: str):
        if not self.enabled or not text:
            return
        try:
            safe = text.replace("'", "''")
            culture = {"zh": "zh-CN", "en": "en-US", "vi": "vi-VN"}.get(self.language, "zh-CN")
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                 f"Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; try{{$s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet,[System.Speech.Synthesis.VoiceAge]::NotSet,0,[Globalization.CultureInfo]::GetCultureInfo('{culture}'))}}catch{{}}; $s.Speak('{safe}')"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            )
        except Exception:
            pass

    def speak(self, text: str):
        self._speak(text)

    def set_language(self, language: str):
        self.language = language if language in self.prompt_sets else "zh"

    def translate(self, text: str) -> str:
        direct = {
            "可以绑定": {"en": "Ready to bind", "vi": "Sẵn sàng liên kết"},
            "请扫描外壳码": {"en": "Please scan shell QR", "vi": "Vui lòng quét mã QR vỏ"},
            "解绑已批准": {"en": "Unbinding approved", "vi": "Đã phê duyệt hủy liên kết"},
        }
        return direct.get(text, {}).get(self.language, text)

    def say(self, key: str):
        if key in self.prompts:
            self._speak(self.prompt_sets.get(self.language, self.prompt_sets["zh"]).get(key, self.prompts[key]))


class BindingStore:

    def __init__(self):
        self.db_path = os.path.join(app_root(), "binding_records.db")
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pcba_sn TEXT NOT NULL, shell_sn TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                created_date TEXT DEFAULT (date('now')))""")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bd_pcba ON bindings(pcba_sn)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bd_shell ON bindings(shell_sn)")
            cur.execute("""CREATE TABLE IF NOT EXISTS mes_offline_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pcba_sn TEXT NOT NULL,
                shell_sn TEXT NOT NULL,
                queued_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING')""")
            cur.execute("""CREATE TABLE IF NOT EXISTS unbind_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, board_sn TEXT NOT NULL, shell_sn TEXT NOT NULL,
                operator_name TEXT NOT NULL, request_reason TEXT NOT NULL,
                quality_approver TEXT NOT NULL, quality_reason TEXT NOT NULL,
                line_leader TEXT NOT NULL, line_leader_reason TEXT NOT NULL,
                requested_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                approved_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                status TEXT NOT NULL DEFAULT 'APPROVED_UNBOUND')""")
            cur.execute("""CREATE TABLE IF NOT EXISTS shell_board_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_sn TEXT NOT NULL UNIQUE,
                shell_sn TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                bound_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                station_code TEXT NOT NULL DEFAULT 'auto_shellbinding',
                binding_line TEXT NOT NULL DEFAULT 'auto_line'
            )""")
            try:
                cur.execute("ALTER TABLE shell_board_mapping ADD COLUMN binding_line TEXT NOT NULL DEFAULT 'auto_line'")
            except sqlite3.OperationalError:
                pass
            # Backfill earlier valid binding records into the explicit 1:1 mapping.
            cur.execute("""INSERT OR IGNORE INTO shell_board_mapping (board_sn,shell_sn,bound_at)
                           SELECT pcba_sn,shell_sn,created_at FROM bindings""")
            # 机器表：记录每台机器的PCBA码和外壳码
            cur.execute("""CREATE TABLE IF NOT EXISTS machines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL UNIQUE,
                pcba_sn TEXT,
                shell_sn TEXT,
                last_updated TEXT DEFAULT (datetime('now','localtime')))""")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mach_pcba ON machines(pcba_sn)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mach_shell ON machines(shell_sn)")
            # 迁移：添加 created_date 列（5年留存标识）
            try:
                cur.execute("ALTER TABLE machines ADD COLUMN created_date TEXT DEFAULT (date('now'))")
            except sqlite3.OperationalError:
                pass  # 列已存在

    def save(self, pcba_sn: str, shell_sn: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO shell_board_mapping (board_sn,shell_sn) VALUES (?, ?)",
                        (pcba_sn, shell_sn))
            cur.execute("INSERT INTO bindings (pcba_sn, shell_sn) VALUES (?, ?)",
                        (pcba_sn, shell_sn))
            conn.commit()
            return {"id": cur.lastrowid, "pcba": pcba_sn, "shell": shell_sn}

    def exists_pcba(self, sn: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM bindings WHERE pcba_sn=?", (sn.strip(),))
            return cur.fetchone()[0] > 0

    def exists_shell(self, sn: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM bindings WHERE shell_sn=?", (sn.strip(),))
            return cur.fetchone()[0] > 0

    def queue_offline(self, pcba_sn: str, shell_sn: str, error: str = "MES_OFFLINE"):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO mes_offline_queue(pcba_sn,shell_sn,last_error) VALUES(?,?,?)",
                         (pcba_sn.strip(), shell_sn.strip(), error))

    def pending_offline(self, limit=20):
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT id,pcba_sn,shell_sn,attempts FROM mes_offline_queue WHERE status='PENDING' ORDER BY id LIMIT ?", (limit,)).fetchall()

    def mark_offline_sent(self, queue_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE mes_offline_queue SET status='SENT' WHERE id=?", (queue_id,))

    def mark_offline_retry(self, queue_id, error):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE mes_offline_queue SET attempts=attempts+1,last_error=? WHERE id=?", (str(error)[:500], queue_id))

    def get_machine(self, machine_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT machine_id, pcba_sn, shell_sn, last_updated FROM machines WHERE machine_id=?", (machine_id,))
            row = cur.fetchone()
            if row:
                return {"machine_id": row[0], "pcba_sn": row[1], "shell_sn": row[2], "last_updated": row[3]}
            return None

    def update_machine(self, machine_id: str, pcba_sn: str, shell_sn: str):
        """Upsert machine binding — created_date stays as first bind time (5-year retention)"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM machines WHERE machine_id=?", (machine_id,))
            if cur.fetchone() is None:
                # 首次绑定，记录创建日期（5年留存起点）
                cur.execute("""INSERT INTO machines (machine_id, pcba_sn, shell_sn, created_date)
                               VALUES (?, ?, ?, date('now'))""",
                            (machine_id, pcba_sn, shell_sn))
            else:
                cur.execute("""UPDATE machines SET
                               pcba_sn=?, shell_sn=?,
                               last_updated=datetime('now','localtime')
                               WHERE machine_id=?""",
                            (pcba_sn, shell_sn, machine_id))
            conn.commit()

    def list_machines(self, limit=100):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT machine_id, pcba_sn, shell_sn, last_updated FROM machines ORDER BY last_updated DESC LIMIT ?", (limit,))
            return [{"machine_id": r[0], "pcba_sn": r[1], "shell_sn": r[2], "last_updated": r[3]} for r in cur.fetchall()]

    def today_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM bindings WHERE created_date=date('now')")
            return cur.fetchone()[0]

    def all_records(self) -> List[Tuple]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT pcba_sn, shell_sn, created_at FROM bindings ORDER BY id DESC")
            return cur.fetchall()

    def export_csv(self) -> str:
        path = os.path.join(app_root(), "binding_records.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["PCBA码", "外壳码", "时间"])
            for r in reversed(self.all_records()):
                w.writerow(r)
        return path

    def clear_all(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM bindings")
            conn.execute("DELETE FROM shell_board_mapping")

    def delete_by_pcba_shell(self, pcba_sn: str, shell_sn: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM bindings WHERE pcba_sn=? AND shell_sn=?",
                      (pcba_sn, shell_sn))
            conn.execute("DELETE FROM shell_board_mapping WHERE board_sn=? AND shell_sn=?",
                      (pcba_sn, shell_sn))

    def approved_unbind(self, pcba_sn, shell_sn, operator, reason, quality, quality_reason, leader, leader_reason):
        """Never delete binding history; deactivate only after two independent approvals."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""INSERT INTO unbind_audit
              (board_sn,shell_sn,operator_name,request_reason,quality_approver,quality_reason,line_leader,line_leader_reason)
              VALUES (?,?,?,?,?,?,?,?)""", (pcba_sn,shell_sn,operator,reason,quality,quality_reason,leader,leader_reason))
            conn.execute("UPDATE shell_board_mapping SET status='unbound' WHERE board_sn=? AND shell_sn=? AND status='active'", (pcba_sn,shell_sn))


class AppState(Enum):
    IDLE = 0
    BINDING = 1
    BOUND = 2
    VIOLATION = 3
    BUSY = 4


STATE_TEXT = {
    AppState.IDLE: "等待扫码",
    AppState.BINDING: "绑定中...",
    AppState.BOUND: "✅ 绑定成功",
    AppState.VIOLATION: "❌ 违规",
    AppState.BUSY: "⏳ 检测中..."
}


class App:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("QR码绑定系统 - PCBA主板与外壳绑定")
        self.root.geometry("780x620")
        self.root.after_idle(lambda: install_station_tabs(self.root))
        self.root.minsize(650, 500)
        self.root.configure(bg="#f0f2f5")
        self.cfg = self._load_cfg()
        # MES-downloaded PCBA expectations are isolated from binding history.
        # Presence here authorizes route lookup; it never means "already bound".
        self.expected_pcba_manifest = ExpectedSnManifest(
            BINDING_GUARD_DB, PDA_EVENT_URL, MES_NEW_STATION, interval=15)
        init_binding_guard_db()
        init_station_activity_db()
        self.validator = SNValidator(CONFIG_FILE)
        self.voice = VoiceEngine(CONFIG_FILE)
        self.store = BindingStore()
        self.state = AppState.IDLE
        self.pcba_sn = ""
        self.shell_sn = ""
        self.total_ok = 0
        self.total_bad = 0
        self.history_check_bypass = False
        self.scan_var = tk.StringVar()
        self.last_pair_var = tk.StringVar(value="上次成功绑定：—")
        self.health_var = tk.StringVar(value="MES 检查中 · SQLite 检查中 · 工单检查中")
        self.last_ack_var = tk.StringVar(value="MES ACK：—")
        self.voice_q = queue.Queue()
        self._voice_worker_running = True
        self._start_voice()
        threading.Thread(target=offline_sync_worker, args=(self.store,), daemon=True,
                         name="qrbinding-offline-sync").start()
        self._scan_timer = None
        self._last_scan_len = 0
        self._build_ui()
        threading.Thread(target=shellbinding_heartbeat_worker, daemon=True, name="shellbinding-heartbeat").start()
        threading.Thread(target=binding_inventory_reconcile_worker, daemon=True,
                         name="shellbinding-inventory-reconcile").start()
        threading.Thread(target=shellbinding_ng_listener, daemon=True, name="shellbinding-ng-listener").start()
        threading.Thread(target=station_activity_sync_worker, daemon=True, name="station-activity-sync").start()
        self._update_ui()
        self.root.after(300, lambda: self.voice.say("scan_pcba"))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._qt_last_request = ""
        self.root.after(250, self._poll_qt_command)
        if os.environ.get("QRBINDING_EMBEDDED_ENGINE") == "1":
            self.root.withdraw()

    def _poll_qt_command(self):
        """Execute commands from the Qt shell on Tk's own UI thread."""
        path = os.path.join(APP_FOLDER, "qrbinding_qt_command.json")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as handle:
                    message = json.load(handle)
                request_id = str(message.get("requestId", ""))
                if request_id and request_id != self._qt_last_request:
                    self._qt_last_request = request_id
                    command = str(message.get("command", ""))
                    if command == "scan_sn": self._process_scan(str(message.get("sn", "")))
                    elif command == "reset_pair": self._do_reset()
                    elif command == "show_rules": self._show_rules()
                    elif command == "show_mapping_table": self._show_mapping_table()
                    elif command == "export_csv": self._export_csv()
                    elif command == "request_scrap": request_direct_scrap(self.root, MES_NEW_STATION, MES_NEW_API, self.scan_var.get())
                    elif command == "release_alarm": self._clear_violation()
        except Exception as exc:
            self._log("WARN", "Qt command failed: %s" % exc)
        finally:
            self.root.after(250, self._poll_qt_command)

    def _load_cfg(self) -> dict:
        d = {
            "binding_rules": {
                "prevent_duplicate_pcba": True,
                "prevent_duplicate_shell": True,
                "auto_bind": True
            }
        }
        if os.path.exists(CONFIG_FILE):
            try:
                loaded = json.load(open(CONFIG_FILE, "r", encoding="utf-8"))
                for k in d:
                    if k in loaded:
                        d[k].update(loaded[k])
            except Exception:
                pass
        return d

    def _build_ui(self):
        self.root.configure(bg="#070d18")
        header=tk.Frame(self.root,bg="#0b1f35",padx=14,pady=9)
        header.pack(fill=tk.X)
        tk.Label(header,text="PCBA外壳绑码 / QR BINDING",font=('Microsoft YaHei UI',18,'bold'),
                 fg="#e0f2fe",bg="#0b1f35").pack(side=tk.LEFT)
        tk.Label(header,text="数据源: USB/TCP扫码枪 · PCBA码 + 外壳码",font=('Microsoft YaHei UI',9),fg="#a7f3d0",bg="#0b1f35").pack(side=tk.LEFT,padx=12)
        try: station_ip=socket.gethostbyname(socket.gethostname())
        except Exception: station_ip="UNKNOWN"
        tk.Label(header,text=f"{MES_NEW_STATION} · {station_ip} · v{APP_VERSION}",font=('Consolas',9),fg="#93c5fd",bg="#0b1f35").pack(side=tk.LEFT,padx=8)
        tk.Label(header,text="● MES ONLINE",font=('Segoe UI',10,'bold'),fg="#22c55e",bg="#0b1f35").pack(side=tk.RIGHT)
        tk.Button(header,text="申请报废",command=lambda: request_direct_scrap(self.root,MES_NEW_STATION,MES_NEW_API,self.scan_var.get()),
                  font=('Microsoft YaHei UI',10,'bold'),fg="white",bg="#b91c1c").pack(side=tk.RIGHT,padx=8)
        start_sync_worker(MES_NEW_STATION, MES_NEW_API)
        self.station_alarm=StationAlarm(self.root,lambda sns:shellbinding_3d_event("DUPLICATE_ALARM_RELEASE",sns=sns,releasedAt=int(time.time()*1000)),MES_NEW_STATION,PDA_EVENT_URL)
        self.last_scanner_input=0
        self.scanner_status=tk.StringVar(value="扫码枪：等待输入")
        tk.Label(header,textvariable=self.scanner_status,font=('Microsoft YaHei UI',10,'bold'),fg="#67e8f9",bg="#0b1f35").pack(side=tk.RIGHT,padx=14)
        self.language_controller=TrilingualController(self.root,header,on_change=self._on_voice_language)
        # Reserve a separate action row.  The retest control must not share the
        # header's right-side space with MES status, scrap, or scanner controls.
        self.retest_action_bar = tk.Frame(self.root, bg="#10243b", height=46,
                                          highlightbackground="#294968", highlightthickness=1)
        self.retest_action_bar.pack(fill=tk.X, padx=12, pady=(0, 4))
        self.root._retest_host = self.retest_action_bar
        self.pass_box_var=tk.StringVar(value="0")
        self.confirmed_box_var=tk.StringVar(value="0")
        box_row=tk.Frame(self.root,bg="#07111f",padx=10,pady=6)
        box_row.pack(fill=tk.X)
        for title,color,var in (("PASS","#22c55e",self.pass_box_var),("Confirmed NG","#ef4444",self.confirmed_box_var)):
            box=tk.Frame(box_row,bg="#10243b",highlightbackground=color,highlightthickness=2,padx=8,pady=5)
            box.pack(side=tk.LEFT,fill=tk.X,expand=True,padx=4)
            tk.Label(box,text="▱",bg="#10243b",fg=color,font=('Segoe UI Symbol',16,'bold')).pack(side=tk.LEFT,padx=(0,6))
            tk.Label(box,text=title,bg="#10243b",fg=color,font=('Segoe UI',10,'bold')).pack(side=tk.LEFT)
            tk.Label(box,textvariable=var,bg=color,fg="white",width=4,font=('Segoe UI',10,'bold')).pack(side=tk.RIGHT)
        nb = ttk.Notebook(self.root)
        self.notebook=nb
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        self.tab_bind = tk.Frame(nb, bg="#f0f2f5")
        nb.add(self.tab_bind, text="📋 绑定")
        self._build_bind_tab()
        self.tab_records = tk.Frame(nb, bg="#f0f2f5")
        nb.add(self.tab_records, text="📐 记录")
        self._build_records_tab()
        self.tab_handover=tk.Frame(nb,bg="#0f172a")
        nb.add(self.tab_handover,text="工程交接单 / HANDOVER")
        self._build_handover_tab()
        self.tab_residence=tk.Frame(nb,bg="#0f172a")
        nb.add(self.tab_residence,text="工位滞留监控 / RESIDENCE")
        self._build_residence_tab()
        self.tab_raw=tk.Frame(nb,bg="#0f172a"); nb.add(self.tab_raw,text="原始数据 / RAW DATA")
        self.raw_tree=ttk.Treeview(self.tab_raw,columns=("time","source","location","raw","status","sn"),show="headings")
        for key,label in (("time","接收时间"),("source","数据源"),("location","设备/接口"),("raw","原始内容"),("status","解析状态"),("sn","关联SN")): self.raw_tree.heading(key,text=label)
        self.raw_tree.column("raw",width=390); self.raw_tree.pack(fill=tk.BOTH,expand=True,padx=8,pady=8)
        bar = tk.Frame(self.root, bg="#dfe6e9", height=24, relief=tk.SUNKEN, bd=1)
        bar.pack(fill=tk.X, pady=(0, 0))
        self.footer = tk.Label(bar, text="就绪 | 绑定: 0  违规: 0",
                               font=('微软雅黑', 9), fg="#636e72",
                               bg="#dfe6e9", anchor="w", padx=8)
        self.footer.pack(fill=tk.X)
        self.root.after(200, lambda: self.scan_text.focus_set())
        self.root.after(500,self._refresh_mes_pages)
        self.root.after(1000,self._refresh_scanner_status)
        self.root.after(300, self._run_preflight)

    def _refresh_scanner_status(self):
        if self.last_scanner_input:
            elapsed=int(time.time()-self.last_scanner_input)
            self.scanner_status.set(f"扫码枪：最近输入 {elapsed}秒前")
        else:
            self.scanner_status.set("扫码枪：等待输入")
        self.root.after(1000,self._refresh_scanner_status)

    def _run_preflight(self):
        self.health_var.set("工位预检运行中…")
        def worker():
            mes_ok=sqlite_ok=api_ok=False; work_order="未选择"
            try:
                with sqlite3.connect(self.store.db_path) as conn:
                    conn.execute("SELECT COUNT(*) FROM shell_board_mapping").fetchone()
                sqlite_ok=True
            except Exception: pass
            base=PDA_EVENT_URL.replace("/api/pda/events","")
            try:
                with urllib.request.urlopen(base+"/api/station/handovers?stationCode="+MES_NEW_STATION,timeout=5) as response:
                    mes_ok=response.status==200
            except Exception: pass
            try:
                with urllib.request.urlopen(base+"/api/station/qr-workorders?stationCode="+MES_NEW_STATION,timeout=5) as response:
                    data=json.loads(response.read().decode("utf-8")); active=data.get("active") or []
                    selected=next((row for row in active if str(row.get("status","")).upper()=="ACTIVE"),None)
                    work_order=str((selected or {}).get("workOrderCode") or "未选择")
            except Exception: pass
            try:
                req=urllib.request.Request(base+"/api/station/shell-bindings/commit",data=b"{}",method="POST",
                    headers={"Content-Type":"application/json"})
                urllib.request.urlopen(req,timeout=5)
            except urllib.error.HTTPError as exc: api_ok=exc.code==400
            except Exception: pass
            text=(f"MES {'在线' if mes_ok else '离线'} · SQLite {'正常' if sqlite_ok else '异常'} · "
                  f"原子绑定API {'正常' if api_ok else '异常'} · 工单 {work_order}")
            self.root.after(0,lambda:self.health_var.set(text))
            self.root.after(0,lambda:self._log("INFO", "工位预检："+text))
        threading.Thread(target=worker,daemon=True,name="qrbinding-preflight").start()

    def _show_rejected_history(self):
        window=tk.Toplevel(self.root);window.title("本机拒绝记录 / REJECTED SCANS");window.geometry("920x480")
        tree=ttk.Treeview(window,columns=("time","type","sn","detail"),show="headings")
        for key,label in (("time","时间"),("type","拒绝类型"),("sn","SN"),("detail","详细信息")):
            tree.heading(key,text=label)
        tree.column("time",width=180);tree.column("type",width=160);tree.column("sn",width=220);tree.column("detail",width=320)
        tree.pack(fill=tk.BOTH,expand=True,padx=10,pady=10)
        rows=[]
        try:
            with sqlite3.connect(BINDING_GUARD_DB) as conn:
                rows += [(datetime.datetime.fromtimestamp(r[2]/1000).strftime("%Y-%m-%d %H:%M:%S"),"重复码",r[0],r[1])
                         for r in conn.execute("SELECT sn,code_type,detected_at FROM duplicate_events ORDER BY detected_at DESC LIMIT 500")]
                rows += [(datetime.datetime.fromtimestamp(r[3]/1000).strftime("%Y-%m-%d %H:%M:%S"),"NG拦截",r[0],f"{r[1] or '-'} / {r[2] or '-'}")
                         for r in conn.execute("SELECT sn,source_station,batch_id,detected_at FROM ng_detection_events ORDER BY detected_at DESC LIMIT 500")]
        except Exception as exc: rows.append(("","数据库错误","",str(exc)))
        for row in sorted(rows,reverse=True)[:1000]: tree.insert("","end",values=row)

    def _build_handover_tab(self):
        cols=("id","batch","source","destination","members","status","sent","received","accepted")
        self.handover_tree=ttk.Treeview(self.tab_handover,columns=cols,show="headings")
        for key,label in (("id","交接单号"),("batch","整盘编号"),("source","来源工位"),("destination","目标工位"),
                          ("members","SN数量"),("status","状态"),("sent","送出时间"),("received","接收时间"),("accepted","接收人/扫码枪")):
            self.handover_tree.heading(key,text=label)
        self.handover_tree.pack(fill=tk.BOTH,expand=True,padx=8,pady=8)

    def _build_residence_tab(self):
        cols=("sn","batch","state","ng","entered","duration","alarm")
        self.residence_tree=ttk.Treeview(self.tab_residence,columns=cols,show="headings")
        for key,label in (("sn","SN"),("batch","整盘编号"),("state","状态"),("ng","NG"),
                          ("entered","入站时间"),("duration","滞留时间"),("alarm","报警")):
            self.residence_tree.heading(key,text=label)
        self.residence_tree.pack(fill=tk.BOTH,expand=True,padx=8,pady=8)

    def _refresh_mes_pages(self):
        try:
            base=PDA_EVENT_URL.replace("/api/pda/events","")
            with urllib.request.urlopen(base+"/api/station/handovers?stationCode=auto_shellbinding",timeout=5) as response:
                rows=json.loads(response.read().decode("utf-8")).get("items",[])
            self.handover_tree.delete(*self.handover_tree.get_children())
            for row in rows:
                self.handover_tree.insert("","end",values=(row.get("transferId",""),row.get("batchId",""),row.get("sourceStation",""),
                    row.get("destinationStation",""),row.get("memberCount",""),row.get("status",""),row.get("sentAt",""),row.get("receivedAt",""),row.get("acceptedBy","")))
            with urllib.request.urlopen(base+"/api/station/residence-stats?stationCode=auto_shellbinding",timeout=5) as response:
                data=json.loads(response.read().decode("utf-8"))
            threshold=int(data.get("thresholdMinutes",30))*60
            self.residence_tree.delete(*self.residence_tree.get_children())
            for row in data.get("current",[]):
                seconds=int(row.get("seconds",0))
                self.residence_tree.insert("","end",values=(row.get("sn",""),row.get("batchId",""),row.get("productState",""),
                    "是" if row.get("isNg") else "否",row.get("enteredAt",""),f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}",
                    "超时" if seconds>=threshold else "正常"))
            with urllib.request.urlopen(base+"/api/station/bucket-snapshots",timeout=5) as response:
                snapshots=json.loads(response.read().decode("utf-8")).get("items",[])
            station={row.get("bucketName"):row.get("payload",[]) for row in snapshots if row.get("stationCode")==MES_NEW_STATION}
            self.pass_box_var.set(str(len(station.get("pass",[]))))
            self.confirmed_box_var.set(str(len(station.get("confirmed_ng",[]))))
        except Exception:
            pass
        self.root.after(5000,self._refresh_mes_pages)

    def _build_bind_tab(self):
        main = self.tab_bind
        tk.Label(main, text="PCBA主板 ↔ 外壳  |  先扫PCBA版码，后扫壳码，MES自动绑定",
                 font=('微软雅黑', 10), fg="#636e72",
                 bg="#f0f2f5").pack(anchor="w", pady=(0, 6))
        card = tk.Frame(main, bg="white", relief=tk.GROOVE, bd=1)
        card.pack(fill=tk.X, pady=(0, 6))
        row1 = tk.Frame(card, bg="white")
        row1.pack(fill=tk.X, padx=14, pady=(10, 4))
        tk.Label(row1, text="版码:", font=('微软雅黑', 11, 'bold'), fg="#e17055",
                 bg="white", width=5, anchor="w").pack(side=tk.LEFT)
        self.pcba_var = tk.StringVar()
        self.pcba_entry = tk.Entry(row1, textvariable=self.pcba_var,
                                   font=('Consolas', 14), bd=1,
                                   relief=tk.SUNKEN, bg="#fff3f0",
                                   state="readonly", readonlybackground="#fff3f0")
        self.pcba_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.pcba_icon = tk.Label(row1, text="⬚", font=('微软雅黑', 14), bg="white")
        self.pcba_icon.pack(side=tk.LEFT, padx=(6, 0))
        row2 = tk.Frame(card, bg="white")
        row2.pack(fill=tk.X, padx=14, pady=(4, 10))
        tk.Label(row2, text="壳码:", font=('微软雅黑', 11, 'bold'), fg="#0984e3",
                 bg="white", width=5, anchor="w").pack(side=tk.LEFT)
        self.shell_var = tk.StringVar()
        self.shell_entry = tk.Entry(row2, textvariable=self.shell_var,
                                    font=('Consolas', 14), bd=1,
                                    relief=tk.SUNKEN, bg="#f0f8ff",
                                    state="readonly", readonlybackground="#f0f8ff")
        self.shell_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.shell_icon = tk.Label(row2, text="⬚", font=('微软雅黑', 14), bg="white")
        self.shell_icon.pack(side=tk.LEFT, padx=(6, 0))
        self.scan_text = tk.Text(main, font=('Consolas', 13), height=1, bd=2,
                                 relief=tk.SUNKEN, bg="#fff8e1")
        self.scan_text.pack(fill=tk.X, ipady=3, pady=(0, 6))
        self.scan_text.bind("<KeyPress>", self._on_scan_key)
        self.scan_text.bind("<Return>", self._on_scan)
        # This screen has its own scanner buffer. Avoid the shared global
        # wedge listener, which can submit partial SNs on remote PCs.
        self.root.bind("<Button-1>", self._refocus_scan, add="+")
        self._scan_timer = None
        btn_row = tk.Frame(main, bg="#f0f2f5")
        btn_row.pack(fill=tk.X, pady=(0, 6))
        self.bind_btn = tk.Button(btn_row, text="✅ 绑定",
                                  font=('微软雅黑', 11, 'bold'), bg="#00b894",
                                  fg="white", bd=0, cursor="hand2",
                                  command=self._do_bind,
                                  activebackground="#00a381",
                                  state=tk.DISABLED, padx=18, pady=4)
        self.bind_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.reset_btn = tk.Button(btn_row, text="🔄 重置",
                                   font=('微软雅黑', 10), bg="#dfe6e9",
                                   fg="#2d3436", bd=0, cursor="hand2",
                                   command=self._do_reset, padx=14, pady=4)
        self.reset_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.reset_btn.config(text="清除当前输入")
        tk.Button(btn_row, text="工位预检", font=('微软雅黑', 10, 'bold'), bg="#0f766e",
                  fg="white", bd=0, command=self._run_preflight, padx=12, pady=4).pack(side=tk.LEFT,padx=(0,6))
        tk.Button(btn_row, text="拒绝记录", font=('微软雅黑', 10), bg="#b45309",
                  fg="white", bd=0, command=self._show_rejected_history, padx=12, pady=4).pack(side=tk.LEFT,padx=(0,6))
        self.history_bypass_btn = tk.Button(
            btn_row, text="历史检查：拦截", font=('微软雅黑', 10, 'bold'),
            bg="#334155", fg="white", bd=0,
            command=self._toggle_history_check_bypass, padx=12, pady=4)
        self.history_bypass_btn.pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_row, text="查看绑定表", font=('微软雅黑', 10), bg="#0ea5e9",
                  fg="white", bd=0, cursor="hand2", command=self._show_mapping_table,
                  padx=14, pady=4).pack(side=tk.LEFT, padx=(0, 6))
        self.rule_btn = tk.Button(btn_row, text="✎ 规则",
                                  font=('微软雅黑', 10), bg="#74b9ff",
                                  fg="white", bd=0, cursor="hand2",
                                  command=self._show_rules, padx=14, pady=4)
        self.rule_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.test_btn = tk.Button(btn_row, text="🔍 测试规则",
                                  font=('微软雅黑', 10), bg="#a29bfe",
                                  fg="white", bd=0, cursor="hand2",
                                  command=self._show_test_rules, padx=14, pady=4)
        self.test_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.status_label = tk.Label(btn_row, text="等待扫码...",
                                     font=('微软雅黑', 10), fg="#0984e3",
                                     bg="#f0f2f5")
        self.status_label.pack(side=tk.RIGHT, padx=(0, 4))
        health=tk.Frame(main,bg="#10243b",padx=10,pady=6)
        health.pack(fill=tk.X,pady=(0,6))
        tk.Label(health,textvariable=self.health_var,bg="#10243b",fg="#fbbf24",
                 font=('Microsoft YaHei UI',9,'bold')).pack(side=tk.LEFT)
        tk.Label(health,textvariable=self.last_ack_var,bg="#10243b",fg="#67e8f9",
                 font=('Consolas',9)).pack(side=tk.RIGHT)
        tk.Label(main,textvariable=self.last_pair_var,bg="#ecfdf5",fg="#047857",
                 font=('Microsoft YaHei UI',10,'bold'),anchor="w",padx=8,pady=5).pack(fill=tk.X,pady=(0,6))
        rules_info = self._rules_summary()
        tk.Label(main, text=rules_info, font=('微软雅黑', 9), fg="#999",
                 bg="#f0f2f5", anchor="w").pack(fill=tk.X, pady=(0, 4))
        log_card = tk.Frame(main, bg="white", relief=tk.GROOVE, bd=1)
        log_card.pack(fill=tk.BOTH, expand=True)
        log_header = tk.Frame(log_card, bg="white")
        log_header.pack(fill=tk.X, padx=12, pady=(6, 2))
        tk.Label(log_header, text="📐 绑定日志",
                 font=('微软雅黑', 11, 'bold'), fg="#1a1a2e",
                 bg="white").pack(side=tk.LEFT)
        tk.Button(log_header, text="清空", font=('微软雅黑', 9), bg="#dfe6e9",
                  fg="#555", bd=0, command=self._clear_log,
                  padx=6, pady=0, cursor="hand2").pack(side=tk.RIGHT)
        self.log = scrolledtext.ScrolledText(log_card, font=('Consolas', 10),
                                             bg="#1a1a2e", fg="#dfe6e9",
                                             height=8, padx=8, pady=6,
                                             state=tk.DISABLED, wrap=tk.WORD,
                                             relief=tk.FLAT)
        self.log.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

    def _build_records_tab(self):
        main = self.tab_records
        stats = tk.Frame(main, bg="#f0f2f5")
        stats.pack(fill=tk.X, pady=(0, 6))
        self.stat_today = tk.Label(stats, text="今日: 0",
                                   font=('微软雅黑', 12, 'bold'), fg="#00b894",
                                   bg="#dfe6e9", padx=20, pady=8)
        self.stat_today.pack(side=tk.LEFT, padx=(0, 10))
        self.stat_total = tk.Label(stats, text="总计: 0",
                                   font=('微软雅黑', 12), fg="#0984e3",
                                   bg="#dfe6e9", padx=20, pady=8)
        self.stat_total.pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(stats, text="📛 导出CSV", font=('微软雅黑', 10), bg="#74b9ff",
                  fg="white", bd=0, cursor="hand2",
                  command=self._export_csv, padx=14, pady=4).pack(side=tk.LEFT)
        tk.Button(stats, text="🔄 刷新", font=('微软雅黑', 10), bg="#dfe6e9",
                  fg="#2d3436", bd=0, cursor="hand2",
                  command=self._refresh_records, padx=14, pady=4).pack(side=tk.LEFT)
        tk.Button(stats, text="🗑️ 清空记录", font=('微软雅黑', 10), bg="#ff7675",
                  fg="white", bd=0, cursor="hand2",
                  command=self._clear_records, padx=14, pady=4).pack(side=tk.LEFT)
        tree_frame = tk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        cols = ('pcba', 'shell', 'time')
        self.records_tree = ttk.Treeview(tree_frame, columns=cols,
                                         show="headings", height=20)
        self.records_tree.heading("pcba", text="PCBA码")
        self.records_tree.heading("shell", text="外壳码")
        self.records_tree.heading("time", text="绑定时间")
        self.records_tree.column("pcba", width=200)
        self.records_tree.column("shell", width=200)
        self.records_tree.column("time", width=180)
        self.records_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                 command=self.records_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.records_tree.config(yscrollcommand=scrollbar.set)
        btn_row = tk.Frame(main, bg="#f0f2f5")
        btn_row.pack(fill=tk.X, pady=(6, 0))
        tk.Button(btn_row, text="🗑️ 删除选中", font=('微软雅黑', 10), bg="#ff7675",
                  fg="white", bd=0, cursor="hand2",
                  command=self._delete_selected_record,
                  padx=14, pady=4).pack(side=tk.LEFT, padx=(0, 6))
        self._refresh_records()

    def _refresh_records(self):
        """刷新记录列表"""
        today = self.store.today_count()
        all_records = self.store.all_records()
        total = len(all_records)
        self.stat_today.config(text=f"今日: {today}")
        self.stat_total.config(text=f"总计: {total}")
        for item in self.records_tree.get_children():
            self.records_tree.delete(item)
        for r in all_records:
            self.records_tree.insert("", tk.END, values=r)

    def _show_mapping_table(self):
        window = tk.Toplevel(self.root)
        window.title("本机 SQLite 绑定映射表")
        window.geometry("920x480")
        columns = ("shell", "board", "date", "line", "station", "status")
        tree = ttk.Treeview(window, columns=columns, show="headings")
        headings = {
            "shell": "外壳 SN", "board": "板 SN", "date": "绑定日期",
            "line": "绑定产线", "station": "绑定工站", "status": "状态",
        }
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=145, anchor="center")
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        with sqlite3.connect(self.store.db_path) as conn:
            rows = conn.execute("""
                SELECT shell_sn,board_sn,bound_at,binding_line,station_code,status
                FROM shell_board_mapping ORDER BY id DESC
            """).fetchall()
        for row in rows:
            tree.insert("", tk.END, values=row)

    def _export_csv(self):
        """导出CSV"""
        path = self.store.export_csv()
        self._log("INFO", f"已导出: {path}")

    def _clear_records(self):
        """清空所有记录"""
        messagebox.showerror("禁止操作", "生产绑定记录禁止清空；错误绑定请走质检+线长解绑审批。", parent=self.root)
        return
        w = tk.Toplevel(self.root)
        w.title("确认清空")
        w.geometry("300x150")
        w.transient(self.root)
        w.grab_set()
        tk.Label(w, text="确定要清空所有绑定记录吗？\n此操作不可恢复！",
                 font=('微软雅黑', 11), fg="#d63031").pack(pady=20)

        def _do_clear():
            self.store.clear_all()
            if offline_pending:
                self._log("WARN", "MES离线：本地绑定已保存，MES恢复后自动补传")
            self._refresh_records()
            self._log("INFO", "已清空所有记录")
            w.destroy()

        btn_row = tk.Frame(w)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="确认清空", font=('微软雅黑', 10, 'bold'),
                  command=_do_clear, bg="#d63031", fg="white", bd=0,
                  padx=16, pady=4).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="取消", font=('微软雅黑', 10),
                  command=w.destroy, bg="#dfe6e9", bd=0,
                  padx=16, pady=4).pack(side=tk.LEFT, padx=6)

    def _delete_selected_record(self):
        """删除选中的记录"""
        selection = self.records_tree.selection()
        if not selection:
            return
        item = selection[0]
        values = self.records_tree.item(item, "values")
        pcba_sn = values[0]
        shell_sn = values[1]
        operator=simpledialog.askstring("解绑申请","请输入操作员姓名",parent=self.root)
        if not operator: return
        reason=simpledialog.askstring("解绑申请","请输入解绑原因",parent=self.root)
        if not reason: return
        quality=simpledialog.askstring("质检批准","请输入质检员姓名",parent=self.root)
        if not quality or quality.strip()==operator.strip():
            messagebox.showerror("禁止批准","质检员必须与操作员不同",parent=self.root); return
        quality_reason=simpledialog.askstring("质检批准","请输入质检批准理由",parent=self.root)
        if not quality_reason: return
        leader=simpledialog.askstring("线长批准","请输入线长姓名",parent=self.root)
        if not leader or leader.strip() in {operator.strip(),quality.strip()}:
            messagebox.showerror("禁止批准","线长、质检员和操作员必须为不同人员",parent=self.root); return
        leader_reason=simpledialog.askstring("线长批准复活","请输入线长批准理由",parent=self.root)
        if not leader_reason: return
        self.store.approved_unbind(pcba_sn,shell_sn,operator,reason,quality,quality_reason,leader,leader_reason)
        record_station_activity("BINDING_UNBOUND_APPROVED",{"boardSn":pcba_sn,"shellSn":shell_sn,
            "operator":operator,"qualityApprover":quality,"lineLeader":leader,"reason":reason})
        self._log("WARN",f"解绑已批准并停用: {pcba_sn} → {shell_sn}")
        self.voice_q.put("解绑已批准")

    def _rules_summary(self) -> str:
        pcba = "有" if self.validator.pcba_rules else "无"
        shell = "有" if self.validator.shell_rules else "无"
        return f"💡 PCBA规则: {pcba}  |  外壳规则: {shell}  |  编辑 config.json 自定义规则"

    def _start_voice(self):
        def worker():
            while self._voice_worker_running:
                try:
                    text = self.voice_q.get(timeout=0.5)
                    if text:
                        self.voice.speak(self.voice.translate(text))
                except queue.Empty:
                    continue
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _say(self, key: str):
        self.voice_q.put(self.voice.prompts.get(key, key))

    def _on_voice_language(self, language):
        self.voice.set_language(language)

    def _refocus_scan(self, event=None):
        """点击任意位置都回到扫码框"""
        try:
            self.scan_text.focus_set()
        except Exception:
            pass

    def _on_scan_key(self, event):
        # Capture scanner input privately. Never let the Tk widget submit or
        # display a partial code; submit only after the exact expected length.
        key_char = event.char or (event.keysym if len(getattr(event, "keysym", "")) == 1 else "")
        if key_char and key_char.isalnum():
            self.scan_text.insert(tk.INSERT, key_char.upper())
            if self._scan_timer:
                try:
                    self.root.after_cancel(self._scan_timer)
                except Exception:
                    pass
            # Exact validation prevents partial submits, so use a short quiet
            # window for fast remote shell/board scanner response.
            self._scan_timer = self.root.after(100, self._process_scan_buffer)
            return "break"
        # Allow normal editing/navigation keys such as Backspace, Delete,
        # arrows, and Home/End to reach the Tk text widget.
        return None

    def _legacy_scan_key_disabled(self, event):
        """捕获按键，构建完整扫码内容"""
        if event.char and event.char.isprintable():
            if self._scan_timer:
                self.root.after_cancel(self._scan_timer)
            # Scanner wedges send characters in a tight burst.  A short gap
            # commits the scan quickly on remote stations without waiting for
            # the MES network path; human typing still submits on Return.
            # Slow/remote scanner wedges can pause between characters.  Do not
            # validate a partial SN while the burst is still arriving.
            self._scan_timer = self.root.after(500, self._process_scan_buffer)
            # Most wedges send the complete SN without a reliable Enter. As
            # soon as the exact valid board/shell length is present, submit
            # immediately instead of waiting for the quiet-period timeout.
            self.root.after_idle(self._process_complete_scan_if_ready)

    def _process_complete_scan_if_ready(self):
        raw = self.scan_text.get("1.0", tk.END).strip()
        if not raw:
            return
        validator = self.validator.validate_pcba if not self.pcba_sn else self.validator.validate_shell
        ok, _msg = validator(raw)
        if not ok:
            return
        if self._scan_timer:
            try:
                self.root.after_cancel(self._scan_timer)
            except Exception:
                pass
            self._scan_timer = None
        self.scan_text.delete("1.0", tk.END)
        self._process_scan(raw)

    def _process_scan_buffer(self):
        """处理缓冲区中的内容(从Text widget读取)"""
        self._scan_timer = None
        raw = self.scan_text.get("1.0", tk.END).strip()
        if raw and len(raw) >= 5:
            expected_ok = self.validator.validate_pcba(raw)[0] if not self.pcba_sn else self.validator.validate_shell(raw)[0]
            if not expected_ok:
                return
            self.scan_text.delete("1.0", tk.END)
            self._process_scan(raw)

    def _on_scan(self, event):
        """扫码枪按Enter时触发(从Text widget读取)"""
        raw = self.scan_text.get("1.0", tk.END).strip()
        if raw and len(raw) >= 5:
            expected_ok = self.validator.validate_pcba(raw)[0] if not self.pcba_sn else self.validator.validate_shell(raw)[0]
            if not expected_ok:
                return "break"
            self.scan_text.delete("1.0", tk.END)
            self._process_scan(raw)
        return "break"

    def _process_scan(self, raw):
        self.raw_tree.insert("",0,values=(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"SCANNER","USB/TCP",raw,"RECEIVED",raw.strip().upper()))
        children=self.raw_tree.get_children()
        if len(children)>1000:self.raw_tree.delete(*children[1000:])
        """统一处理扫描输入"""
        self.last_scanner_input=time.time()
        threading.Thread(target=record_station_activity, args=("SCAN_INPUT", {
            "sn": raw.strip().upper(), "expected": "board" if not self.pcba_sn else "shell"
        }), daemon=True).start()
        self.scan_var.set(raw)
        self.root.after(1000, lambda: self.scan_var.set(""))
        if self.state == AppState.BINDING or self.state == AppState.BOUND:
            self._do_reset()
        if not self.pcba_sn:
            self._try_pcba(raw)
        elif not self.shell_sn:
            self._try_shell(raw)
        else:
            self._do_reset()
            self._try_pcba(raw)
        self.root.after(50, lambda: self.scan_text.focus_set())

    def _try_pcba(self, sn: str):
        ok, msg = self.validator.validate_pcba(sn)
        if not ok:
            self._scan_block(sn, msg)
            return
        local_ng = binding_guard_ng(sn)
        if local_ng:
            self._record_blocked_pcba_ng(sn, f"LOCAL NG: {local_ng[0]} / {local_ng[1] or '-'}")
            self._violation(sn, f"LOCAL NG BLOCK: {local_ng[0]} / {local_ng[1] or '-'}")
            return
        if binding_guard_duplicate(sn):
            if self.history_check_bypass:
                self._mark_history_only(sn, "PCBA", "LOCAL_HISTORY")
            else:
                self._duplicate(sn, "PCBA")
                return
        if self.cfg.get("binding_rules", {}).get("prevent_duplicate_pcba", True):
            if self.store.exists_pcba(sn):
                if self.history_check_bypass:
                    self._mark_history_only(sn, "PCBA码", "BINDING_HISTORY")
                else:
                    self._duplicate(sn, "PCBA码")
                    return
        # Show the board SN immediately. MES guard is network I/O and must
        # never block the scanner/UI thread; the old synchronous call made a
        # scan appear stuck for up to five seconds.
        self.pcba_sn = sn
        self.pcba_var.set(sn)
        self.pcba_icon.config(text="...")
        self.pcba_entry.config(readonlybackground="#fff8cc")
        self.state = AppState.BUSY
        self._update_ui()
        if MES_LOCAL_FIRST_BINDING:
            self._finish_mes_guard(sn, "board", (True, "LOCAL_ONLY", {}))
        else:
            threading.Thread(
                target=self._check_mes_guard_async,
                args=(sn, "board"), daemon=True, name="qrbinding-board-mes-guard"
            ).start()

    def _check_mes_guard_async(self, sn, phase):
        try:
            result = mes_scan_guard(sn, phase)
        except Exception as exc:
            result = (False, f"MES_GUARD_ERROR: {exc}", {})
        self.root.after(0, lambda: self._finish_mes_guard(sn, phase, result))

    def _finish_mes_guard(self, sn, phase, result):
        if phase == "board" and self.pcba_sn != sn:
            return
        if phase == "shell" and self.shell_sn != sn:
            return
        mes_clear, mes_code, _mes_detail = result
        if not mes_clear:
            if phase == "board":
                self.pcba_sn = ""
                self.pcba_var.set("")
                self.pcba_icon.config(text="!")
                self.pcba_entry.config(readonlybackground="#fff3f0")
            else:
                self.shell_sn = ""
                self.shell_var.set("")
                self.shell_icon.config(text="!")
                self.shell_entry.config(readonlybackground="#f0f8ff")
            if mes_code == "ACTIVE_CONFIRMED_NG":
                self._violation(sn, f"MES NG BLOCK: {mes_code}")
            else:
                self._scan_block(sn, f"MES SCAN BLOCK: {mes_code}")
            return
        if phase == "board":
            self.pcba_icon.config(text="...")
            if MES_LOCAL_FIRST_BINDING:
                # Local NG/duplicate checks already passed; prompt for shell
                # immediately instead of waiting for the remote MES query.
                self._try_pcba_ng_result(sn, [])
            else:
                self._try_pcba_do_ng_check(sn)
        else:
            self.shell_icon.config(text="✅")
            self.shell_entry.config(readonlybackground="#e6ffe6")
            self._log("INFO", f"壳码: {sn} ✅")
            threading.Thread(target=shellbinding_3d_event,
                             args=("SCAN_GUARD_CHECK",),
                             kwargs={"sn": sn, "result": "CLEAR", "bindingPhase": "shell", "shellSn": sn},
                             daemon=True).start()
            self.voice_q.put("可以绑定")
            if self.pcba_sn and self.cfg.get("binding_rules", {}).get("auto_bind", True):
                self.root.after(50, self._do_bind)
            self._update_ui()

    def _try_pcba_do_ng_check(self, sn: str):
        """后台线程查询MES NG，结果回主线程处理"""
        self.state = AppState.BUSY
        self._update_ui()
        def _check():
            try:
                records = check_mes_ng(sn)
            except Exception as exc:
                records = None
                self._log("ERROR", f"NG check unavailable for {sn}: {exc}")
            self.root.after(0, lambda: self._try_pcba_ng_result(sn, records))
        threading.Thread(target=_check, daemon=True).start()

    def _try_pcba_ng_result(self, sn: str, records: list):
        """NG检查结果回调 — records是NG记录列表，空列表=无NG"""
        if records is None:
            self._violation(sn, "NG CHECK UNAVAILABLE: 本地和 MES 均无法确认 NG，禁止绑定")
            return
        if records:
            # 构造具体站点的违规描述
            station_labels = {
                "auto_ict": "ICT", "auto_fct": "FCT", "auto_depanel": "分板",
                "auto_assem_ate": "组装ATE", "auto_supersonic": "超声",
                "auto_agingcab": "老化柜", "auto_hivolt_ate": "高压ATE",
                "auto_package_ate": "包装ATE", "auto_shellbinding": "外壳绑码",
            }
            stations_hit = [station_labels.get(r.get("station_code",""), r.get("station_code","?"))
                            for r in records]
            detail = "MES拦截：此PCBA在以下工站有NG → " + "/".join(stations_hit)
            self._violation(sn, detail)
            # 记录到Flask拦截日志（第一个站为上游来源）
            upstream = records[0].get("station_code", "unknown") if records else ""
            self._record_blocked_pcba_ng(sn, detail, upstream=upstream)
            threading.Thread(target=report_interception, args=(sn, upstream, ""), daemon=True).start()
            return
        self.pcba_sn = sn
        self.pcba_var.set(sn)
        self.pcba_icon.config(text="✅")
        self.pcba_entry.config(readonlybackground="#e6ffe6")
        self.shell_entry.config(readonlybackground="#fff4a8")
        self._blink_entry(self.shell_entry, "#fff4a8")
        self._log("INFO", f"版码: {sn} ✅")
        threading.Thread(target=shellbinding_3d_event,
                         args=("SCAN_GUARD_CHECK",),
                         kwargs={"sn": sn, "result": "CLEAR", "bindingPhase": "board", "pcbaSn": sn, "shellSn": self.shell_sn},
                         daemon=True).start()
        self.voice_q.put("请扫描外壳码")
        self._update_ui()

    def _try_shell(self, sn: str):
        ok, msg = self.validator.validate_shell(sn)
        if not ok:
            self._scan_block(sn, msg)
            return
        # A shell code is a new material label, not an upstream production SN.
        # Never classify it using the PCBA NG cache populated by MES.
        if binding_guard_duplicate(sn):
            if self.history_check_bypass:
                self._mark_history_only(sn, "SHELL", "LOCAL_HISTORY")
            else:
                self._duplicate(sn, "SHELL")
                return
        if self.cfg.get("binding_rules", {}).get("prevent_duplicate_shell", True):
            if self.store.exists_shell(sn):
                if self.history_check_bypass:
                    self._mark_history_only(sn, "外壳码", "BINDING_HISTORY")
                else:
                    self._duplicate(sn, "外壳码")
                    return
        # Display the shell SN immediately; perform the MES guard off the Tk
        # thread just like the board path.
        self.shell_sn = sn
        self.shell_var.set(sn)
        self.shell_icon.config(text="...")
        self.shell_entry.config(readonlybackground="#fff8cc")
        self.state = AppState.BUSY
        self._update_ui()
        # Local format/NG/duplicate checks are complete above. The atomic MES
        # commit below remains authoritative, so avoid a second shell round-trip.
        self._finish_mes_guard(sn, "shell", (True, "LOCAL_ONLY", {}))

    def _violation(self, sn: str, detail: str = ''):
        self.state = AppState.VIOLATION
        self.total_bad += 1
        self._say("violation")
        msg = f"违规: {sn}  |  {detail}" if detail else f"违规: {sn}"
        self._log("ERROR", msg)
        self._update_ui()
        self.station_alarm.trigger("NG报警",[sn],"发现不良品，禁止不良品离开本站")

    def _record_blocked_pcba_ng(self, pcba_sn: str, detail: str, *, upstream: str = ""):
        """Record blocked association without marking the shell NG."""
        payload = {"pcbaSn": pcba_sn, "shellSn": self.shell_sn or "",
                   "reason": "BLOCKED_BY_PCBA_NG", "detail": detail,
                   "upstreamStation": upstream, "bindingCreated": False}
        threading.Thread(target=record_station_activity,
                         args=("BIND_BLOCKED_PCBA_NG", payload), daemon=True,
                         name="qrbinding-blocked-ng-record").start()

    def _scan_block(self, sn: str, detail: str = ''):
        """Reject format/route errors without falsely marking the SN as NG."""
        self.state = AppState.VIOLATION
        msg = f"SCAN BLOCK: {sn} | {detail}" if detail else f"SCAN BLOCK: {sn}"
        self._log("WARN", msg)
        record_station_activity("SCAN_BLOCKED", {"sn": sn, "reason": detail, "isNg": False})
        self._update_ui()
        self.station_alarm.trigger("扫描拦截", [sn], f"{detail}；此记录不是NG")

    def _duplicate(self, sn: str, label: str = '码'):
        """重复扫描，不算违规"""
        self.state = AppState.VIOLATION
        self._say("violation")
        self._log("WARN", f"{label}重复: {sn}")
        self._update_ui()
        self.station_alarm.trigger("重码报警",[sn],"发现重复编码，禁止离开本站")

    def _toggle_history_check_bypass(self):
        self.history_check_bypass = not self.history_check_bypass
        if self.history_check_bypass:
            self.history_bypass_btn.configure(text="历史检查：只标记", bg="#d97706")
            self._log("WARN", "历史检查旁路已开启：历史重复只标记，不拦截；当前NG仍拦截")
            record_station_activity("HISTORY_CHECK_BYPASS_ENABLED", {
                "operator": MES_NEW_OPERATOR, "activeNgStillBlocked": True})
        else:
            self.history_bypass_btn.configure(text="历史检查：拦截", bg="#334155")
            self._log("INFO", "历史检查旁路已关闭：恢复历史重复拦截")
            record_station_activity("HISTORY_CHECK_BYPASS_DISABLED", {
                "operator": MES_NEW_OPERATOR})
        self.root.after(50, self.scan_text.focus_set)

    def _mark_history_only(self, sn: str, label: str, source: str):
        binding_guard_record_duplicate(sn, label)
        self._log("WARN", f"历史检查只标记: {label} {sn} ({source})")
        record_station_activity("HISTORY_CHECK_MARKED", {
            "sn": sn, "codeType": label, "source": source,
            "bypass": True, "bindingAllowed": True})
        shellbinding_3d_event(
            "HISTORY_CHECK_MARKED", sn=sn, result="MARKED",
            codeType=label, source=source, bypass=True,
            bindingAllowed=True, alarm=False)

    def _clear_violation(self):
        if self.state == AppState.VIOLATION:
            self.state = AppState.IDLE
            self._update_ui()

    @staticmethod
    def _mes_error_zh(code):
        return {
            "BLOCK_OUT_OF_SEQUENCE":"上游工序不完整，禁止跳站",
            "ACTIVE_CONFIRMED_NG":"存在未维修的确认NG",
            "PCBA_ALREADY_BOUND":"PCBA已绑定其他外壳",
            "SHELL_ALREADY_BOUND":"外壳已绑定其他PCBA",
            "QR_NOT_BOUND":"二维码未绑定当前工单",
            "QR_WORK_ORDER_MISMATCH":"二维码与当前工单不一致",
            "MES_BINDING_UNAVAILABLE":"MES离线，禁止绑定",
            "MES_GUARD_UNAVAILABLE":"MES检查不可用，禁止操作",
        }.get(str(code),str(code))

    def _do_bind(self):
        """Start MES binding off the Tk thread so a slow remote MES cannot freeze the UI."""
        if not self.pcba_sn or not self.shell_sn:
            return
        self.state = AppState.BINDING
        self._update_ui()
        threading.Thread(target=self._do_bind_blocking, daemon=True,
                         name="qrbinding-mes-bind").start()

    def _do_bind_blocking(self):
        if not self.pcba_sn or not self.shell_sn:
            return
        self.state = AppState.BINDING
        self._update_ui()
        if MES_LOCAL_FIRST_BINDING:
            committed, acknowledgement, mes_detail = True, "MES_OFFLINE_PENDING", {
                "offline": True, "error": "LOCAL_FIRST_MES_DEFERRED"
            }
        else:
            committed, acknowledgement, mes_detail = mes_binding_commit(self.pcba_sn, self.shell_sn)
        if not committed:
            self.state = AppState.VIOLATION
            explanation = self._mes_error_zh(acknowledgement)
            self._log("ERROR", f"MES绑定失败: {explanation} ({acknowledgement}) | {mes_detail}")
            self.station_alarm.trigger("MES绑定拦截", [self.pcba_sn, self.shell_sn],
                                       f"{explanation}，禁止产品离开本站")
            self._update_ui()
            return
        try:
            rec = self.store.save(self.pcba_sn, self.shell_sn)
            offline_pending = str(acknowledgement).startswith("MES_OFFLINE") or bool(mes_detail.get("offline"))
            if offline_pending:
                self.store.queue_offline(self.pcba_sn, self.shell_sn, mes_detail.get("error", "MES_OFFLINE"))
            binding_guard_save_pair(self.pcba_sn, self.shell_sn)
            activity = {"boardSn": self.pcba_sn, "shellSn": self.shell_sn, "bindingLine": "manual_line"}
            if MES_LOCAL_FIRST_BINDING:
                threading.Thread(target=record_station_activity, args=("BIND_SUCCESS", activity), daemon=True).start()
            else:
                record_station_activity("BIND_SUCCESS", activity)
            # 记录到机器表（5年留存）
            if MES_LOCAL_FIRST_BINDING:
                threading.Thread(target=self.store.update_machine, args=(MES_NEW_STATION, self.pcba_sn, self.shell_sn), daemon=True).start()
            else:
                self.store.update_machine(MES_NEW_STATION, self.pcba_sn, self.shell_sn)
            self._log("SUCCESS",
                      f"✅ MES绑定成功 | 版码: {self.pcba_sn}  →  壳码: {self.shell_sn} | ACK: {acknowledgement}")
            self.last_pair_var.set(f"上次成功绑定：外壳 {self.shell_sn}  ↔  PCBA {self.pcba_sn}")
            self.last_ack_var.set(f"MES ACK：{acknowledgement}")
            self._refresh_records()
        except Exception as e:
            record_station_activity("BIND_FAILURE", {"boardSn": self.pcba_sn, "shellSn": self.shell_sn, "error": str(e)})
            self._log("ERROR", f"写入DB失败: {e}")
            self.state = AppState.IDLE
            self._update_ui()
            return

        self.total_ok += 1
        self.state = AppState.BOUND
        self._say("success")
        self._update_ui()
        self.root.after(1500, self._do_reset)

    def _blink_entry(self, entry, color, count=6):
        """Briefly blink the next required input without blocking Tk."""
        def tick(n):
            if n <= 0:
                entry.config(readonlybackground=color)
                return
            current = entry.cget("readonlybackground")
            entry.config(readonlybackground="#ffffff" if current == color else color)
            self.root.after(180, lambda: tick(n - 1))
        tick(count)

    def _do_reset(self):
        self.state = AppState.IDLE
        self.pcba_sn = ""
        self.shell_sn = ""
        self.pcba_var.set("")
        self.shell_var.set("")
        self.pcba_icon.config(text="⬚")
        self.shell_icon.config(text="⬚")
        self.pcba_entry.config(readonlybackground="#fff4a8")
        self.shell_entry.config(readonlybackground="#f0f8ff")
        self._update_ui()
        self.root.after(100, lambda: self.scan_text.focus_set())
        self._blink_entry(self.pcba_entry, "#fff4a8")
        self._say("scan_pcba")

    def _update_ui(self):
        st = STATE_TEXT.get(self.state, "")
        colors = {
            AppState.IDLE: "#0984e3",
            AppState.BINDING: "#fdcb6e",
            AppState.BOUND: "#00b894",
            AppState.VIOLATION: "#d63031"
        }
        self.status_label.config(text=st, fg=colors.get(self.state, "#636e72"))
        can_bind = self.state == AppState.IDLE and self.pcba_sn and self.shell_sn
        self.bind_btn.config(
            state=tk.NORMAL if can_bind else tk.DISABLED,
            bg="#00b894" if can_bind else "#b2bec3"
        )
        self.footer.config(
            text=f"状态: {st} | 绑定: {self.total_ok} | 违规: {self.total_bad}")

    def _log(self, level: str, msg: str):
        colors = {'INFO': "#74b9ff", 'SUCCESS': "#00b894", 'ERROR': "#d63031"}
        prefix = {'INFO': " ℹ️", 'SUCCESS': " ✅", 'ERROR': " ❌"}
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f'[{ts}]{prefix.get(level, " ")}{msg}\n'
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, line)
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.config(state=tk.DISABLED)

    def _test_input(self):
        pcba = self.pcba_sn.strip()
        shell = self.shell_sn.strip()
        if not pcba and not shell:
            self._log("INFO", "请先扫描PCBA或外壳码")
            return
        self.validator = SNValidator(CONFIG_FILE)
        results = []
        if pcba:
            ok, msg = self.validator.validate_pcba(pcba)
            results.append(f"PCBA: {ok}, {msg}")
        if shell:
            ok, msg = self.validator.validate_shell(shell)
            results.append(f"外壳: {ok}, {msg}")
        self._log("INFO", " | ".join(results))

    def _show_test_rules(self):
        """通用规则测试工具"""
        w = tk.Toplevel(self.root)
        w.title("规则测试工具")
        w.geometry("600x500")
        w.transient(self.root)
        tk.Label(w, text="🔍 正则规则测试工具",
                 font=('微软雅黑', 14, 'bold'), fg="#1a1a2e").pack(pady=10)
        f1 = tk.LabelFrame(w, text="PCBA规则测试",
                           font=('微软雅黑', 10), padx=10, pady=5)
        f1.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(f1, text="正则:", font=('微软雅黑', 9)).pack(anchor="w")
        pcba_regex = tk.Entry(f1, font=('Consolas', 10))
        pcba_regex.pack(fill=tk.X, pady=2)
        pcba_regex.insert(0, "^5G[A-Z0-9]{8}$")
        tk.Label(f1, text="测试SN (逗号分隔):", font=('微软雅黑', 9)).pack(anchor="w")
        pcba_tests = tk.Entry(f1, font=('Consolas', 10))
        pcba_tests.pack(fill=tk.X, pady=2)
        pcba_tests.insert(0, "5G5608888A,5G560888,5G5608888AA")
        pcba_result = tk.Text(f1, font=('Consolas', 9), height=3, bg="#f8f9fa")
        pcba_result.pack(fill=tk.X, pady=5)
        f2 = tk.LabelFrame(w, text="外壳规则测试",
                           font=('微软雅黑', 10), padx=10, pady=5)
        f2.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(f2, text="正则:", font=('微软雅黑', 9)).pack(anchor="w")
        shell_regex = tk.Entry(f2, font=('Consolas', 10))
        shell_regex.pack(fill=tk.X, pady=2)
        shell_regex.insert(0, "^NV18A[A-Z0-9]{9}$")
        tk.Label(f2, text="测试SN (逗号分隔):", font=('微软雅黑', 9)).pack(anchor="w")
        shell_tests = tk.Entry(f2, font=('Consolas', 10))
        shell_tests.pack(fill=tk.X, pady=2)
        shell_tests.insert(0, "NV18A2619K2371,NV18A2619K23,123456")
        shell_result = tk.Text(f2, font=('Consolas', 9), height=3, bg="#f8f9fa")
        shell_result.pack(fill=tk.X, pady=5)

        def test_regex(pattern, test_cases, result_text):
            result_text.delete("1.0", tk.END)
            if not pattern.strip():
                result_text.insert(tk.END, "请输入正则表达式\n")
                return
            try:
                regex = re.compile(pattern.strip())
                result_text.insert(tk.END, f"✅ 正则有效: {pattern}\n")
                result_text.insert(tk.END, "----------------------------------------\n")
                for sn in test_cases.split(","):
                    sn = sn.strip()
                    if not sn:
                        continue
                    match = bool(regex.match(sn))
                    icon = "✅" if match else "❌"
                    result_text.insert(tk.END, f"{icon} {sn}\n")
            except re.error as e:
                result_text.insert(tk.END, f"❌ 正则错误: {e}\n")

        def do_test_pcba():
            test_regex(pcba_regex.get(), pcba_tests.get(), pcba_result)

        def do_test_shell():
            test_regex(shell_regex.get(), shell_tests.get(), shell_result)

        btn_frame = tk.Frame(w)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="测试PCBA", font=('微软雅黑', 10),
                  command=do_test_pcba, bg="#00b894", fg="white",
                  padx=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="测试外壳", font=('微软雅黑', 10),
                  command=do_test_shell, bg="#0984e3", fg="white",
                  padx=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="关闭", font=('微软雅黑', 10),
                  command=w.destroy, bg="#dfe6e9",
                  padx=15).pack(side=tk.LEFT, padx=5)

    def _make_regex(self, total, prefix, suffix, middle_type, middle_custom):
        """根据可视化字段生成正则表达式"""
        if not total:
            return ""
        try:
            tot = int(total)
        except Exception:
            return ""

        prefix = prefix.strip()
        suffix = suffix.strip()
        middle_type = middle_type or "数字"

        if middle_type == "数字":
            mid_pat = "\\d"
        elif middle_type == "字母":
            mid_pat = "[A-Za-z]"
        elif middle_type == "字母数字":
            mid_pat = "[A-Za-z0-9]"
        elif middle_type == "指定字符":
            mc = middle_custom.strip()
            mid_pat = f"[{mc}]" if mc else "\\w"
        else:
            mid_pat = "\\w"

        fixed_len = len(prefix) + len(suffix)
        mid_count = tot - fixed_len
        if mid_count <= 0:
            return ""
        middle = f'{mid_pat}{"{" + str(mid_count) + "}"}'
        regex = f"^{re.escape(prefix)}{middle}{re.escape(suffix)}$"
        return regex

    def _build_rule_section(self, parent, title, color, existing_patterns):
        """构建一个规则的可视化编辑器 + 原始正则文本区"""
        frame = tk.LabelFrame(parent, text=title,
                              font=('微软雅黑', 10, 'bold'), fg=color,
                              padx=10, pady=6)
        builder = tk.Frame(frame)
        builder.pack(fill=tk.X, pady=(0, 6))
        tk.Label(builder, text="可视化配置（生成正则）",
                 font=('微软雅黑', 9), fg="#636e72").pack(anchor="w")
        row1 = tk.Frame(builder, bg=frame["bg"])
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="总字符", font=('微软雅黑', 9), width=7,
                 anchor="w", bg=frame["bg"]).pack(side=tk.LEFT)
        e_total = tk.Entry(row1, font=('Consolas', 10), width=8)
        e_total.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(row1, text="开头", font=('微软雅黑', 9), width=5,
                 anchor="w", bg=frame["bg"]).pack(side=tk.LEFT)
        e_prefix = tk.Entry(row1, font=('Consolas', 10), width=10)
        e_prefix.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(row1, text="结尾:", font=('微软雅黑', 9), width=5,
                 anchor="w", bg=frame["bg"]).pack(side=tk.LEFT)
        e_suffix = tk.Entry(row1, font=('Consolas', 10), width=10)
        e_suffix.pack(side=tk.LEFT)
        row2 = tk.Frame(builder, bg=frame["bg"])
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="中间:", font=('微软雅黑', 9), width=7,
                 anchor="w", bg=frame["bg"]).pack(side=tk.LEFT)
        mid_var = tk.StringVar(value="数字")
        om = ttk.Combobox(row2, textvariable=mid_var,
                          values=["数字", "字母", "字母数字", "指定字符"],
                          font=('微软雅黑', 9), width=10, state="readonly")
        om.pack(side=tk.LEFT, padx=(0, 6))
        e_custom = tk.Entry(row2, font=('Consolas', 9), width=12)
        e_custom.pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(row2, text="指定字符如A-Z0-9", font=('微软雅黑', 8),
                 fg="#999", bg=frame["bg"]).pack(side=tk.LEFT)
        row3 = tk.Frame(builder, bg=frame["bg"])
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="预览:", font=('微软雅黑', 9), width=7,
                 anchor="w", bg=frame["bg"]).pack(side=tk.LEFT)
        preview = tk.Label(row3, text="（请填写上方条件）",
                           font=('Consolas', 10, 'bold'), fg="#0984e3",
                           bg="#f0f8ff", anchor="w", padx=4)
        preview.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

        def _update_preview(*args):
            r = self._make_regex(e_total.get(), e_prefix.get(), e_suffix.get(),
                                 mid_var.get(), e_custom.get())
            preview.config(text=r if r else "（请填写上方条件）")

        e_total.bind("<KeyRelease>", _update_preview)
        e_prefix.bind("<KeyRelease>", _update_preview)
        e_suffix.bind("<KeyRelease>", _update_preview)
        om.bind("<<ComboboxSelected>>", _update_preview)
        e_custom.bind("<KeyRelease>", _update_preview)

        def _add_to_list():
            r = self._make_regex(e_total.get(), e_prefix.get(), e_suffix.get(),
                                 mid_var.get(), e_custom.get())
            if r and r not in existing_patterns:
                existing_patterns.append(r)
                _refresh_list()
                _update_preview()

        tk.Button(row3, text="+ 添加规则", font=('微软雅黑', 9), bg="#00b894",
                  fg="white", bd=0, padx=8,
                  command=_add_to_list).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Label(builder, text="已添加的规则（可直接编辑，删除即移除）",
                 font=('微软雅黑', 9), fg="#636e72").pack(anchor="w", pady=(4, 2))
        list_frame = tk.Frame(builder)
        list_frame.pack(fill=tk.X)
        listbox = tk.Listbox(list_frame, font=('Consolas', 10), height=3,
                             bg="white", selectmode=tk.EXTENDED)
        listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scroll = tk.Scrollbar(list_frame, orient=tk.VERTICAL,
                              command=listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scroll.set)

        def _refresh_list():
            listbox.delete(0, tk.END)
            for p in existing_patterns:
                listbox.insert(tk.END, p)

        _refresh_list()

        def _del_selected():
            sel = listbox.curselection()
            for i in reversed(sel):
                existing_patterns.pop(i)
            _refresh_list()

        tk.Button(list_frame, text="删除", font=('微软雅黑', 8), bg="#ff7675",
                  fg="white", bd=0, padx=6,
                  command=_del_selected).pack(pady=2)
        sep = tk.Frame(frame, bg="#dfe6e9", height=1)
        sep.pack(fill=tk.X, pady=6)
        tk.Label(frame, text="专家模式 - 直接写正则（每行一条，覆盖上方）",
                 font=('微软雅黑', 9), fg="#999").pack(anchor="w")
        raw_text = tk.Text(frame, font=('Consolas', 10), fg="#333", height=2,
                           bg="white", relief=tk.SOLID, bd=1, padx=6, pady=4)
        raw_text.pack(fill=tk.X)
        raw_text.insert(tk.END, "\n".join(existing_patterns))

        def _sync_to_raw(*args):
            current_raw = raw_text.get("1.0", tk.END).strip()
            for p in existing_patterns:
                if p not in current_raw:
                    current_raw += "\n" + p
            raw_text.delete("1.0", tk.END)
            raw_text.insert(tk.END, current_raw.strip())

        return (frame, existing_patterns, _refresh_list, raw_text)

    def _show_rules(self):
        w = tk.Toplevel(self.root)
        w.title("SN规则配置")
        w.geometry("680x620")
        w.transient(self.root)
        w.grab_set()
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {"sn_rules": {"pcba": {"patterns": []}, "shell": {"patterns": []}}}
        else:
            pcba_patterns = list(cfg.get("sn_rules", {}).get("pcba", {}).get("patterns", []))
            shell_patterns = list(cfg.get("sn_rules", {}).get("shell", {}).get("patterns", []))
            tk.Label(w, text="🔡 规则配置  |  上方可视化配置适合常规格式，右下专家模式可写任意正则",
                     font=('微软雅黑', 10), fg="#636e72").pack(anchor="w", padx=14, pady=(10, 4))
            v_scroll = tk.Scrollbar(w, orient=tk.VERTICAL)
            v_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(0, 10))
            canvas = tk.Canvas(w, bg="#f0f2f5", highlightthickness=0,
                               yscrollcommand=v_scroll.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                        padx=(10, 0), pady=(0, 10))
            v_scroll.config(command=canvas.yview)
            scrollable = tk.Frame(canvas, bg="#f0f2f5")
            scroll_win = canvas.create_window((0, 0), window=scrollable, anchor="nw")

            def _on_frame_configure(event):
                bbox = canvas.bbox("all")
                if bbox:
                    canvas.config(scrollregion=bbox)
                    cw = canvas.winfo_width()
                    if cw > 1:
                        canvas.itemconfig(scroll_win, width=cw)

            scrollable.bind("<Configure>", _on_frame_configure)

            def _on_mousewheel(event):
                canvas.yview_scroll(-1 * (event.delta // 120), "units")

            canvas.bind("<MouseWheel>", _on_mousewheel)
            pcba_frame, pcba_list, pcba_refresh, pcba_raw_text = \
                self._build_rule_section(scrollable, "📋 PCBA版规则", "#e17055", pcba_patterns)
            pcba_frame.pack(fill=tk.X, padx=6, pady=(0, 8))
            shell_frame, shell_list, shell_refresh, shell_raw_text = \
                self._build_rule_section(scrollable, "📋 外壳规则", "#0984e3", shell_patterns)
            shell_frame.pack(fill=tk.X, padx=6, pady=(0, 8))

            def _on_mousewheel(event):
                canvas.yview_scroll(-1 * (event.delta // 120), "units")

            canvas.bind_all("<MouseWheel>", _on_mousewheel)

            def _do_save():
                pcba_text_raw = pcba_raw_text.get("1.0", tk.END).strip()
                shell_text_raw = shell_raw_text.get("1.0", tk.END).strip()
                pcba_final = [l.strip() for l in pcba_text_raw.split("\n") if l.strip()]
                shell_final = [l.strip() for l in shell_text_raw.split("\n") if l.strip()]
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except Exception:
                    cfg = {}
                if "sn_rules" not in cfg:
                    cfg["sn_rules"] = {"pcba": {}, "shell": {}}
                cfg["sn_rules"]["pcba"]["patterns"] = pcba_final
                cfg["sn_rules"]["shell"]["patterns"] = shell_final
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
                self.validator = SNValidator(CONFIG_FILE)
                self._log("INFO", f"规则已保存: PCBA {len(pcba_final)}条, 外壳 {len(shell_final)}条")
                canvas.unbind_all("<MouseWheel>")
                w.destroy()

            btn_row = tk.Frame(w, bg="#f0f2f5")
            btn_row.pack(pady=(0, 8))
            tk.Button(btn_row, text="💾 保存", font=('微软雅黑', 11, 'bold'),
                      command=_do_save, padx=20, pady=4, bg="#00b894",
                      fg="white", bd=0, cursor="hand2").pack(side=tk.LEFT, padx=6)
            tk.Button(btn_row, text="取消", font=('微软雅黑', 10),
                      command=lambda: (canvas.unbind_all("<MouseWheel>"), w.destroy()),
                      padx=16, pady=4, bg="#dfe6e9", bd=0,
                      cursor="hand2").pack(side=tk.LEFT, padx=6)

    def _on_close(self):
        self._voice_worker_running = False
        try:
            with open(SHUTDOWN_FILE, "w", encoding="utf-8") as marker:
                marker.write("operator-close\n")
        except OSError:
            pass
        _shutdown_event.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ================================================================
# 本地HTTP API服务器 (port LOCAL_PORT)
# ================================================================
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from http.server import HTTPServer
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

_app_ref = [None]  # 全局App引用，供HTTP handler使用


class LocalAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == "/api/heartbeat":
            cfg = get_station_config()
            import socket as sock_module
            try:
                hostname = sock_module.gethostname()
                ip = sock_module.gethostbyname(hostname)
            except Exception:
                ip = "unknown"
            resp = {
                "status": "ok",
                "app": "qrbinding",
                "version": APP_VERSION,
                "station": cfg.get("station", "UNKNOWN"),
                "ip": ip,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode())
        elif self.path == "/api/binding/status":
            app = _app_ref[0]
            if app:
                try:
                    resp = {
                        "state": str(app.state.name),
                        "pcba_sn": app.pcba_sn,
                        "shell_sn": app.shell_sn,
                        "total_ok": app.total_ok,
                        "total_bad": app.total_bad,
                    }
                except Exception:
                    resp = {"error": "app not ready"}
            else:
                resp = {"error": "app not initialized"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode())
        elif self.path == "/api/binding/records":
            app = _app_ref[0]
            if app:
                try:
                    records = app.store.all_records()
                    resp = {"records": [{"pcba": r[0], "shell": r[1], "time": r[2]} for r in records]}
                except Exception as e:
                    resp = {"error": str(e)}
            else:
                resp = {"error": "app not initialized"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode())
        elif self.path == "/api/binding/export":
            app = _app_ref[0]
            if app:
                try:
                    path = app.store.export_csv()
                    resp = {"ok": True, "path": path}
                except Exception as e:
                    resp = {"ok": False, "error": str(e)}
            else:
                resp = {"error": "app not initialized"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode())
        else:
            self.send_response(404)
            self.end_headers()

    # ===== Station exe lifecycle (for /start and /stop endpoints) =====
    def start_ststation_exe(exe_name=None):
        """Start the station exe. Returns {started: True/False, exe, pid, error}."""
        import os, subprocess
        if not exe_name:
            return {"started": False, "exe": exe_name, "error": "exe name required"}
        candidates = [
            os.path.join("D:\\Stations", exe_name),
            os.path.join("D:\\stations", exe_name),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    proc = subprocess.Popen([path], cwd=os.path.dirname(path),
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    return {"started": True, "exe": exe_name, "pid": proc.pid, "path": path}
                except Exception as e:
                    return {"started": False, "exe": exe_name, "error": str(e)}
        return {"started": False, "exe": exe_name, "error": "exe not found in D:\\Stations"}

    def stop_station_exe(exe_name=None):
        """Stop a running station exe by name. Returns {stopped: True/False, exe, error}."""
        import os, subprocess
        if not exe_name:
            return {"stopped": False, "exe": exe_name, "error": "exe name required"}
        try:
            subprocess.run(["taskkill", "/IM", exe_name, "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            return {"stopped": True, "exe": exe_name}
        except Exception as e:
            return {"stopped": False, "exe": exe_name, "error": str(e)}

    def get_station_status():
        """Check which station exe processes are running."""
        import subprocess
        names = ["ICT_station.exe", "FCT_station.exe", "PCBADividerStation.exe",
                 "QRBinding_v2.exe", "AssemblyATE.exe", "ScannerHelper_ATE.exe",
                 "UltrasonicStation.exe", "AgingCab.exe", "HiVoltATE.exe",
                 "PackingATE.exe", "PackingStation.exe"]
        running = []
        try:
            out = subprocess.check_output("tasklist /FO CSV /NH", stderr=subprocess.DEVNULL, text=True)
            for line in out.splitlines():
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    name = parts[0].strip('"')
                    if name in names:
                        running.append({"name": name, "pid": int(parts[1].strip('"'))})
        except Exception:
            pass
        return {"running": running}

    def do_POST(self):
        if self.path == "/api/binding/reset":
            app = _app_ref[0]
            if app:
                try:
                    app._do_reset()
                    resp = {"ok": True}
                except Exception as e:
                    resp = {"ok": False, "error": str(e)}
            else:
                resp = {"error": "app not initialized"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode())
        elif self.path == "/start":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length else ""
                data = json.loads(body) if body else {}
                exe_name = data.get("exe") if isinstance(data, dict) else None
                result = self.start_ststation_exe(exe_name)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"started": False, "error": str(e)}).encode())
        elif self.path == "/stop":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length else ""
                data = json.loads(body) if body else {}
                exe_name = data.get("exe") if isinstance(data, dict) else None
                result = self.stop_station_exe(exe_name)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"stopped": False, "error": str(e)}).encode())
        elif self.path == "/status":
            try:
                result = self.get_station_status()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path == "/stats":
            try:
                import sqlite3 as _sq
                from datetime import datetime as _dt
                today = _dt.now().strftime("%Y-%m-%d")
                db_path = os.path.join(app_root(), "binding_records.db")
                conn = _sq.connect(db_path)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM bindings")
                total = cur.fetchone()[0] or 0
                conn.close()
                # dup = shell appearing more than once (multiple PCBA bound to same shell)
                conn2 = _sq.connect(db_path)
                cur2 = conn2.cursor()
                cur2.execute("SELECT COUNT(*) FROM (SELECT shell_sn FROM bindings GROUP BY shell_sn HAVING COUNT(*)>1)")
                dup = cur2.fetchone()[0] or 0
                conn2.close()
                result = {"total": total, "pass": total, "fail": 0, "dup": dup, "date": today}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()


def _open_firewall_ports():
    """Open ports 1004, 10086 in Windows Firewall on startup."""
    import subprocess
    ports = [str(LOCAL_PORT), str(WS_PORT)]
    for port in ports:
        try:
            subprocess.run(
                ["netsh", "advfirewall", "firewall", "add", "rule",
                 f"name=StationHelper_Port{port}",
                 "dir=in", "action=allow",
                 f"localport={port}", "protocol=tcp", "enable=yes"],
                capture_output=True, timeout=10
            )
            print(f"[firewall] port {port} opened")
        except Exception as e:
            print(f"[firewall] port {port} failed: {e}")

def start_http_server():
    _open_firewall_ports()
    try:
        server = HTTPServer(("0.0.0.0", LOCAL_PORT), LocalAPIHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True, name="HTTP-API")
        t.start()
        print(f"[HTTP] API started: http://0.0.0.0:{LOCAL_PORT}")
    except Exception as e:
        print(f"[HTTP] Start failed: {e}")

# ===== Sync Server (port 8089) — requires API key auth =====
class SyncHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def _auth(self):
        key = self.headers.get("X-Api-Key") or self.path.split("?key=")[-1].split("&")[0]
        if key != API_KEY:
            self.send_response(401); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(b'{"error":"unauthorized"}'); return False
        return True
    def _json(self, data, code=200):
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    def do_GET(self):
        # Local QR Binding NG lookup uses the same authenticated sync service
        # port instead of the legacy standalone Flask port 5002.
        if self.path.startswith("/ng_check") and self.client_address[0] in {"127.0.0.1", "::1"}:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            sn = (query.get("sn") or [""])[0].strip().upper()
            guard_path = os.path.join(app_root(), "binding_guard.db")
            try:
                with sqlite3.connect(guard_path) as conn:
                    row = conn.execute(
                        "SELECT source_station,batch_id FROM confirmed_ng WHERE sn=?", (sn,)
                    ).fetchone()
                records = ([{"station_code": row[0], "batch_id": row[1], "repair_status": "pending"}]
                           if row else [])
                self._json({"found": bool(records), "records": records})
            except Exception as exc:
                self._json({"error": str(exc)}, 500)
            return
        if not self._auth(): return
        from datetime import datetime as _dt
        db_path = os.path.join(app_root(), "binding_records.db")
        if self.path.startswith("/stats"):
            try:
                today = _dt.now().strftime("%Y-%m-%d")
                conn = sqlite3.connect(db_path); cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM bindings"); total = cur.fetchone()[0] or 0
                conn2 = sqlite3.connect(db_path); cur2 = conn2.cursor()
                cur2.execute("SELECT COUNT(*) FROM (SELECT shell_sn FROM bindings GROUP BY shell_sn HAVING COUNT(*)>1)"); dup = cur2.fetchone()[0] or 0
                conn.close(); conn2.close()
                self._json({"total": total, "pass": total, "fail": 0, "dup": dup, "date": today})
            except Exception as e: self._json({"error": str(e)}, 500)
        elif self.path.startswith("/pools"):
            # QRBinding doesn't have SN pools - return binding counts
            try:
                conn = sqlite3.connect(db_path); cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM bindings"); total = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(DISTINCT pcba_sn) FROM bindings"); pcba_count = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(DISTINCT shell_sn) FROM bindings"); shell_count = cur.fetchone()[0] or 0
                conn.close()
                self._json({"sn_pool": [], "ng_pool": [], "dup_pool": [],
                    "sn_pool_count": pcba_count, "ng_pool_count": 0, "dup_pool_count": 0,
                    "total_bindings": total, "unique_pcba": pcba_count, "unique_shell": shell_count})
            except Exception as e: self._json({"error": str(e)}, 500)
        elif self.path.startswith("/sn_records"):
            try:
                limit = 100
                if "limit=" in self.path: limit = int(self.path.split("limit=")[-1].split("&")[0])
                conn = sqlite3.connect(db_path)
                rows = conn.execute("SELECT pcba_sn, shell_sn, created_at FROM bindings ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                conn.close()
                self._json([{"sn": r[0], "shell": r[1], "time": r[2]} for r in rows])
            except Exception as e: self._json({"error": str(e)}, 500)
        elif self.path.startswith("/ng_pool"):
            self._json([])  # QRBinding has no NG pool
        elif self.path.startswith("/dup_pool"):
            try:
                conn = sqlite3.connect(db_path)
                rows = conn.execute("SELECT shell_sn, COUNT(*) as cnt FROM bindings GROUP BY shell_sn HAVING COUNT(*)>1 ORDER BY cnt DESC LIMIT 100").fetchall()
                conn.close()
                self._json({"dup_pool": [{"shell": r[0], "count": r[1]} for r in rows], "count": len(rows)})
            except Exception as e: self._json({"error": str(e)}, 500)
        elif self.path.startswith("/health"):
            self._json({"status": "ok"})
        else:
            self._json({"error": "not found"}, 404)

def start_sync_server():
    try:
        import subprocess
        subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule",
            f"name=StationSync_Port{SYNC_PORT}", "dir=in", "action=allow",
            f"localport={SYNC_PORT}", "protocol=tcp", "enable=yes"],
            capture_output=True, timeout=10)
    except: pass
    try:
        server = ThreadingHTTPServer(("0.0.0.0", SYNC_PORT), SyncHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True, name="SyncServer-8089")
        t.start(); print(f"[sync] Sync server: http://0.0.0.0:{SYNC_PORT}")
    except Exception as e: print(f"[sync] Failed: {e}")


if __name__ == "__main__":
    if "--worker" in sys.argv:
        _instance_mutex = acquire_single_instance("AUTO_QR_BINDING_WORKER_" + MES_NEW_STATION.upper())
        if _instance_mutex is None: raise SystemExit("QR Binding Agent is already running")
        # 工作进程模式：运行主程序
        init_station_config()
        # QR is a native desktop station; no local browser/API listener is
        # required.  Keep only the shared 8089 synchronization service.
        # 8089 belongs exclusively to the standalone common NG/SN service.
        # QR reads that service and must not start a competing legacy server.
        start_mes_bridge()
        start_ws_server()
        register_ip_to_mes()   # 向MES注册本工位IP
        app = App()
        _app_ref[0] = app
        install_station_retest_panel(
            app.root, MES_NEW_STATION, MES_NEW_API,
            test_station=False,
        )
        from station_repair_workflow import install_repair_workflow
        install_repair_workflow(app.root, MES_NEW_STATION, MES_NEW_API, "PCBA外壳绑码")
        app.root.protocol("WM_DELETE_WINDOW", app._on_close)
        # Station startup must not open a browser. The operator uses the
        # native Agent window; MES/3D synchronization continues in background.
        print("QR Binding System started")
        app.root.mainloop()
    else:
        _watchdog_mutex = acquire_single_instance("AUTO_QR_BINDING_WATCHDOG_" + MES_NEW_STATION.upper())
        if _watchdog_mutex is None: raise SystemExit("QR Binding watchdog is already running")
        # 看门狗模式：启动工作进程，崩溃后自动重启
        run_watchdog()
