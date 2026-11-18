# -*- coding: utf-8 -*-
"""Repair quality station agent: MES-managed NG/duplicate guard + local offline cache."""
import json
import os
import sqlite3
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
from datetime import datetime
from tkinter import messagebox, ttk

from mes_client import MesClient

# Shared MES-owned repair contract used by every station agent.
RESERVOIR_PY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "station-component-reservoir", "python"))
if RESERVOIR_PY not in sys.path:
    sys.path.insert(0, RESERVOIR_PY)
from station_components.ng_closed_loop import ClosedLoopState, apply_transition

BASE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "rework.db")
MES_API = os.environ.get("MES_API", "http://192.168.6.155:8080/api").rstrip("/")
PDA_EVENT_URL = os.environ.get("PDA_EVENT_URL", f"{MES_API}/pda/events")
STATION_CODE = os.environ.get("MES_STATION_CODE", "manu_rework")
STATION_IP = os.environ.get("MES_STATION_IP", "192.168.6.160")
LINE_CODE = os.environ.get("MES_LINE_CODE", "L004")
OPERATOR = os.environ.get("MES_OPERATOR", "QC_VN_01")
PASSWORD = os.environ.get("MES_PASSWORD", "Factory@123")
_ng_sync_started = False

os.makedirs(DATA_DIR, exist_ok=True)


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def sync_active_ng_registry():
    """Continuously mirror the MES-wide active-NG registry into rework.db."""
    base = MES_API[:-4] if MES_API.endswith("/api") else MES_API
    while True:
        try:
            with urllib.request.urlopen(base + "/api/station/ng-guard", timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            now = int(time.time() * 1000)
            version = int(data.get("version") or 0)
            rows = []
            for item in data.get("items") or []:
                sn = str(item.get("sn") or "").strip().upper()
                if sn:
                    rows.append((sn, item.get("sourceStationCode") or item.get("stationCode"),
                                 item.get("batchId"), json.dumps(item, ensure_ascii=False), version, now))
            with db_connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                conn.executemany("INSERT OR IGNORE INTO mes_confirmed_ng_cache VALUES(?,?,?,?,?,?)", rows)
        except Exception:
            pass
        time.sleep(15)


def init_db():
    global _ng_sync_started
    with db_connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sn_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT, sn TEXT NOT NULL UNIQUE,
          first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, station_code TEXT NOT NULL,
          result TEXT NOT NULL, mes_synced INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ng_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT, sn TEXT NOT NULL, source TEXT NOT NULL,
          defect_code TEXT, status TEXT NOT NULL DEFAULT 'pending', detected_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rework_ng_sn ON ng_records(sn);
        CREATE TABLE IF NOT EXISTS duplicate_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, sn TEXT NOT NULL, source TEXT NOT NULL,
          decision TEXT NOT NULL DEFAULT 'blocked', detected_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mes_sync_queue (
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, sn TEXT NOT NULL,
          result TEXT NOT NULL, payload TEXT, created_at TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS mes_confirmed_ng_cache (
          sn TEXT PRIMARY KEY, source_station TEXT, batch_id TEXT,
          payload TEXT NOT NULL, registry_version INTEGER NOT NULL DEFAULT 0,
          synced_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS motherboards (
          batch_id TEXT PRIMARY KEY, source_station TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'waiting_repair', received_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS motherboard_members (
          id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL, sn TEXT NOT NULL,
          slot INTEGER, incoming_result TEXT NOT NULL DEFAULT 'NG', defect_code TEXT,
          repair_status TEXT NOT NULL DEFAULT 'waiting', updated_at TEXT NOT NULL,
          UNIQUE(batch_id, sn)
        );
        CREATE INDEX IF NOT EXISTS idx_rework_member_sn ON motherboard_members(sn);
        CREATE TABLE IF NOT EXISTS repair_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT, sn TEXT NOT NULL,
          action TEXT NOT NULL, result TEXT, defect_code TEXT, repair_method TEXT,
          operator TEXT, started_at TEXT NOT NULL, completed_at TEXT, mes_synced INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_repair_records_sn ON repair_records(sn);
        CREATE TABLE IF NOT EXISTS repair_work_orders (
          work_order_no TEXT PRIMARY KEY, handover_bill_no TEXT, batch_id TEXT NOT NULL,
          ng_sn TEXT NOT NULL, source_station TEXT NOT NULL, submitted_at TEXT,
          received_at TEXT, repair_started_at TEXT, repair_completed_at TEXT,
          repair_method TEXT, repair_result TEXT, operator TEXT,
          retest_history TEXT NOT NULL DEFAULT '[]',
          status TEXT NOT NULL DEFAULT 'WAITING_RECEIPT', mes_synced INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_local_repair_wo_batch ON repair_work_orders(batch_id);
        CREATE TABLE IF NOT EXISTS repair_event_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
          work_order_no TEXT, shipment_id TEXT, box_qr TEXT, station_qr TEXT,
          sns_json TEXT NOT NULL DEFAULT '[]', quantity INTEGER, state TEXT NOT NULL,
          fact_json TEXT NOT NULL, recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS repair_material_usage (
          id INTEGER PRIMARY KEY AUTOINCREMENT, work_order_no TEXT NOT NULL, ng_sn TEXT,
          material_code TEXT, material_name TEXT, quantity REAL NOT NULL, unit TEXT,
          operator TEXT, recorded_at TEXT NOT NULL, mes_synced INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ng_migrations (
          id INTEGER PRIMARY KEY AUTOINCREMENT, migration_key TEXT NOT NULL UNIQUE,
          batch_id TEXT, sn TEXT NOT NULL, slot INTEGER, source_station TEXT NOT NULL,
          destination_station TEXT NOT NULL, defect_code TEXT, status TEXT NOT NULL DEFAULT 'received',
          migrated_at TEXT NOT NULL, completed_at TEXT, mes_synced INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_ng_migrations_batch ON ng_migrations(batch_id);
        CREATE INDEX IF NOT EXISTS idx_ng_migrations_sn ON ng_migrations(sn);
        CREATE TABLE IF NOT EXISTS motherboard_migration_state (
          batch_id TEXT PRIMARY KEY, source_station TEXT NOT NULL, destination_station TEXT NOT NULL,
          member_count INTEGER NOT NULL DEFAULT 0, ng_count INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'received', migrated_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        """)
        columns={row[1] for row in conn.execute("PRAGMA table_info(repair_work_orders)").fetchall()}
        if "retest_history" not in columns:
            conn.execute("ALTER TABLE repair_work_orders ADD COLUMN retest_history TEXT NOT NULL DEFAULT '[]'")
    if not _ng_sync_started:
        _ng_sync_started = True
        threading.Thread(target=sync_active_ng_registry, daemon=True,
                         name="rework-active-ng-registry").start()


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def post_pda(event_type, payload=None):
    body = {"type": event_type, "stationCode": STATION_CODE, "payload": payload or {}}
    try:
        req = urllib.request.Request(PDA_EVENT_URL, json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                     {"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=3) as response:
            response.read()
        return True
    except Exception:
        return False

def mes_scan_guard(sn):
    body={"type":"SCAN_GUARD_CHECK","stationCode":STATION_CODE,
          "payload":{"sn":sn,"result":"CLEAR","eventType":"repair_receipt_scanner"}}
    request=urllib.request.Request(PDA_EVENT_URL,json.dumps(body,ensure_ascii=False).encode("utf-8"),
                                   {"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(request,timeout=5) as response:return response.status,json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:data=json.loads(exc.read().decode("utf-8"))
        except Exception:data={"code":f"HTTP_{exc.code}"}
        return exc.code,data
    except Exception as exc:return 0,{"code":"MES_OFFLINE","message":str(exc)}


def mes_ng_check(sn):
    url = f"{MES_API}/mes/ng-registry/check?sn={urllib.parse.quote(sn)}&stationCode={STATION_CODE}&lineCode={LINE_CODE}"
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
        body = data.get("data", data)
        return bool(body.get("found") or body.get("hasNg") or body.get("isNg")), body
    except Exception:
        return False, {"offline": True}


def mes_post(path, payload):
    request = urllib.request.Request(f"{MES_API}{path}", json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                     {"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            data = {"error": {"code": f"HTTP_{exc.code}"}}
        return exc.code, data
    except Exception as exc:
        return 0, {"error": {"code": "MES_OFFLINE", "message": str(exc)}}


class RepairStation:
    def __init__(self, root):
        self.root = root
        self.root.title("回修站质量工位 / Repair Quality Station")
        self.root.geometry("1180x900")
        self.root.minsize(1080, 760)
        self.root.configure(bg="#0f172a")
        self.mes = MesClient(MES_API, STATION_CODE, LINE_CODE, OPERATOR, PASSWORD,
                             heartbeat_interval=10, auto_start=True)
        self.status_var = tk.StringVar(value="等待扫码 / Waiting for scan")
        self.sn_var = tk.StringVar()
        self._build_ui()
        self.refresh_table()
        self.root.after(5000, self._auto_refresh)
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        threading.Thread(target=self._sync_loop, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        tk.Label(self.root, text="回修站质量工位", font=("Microsoft YaHei", 26, "bold"),
                 fg="#67e8f9", bg="#0f172a").pack(pady=(20, 5))
        tk.Label(self.root, text=f"{STATION_CODE}  |  MES + Local SQLite", font=("Arial", 12),
                 fg="#94a3b8", bg="#0f172a").pack()
        row = tk.Frame(self.root, bg="#0f172a")
        row.pack(fill="x", padx=35, pady=20)
        entry = tk.Entry(row, textvariable=self.sn_var, font=("Consolas", 20), bg="#1e293b", fg="white",
                         insertbackground="white")
        entry.pack(side="left", fill="x", expand=True, ipady=8)
        entry.bind("<Return>", lambda _e: self.scan())
        tk.Button(row, text="扫码检查 / CHECK", command=self.scan, font=("Microsoft YaHei", 13, "bold"),
                  bg="#0891b2", fg="white", padx=18).pack(side="left", padx=(12, 0), ipady=7)
        entry.focus_set()
        tk.Label(self.root, textvariable=self.status_var, font=("Microsoft YaHei", 16, "bold"),
                 fg="#f8fafc", bg="#1e293b", pady=12).pack(fill="x", padx=35)
        buttons = tk.Frame(self.root, bg="#0f172a")
        buttons.pack(fill="x", padx=35, pady=12)
        tk.Button(buttons, text="刷新记录", command=self.refresh_table).pack(side="left", padx=4)
        tk.Label(self.root,text="MES待接收维修交接表 / PENDING REPAIR RECEIPTS",bg="#0f172a",fg="#fbbf24",
                 font=("Microsoft YaHei",11,"bold")).pack(anchor="w",padx=35)
        self.incoming_tree=ttk.Treeview(self.root,columns=("request","batch","source","members","sent","status"),show="headings",height=6)
        for key,title,width in (("request","申请号",80),("batch","整盘/SN",190),("source","来源工位",130),
                                ("members","成员",70),("sent","送出时间",165),("status","状态",130)):
            self.incoming_tree.heading(key,text=title);self.incoming_tree.column(key,width=width)
        self.incoming_tree.pack(fill="x",padx=35,pady=(3,12))
        tk.Label(self.root,text="维修中（扫码接收后开始计时，限时2小时） / REPAIR IN PROGRESS",
                 bg="#0f172a",fg="#67e8f9",font=("Microsoft YaHei",11,"bold")).pack(anchor="w",padx=35)
        self.active_tree=ttk.Treeview(self.root,columns=("batch","source","started","elapsed","alarm"),show="headings",height=5)
        for key,title,width in (("batch","整盘/SN",220),("source","来源工位",140),("started","开始维修",175),
                                ("elapsed","已用时间",120),("alarm","状态",150)):
            self.active_tree.heading(key,text=title);self.active_tree.column(key,width=width)
        self.active_tree.pack(fill="x",padx=35,pady=(3,12))
        complete_row=tk.Frame(self.root,bg="#0f172a");complete_row.pack(fill="x",padx=35,pady=(0,10))
        self.repair_complete_var=tk.BooleanVar(value=False)
        self.repair_method_var=tk.StringVar()
        tk.Checkbutton(complete_row,text="确认维修完成 / REPAIR COMPLETED",variable=self.repair_complete_var,
                       bg="#0f172a",fg="#f8fafc",selectcolor="#1e293b",activebackground="#0f172a").pack(side="left")
        tk.Entry(complete_row,textvariable=self.repair_method_var,width=36).pack(side="left",padx=8)
        tk.Button(complete_row,text="完成维修工单",command=self.complete_work_order,bg="#16a34a",fg="white").pack(side="left")
        material_row=tk.Frame(self.root,bg="#0f172a");material_row.pack(fill="x",padx=35,pady=(0,5))
        self.material_code_var=tk.StringVar();self.material_name_var=tk.StringVar();self.material_qty_var=tk.StringVar(value="1")
        self.no_material_var=tk.BooleanVar(value=False);self.material_items=[]
        for label,var,width in (("物料编码",self.material_code_var,16),("物料名称",self.material_name_var,18),("数量",self.material_qty_var,7)):
            tk.Label(material_row,text=label,bg="#0f172a",fg="#cbd5e1").pack(side="left")
            tk.Entry(material_row,textvariable=var,width=width).pack(side="left",padx=(3,8))
        tk.Button(material_row,text="添加更换物料",command=self.add_material,bg="#0369a1",fg="white").pack(side="left",padx=4)
        tk.Checkbutton(material_row,text="无物料更换",variable=self.no_material_var,bg="#0f172a",fg="#f8fafc",
                       selectcolor="#1e293b",activebackground="#0f172a").pack(side="left",padx=8)
        self.material_summary_var=tk.StringVar(value="尚未登记物料")
        tk.Label(self.root,textvariable=self.material_summary_var,bg="#0f172a",fg="#fbbf24").pack(anchor="w",padx=35,pady=(0,8))
        tk.Label(self.root,text="维修工单表 / REPAIR WORK ORDERS",bg="#0f172a",fg="#a7f3d0",
                 font=("Microsoft YaHei",11,"bold")).pack(anchor="w",padx=35)
        self.wo_tree=ttk.Treeview(self.root,columns=("wo","batch","sn","source","status","retests"),show="headings",height=5)
        for key,title,width in (("wo","维修工单号",180),("batch","批次",170),("sn","NG SN",180),
                                ("source","来源",100),("status","状态",130),("retests","复测履历",180)):
            self.wo_tree.heading(key,text=title);self.wo_tree.column(key,width=width)
        self.wo_tree.pack(fill="x",padx=35,pady=(3,10))
        self.wo_tree.bind("<Double-1>", lambda _event: self.show_work_order_history())
        tk.Button(buttons, text="维修工单历史 / WO HISTORY", command=self.show_work_order_history,
                  bg="#7c3aed", fg="white").pack(side="left", padx=4)
        self.tree = ttk.Treeview(self.root, columns=("time", "sn", "result", "source", "sync"), show="headings")
        for key, title, width in (("time", "Time", 155), ("sn", "SN", 260), ("result", "Result", 100),
                                  ("source", "Source", 140), ("sync", "MES", 80)):
            self.tree.heading(key, text=title); self.tree.column(key, width=width)
        self.tree.pack(fill="both", expand=True, padx=35, pady=(0, 25))

    def show_work_order_history(self):
        """Read-only history view; MES/local records remain append-only."""
        selected = self.wo_tree.selection()
        if not selected:
            messagebox.showinfo("维修工单历史 / WO HISTORY", "请先选择一张维修工单")
            return
        values = self.wo_tree.item(selected[0], "values")
        work_order_no = values[0]
        with db_connect() as conn:
            wo = conn.execute("SELECT * FROM repair_work_orders WHERE work_order_no=?", (work_order_no,)).fetchone()
            records = conn.execute(
                "SELECT action,result,defect_code,repair_method,operator,started_at FROM repair_records WHERE batch_id=(SELECT batch_id FROM repair_work_orders WHERE work_order_no=?) ORDER BY started_at",
                (work_order_no,)
            ).fetchall()
            materials = conn.execute(
                "SELECT material_code,material_name,quantity,unit,operator,recorded_at FROM repair_material_usage WHERE work_order_no=? ORDER BY recorded_at",
                (work_order_no,)
            ).fetchall()
        if not wo:
            messagebox.showwarning("维修工单历史 / WO HISTORY", "本地没有该工单历史；请等待 MES 同步")
            return
        lines = [
            f"WO: {wo['work_order_no']}", f"Batch: {wo['batch_id']}", f"SN: {wo['ng_sn']}",
            f"Source: {wo['source_station']}", f"Status: {wo['status']}",
            f"Received: {wo['received_at'] or '-'}", f"Started: {wo['repair_started_at'] or '-'}",
            f"Completed: {wo['repair_completed_at'] or '-'}", "", "EVENTS / 事件"
        ]
        for row in records:
            lines.append(f"{row['started_at']} | {row['action']} | {row['result'] or '-'} | {row['repair_method'] or '-'} | {row['operator'] or '-'}")
        lines.append("\nMATERIALS / 物料")
        for row in materials:
            lines.append(f"{row['recorded_at']} | {row['material_code']} {row['material_name'] or ''} | QTY {row['quantity']} {row['unit'] or ''} | OP {row['operator'] or '-'}")
        dialog = tk.Toplevel(self.root)
        dialog.title("维修工单历史 / WO HISTORY")
        dialog.geometry("900x620")
        dialog.transient(self.root)
        text = tk.Text(dialog, wrap="word", bg="#0f172a", fg="#e2e8f0", font=("Consolas", 11))
        text.pack(fill="both", expand=True, padx=12, pady=12)
        text.insert("1.0", "\n".join(lines)); text.configure(state="disabled")
        tk.Button(dialog, text="关闭 / CLOSE", command=dialog.destroy).pack(pady=(0, 12))

    def scan(self):
        sn = self.sn_var.get().strip().upper()
        self.sn_var.set("")
        if not sn or len(sn) < 6 or not all(c.isalnum() or c in "-_" for c in sn):
            self.status_var.set("无效编码 / Invalid SN")
            return
        status,result=mes_post("/station/maintenance-handovers/receive",{"stationCode":STATION_CODE,"sn":sn})
        if status!=200:
            error=result.get("error") or result
            code=error.get("code") or "NO_REPAIR_HANDOVER"
            self.status_var.set(f"拦截 / BLOCKED: {sn} · {code}")
            messagebox.showerror("拦截 / BLOCKED",f"{sn}\n{code}\n未找到发往维修站的有效交接单")
            return
        transfer=result;batch_id=str(transfer.get("batchId") or sn);ts=now_text()
        # Record the shared closed-loop fact when MES provides its command evidence.
        event_id = transfer.get("eventId") or transfer.get("ngEventId")
        if event_id and transfer.get("commandId") and transfer.get("mesDecisionId"):
            fact = apply_transition(ClosedLoopState.REPAIR_ORDERED, "RECEIVE_REPAIR", {
                "eventId": event_id, "commandId": transfer["commandId"],
                "mesDecisionId": transfer["mesDecisionId"], "domainCode": "MANUAL_LINE",
                "workOrderId": transfer.get("repairWorkOrderNo"), "repairWoId": transfer.get("repairWorkOrderNo"),
                "shipmentId": transfer.get("shipmentId"), "boxQr": transfer.get("boxQr") or transfer.get("stationQr"),
                "stationQr": transfer.get("stationQr") or transfer.get("boxQr"),
                "sns": transfer.get("sns") or [sn], "quantity": transfer.get("quantity") or 1,
            })
        else:
            fact = None
        with db_connect() as conn:
            conn.execute("INSERT OR REPLACE INTO motherboards(batch_id,source_station,status,received_at,updated_at) VALUES(?,?,?,?,?)",
                         (batch_id,transfer.get("sourceStationCode") or "MES","received",ts,ts))
            conn.execute("INSERT OR IGNORE INTO ng_migrations(migration_key,batch_id,sn,source_station,destination_station,status,migrated_at) VALUES(?,?,?,?,?,'received',?)",
                         (f"{batch_id}:{sn}:receipt",batch_id,sn,transfer.get("sourceStationCode") or "MES",STATION_CODE,ts))
            conn.execute("""INSERT INTO repair_work_orders(work_order_no,batch_id,ng_sn,source_station,received_at,repair_started_at,retest_history,status,operator,updated_at)
              VALUES(?,?,?,?,?,?,?,'REPAIR_IN_PROGRESS',?,?) ON CONFLICT(work_order_no) DO UPDATE SET
              received_at=excluded.received_at,repair_started_at=excluded.repair_started_at,retest_history=excluded.retest_history,status='REPAIR_IN_PROGRESS',updated_at=excluded.updated_at""",
            (transfer.get("repairWorkOrderNo"),batch_id,sn,transfer.get("sourceStationCode") or "MES",
               transfer.get("receivedAt") or ts,transfer.get("repairStartedAt") or ts,json.dumps(transfer.get("retestHistory") or [],ensure_ascii=False),OPERATOR,ts))
            if fact:
                conn.execute("""INSERT OR IGNORE INTO repair_event_history
                  (event_id,work_order_no,shipment_id,box_qr,station_qr,sns_json,quantity,state,fact_json,recorded_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?)""", (fact["eventId"], fact.get("repairWoId"), fact.get("shipmentId"),
                    fact.get("boxQr"), fact.get("stationQr"), json.dumps(fact.get("sns") or [], ensure_ascii=False),
                    fact.get("quantity"), fact["state"], json.dumps(fact, ensure_ascii=False), ts))
        self.status_var.set(f"维修交接已接收 / RECEIVED: {batch_id} · {sn}")
        self.refresh_table()

    def add_material(self):
        code=self.material_code_var.get().strip();name=self.material_name_var.get().strip()
        try: qty=float(self.material_qty_var.get())
        except ValueError: qty=0
        if not code or not name or qty<=0:
            messagebox.showwarning("更换物料","必须填写物料编码、名称和大于0的数量");return
        self.material_items.append({"materialCode":code,"materialName":name,"quantity":qty,"unit":"PCS"})
        self.no_material_var.set(False);self.material_code_var.set("");self.material_name_var.set("");self.material_qty_var.set("1")
        self.material_summary_var.set("；".join(f"{x['materialCode']} {x['materialName']} × {x['quantity']}" for x in self.material_items))

    def complete_work_order(self):
        selection=self.active_tree.selection()
        if len(selection)!=1:
            messagebox.showwarning("维修工单","请选择一张维修中的工单")
            return
        batch_id=str(self.active_tree.item(selection[0],"values")[0] or "")
        with db_connect() as conn:
            row=conn.execute("SELECT work_order_no FROM repair_work_orders WHERE batch_id=? AND status='REPAIR_IN_PROGRESS' ORDER BY received_at DESC LIMIT 1",(batch_id,)).fetchone()
        if not row:
            messagebox.showwarning("维修工单","本地没有该批次的维修中工单，请先扫码接收")
            return
        work_order_no=row["work_order_no"]
        method=self.repair_method_var.get().strip()
        if not self.repair_complete_var.get() or not method:
            messagebox.showwarning("维修完成","必须勾选维修完成并填写维修方法")
            return
        if not self.material_items and not self.no_material_var.get():
            messagebox.showwarning("维修物料","请登记更换物料，或明确勾选‘无物料更换’")
            return
        status,result=mes_post(f"/station/maintenance-work-orders/{urllib.parse.quote(work_order_no)}/complete",
                               {"completed":True,"repairMethod":method,"repairResult":"repaired","operator":OPERATOR,
                                "materialsConfirmed":True,"materials":self.material_items})
        if status!=200:
            messagebox.showerror("完成失败",json.dumps(result,ensure_ascii=False))
            return
        with db_connect() as conn:
            conn.execute("UPDATE repair_work_orders SET status='PENDING_QUALITY',repair_method=?,repair_result='repaired',repair_completed_at=?,updated_at=? WHERE work_order_no=?",
                          (method,now_text(),now_text(),work_order_no))
            wo=conn.execute("SELECT ng_sn FROM repair_work_orders WHERE work_order_no=?",(work_order_no,)).fetchone()
            for item in self.material_items:
                conn.execute("""INSERT INTO repair_material_usage
                  (work_order_no,ng_sn,material_code,material_name,quantity,unit,operator,recorded_at,mes_synced)
                  VALUES(?,?,?,?,?,?,?,?,1)""",(work_order_no,wo["ng_sn"] if wo else None,item["materialCode"],
                    item["materialName"],item["quantity"],item.get("unit","PCS"),OPERATOR,now_text()))
        self.repair_complete_var.set(False);self.repair_method_var.set("")
        self.material_items=[];self.no_material_var.set(False);self.material_summary_var.set("尚未登记物料")
        self.status_var.set(f"维修完成，等待品质和线长批准 / {work_order_no}")
        self.refresh_table()

    def _block(self, sn, kind, source, detail=None):
        ts = now_text()
        with db_connect() as conn:
            if kind == "DUPLICATE_SN":
                conn.execute("INSERT INTO duplicate_events(sn,source,detected_at) VALUES(?,?,?)", (sn, source, ts))
                text = f"发现重复编码，禁止离开本站\n{sn}"
            else:
                conn.execute("INSERT INTO ng_records(sn,source,defect_code,detected_at) VALUES(?,?,?,?)",
                             (sn, source, "MES_NG", ts))
                text = f"发现不良品，禁止不良品离开本站\n{sn}"
        result = "FAIL"
        event_type = "duplicate" if kind == "DUPLICATE_SN" else "ng_history"
        if not self.mes.push_event(sn, event_type, result, operator=OPERATOR):
            self._queue(event_type, sn, result, detail or {})
        post_pda(kind, {"sn": sn, "source": source, "stationCode": STATION_CODE})
        self.status_var.set(text.replace("\n", "  "))
        messagebox.showerror("拦截 / BLOCKED", text)
        self.refresh_table()

    def _queue(self, event_type, sn, result, payload):
        with db_connect() as conn:
            conn.execute("INSERT INTO mes_sync_queue(event_type,sn,result,payload,created_at) VALUES(?,?,?,?,?)",
                         (event_type, sn, result, json.dumps(payload, ensure_ascii=False), now_text()))

    def _sync_loop(self):
        while True:
            try:
                with db_connect() as conn:
                    rows = conn.execute("SELECT * FROM mes_sync_queue ORDER BY id LIMIT 20").fetchall()
                for row in rows:
                    if self.mes.push_event(row["sn"], row["event_type"], row["result"], operator=OPERATOR):
                        with db_connect() as conn:
                            conn.execute("DELETE FROM mes_sync_queue WHERE id=?", (row["id"],))
                    else:
                        with db_connect() as conn:
                            conn.execute("UPDATE mes_sync_queue SET attempts=attempts+1 WHERE id=?", (row["id"],))
                        break
            except Exception:
                pass
            time.sleep(10)

    def _heartbeat_loop(self):
        while True:
            post_pda("AGENT_HEARTBEAT", {"agent": "repair_quality_station", "status": "running",
                                         "stationIp": STATION_IP,
                                         "timestamp": int(time.time() * 1000)})
            time.sleep(5)

    def refresh_table(self):
        self.wo_tree.delete(*self.wo_tree.get_children())
        with db_connect() as conn:
            work_orders=conn.execute("SELECT * FROM repair_work_orders ORDER BY updated_at DESC LIMIT 100").fetchall()
        for row in work_orders:
            try:
                history=json.loads(row["retest_history"] or "[]")
                retest_text="; ".join(f"#{x.get('attemptNo')} {x.get('executionStation') or x.get('originStation')} {x.get('result') or ''}" for x in history)
            except Exception:
                retest_text=""
            self.wo_tree.insert("","end",values=(row["work_order_no"],row["batch_id"],row["ng_sn"],row["source_station"],row["status"],retest_text))
        self.incoming_tree.delete(*self.incoming_tree.get_children())
        try:
            url=f"{MES_API}/station/route-requests?destinationStation={STATION_CODE}&status=WAITING_RECEIPT"
            with urllib.request.urlopen(url,timeout=4) as response:requests=json.loads(response.read().decode("utf-8")).get("items",[])
            for row in requests:
                board=row.get("motherboard") or {};members=board.get("subBoards") or []
                bill=f"{row.get('billNo') or row.get('requestId')} / {row.get('repairWorkOrderNo') or '-'}"
                self.incoming_tree.insert("","end",values=(bill,row.get("batchId"),row.get("sourceStation"),len(members),row.get("submittedAt"),row.get("status")))
        except Exception:pass
        self.active_tree.delete(*self.active_tree.get_children())
        try:
            url=f"{MES_API}/station/route-requests?destinationStation={STATION_CODE}&status=REPAIR_IN_PROGRESS"
            with urllib.request.urlopen(url,timeout=4) as response:
                active=json.loads(response.read().decode("utf-8")).get("items",[])
            for row in active:
                if row.get("repairWorkOrderNo"):
                    board=row.get("motherboard") or {};ng_sn=board.get("mainSn") or row.get("batchId")
                    with db_connect() as conn:
                        conn.execute("""INSERT INTO repair_work_orders(work_order_no,handover_bill_no,batch_id,ng_sn,source_station,submitted_at,received_at,repair_started_at,status,updated_at)
                          VALUES(?,?,?,?,?,?,?,?, 'REPAIR_IN_PROGRESS',?) ON CONFLICT(work_order_no) DO UPDATE SET
                          status='REPAIR_IN_PROGRESS',received_at=excluded.received_at,repair_started_at=excluded.repair_started_at,updated_at=excluded.updated_at""",
                          (row.get("repairWorkOrderNo"),row.get("billNo"),row.get("batchId"),ng_sn,row.get("sourceStation"),
                           row.get("submittedAt"),row.get("processedAt"),row.get("repairStartedAt"),now_text()))
                seconds=int(row.get("repairElapsedSeconds") or 0)
                elapsed=f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"
                alarm="超时报警 / TIMEOUT" if row.get("repairAlarmAt") else "维修中 / REPAIRING"
                self.active_tree.insert("","end",values=(row.get("batchId"),row.get("sourceStation"),
                    row.get("repairStartedAt"),elapsed,alarm))
        except Exception:pass
        for item in self.tree.get_children(): self.tree.delete(item)
        with db_connect() as conn:
            rows = conn.execute("SELECT last_seen AS t,sn,result,'scan' AS src,mes_synced FROM sn_records ORDER BY id DESC LIMIT 100").fetchall()
        for row in rows:
            self.tree.insert("", "end", values=(row["t"], row["sn"], row["result"], row["src"], "MES" if row["mes_synced"] else "QUEUE"))

    def _auto_refresh(self):
        if self.root.winfo_exists():
            self._apply_ng_releases()
            self.refresh_table()
            self.root.after(5000, self._auto_refresh)

    def _apply_ng_releases(self):
        try:
            url=f"{MES_API}/station/ng-releases?stationCode={urllib.parse.quote(STATION_CODE)}"
            with urllib.request.urlopen(url,timeout=4) as response:
                releases=json.loads(response.read().decode("utf-8")).get("items",[])
            for release in releases:
                sn=str(release.get("sn") or "").strip().upper();batch_id=str(release.get("batchId") or "")
                if not sn: continue
                with db_connect() as conn:
                    removed=conn.execute("DELETE FROM ng_records WHERE UPPER(sn)=?",(sn,)).rowcount
                    conn.execute("UPDATE motherboard_members SET repair_status='revived',updated_at=? WHERE UPPER(sn)=? OR batch_id=?",(now_text(),sn,batch_id))
                    conn.execute("UPDATE ng_migrations SET status='completed',completed_at=? WHERE UPPER(sn)=? OR batch_id=?",(now_text(),sn,batch_id))
                    conn.execute("UPDATE motherboards SET status='returned_to_origin',updated_at=? WHERE batch_id=?",(now_text(),batch_id))
                mes_post(f"/station/ng-releases/{release.get('releaseId')}/ack",{"stationCode":STATION_CODE,"localRowsRemoved":removed})
        except Exception:
            pass

    def close(self):
        self.mes.stop()
        self.root.destroy()


if __name__ == "__main__":
    init_db()
    app_root = tk.Tk()
    RepairStation(app_root)
    app_root.mainloop()
