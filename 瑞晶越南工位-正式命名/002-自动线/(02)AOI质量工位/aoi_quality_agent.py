# -*- coding: utf-8 -*-
"""AOI quality station: heartbeat, duplicate-SN and confirmed-NG blocking."""

import json
import sqlite3
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
import urllib.request
from pathlib import Path

try:
    import pymysql
except ImportError:
    pymysql = None


STATION_CODE = "auto_aio"
MES_EVENTS_URL = "http://192.168.6.155:8080/api/pda/events"
HEARTBEAT_SECONDS = 5
APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0,str(APP_DIR.parent))
MANUAL_LINE=APP_DIR.parent.parent/'002-自动线'
if str(MANUAL_LINE) not in sys.path and MANUAL_LINE.exists():sys.path.insert(1,str(MANUAL_LINE))
from station_resource_startup import start_first_install_resource_read
start_first_install_resource_read(APP_DIR)
from station_alarm import StationAlarm
from station_i18n import TrilingualController
from station_data_sync import DurableMesSync
from station_runtime_safety import acquire_single_instance
from station_ui_primitives import register_scanner_entry
DB_PATH = APP_DIR / "aoi_quality.db"
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "root1234"
MYSQL_DATABASE = "pcb_detection"
MYSQL_TABLE = "detection_board"
MYSQL_POLL_SECONDS = 2
MES_SYNC = DurableMesSync(DB_PATH, MES_EVENTS_URL, STATION_CODE)


def connect():
    return sqlite3.connect(str(DB_PATH), timeout=5)


def init_database():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sn_records (
          sn TEXT PRIMARY KEY,
          first_seen_at INTEGER NOT NULL,
          last_seen_at INTEGER NOT NULL,
          scan_count INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS confirmed_ng (
          sn TEXT PRIMARY KEY,
          source_station TEXT,
          batch_id TEXT,
          defect_code TEXT,
          status TEXT NOT NULL DEFAULT 'blocked',
          updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS detection_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sn TEXT NOT NULL,
          decision TEXT NOT NULL,
          detected_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mysql_sync_state (
          source_name TEXT PRIMARY KEY,
          last_id INTEGER NOT NULL DEFAULT 0,
          updated_at INTEGER NOT NULL
        );
        """)


def post_event(event_type, payload):
    return MES_SYNC.send(event_type, payload)


def reconcile_local_inventory():
    """Continuously compare the station's durable SN/NG state with MES."""
    while True:
        try:
            with connect() as db:
                sns = [{"sn": row[0]} for row in db.execute("SELECT sn FROM sn_records ORDER BY sn")]
                ngs = [{"sn": row[0]} for row in db.execute(
                    "SELECT sn FROM confirmed_ng WHERE status='blocked' ORDER BY sn")]
            version = int(time.time() * 1000)
            MES_SYNC.reconcile("sn_records", sns, version, "sn")
            MES_SYNC.reconcile("confirmed_ng", ngs, version, "sn")
        except Exception:
            pass
        time.sleep(60)


def is_duplicate_and_save(sn):
    now = int(time.time() * 1000)
    with connect() as db:
        row = db.execute("SELECT scan_count FROM sn_records WHERE sn=?", (sn,)).fetchone()
        if row:
            db.execute("UPDATE sn_records SET last_seen_at=?,scan_count=scan_count+1 WHERE sn=?", (now, sn))
            return True
        db.execute("INSERT INTO sn_records VALUES (?,?,?,1)", (sn, now, now))
        return False


def confirmed_ng(sn):
    with connect() as db:
        return db.execute(
            "SELECT source_station,batch_id,defect_code FROM confirmed_ng WHERE sn=? AND status='blocked'", (sn,)
        ).fetchone()


def log_decision(sn, decision):
    with connect() as db:
        db.execute("INSERT INTO detection_log(sn,decision,detected_at) VALUES (?,?,?)",
                   (sn, decision, int(time.time() * 1000)))


def mysql_last_id():
    with connect() as db:
        row = db.execute("SELECT last_id FROM mysql_sync_state WHERE source_name='aoi_detection_board'").fetchone()
        return int(row[0]) if row else 0


def mysql_sync_row():
    """Return the persisted MySQL cursor row, or None before the first sync."""
    with connect() as db:
        return db.execute("SELECT last_id FROM mysql_sync_state WHERE source_name='aoi_detection_board'").fetchone()


def save_mysql_last_id(row_id):
    with connect() as db:
        db.execute("""
          INSERT INTO mysql_sync_state(source_name,last_id,updated_at) VALUES ('aoi_detection_board',?,?)
          ON CONFLICT(source_name) DO UPDATE SET last_id=excluded.last_id,updated_at=excluded.updated_at
        """, (int(row_id), int(time.time() * 1000)))


def mysql_connection():
    if pymysql is None:
        raise RuntimeError("pymysql 未安装，请执行: pip install pymysql")
    return pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                           password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                           connect_timeout=5, read_timeout=5)


def sync_confirmed_event(event):
    payload = event.get("payload") or {}
    source = event.get("stationCode") or payload.get("stationCode") or "MES"
    now = int(time.time() * 1000)
    boards = payload.get("subBoards") or []
    if not boards and payload.get("sn") and (payload.get("isConfirmedNG") or payload.get("confirmed")):
        boards = [payload]
    with connect() as db:
        for board in boards:
            if not board.get("sn") or not (board.get("isConfirmedNG") or board.get("confirmed")):
                continue
            db.execute("""
              INSERT INTO confirmed_ng(sn,source_station,batch_id,defect_code,status,updated_at)
              VALUES (?,?,?,?, 'blocked', ?)
              ON CONFLICT(sn) DO UPDATE SET source_station=excluded.source_station,
                batch_id=excluded.batch_id,defect_code=excluded.defect_code,status='blocked',updated_at=excluded.updated_at
            """, (str(board["sn"]).strip().upper(), source, payload.get("batchId"),
                  board.get("defectCode") or payload.get("defectCode") or "CONFIRMED_NG", now))


def confirmed_ng_listener():
    url = MES_EVENTS_URL + "?node=aoi_quality_agent&types=NG_DEFECT,ng_confirmed"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                for raw in response:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line.startswith("data: "):
                        sync_confirmed_event(json.loads(line[6:]))
        except Exception:
            time.sleep(2)


class AoiQualityAgent:
    def __init__(self, root):
        self.root = root
        root.title("AOI Quality Agent / AOI质量工位")
        root.geometry("720x340")
        root.configure(bg="#0f172a")
        self.sn = tk.StringVar()
        self.status = tk.StringVar(value="运行中：等待扫描 / Running")
        tk.Label(root, text="AOI质量工位 / AOI QUALITY STATION", bg="#0f172a", fg="#22d3ee",
                 font=("Arial", 22, "bold")).pack(pady=(25, 5))
        tk.Label(root, text="心跳 + 重复编码 + 确认不良拦截", bg="#0f172a", fg="#cbd5e1",
                 font=("Microsoft YaHei", 12)).pack()
        tk.Label(root,text=f"数据源: MYSQL · {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}.{MYSQL_TABLE} + 扫码枪",bg="#0f172a",fg="#a7f3d0",font=("Consolas",9)).pack()
        self.alarm=StationAlarm(root,lambda sns:post_event("DUPLICATE_ALARM_RELEASE",{"sns":sns,"releasedAt":int(time.time()*1000)}),STATION_CODE,MES_EVENTS_URL)
        self.language=TrilingualController(root)
        notebook=ttk.Notebook(root); notebook.pack(fill="both",expand=True,padx=10,pady=8)
        live=tk.Frame(notebook,bg="#0f172a"); handover=tk.Frame(notebook,bg="#0f172a"); residence=tk.Frame(notebook,bg="#0f172a")
        notebook.add(live,text="实时监控 / LIVE"); notebook.add(handover,text="工程交接单 / HANDOVER"); notebook.add(residence,text="工位滞留监控 / RESIDENCE")
        self.entry = tk.Entry(live, textvariable=self.sn, font=("Consolas", 22), justify="center")
        register_scanner_entry(root, self.entry)
        self.entry.pack(fill="x", padx=55, pady=24)
        self.entry.bind("<Return>", self.scan)
        tk.Button(live, text="扫描测试 / TEST SCAN", command=lambda: self.scan(test_mode=True), bg="#0891b2", fg="white",
                  font=("Microsoft YaHei", 12, "bold")).pack()
        tk.Label(live, textvariable=self.status, bg="#0f172a", fg="#fbbf24",
                 font=("Microsoft YaHei", 13, "bold"), wraplength=650).pack(pady=18)
        self.handover_tree=ttk.Treeview(handover,columns=("batch","source","destination","count","status","sent","received"),show="headings")
        for k,v in (("batch","整盘编号"),("source","来源"),("destination","目标"),("count","数量"),("status","状态"),("sent","送出"),("received","接收")): self.handover_tree.heading(k,text=v)
        self.handover_tree.pack(fill="both",expand=True,padx=8,pady=8)
        self.residence_tree=ttk.Treeview(residence,columns=("sn","batch","state","ng","entered","duration","alarm"),show="headings")
        for k,v in (("sn","SN"),("batch","整盘"),("state","状态"),("ng","NG"),("entered","入站"),("duration","滞留"),("alarm","报警")): self.residence_tree.heading(k,text=v)
        self.residence_tree.pack(fill="both",expand=True,padx=8,pady=8)
        root.after(500,self.refresh_mes_pages)
        self.entry.focus_set()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        threading.Thread(target=confirmed_ng_listener, daemon=True).start()
        threading.Thread(target=self.mysql_poll_loop, daemon=True).start()

    def refresh_mes_pages(self):
        try:
            base=MES_EVENTS_URL.replace("/api/pda/events","")
            with urllib.request.urlopen(base+f"/api/station/handovers?stationCode={STATION_CODE}",timeout=5) as response: rows=json.loads(response.read().decode()).get("items",[])
            self.handover_tree.delete(*self.handover_tree.get_children())
            for r in rows: self.handover_tree.insert("","end",values=(r.get("batchId"),r.get("sourceStation"),r.get("destinationStation"),r.get("memberCount"),r.get("status"),r.get("sentAt"),r.get("receivedAt")))
            with urllib.request.urlopen(base+f"/api/station/residence-stats?stationCode={STATION_CODE}",timeout=5) as response: data=json.loads(response.read().decode())
            threshold=int(data.get("thresholdMinutes",30))*60; self.residence_tree.delete(*self.residence_tree.get_children())
            for r in data.get("current",[]):
                s=int(r.get("seconds",0)); self.residence_tree.insert("","end",values=(r.get("sn"),r.get("batchId"),r.get("productState"),"是" if r.get("isNg") else "否",r.get("enteredAt"),f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}","超时" if s>=threshold else "正常"))
        except Exception: pass
        self.root.after(5000,self.refresh_mes_pages)

    def heartbeat_loop(self):
        while True:
            try:
                body = json.dumps({"type": "AGENT_HEARTBEAT", "stationCode": STATION_CODE,
                    "payload": {"agent": "aoi_quality_agent", "status": "running",
                    "timestamp": int(time.time() * 1000)}}).encode("utf-8")
                request = urllib.request.Request(MES_EVENTS_URL, data=body, method="POST",
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=3) as response:
                    response.read()
            except Exception:
                pass
            time.sleep(HEARTBEAT_SECONDS)

    def mysql_poll_loop(self):
        startup_baseline_pending = mysql_sync_row() is None  # first-ever run: establish baseline without replay
        while True:
            try:
                last_id = mysql_last_id()
                with mysql_connection() as mysql:
                    with mysql.cursor() as cursor:
                        if startup_baseline_pending:
                            cursor.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM detection_board")
                            baseline = int((cursor.fetchone() or {}).get("max_id") or 0)
                            save_mysql_last_id(baseline)
                            startup_baseline_pending = False
                            self.root.after(0, self.status.set,
                                            f"MySQL 已建立启动基线 / Startup baseline {baseline}")
                            time.sleep(MYSQL_POLL_SECONDS)
                            continue
                        cursor.execute(
                            "SELECT id, number, pass, finish_time, bcr_codes, total, ng "
                            "FROM detection_board WHERE id > %s ORDER BY id LIMIT 200", (last_id,))
                        rows = cursor.fetchall()
                for row in rows:
                    sn = str(row.get("number") or row.get("bcr_codes") or "").strip().upper()
                    row_id = int(row["id"])
                    if not sn:
                        save_mysql_last_id(row_id)
                        continue
                    duplicate = is_duplicate_and_save(sn)
                    if duplicate:
                        log_decision(sn, "MYSQL_DUPLICATE_BLOCKED")
                        post_event("DUPLICATE_SN", {"sn": sn, "batchId": f"AOI-MYSQL-{sn}", "sourceRowId": row_id})
                        self.root.after(0,lambda s=sn:self.alarm.trigger("重码报警",[s],"发现重复编码，禁止离开本站"))
                    elif not bool(row.get("pass")):
                        now = int(time.time() * 1000)
                        with connect() as db:
                            db.execute("""
                              INSERT INTO confirmed_ng(sn,source_station,batch_id,defect_code,status,updated_at)
                              VALUES (?, 'auto_aio', ?, 'AOI_NG', 'blocked', ?)
                              ON CONFLICT(sn) DO UPDATE SET status='blocked',defect_code='AOI_NG',updated_at=excluded.updated_at
                            """, (sn, f"AOI-{row_id}", now))
                        log_decision(sn, "MYSQL_CONFIRMED_NG")
                        post_event("NG_DEFECT", {
                            "mainSn": sn, "batchId": f"AOI-{row_id}", "sourceRowId": row_id,
                            "subBoards": [{"sn": sn, "slot": 1, "result": "NG", "isConfirmedNG": True,
                                           "defectCode": "AOI_NG"}],
                        })
                        self.root.after(0,lambda s=sn:self.alarm.trigger("NG报警",[s],"发现不良品，禁止不良品离开本站"))
                    else:
                        log_decision(sn, "MYSQL_ACCEPTED")
                    save_mysql_last_id(row_id)
                self.root.after(0, self.status.set,
                                f"MySQL 已连接 / Connected · last id {mysql_last_id()}")
            except Exception as exc:
                self.root.after(0, self.status.set, f"MySQL 读取失败 / Read failed: {exc}")
            time.sleep(MYSQL_POLL_SECONDS)

    def scan(self, _event=None, test_mode=False):
        sn = self.sn.get().strip().upper()
        self.sn.set("")
        if not sn:
            return
        try:
            ng = confirmed_ng(sn)
            # Button-driven test scans neither query nor mutate the production
            # duplicate registry. Scanner/Enter input remains fully guarded.
            duplicate = False if test_mode else is_duplicate_and_save(sn)
            if ng:
                log_decision(sn, "CONFIRMED_NG_BLOCKED")
                post_event("NG_DEFECT", {"sn": sn, "defectCode": "CONFIRMED_NG", "confirmed": True,
                                          "isConfirmedNG": True, "sourceStation": ng[0], "batchId": ng[1]})
                self.status.set(f"确认不良，禁止离开本站 / CONFIRMED NG: {sn}")
                self.alarm.trigger("NG报警",[sn],"发现不良品，禁止不良品离开本站")
            elif duplicate:
                log_decision(sn, "DUPLICATE_BLOCKED")
                post_event("DUPLICATE_SN", {"sn": sn, "batchId": f"AOI-{sn}"})
                self.status.set(f"重复编码，禁止离开本站 / DUPLICATE: {sn}")
                self.alarm.trigger("重码报警",[sn],"发现重复编码，禁止离开本站")
            else:
                log_decision(sn, "ACCEPTED")
                post_event("SCAN_GUARD_CHECK", {"sn": sn, "result": "CLEAR", "eventType": "aoi_quality_scan"})
                self.status.set(f"扫描通过 / ACCEPTED: {sn}")
        except Exception as exc:
            self.status.set(f"MES/SQLite 错误，保持拦截 / BLOCKED: {exc}")
        self.entry.focus_set()


if __name__ == "__main__":
    _instance_mutex = acquire_single_instance("MANU_AOI_AGENT")
    if _instance_mutex is None: raise SystemExit("AOI Agent is already running")
    # Compatibility launcher only. The Streamlit application is the single AOI
    # MySQL consumer; starting the legacy Tk poller as well would double-report.
    dashboard = APP_DIR / "aoi_station.py"
    def dashboard_online():
        try:
            with socket.create_connection(("127.0.0.1", 8502), timeout=1):
                return True
        except OSError:
            return False

    def service_heartbeat():
        while True:
            if dashboard_online():
                try:
                    body = json.dumps({"type": "AGENT_HEARTBEAT", "stationCode": STATION_CODE,
                        "payload": {"agent": "aoi_streamlit", "status": "running",
                        "timestamp": int(time.time() * 1000)}}).encode("utf-8")
                    request = urllib.request.Request(MES_EVENTS_URL, data=body, method="POST",
                        headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(request, timeout=3) as response:
                        response.read()
                except Exception:
                    pass
            time.sleep(HEARTBEAT_SECONDS)

    threading.Thread(target=service_heartbeat, daemon=True, name="aoi-service-heartbeat").start()
    while True:
        if dashboard_online():
            time.sleep(2)
            continue
        subprocess.call([sys.executable, "-m", "streamlit", "run", str(dashboard),
            "--server.port", "8502", "--server.address", "0.0.0.0", "--server.headless", "true"])
        time.sleep(2)
