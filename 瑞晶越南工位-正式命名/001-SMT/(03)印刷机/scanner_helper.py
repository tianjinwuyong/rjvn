"""
Scanner Helper — 全局键盘捕获 + WebSocket + SQLite CRUD HTTP API + 自带 HTML 界面

双击运行，自动打开浏览器。
提供 HTTP API 供 HTML 页面操作本地资源（SN池、NG池、SQLite记录）。

用法:
    python scanner_helper.py         开发模式
    ./dist/Scanner_Helper.exe   打包后模式（自动打开浏览器）

依赖:
    pip install pynput websockets
"""

import asyncio
import json
import threading
import time
import logging
import sqlite3
import queue
import socket
import os
import sys
import webbrowser
import tempfile
from collections import deque
import subprocess
import winreg
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, date

# pynput 全局键盘钩子
from pynput import keyboard

# WebSocket 服务器
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("[warn] websockets not installed. Run: pip install websockets")

# 可选数据库驱动
try:
    import pymysql
    HAVE_MYSQL = True
except ImportError:
    HAVE_MYSQL = False

try:
    import pymssql
    HAVE_MSSQL = True
except ImportError:
    HAVE_MSSQL = False

# 可选 Excel 读取
try:
    import openpyxl
    HAVE_OPENPYXL = True
except ImportError:
    HAVE_OPENPYXL = False
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("[warn] websockets not installed. Run: pip install websockets")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("scanner_helper")


# ================================================================
# 配置
# ================================================================
HTTP_PORT = 8089
WS_PORT = 1004
SCAN_MIN_CHARS = 3
SCAN_MAX_GAP_MS = 80
SCAN_FINAL_WAIT_MS = 150
AUTO_START_NAME = "StationHelper"

# 外部数据源连接池
DB_CONNECTIONS = {}  # conn_id -> {type, conn, config}

#  bundled HTML（PyInstaller 模式下从资源目录读取）
HTML_CONTENT = ""


# ================================================================
# 外部数据源连接管理器 (MySQL / SQL Server / SQLite / Excel)
# ================================================================

def connect_datasource(ds_type, config):
    """连接到外部数据源，返回 (conn_id, tables_or_error)"""
    conn_id = f"{ds_type}_{int(time.time())}_{len(DB_CONNECTIONS)}"
    try:
        if ds_type == "mysql":
            if not HAVE_MYSQL:
                return None, "pymysql 未安装，请运行: pip install pymysql"
            conn = pymysql.connect(
                host=config.get("host", "localhost"),
                port=int(config.get("port", 3306)),
                user=config.get("user", "root"),
                password=config.get("password", ""),
                database=config.get("database", ""),
                charset='utf8mb4',
                connect_timeout=5
            )
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [r[0] for r in cursor.fetchall()]
            cursor.close()
            DB_CONNECTIONS[conn_id] = {"type": ds_type, "conn": conn, "config": config}
            return conn_id, tables

        elif ds_type == "sqlserver":
            if not HAVE_MSSQL:
                return None, "pymssql 未安装，请运行: pip install pymssql"
            conn = pymssql.connect(
                host=config.get("host", "localhost"),
                port=int(config.get("port", 1433)),
                user=config.get("user", "sa"),
                password=config.get("password", ""),
                database=config.get("database", ""),
                charset='utf8',
                timeout=5
            )
            cursor = conn.cursor()
            cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
            tables = [r[0] for r in cursor.fetchall()]
            cursor.close()
            DB_CONNECTIONS[conn_id] = {"type": ds_type, "conn": conn, "config": config}
            return conn_id, tables

        elif ds_type == "sqlite":
            path = config.get("filepath", "")
            if not path or not os.path.exists(path):
                return None, f"文件不存在: {path}"
            conn = sqlite3.connect(path, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r[0] for r in cursor.fetchall()]
            cursor.close()
            DB_CONNECTIONS[conn_id] = {"type": ds_type, "conn": conn, "config": config}
            return conn_id, tables

        elif ds_type == "excel":
            path = config.get("filepath", "")
            if not path or not os.path.exists(path):
                return None, f"文件不存在: {path}"
            if not HAVE_OPENPYXL:
                return None, "openpyxl 未安装，请运行: pip install openpyxl"
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            sheets = wb.sheetnames
            DB_CONNECTIONS[conn_id] = {"type": ds_type, "conn": wb, "config": config, "path": path}
            return conn_id, sheets  # sheet names as "tables"

        else:
            return None, f"不支持的数据源类型: {ds_type}"
    except Exception as e:
        return None, str(e)


def query_datasource(conn_id, sql):
    """对已连接的数据源执行查询。Excel 模式下 sql 为 sheet_name"""
    info = DB_CONNECTIONS.get(conn_id)
    if not info:
        return None, "连接不存在或已断开"
    if info["type"] == "excel":
        return _read_excel_sheet(info.get("conn"), sql)
    conn = info.get("conn")
    if not conn:
        return None, "连接已关闭"
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        cursor.close()
        result = []
        for row in rows:
            result.append({col: (str(v) if v is not None else None) for col, v in zip(cols, row)})
        return result, None
    except Exception as e:
        return None, str(e)


def _read_excel_sheet(wb, sheet_name):
    """读取 Excel 工作表中的数据"""
    try:
        ws = wb[sheet_name]
    except KeyError:
        return None, f"工作表不存在: {sheet_name}"
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], None
    # 第一行为表头
    headers = [str(c) if c is not None else f"Col{i}" for i, c in enumerate(rows[0])]
    result = []
    for row in rows[1:]:
        row_data = {}
        for i, val in enumerate(row):
            col_name = headers[i] if i < len(headers) else f"Col{i}"
            row_data[col_name] = str(val) if val is not None else None
        result.append(row_data)
    return result, None


def disconnect_datasource(conn_id):
    """断开数据源连接"""
    info = DB_CONNECTIONS.pop(conn_id, None)
    if info and "conn" in info:
        try:
            close_fn = getattr(info["conn"], "close", None)
            if close_fn:
                close_fn()
        except Exception:
            pass
    return True


def get_datasource_info(conn_id):
    """获取连接信息"""
    info = DB_CONNECTIONS.get(conn_id)
    if not info:
        return None
    return {
        "type": info["type"],
        "config": {k: v for k, v in info["config"].items() if k not in ("password",)},
    }


def load_html():
    """加载 bundled HTML 或从外部文件读取（开发模式）"""
    global HTML_CONTENT

    # 尝试 PyInstaller 打包资源目录
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        html_path = os.path.join(base, 'index_fct.html')
    else:
        # 开发模式：找同目录的 HTML
        html_path = os.path.join(os.path.dirname(__file__), 'index_fct.html')

    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            HTML_CONTENT = f.read()
        log.info(f"已加载 HTML: {html_path} ({len(HTML_CONTENT)} bytes)")
    else:
        log.warning("未找到 index_fct.html，浏览器界面将不可用")


# ================================================================
# Network helpers
# ================================================================
def get_local_ips():
    """Get all non-loopback IPv4 addresses of this machine."""
    ips = []
    try:
        # Method 1: UDP connect trick (gives primary outgoing IP)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            primary = s.getsockname()[0]
            if primary and primary != "127.0.0.1":
                ips.append(primary)
    except:
        pass
    try:
        # Method 2: enumerate all interfaces
        hostname = socket.gethostname()
        for addr in socket.getaddrinfo(hostname, None):
            ip = addr[4][0]
            if ip and not ip.startswith("127.") and ":" not in ip:
                if ip not in ips:
                    ips.append(ip)
    except:
        pass
    return ips

# ================================================================
# SQLite 数据库
# ================================================================
def get_db_path():
    """数据库路径：exe 同目录下"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "fct_local.db")
    return os.path.join(os.path.dirname(__file__), "fct_local.db")

DB_PATH = get_db_path()

def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sn_records (
            sn     TEXT PRIMARY KEY,
            result TEXT NOT NULL DEFAULT 'PASS',
            time   TEXT NOT NULL,
            source TEXT DEFAULT 'scanner'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ng_pool (
            sn     TEXT PRIMARY KEY,
            result TEXT NOT NULL DEFAULT 'NG',
            time   TEXT NOT NULL,
            source TEXT DEFAULT 'scanner'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dup_pool (
            sn   TEXT PRIMARY KEY,
            time TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            id    INTEGER PRIMARY KEY CHECK (id = 1),
            total INTEGER NOT NULL DEFAULT 0,
            pass  INTEGER NOT NULL DEFAULT 0,
            fail  INTEGER NOT NULL DEFAULT 0,
            dup   INTEGER NOT NULL DEFAULT 0,
            date  TEXT NOT NULL
        )
    """)
    today = date.today().isoformat()
    cur.execute("INSERT OR IGNORE INTO stats (id,total,pass,fail,dup,date) VALUES (1,0,0,0,0,?)", (today,))
    conn.commit()
    conn.close()
    log.info(f"SQLite 初始化: {DB_PATH}")
    migrate_db()


def migrate_db():
    """Schema 迁移：添加 station/line_name/operator/date 列"""
    conn = get_db()
    cur = conn.cursor()
    migrations = [
        ("sn_records", ["station", "line_name", "operator", "date"]),
        ("ng_pool",    ["station", "line_name", "operator", "date"]),
        ("dup_pool",   ["station", "line_name", "operator", "date"]),
    ]
    for table, cols in migrations:
        for col in cols:
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT ''")
                log.info(f"迁移: {table} 添加列 {col}")
            except sqlite3.OperationalError:
                pass  # 列已存在
    # 创建配置表（用于存储工位/产线/操作员配置）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS station_config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
    """)
    cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('station', '01')")
    cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('line_name', 'AUTO-LINE-1')")
    cur.execute("INSERT OR IGNORE INTO station_config (key, value) VALUES ('operator', '')")
    conn.commit()
    conn.close()


# ================================================================
# 自动启动（Windows 注册表）
# ================================================================

def set_auto_start(enabled):
    """设置开机自启（HKCU Run key）"""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            if getattr(sys, 'frozen', False):
                cmd = f'"{sys.executable}"'
            else:
                cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, AUTO_START_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, AUTO_START_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        log.info(f"开机自启 -> {'开启' if enabled else '关闭'}")
        return True
    except Exception as e:
        log.warning(f"设置自启失败: {e}")
        return False


def get_auto_start():
    """检查开机自启状态"""
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
# 看门狗（Watchdog）—— 崩溃自动重启
# ================================================================

WATCHDOG_MARKER_FILE = os.path.join(
    tempfile.gettempdir(), "station_helper_watchdog.json"
)


def write_watchdog_marker(restart_count):
    """写看门狗标记文件（供工作进程读取状态）"""
    try:
        with open(WATCHDOG_MARKER_FILE, 'w') as f:
            json.dump({
                "restart_count": restart_count,
                "watchdog_pid": os.getpid(),
            }, f)
    except Exception:
        pass


def read_watchdog_marker():
    """读取看门狗状态"""
    try:
        with open(WATCHDOG_MARKER_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"restart_count": 0, "watchdog_pid": 0}


def get_watchdog_status():
    """获取看门狗运行状态"""
    is_worker = "--worker" in sys.argv
    if is_worker:
        marker = read_watchdog_marker()
        return {
            "enabled": True,
            "is_worker": True,
            "restart_count": marker.get("restart_count", 0),
            "watchdog_pid": marker.get("watchdog_pid", 0),
        }
    return {
        "enabled": False,
        "is_worker": False,
        "restart_count": 0,
        "watchdog_pid": 0,
    }


def run_watchdog():
    """看门狗进程：启动工作子进程，崩溃后自动重启"""
    write_watchdog_marker(0)
    log.info("=" * 50)
    log.info("  看门狗已启动 — 工作进程崩溃后自动重启")
    log.info("=" * 50)

    try:
        while not _shutdown_event.is_set():
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "--worker"]
                sout = subprocess.DEVNULL
                serr = subprocess.DEVNULL
            else:
                cmd = [sys.executable, __file__, "--worker"]
                sout = None
                serr = None

            proc = subprocess.Popen(cmd, stdout=sout, stderr=serr)
            log.info(f"[WATCHDOG] 工作进程已启动 (PID: {proc.pid})")
            proc.wait()

            if _shutdown_event.is_set():
                break

            if proc.returncode == 0:
                log.info("[WATCHDOG] 工作进程正常退出，看门狗停止")
                break
            if proc.returncode == 42:
                log.info("[WATCHDOG] 工作进程请求重启")
                for _ in range(2):
                    if _shutdown_event.is_set():
                        return
                    time.sleep(1)
                continue

            write_watchdog_marker(
                read_watchdog_marker().get("restart_count", 0) + 1
            )
            log.warning(
                f"[WATCHDOG] 工作进程异常退出 (code: {proc.returncode})，"
                f"3秒后重启"
            )
            for _ in range(3):
                if _shutdown_event.is_set():
                    return
                time.sleep(1)
    except KeyboardInterrupt:
        log.info("[WATCHDOG] 收到 Ctrl+C")
    finally:
        _shutdown_event.set()
        log.info("[WATCHDOG] 已停止")


def get_pools():
    conn = get_db()
    cur = conn.cursor()
    sn_set  = [r[0] for r in cur.execute("SELECT sn FROM sn_records").fetchall()]
    ng_set  = [r[0] for r in cur.execute("SELECT sn FROM ng_pool").fetchall()]
    dup_set = [r[0] for r in cur.execute("SELECT sn FROM dup_pool").fetchall()]
    conn.close()
    return {
        "sn_pool": sn_set, "ng_pool": ng_set, "dup_pool": dup_set,
        "sn_pool_count": len(sn_set), "ng_pool_count": len(ng_set), "dup_pool_count": len(dup_set),
    }

def get_sn_records(limit=100, from_time=None, to_time=None, from_date=None):
    conn = get_db()
    sql = "SELECT sn, result, time, source, station, line_name, operator, date FROM sn_records WHERE 1=1"
    params = []
    today = date.today().isoformat()
    if from_date:
        sql += " AND date = ?"
        params.append(from_date)
    elif from_time or to_time:
        sql += " AND date = ?"
        params.append(today)
    if from_time:
        sql += " AND time >= ?"
        params.append(from_time)
    if to_time:
        sql += " AND time <= ?"
        params.append(to_time)
    sql += " ORDER BY date DESC, time DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [{"sn": r[0], "result": r[1], "time": r[2], "source": r[3],
             "station": r[4] or "", "line_name": r[5] or "", "operator": r[6] or "",
             "date": r[7] or ""} for r in rows]

def add_sn_record(sn, result="PASS", source="manual", station="", line_name="", operator=""):
    conn = get_db()
    now = datetime.now().strftime("%H:%M:%S")
    today = date.today().isoformat()
    conn.execute("INSERT OR REPLACE INTO sn_records (sn,result,time,source,station,line_name,operator,date) VALUES (?,?,?,?,?,?,?,?)",
                 (sn.upper(), result, now, source, station, line_name, operator, today))
    conn.commit()
    conn.close()

def delete_sn_record(sn):
    conn = get_db()
    conn.execute("DELETE FROM sn_records WHERE sn=?", (sn.upper(),))
    conn.commit()
    conn.close()

def get_ng_pool(limit=100):
    conn = get_db()
    rows = conn.execute(
        "SELECT sn, result, time, source, station, line_name, operator, date FROM ng_pool ORDER BY date DESC, time DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [{"sn": r[0], "result": r[1], "time": r[2], "source": r[3],
             "station": r[4] or "", "line_name": r[5] or "", "operator": r[6] or "",
             "date": r[7] or ""} for r in rows]

def add_ng_pool(sn, source="manual", station="", line_name="", operator=""):
    conn = get_db()
    now = datetime.now().strftime("%H:%M:%S")
    today = date.today().isoformat()
    conn.execute("INSERT OR REPLACE INTO ng_pool (sn,result,time,source,station,line_name,operator,date) VALUES (?,?,?,?,?,?,?,?)",
                 (sn.upper(), "NG", now, source, station, line_name, operator, today))
    conn.commit()
    conn.close()

def delete_ng_pool(sn):
    conn = get_db()
    conn.execute("DELETE FROM ng_pool WHERE sn=?", (sn.upper(),))
    conn.commit()
    conn.close()

def get_dup_pool(limit=100):
    conn = get_db()
    rows = conn.execute("SELECT sn, time, station, line_name, operator, date FROM dup_pool ORDER BY date DESC, time DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [{"sn": r[0], "time": r[1],
             "station": r[2] or "", "line_name": r[3] or "", "operator": r[4] or "",
             "date": r[5] or ""} for r in rows]

def add_dup_pool(sn, station="", line_name="", operator=""):
    conn = get_db()
    now = datetime.now().strftime("%H:%M:%S")
    today = date.today().isoformat()
    conn.execute("INSERT OR REPLACE INTO dup_pool (sn,time,station,line_name,operator,date) VALUES (?,?,?,?,?,?)",
                 (sn.upper(), now, station, line_name, operator, today))
    conn.commit()
    conn.close()

def delete_dup_pool(sn):
    conn = get_db()
    conn.execute("DELETE FROM dup_pool WHERE sn=?", (sn.upper(),))
    conn.commit()
    conn.close()

def get_stats():
    conn = get_db()
    today = date.today().isoformat()
    row = conn.execute(
        "SELECT total,pass,fail,dup,date FROM stats WHERE date=? OR id=1 ORDER BY date DESC LIMIT 1", (today,)
    ).fetchone()
    conn.close()
    if row:
        return {"total": row[0], "pass": row[1], "fail": row[2], "dup": row[3], "date": row[4]}
    return {"total": 0, "pass": 0, "fail": 0, "dup": 0, "date": today}

def update_stats(result: str):
    conn = get_db()
    today = date.today().isoformat()
    conn.execute("INSERT OR IGNORE INTO stats (id,total,pass,fail,dup,date) VALUES (1,0,0,0,0,?)", (today,))
    conn.execute("UPDATE stats SET total=total+1 WHERE id=1")
    if result == "PASS":
        conn.execute("UPDATE stats SET pass=pass+1 WHERE id=1")
    elif result == "NG":
        conn.execute("UPDATE stats SET fail=fail+1 WHERE id=1")
    elif result == "DUP":
        conn.execute("UPDATE stats SET dup=dup+1 WHERE id=1")
    conn.commit()
    conn.close()

def reset_all():
    conn = get_db()
    conn.execute("DELETE FROM sn_records")
    conn.execute("DELETE FROM ng_pool")
    conn.execute("DELETE FROM dup_pool")
    conn.execute("UPDATE stats SET total=0,pass=0,fail=0,dup=0 WHERE id=1")
    conn.commit()
    conn.close()
    log.info("所有池和记录已清空")


# ================================================================
# HTTP API 服务器
# ================================================================
_shutdown_event = threading.Event()

class FCTApiHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 静默 HTTP 日志

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def send_html(self, content, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def read_body(self):
        cl = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(cl).decode("utf-8") if cl else ""

    def handle_cors(self):
        if self.command == "OPTIONS":
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return True
        return False

    def do_OPTIONS(self):
        self.handle_cors()

    def do_GET(self):
        if self.handle_cors():
            return
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            limit = int((qs.get('limit') or [100])[0])
            if limit < 1: limit = 100
            if limit > 1000: limit = 1000
        except (ValueError, TypeError):
            limit = 100

        # Serve bundled HTML
        if path in ("/",):
            if HTML_CONTENT:
                self.send_html(HTML_CONTENT)
            else:
                self.send_html("<html><body><h1>Scanner Helper</h1><p>index_fct.html not found.</p></body></html>", 404)
            return

        try:
            if path == "/health":
                self.send_json({"status": "ok", "time": datetime.now().isoformat()})
            elif path == "/api/heartbeat":
                self.send_json({"status": "alive", "time": datetime.now().isoformat()})
            elif path == "/api/device/path":
                self.send_json({"cwd": os.getcwd(), "exe_dir": os.path.dirname(os.path.abspath(__file__))})
            elif path == "/api/device/network":
                ips = get_local_ips()
                self.send_json({"ips": ips, "primary": ips[0] if ips else ""})
            elif path == "/pools":
                self.send_json(get_pools())
            elif path == "/sn_records":
                from_time = qs.get('from', [None])[0]
                to_time = qs.get('to', [None])[0]
                if qs.get('today', [None])[0]:
                    from_time = "08:00:00"
                    to_time = datetime.now().strftime("%H:%M:%S")
                elif from_time:
                    from_time = from_time + ":00" if from_time.count(':') == 1 else from_time
                elif to_time:
                    to_time = to_time + ":00" if to_time.count(':') == 1 else to_time
                self.send_json(get_sn_records(limit=limit, from_time=from_time, to_time=to_time))
            elif path == "/ng_pool":
                self.send_json(get_ng_pool(limit=limit))
            elif path == "/dup_pool":
                self.send_json(get_dup_pool(limit=limit))
            elif path == "/stats":
                self.send_json(get_stats())
            elif path.startswith("/sn_records/"):
                sn = path.split("/")[-1]
                rec = next((r for r in get_sn_records() if r["sn"] == sn.upper()), None)
                if rec:
                    self.send_json(rec)
                else:
                    self.send_json({"error": "not found"}, 404)
            elif path.startswith("/ng_pool/"):
                sn = path.split("/")[-1]
                rec = next((r for r in get_ng_pool() if r["sn"] == sn.upper()), None)
                if rec:
                    self.send_json(rec)
                else:
                    self.send_json({"error": "not found"}, 404)
            elif path == "/db/connections":
                conns = {}
                for cid, info in DB_CONNECTIONS.items():
                    conns[cid] = {"type": info["type"]}
                self.send_json(conns)
            elif path == "/config/station":
                conn = get_db()
                rows = conn.execute("SELECT key, value FROM station_config").fetchall()
                conn.close()
                cfg = {r[0]: r[1] for r in rows}
                self.send_json(cfg)
            elif path == "/api/settings/autostart":
                self.send_json({"enabled": get_auto_start()})
            elif path == "/api/settings/watchdog":
                self.send_json(get_watchdog_status())
            elif path == "/api/station/ips":
                conn = get_db()
                rows = conn.execute("SELECT key, value FROM station_config WHERE key IN ('ip_prev','ip_current','ip_next')").fetchall()
                conn.close()
                ips = {r[0]: r[1] for r in rows}
                self.send_json(ips)
            elif path.startswith("/db/tables"):
                qs = urlparse(self.path).query
                params = parse_qs(qs)
                conn_id = (params.get("conn_id") or [None])[0]
                if not conn_id or conn_id not in DB_CONNECTIONS:
                    self.send_json({"error": "无效的连接ID"}, 400)
                    return
                info = DB_CONNECTIONS[conn_id]
                if info["type"] == "excel":
                    self.send_json({"tables": [], "type": "excel", "path": info.get("path", "")})
                    return
                conn = info.get("conn")
                if not conn:
                    self.send_json({"error": "连接已关闭"}, 400)
                    return
                try:
                    cursor = conn.cursor()
                    if info["type"] == "mysql":
                        cursor.execute("SHOW TABLES")
                    elif info["type"] == "sqlserver":
                        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
                    else:
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                    tables = [r[0] for r in cursor.fetchall()]
                    cursor.close()
                    self.send_json({"tables": tables, "type": info["type"]})
                except Exception as e:
                    self.send_json({"error": str(e)}, 500)
            elif path.startswith("/dup_pool/"):
                sn = path.split("/")[-1]
                rec = next((r for r in get_dup_pool() if r["sn"] == sn.upper()), None)
                if rec:
                    self.send_json(rec)
                else:
                    self.send_json({"error": "not found"}, 404)
            else:
                self.send_json({"error": "not found"}, 404)
        except Exception as e:
            log.warning(f"HTTP GET error: {e}")
            self.send_json({"error": str(e)}, 500)

    def do_POST(self):
        if self.handle_cors():
            return
        path = urlparse(self.path).path
        body = self.read_body()
        try:
            data = json.loads(body) if body else {}
            if path == "/sn_records":
                sn = (data.get("sn") or "").strip().upper()
                if not sn:
                    self.send_json({"error": "sn is required"}, 400); return
                result = data.get("result", "PASS")
                add_sn_record(sn, result, data.get("source", "manual"),
                              data.get("station", ""), data.get("line_name", ""), data.get("operator", ""))
                update_stats(result)
                self.send_json({"ok": True, "sn": sn})
            elif path == "/ng_pool":
                sn = (data.get("sn") or "").strip().upper()
                if not sn:
                    self.send_json({"error": "sn is required"}, 400); return
                add_ng_pool(sn, data.get("source", "manual"),
                            data.get("station", ""), data.get("line_name", ""), data.get("operator", ""))
                update_stats("NG")
                self.send_json({"ok": True, "sn": sn})
            elif path == "/dup_pool":
                sn = (data.get("sn") or "").strip().upper()
                if not sn:
                    self.send_json({"error": "sn is required"}, 400); return
                add_dup_pool(sn, data.get("station", ""), data.get("line_name", ""), data.get("operator", ""))
                update_stats("DUP")
                self.send_json({"ok": True, "sn": sn})
            elif path == "/reset":
                reset_all()
                self.send_json({"ok": True})
            elif path == "/shutdown":
                self.send_json({"ok": True})
                threading.Timer(0.5, _shutdown_event.set).start()
            elif path == "/db/connect":
                ds_type = data.get("type", "")
                config = data.get("config", {})
                conn_id, result = connect_datasource(ds_type, config)
                if conn_id:
                    self.send_json({"conn_id": conn_id, "tables": result})
                else:
                    self.send_json({"error": result}, 400)
            elif path == "/db/query":
                conn_id = data.get("conn_id", "")
                sql = data.get("sql", "")
                if not conn_id or not sql:
                    self.send_json({"error": "conn_id and sql required"}, 400)
                    return
                rows, err = query_datasource(conn_id, sql)
                if err:
                    self.send_json({"error": err}, 400)
                else:
                    self.send_json({"rows": rows, "count": len(rows)})
            elif path == "/db/disconnect":
                conn_id = data.get("conn_id", "")
                disconnect_datasource(conn_id)
                self.send_json({"ok": True})
            elif path == "/config/station":
                cfg = data  # {station, line_name, operator}
                conn = get_db()
                for key in ("station", "line_name", "operator"):
                    if key in cfg:
                        conn.execute("INSERT OR REPLACE INTO station_config (key, value) VALUES (?, ?)",
                                     (key, cfg[key]))
                conn.commit()
                conn.close()
                self.send_json({"ok": True})
            elif path == "/api/station/ips":
                conn = get_db()
                for key in ("ip_prev", "ip_current", "ip_next"):
                    if key in data:
                        conn.execute("INSERT OR REPLACE INTO station_config (key, value) VALUES (?, ?)",
                                     (key, data[key]))
                conn.commit()
                conn.close()
                self.send_json({"ok": True})
            elif path == "/api/device/network" and self.command == "POST":
                ip = (data.get("ip") or "").strip()
                if not ip:
                    self.send_json({"error": "ip is required"}, 400)
                    return
                import subprocess, platform, tempfile, os
                if platform.system() != "Windows":
                    self.send_json({"error": "仅支持 Windows"})
                    return
                try:
                    # Find the first physical up adapter
                    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object -First 1 -ExpandProperty Name"],
                        capture_output=True, text=True, timeout=10)
                    iface = r.stdout.strip() if r.stdout else ""
                    if not iface:
                        self.send_json({"error": "未找到可用网卡"})
                        return
                    # Try netsh directly first
                    cmd = f'netsh interface ip set address name="{iface}" static {ip} 255.255.255.0 192.168.0.1 1'
                    r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
                    if r2.returncode == 0:
                        self.send_json({"ok": True, "ip": ip, "adapter": iface})
                        return
                    # Failed → write temp script and run elevated
                    ps_script = f'netsh interface ip set address name="{iface}" static {ip} 255.255.255.0 192.168.0.1 1'
                    ps_file = os.path.join(tempfile.gettempdir(), f'_fct_setip_{int(time.time())}.ps1')
                    with open(ps_file, 'w', encoding='utf-8') as f:
                        f.write(ps_script)
                    try:
                        elevate_cmd = f'Start-Process -Verb RunAs -Wait -WindowStyle Normal -FilePath powershell -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","{ps_file}"'
                        subprocess.run(["powershell", "-NoProfile", "-Command", elevate_cmd],
                            capture_output=True, text=True, timeout=60)
                    finally:
                        try: os.remove(ps_file)
                        except: pass
                    # Verify IP actually changed
                    r4 = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f'Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "{iface}" | Select-Object -ExpandProperty IPAddress'],
                        capture_output=True, text=True, timeout=10)
                    actual_ip = r4.stdout.strip() if r4.stdout else ""
                    if actual_ip == ip:
                        self.send_json({"ok": True, "ip": ip, "adapter": iface})
                    else:
                        self.send_json({"error": "更改IP需要管理员权限 — 请右键以管理员身份运行此程序"})
                except subprocess.TimeoutExpired:
                    self.send_json({"error": "更改IP超时"})
                except Exception as e:
                    self.send_json({"error": f"更改IP异常: {e}"})
            elif path == "/batch":
                results = []
                for op in data.get("ops", []):
                    try:
                        sn = (op.get("sn") or "").strip().upper()
                        stn = op.get("station", "")
                        ln  = op.get("line_name", "")
                        opr = op.get("operator", "")
                        if op.get("op") == "add_sn":
                            add_sn_record(sn, op.get("result","PASS"), op.get("source","manual"), stn, ln, opr)
                            results.append({"op": "add_sn", "sn": sn, "ok": True})
                        elif op.get("op") == "add_ng":
                            add_ng_pool(sn, op.get("source","manual"), stn, ln, opr)
                            results.append({"op": "add_ng", "sn": sn, "ok": True})
                        elif op.get("op") == "add_dup":
                            add_dup_pool(sn, stn, ln, opr)
                            results.append({"op": "add_dup", "sn": sn, "ok": True})
                        elif op.get("op") == "del_sn":
                            delete_sn_record(sn)
                            results.append({"op": "del_sn", "sn": sn, "ok": True})
                        elif op.get("op") == "del_ng":
                            delete_ng_pool(sn)
                            results.append({"op": "del_ng", "sn": sn, "ok": True})
                        elif op.get("op") == "del_dup":
                            delete_dup_pool(sn)
                            results.append({"op": "del_dup", "sn": sn, "ok": True})
                    except Exception as ex:
                        results.append({"op": op.get("op"), "sn": op.get("sn"), "ok": False, "error": str(ex)})
                self.send_json({"results": results})
            elif path == "/api/operator/login":
                barcode = (data.get("barcode") or "").strip()
                station = (data.get("station") or "").strip()
                line_name = (data.get("line_name") or "").strip()
                if not barcode:
                    self.send_json({"error": "barcode required"}, 400)
                    return
                # Parse barcode: try JSON first, then URL params, then raw
                op_id = barcode
                op_name = ""
                try:
                    parsed = json.loads(barcode)
                    op_id = parsed.get("id") or parsed.get("employee_id") or parsed.get("emp_id") or barcode
                    op_name = parsed.get("name") or parsed.get("employee_name") or ""
                except (json.JSONDecodeError, TypeError):
                    if "?" in barcode:
                        from urllib.parse import parse_qs
                        params = parse_qs(barcode.split("?")[1])
                        op_id = (params.get("id") or params.get("employee_id") or params.get("emp") or [barcode])[0]
                        op_name = (params.get("name") or params.get("employee_name") or [""])[0]
                # Save to station_config
                conn = get_db()
                conn.execute("INSERT OR REPLACE INTO station_config (key, value) VALUES ('operator', ?)", (op_name or op_id,))
                if station:
                    conn.execute("INSERT OR REPLACE INTO station_config (key, value) VALUES ('station', ?)", (station,))
                if line_name:
                    conn.execute("INSERT OR REPLACE INTO station_config (key, value) VALUES ('line_name', ?)", (line_name,))
                conn.commit()
                conn.close()
                self.send_json({"ok": True, "operator": {"id": op_id, "name": op_name or op_id}})
            elif path == "/api/settings/autostart":
                enabled = data.get("enabled", False)
                ok = set_auto_start(enabled)
                self.send_json({"ok": ok, "enabled": enabled if ok else get_auto_start()})
            elif path == "/api/settings/restart":
                log.info("[API] 收到重启请求")
                threading.Timer(0.3, lambda: sys.exit(42)).start()
                self.send_json({"ok": True, "message": "正在重启..."})
            else:
                self.send_json({"error": "not found"}, 404)
        except Exception as e:
            log.warning(f"HTTP POST error: {e}")
            self.send_json({"error": str(e)}, 500)

    def do_DELETE(self):
        if self.handle_cors():
            return
        path = urlparse(self.path).path
        try:
            if path.startswith("/sn_records/"):
                sn = path.split("/")[-1]
                delete_sn_record(sn)
                self.send_json({"ok": True, "sn": sn})
            elif path.startswith("/ng_pool/"):
                sn = path.split("/")[-1]
                delete_ng_pool(sn)
                self.send_json({"ok": True, "sn": sn})
            elif path.startswith("/dup_pool/"):
                sn = path.split("/")[-1]
                delete_dup_pool(sn)
                self.send_json({"ok": True, "sn": sn})
            else:
                self.send_json({"error": "not found"}, 404)
        except Exception as e:
            log.warning(f"HTTP DELETE error: {e}")
            self.send_json({"error": str(e)}, 500)


def run_http_server():
    server = HTTPServer(("0.0.0.0", HTTP_PORT), FCTApiHandler)
    server.timeout = 1
    log.info(f"HTTP API 已启动: http://localhost:{HTTP_PORT}")
    while not _shutdown_event.is_set():
        server.handle_request()
    server.server_close()
    log.info("HTTP API 已关闭")


# ================================================================
# 全局键盘捕获（扫码枪）
# ================================================================
SCAN_BUFFER = deque(maxlen=64)
LAST_KEY_TIME = 0
SCAN_MODE = False
SCAN_COLLECTOR = None
WS_BROADCAST_QUEUE = queue.Queue()


class ScanCollector:
    def __init__(self):
        self._timer = None

    def schedule_submit(self, delay_ms):
        self.cancel()
        self._timer = threading.Timer(delay_ms / 1000, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def cancel(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _on_timeout(self):
        global SCAN_MODE, SCAN_BUFFER
        if SCAN_MODE and len(SCAN_BUFFER) >= SCAN_MIN_CHARS:
            sn = "".join(SCAN_BUFFER).strip()
            log.info(f"[SCAN] {sn}")
            _handle_scan_result(sn)
            WS_BROADCAST_QUEUE.put_nowait(sn)
        SCAN_MODE = False
        SCAN_BUFFER.clear()


def _get_station_config():
    """从数据库读取工位配置"""
    try:
        conn = get_db()
        rows = conn.execute("SELECT key, value FROM station_config").fetchall()
        conn.close()
        cfg = {r[0]: r[1] for r in rows}
        return cfg.get("station", ""), cfg.get("line_name", ""), cfg.get("operator", "")
    except Exception:
        return "", "", ""


def _handle_scan_result(sn: str):
    stn, ln, opr = _get_station_config()
    conn = get_db()
    cur = conn.cursor()
    if cur.execute("SELECT 1 FROM ng_pool WHERE sn=?", (sn,)).fetchone():
        update_stats("NG")
        conn.close()
        log.info(f"[RESULT] NG (ng_pool): {sn}")
        return
    if cur.execute("SELECT 1 FROM sn_records WHERE sn=?", (sn,)).fetchone():
        update_stats("DUP")
        add_dup_pool(sn, stn, ln, opr)
        conn.close()
        log.info(f"[RESULT] DUP (local): {sn}")
        return
    if cur.execute("SELECT 1 FROM dup_pool WHERE sn=?", (sn,)).fetchone():
        update_stats("DUP")
        conn.close()
        log.info(f"[RESULT] DUP (dup_pool): {sn}")
        return
    update_stats("PASS")
    add_sn_record(sn, "PASS", "scanner", stn, ln, opr)
    conn.close()
    log.info(f"[RESULT] PASS: {sn}")


def _process_key(key):
    try:
        if hasattr(key, 'char') and key.char:
            return key.char
    except Exception:
        pass
    return {keyboard.Key.enter: None, keyboard.Key.space: ' ', keyboard.Key.tab: '\t'}.get(key, '')


def _on_press(key):
    global SCAN_MODE, LAST_KEY_TIME, SCAN_BUFFER, SCAN_COLLECTOR
    try:
        c = _process_key(key)
        if c is None:
            SCAN_COLLECTOR.cancel()
            if SCAN_MODE and len(SCAN_BUFFER) >= SCAN_MIN_CHARS:
                sn = "".join(SCAN_BUFFER).strip()
                log.info(f"[SCAN] {sn}")
                _handle_scan_result(sn)
                WS_BROADCAST_QUEUE.put_nowait(sn)
            SCAN_MODE = False
            SCAN_BUFFER.clear()
            LAST_KEY_TIME = time.time() * 1000
        elif c:
            now = time.time() * 1000
            gap = now - LAST_KEY_TIME
            if gap < SCAN_MAX_GAP_MS:
                SCAN_MODE = True
                SCAN_BUFFER.append(c)
            else:
                SCAN_BUFFER.clear()
                SCAN_MODE = False
            LAST_KEY_TIME = now
            SCAN_COLLECTOR.schedule_submit(SCAN_FINAL_WAIT_MS)
    except Exception as e:
        log.warning(f"key error: {e}")


# ================================================================
# WebSocket 服务器
# ================================================================
connected_clients = set()

async def ws_handler_main(websocket, path):
    global connected_clients
    connected_clients.add(websocket)
    cid = id(websocket)
    log.info(f"[WS] 客户端连接: {cid} (总计: {len(connected_clients)})")
    try:
        async for msg in websocket:
            log.debug(f"[WS] <- {cid}: {msg}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        log.info(f"[WS] 客户端断开 (剩余: {len(connected_clients)})")

async def ws_broadcast_loop():
    while not _shutdown_event.is_set():
        try:
            sn = await asyncio.get_event_loop().run_in_executor(
                None, WS_BROADCAST_QUEUE.get, True, 0.5
            )
            if connected_clients:
                await asyncio.gather(
                    *[ws.send(sn) for ws in list(connected_clients)],
                    return_exceptions=True
                )
                log.info(f"[WS] 广播 -> {len(connected_clients)} 客户端: {sn}")
        except queue.Empty:
            pass
        except Exception as e:
            log.warning(f"broadcast error: {e}")

async def ws_server_main():
    log.info(f"WebSocket 已启动: ws://0.0.0.0:{WS_PORT}")
    broadcast_task = asyncio.create_task(ws_broadcast_loop())
    async with websockets.serve(ws_handler_main, "0.0.0.0", WS_PORT):
        await _shutdown_event.wait()
    broadcast_task.cancel()


# ================================================================
# 入口
# ================================================================
def check_port(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    r = sock.connect_ex(('localhost', port))
    sock.close()
    return r == 0

def open_browser():
    """延迟打开浏览器，确保服务器已就绪"""
    def _open():
        time.sleep(1.5)
        url = f"http://localhost:{HTTP_PORT}/"
        log.info(f"打开浏览器: {url}")
        webbrowser.open(url)
    t = threading.Thread(target=_open, daemon=True)
    t.start()

def run():
    global SCAN_COLLECTOR
    SCAN_COLLECTOR = ScanCollector()

    # 工作进程模式标记
    if "--worker" in sys.argv:
        log.info("[WATCHDOG] 以工作进程模式运行")

    # 清理旧看门狗标记文件
    try:
        if os.path.exists(WATCHDOG_MARKER_FILE):
            os.remove(WATCHDOG_MARKER_FILE)
    except Exception:
        pass

    # 加载 HTML
    load_html()

    # 初始化数据库
    init_db()

    # 检查端口
    for port, name in [(HTTP_PORT, "HTTP"), (WS_PORT, "WebSocket")]:
        if check_port(port):
            log.error(f"端口 {port} 已被占用 ({name})，请先关闭已有程序"); return

    # HTTP API 线程
    threading.Thread(target=run_http_server, daemon=True, name="HTTP-API").start()

    # WebSocket 线程
    def ws_loop():
        asyncio.run(ws_server_main())
    threading.Thread(target=ws_loop, daemon=True, name="WS-Server").start()

    # 自动打开浏览器
    open_browser()

    log.info("=" * 50)
    log.info("Scanner Helper 已启动")
    log.info(f"  浏览器界面: http://localhost:{HTTP_PORT}/")
    log.info(f"  HTTP API : http://localhost:{HTTP_PORT}")
    log.info(f"  WebSocket: ws://localhost:{WS_PORT}")
    log.info(f"  SQLite   : {DB_PATH}")
    log.info("  扫码输入 → 自动写入 sn_records / ng_pool / dup_pool")
    log.info("按 Ctrl+C 退出")
    log.info("=" * 50)

    try:
        with keyboard.Listener(on_press=_on_press) as listener:
            listener.join()
    except KeyboardInterrupt:
        log.info("收到 Ctrl+C，正在退出...")
        _shutdown_event.set()
        sys.exit(0)

if __name__ == "__main__":
    # Auto-elevate to admin for network IP changes
    if "--no-elevate" not in sys.argv:
        try:
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                script = os.path.abspath(__file__)
                args = " ".join(f'"{a}"' for a in sys.argv[1:] if a != "--no-elevate")
                ps = f'Start-Process -Verb RunAs -WindowStyle Normal -FilePath python -ArgumentList "-u","{script}",{args}'
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=30)
                sys.exit(0)
        except Exception:
            pass  # Non-Windows or other issues, continue as normal user

    missing = []
    try: import pynput
    except ImportError: missing.append("pynput")
    if not WEBSOCKETS_AVAILABLE: missing.append("websockets")
    if missing:
        print(f"[error] 缺少依赖: {', '.join(missing)}")
        print("请运行: pip install " + " ".join(missing))
        sys.exit(1)

    if "--worker" in sys.argv:
        run()
    elif getattr(sys, 'frozen', False) and "--no-watchdog" not in sys.argv:
        run_watchdog()
    else:
        run()
