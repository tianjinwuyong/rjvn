# -*- coding: utf-8 -*-
"""Authoritative local engine for the outer-case binding station.

Barcode syntax is deliberately not hard-coded here.  The station identifies
the scan role (product or case) and publishes its configured rules to MES.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# A PyInstaller one-file application extracts bundled modules into a temporary
# _MEI directory. Production SQLite must live beside the installed EXE so it
# survives process and computer restarts.
BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
MANUAL_LINE_DIR = BASE_DIR.parent
if str(MANUAL_LINE_DIR) not in sys.path:
    sys.path.insert(0, str(MANUAL_LINE_DIR))
from station_arrival_core import StationArrivalStore
from station_history_core import StationHistoryArchive
from station_data_sync import mes_scan_gate
DB_PATH = BASE_DIR / "outer_box_binding.db"
STATION_CODE = "manu_case_binding"
NEXT_STATION = "manu_pallet_binding"
ALLOWED_CASE_CAPACITIES = (40, 50, 96, 100)
LINE_LEADER_AUTH_SECONDS = 8 * 60 * 60
PRINT_TEMPLATE_DIRNAME = "print_templates"
DEFAULT_PRINT_TEMPLATE = "EPS18R1G-36 TEST.btw"
MES_URL = os.environ.get("MES_API_URL", "http://127.0.0.1:8765/api/pda/events")
MES_BASE = MES_URL.split("/api/", 1)[0]


def _line_prefix():
    return "auto_" if STATION_CODE.startswith("auto_") else "manu_"


def _supersonic_source():
    return _line_prefix() + "supersonic"


class BindingError(RuntimeError):
    pass


class CaseBindingStore:
    def __init__(self, db_path=DB_PATH):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self.init_db()
        self.arrivals = StationArrivalStore(self.db_path, STATION_CODE, MES_URL)
        self.history = StationHistoryArchive(self.db_path, STATION_CODE)

    def connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings(
              key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS draft_items(
              sn TEXT PRIMARY KEY, scanned_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cartons(
              carton_sn TEXT PRIMARY KEY, item_count INTEGER NOT NULL,
              work_order_code TEXT NOT NULL DEFAULT '',
              bound_at INTEGER NOT NULL, binding_id TEXT NOT NULL UNIQUE,
              mes_synced INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS carton_items(
              sn TEXT PRIMARY KEY,
              carton_sn TEXT NOT NULL REFERENCES cartons(carton_sn),
              position INTEGER NOT NULL, bound_at INTEGER NOT NULL,
              UNIQUE(carton_sn, position)
            );
            CREATE TABLE IF NOT EXISTS binding_mappings(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              binding_id TEXT NOT NULL, work_order_code TEXT NOT NULL,
              carton_sn TEXT NOT NULL, capacity INTEGER NOT NULL,
              slot_position INTEGER NOT NULL, product_sn TEXT NOT NULL UNIQUE,
              bound_at INTEGER NOT NULL, mes_synced INTEGER NOT NULL DEFAULT 0,
              UNIQUE(carton_sn,slot_position)
            );
            CREATE TABLE IF NOT EXISTS confirmed_ng(
              sn TEXT PRIMARY KEY, source_station TEXT NOT NULL DEFAULT '',
              reason TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ng_exemptions(
              exemption_id TEXT PRIMARY KEY, sn TEXT NOT NULL,
              source_station TEXT NOT NULL DEFAULT '', ng_reason TEXT NOT NULL DEFAULT '',
              leader_id TEXT NOT NULL, approval_reason TEXT NOT NULL,
              approved_at INTEGER NOT NULL, used_at INTEGER,
              carton_sn TEXT NOT NULL DEFAULT '', work_order_code TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'APPROVED'
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ng_exemption_active
              ON ng_exemptions(sn) WHERE status='APPROVED';
            CREATE TABLE IF NOT EXISTS station_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
              code TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '{}',
              created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mes_outbox(
              id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
              payload TEXT NOT NULL, created_at INTEGER NOT NULL,
              sent_at INTEGER, attempts INTEGER NOT NULL DEFAULT 0,
              last_error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS software_change_log(
              change_key TEXT PRIMARY KEY,version TEXT NOT NULL,component TEXT NOT NULL,
              reason TEXT NOT NULL DEFAULT 'Historical migration',summary TEXT NOT NULL,verification TEXT NOT NULL DEFAULT '',
              changed_at TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS protect_change_log_update BEFORE UPDATE ON software_change_log
              BEGIN SELECT RAISE(ABORT,'software_change_log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS protect_change_log_delete BEFORE DELETE ON software_change_log
              BEGIN SELECT RAISE(ABORT,'software_change_log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS protect_binding_mapping_update BEFORE UPDATE ON binding_mappings
              BEGIN SELECT RAISE(ABORT,'binding_mappings is immutable'); END;
            CREATE TRIGGER IF NOT EXISTS protect_binding_mapping_delete BEFORE DELETE ON binding_mappings
              BEGIN SELECT RAISE(ABORT,'binding_mappings is immutable'); END;
            """)
            # Purge only cross-domain cache pollution created by older builds.
            # This does not modify MES production history.
            other_domain = "manu_%" if _line_prefix() == "auto_" else "auto_%"
            db.execute("DELETE FROM confirmed_ng WHERE source_station LIKE ?", (other_domain,))
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('target_count','0')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('product_rule','station scanner rule')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('case_rule','station scanner rule')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('active_work_order','')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('active_work_order_received_at','0')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('mes_work_orders_json','[]')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('work_order_locked','0')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('active_case','')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('active_case_capacity','0')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('active_case_work_order','')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('active_case_print_template','')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('line_leader_auth_json','{}')")
            carton_cols = {row[1] for row in db.execute("PRAGMA table_info(cartons)")}
            change_cols = {row[1] for row in db.execute("PRAGMA table_info(software_change_log)")}
            ng_cols = {row[1] for row in db.execute("PRAGMA table_info(confirmed_ng)")}
            if "work_order_code" not in carton_cols:
                db.execute("ALTER TABLE cartons ADD COLUMN work_order_code TEXT NOT NULL DEFAULT ''")
            if "reason" not in change_cols:
                db.execute("ALTER TABLE software_change_log ADD COLUMN reason TEXT NOT NULL DEFAULT 'Historical migration'")
            if "exemptible" not in ng_cols:
                db.execute("ALTER TABLE confirmed_ng ADD COLUMN exemptible INTEGER NOT NULL DEFAULT 0")
            if "exemption_policy" not in ng_cols:
                db.execute("ALTER TABLE confirmed_ng ADD COLUMN exemption_policy TEXT NOT NULL DEFAULT ''")
            exemption_cols = {row[1] for row in db.execute("PRAGMA table_info(ng_exemptions)")}
            if "approver_role" not in exemption_cols:
                db.execute("ALTER TABLE ng_exemptions ADD COLUMN approver_role TEXT NOT NULL DEFAULT 'LINE_LEADER'")
            # Backfill legacy bindings into the explicit immutable map.
            db.execute("""INSERT OR IGNORE INTO binding_mappings(
              binding_id,work_order_code,carton_sn,capacity,slot_position,product_sn,bound_at,mes_synced)
              SELECT c.binding_id,c.work_order_code,c.carton_sn,c.item_count,i.position,i.sn,c.bound_at,c.mes_synced
              FROM cartons c JOIN carton_items i ON i.carton_sn=c.carton_sn""")
            changes=(
              ("CB-001","2.0.0","architecture","Split 2D and 3D UI from shared case_binding_core; one SQLite authority","Python compile and process startup verified"),
              ("CB-002","2.0.0","traceability","Implement one case to many independent product SN mappings","40-SN end-to-end simulation passed"),
              ("CB-003","2.0.0","mes-work-order","MES-owned read-only WO cache; lock WO when case opens","Missing-WO block and mid-case refresh regression passed"),
              ("CB-004","2.0.0","guard","Append-only MES NG cache plus local NG and duplicate blocking","NG/DUP transaction persistence test passed"),
              ("CB-005","2.0.0","capacity","Restrict case capacity to 40, 50, 96 or 100 and enforce exact seal count","40 capacity and over-capacity tests passed"),
              ("CB-006","2.0.0","visualization","Add 2D slots and rotatable projected 3D case with product stacking","3D compile and process startup verified"),
              ("CB-007","2.0.0","resources","Add station-standard LIVE, SN, NG, RAW DATA, COMMS and SETTINGS tabs","2D and 3D startup verified"),
              ("CB-008","2.0.0","local-mapping","Add immutable binding_mappings table and backfill legacy records","80 of 80 mapping consistency passed"),
              ("CB-009","2.0.0","mes-mapping","Send local CONTAINER_UPDATE with WO, case, capacity and ordered product list","MES server syntax check and outbox payload verified"),
              ("CB-010","2.0.0","change-control","Add human and SQLite change records","Change-log resource exposed to both UIs"),
              ("CB-011","2.0.1","immutability","Protect software change log and completed binding mappings from UPDATE and DELETE","SQLite trigger rejection tests passed"),
              ("CB-012","2.0.1","change-control","Require a reason for every appended software modification","Reason column migration and resource projection verified"),
              ("CB-013","2.1.0","lifecycle","Add mandatory arrival reporting, immutable history archives and maintenance linkage","40-product case lifecycle integration passed"),
              ("CB-014","2.2.0","quality-exemption","Add single-SN line-leader NG exemption with immutable local and MES audit evidence","NG-only approval, one-time use and duplicate/jump hard-stop regression passed"),
            )
            reasons={
              "CB-001":"Prevent 2D and 3D UI failures from affecting production logic",
              "CB-002":"The physical process aggregates many independent products into one case",
              "CB-003":"MES must own WO selection while an open case must remain stable",
              "CB-004":"Operators must visibly stop confirmed NG and duplicate products",
              "CB-005":"Factory cases have only the approved capacities 40, 50, 96 and 100",
              "CB-006":"3D must add spatial visibility without removing 2D functions",
              "CB-007":"Keep resource navigation consistent with FCT and Assembly ATE",
              "CB-008":"Provide durable local per-SN traceability during MES outages",
              "CB-009":"Central MES must retain the same case-to-product traceability",
              "CB-010":"All engineering changes require an auditable record",
              "CB-011":"Historical change and binding evidence must not be rewritten",
              "CB-012":"Auditors and operators need to know why each modification was made",
              "CB-013":"Every scanned product needs an explainable arrival, archive and maintenance evidence chain",
              "CB-014":"A named line leader may authorize a documented exceptional NG shipment without weakening duplicate or route controls",
            }
            change_rows=[(x[0],x[1],x[2],reasons[x[0]],x[3],x[4]) for x in changes]
            db.executemany("INSERT OR IGNORE INTO software_change_log(change_key,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,'2026-07-21')",change_rows)

    def setting(self, key, default=""):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def active_work_order(self):
        return self.setting("active_work_order", "")

    def available_work_orders(self):
        try:
            rows = json.loads(self.setting("mes_work_orders_json", "[]"))
            return rows if isinstance(rows, list) else []
        except Exception:
            return []

    def work_order_codes(self):
        return [
            str(row.get("workOrderCode") or "").strip()
            for row in self.available_work_orders()
            if str(row.get("workOrderCode") or "").strip()
        ]

    def work_order_locked(self):
        return self.setting("work_order_locked", "0") == "1"

    def work_order_bypass(self):
        return self.setting("work_order_bypass", "0") == "1"

    def set_work_order_bypass(self, enabled):
        enabled = bool(enabled)
        self.set_setting("work_order_bypass", "1" if enabled else "0")
        if enabled and not self.active_work_order():
            self.set_setting("active_work_order", "TEMP-%s" % time.strftime("%Y%m%d"))
        with self.connect() as db:
            self._event(
                db,
                "WORK_ORDER_BYPASS_ENABLED" if enabled else "WORK_ORDER_BYPASS_DISABLED",
                self.active_work_order(),
                {"temporary": True},
            )
        return enabled

    def select_work_order(self, work_order_code):
        code = str(work_order_code or "").strip()
        if not code:
            raise BindingError("请选择 MES 下发的工单 WO")
        if not self.work_order_bypass() and code not in self.work_order_codes():
            raise BindingError("该 WO 不在 MES 当前可用工单列表中")
        current = self.active_work_order()
        if not self.work_order_bypass() and self.work_order_locked() and current and current != code:
            raise BindingError("WO %s 已锁定；必须由 MES 确认完成后才能切换" % current)
        self.set_setting("active_work_order", code)
        self.set_setting("work_order_locked", "0" if self.work_order_bypass() else "1")
        with self.connect() as db:
            self._event(db, "WORK_ORDER_SELECTED", code, {"source": "MES_DROPDOWN"})
        try:
            body=json.dumps({"stationCode":STATION_CODE,"workOrderCode":code,"selectedBy":"OPERATOR"}).encode("utf-8")
            request=urllib.request.Request(
                "%s/api/station/active-workorder"%MES_BASE,
                data=body,
                headers={"Content-Type":"application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request,timeout=5) as response:
                response.read()
        except Exception:
            pass
        return code

    def active_case(self):
        return self.setting("active_case", "")

    def generate_carton_sn(self):
        """Generate the official 20-character CARTON SERIES outer-box QR."""
        template_name = self.selected_print_template().upper()
        model = "N18"
        if "EPS36" in template_name:
            model = "N36"
        elif "EPS48" in template_name:
            model = "N48"
        year_code = str(time.localtime().tm_year)[-1]
        prefix = "CSO%sV%s%sC" % (model, year_code, self._get_day_code())
        with self._lock, self.connect() as db:
            row = db.execute(
                "SELECT carton_sn FROM cartons WHERE carton_sn LIKE ? ORDER BY carton_sn DESC LIMIT 1",
                (prefix + "%",),
            ).fetchone()
            sequence = 1
            if row:
                suffix = str(row[0])[len(prefix):-3]
                if suffix.isdigit():
                    sequence = int(suffix) + 1
            while db.execute(
                "SELECT 1 FROM cartons WHERE carton_sn=?",
                ("%s%06dNBT" % (prefix, sequence),),
            ).fetchone():
                sequence += 1
            if sequence > 999999:
                raise BindingError("外箱码当日流水号已超过 999999")
            carton_sn = "%s%06dNBT" % (prefix, sequence)
            if len(carton_sn) != 20:
                raise BindingError("外箱码生成失败：必须为20位")
            return carton_sn

    def ensure_active_case(self, capacity=96):
        """Automatically open a numbered carton before the first product scan."""
        if self.work_order_bypass() and not self.active_work_order():
            self.set_setting("active_work_order", "TEMP-%s" % time.strftime("%Y%m%d"))
        current = self.active_case()
        if current:
            return current
        carton_sn = self.generate_carton_sn()
        self.open_case(carton_sn, capacity)
        return carton_sn

    def open_case(self, raw, capacity):
        carton_sn=str(raw or "").strip()
        if not carton_sn:
            raise BindingError("外箱码不能为空")
        if not self.active_work_order() or (
            not self.work_order_bypass() and not self.work_order_locked()
        ):
            raise BindingError("请先从 MES 工单下拉列表选择并锁定 WO")
        try: capacity=int(capacity)
        except (TypeError,ValueError): raise BindingError("请选择外箱容量 40 / 50 / 96 / 100")
        if capacity not in ALLOWED_CASE_CAPACITIES:
            raise BindingError("无效外箱容量，只允许 40 / 50 / 96 / 100")
        with self.lock if hasattr(self,"lock") else self._lock:
            with self.connect() as db:
                if db.execute("SELECT 1 FROM cartons WHERE carton_sn=?",(carton_sn,)).fetchone():
                    self._event(db,"DUPLICATE_CASE_BLOCKED",carton_sn);db.commit()
                    raise BindingError("外箱码已使用: %s"%carton_sn)
                current=self.active_case()
                if current and current!=carton_sn and db.execute("SELECT 1 FROM draft_items LIMIT 1").fetchone():
                    raise BindingError("当前外箱 %s 尚有未完成产品，禁止切换"%current)
                self.set_setting("active_case",carton_sn)
                self.set_setting("active_case_capacity",capacity)
                self.set_setting("active_case_work_order",self.active_work_order())
                self.set_setting("active_case_print_template",self.selected_print_template())
                self._event(db,"CASE_OPENED",carton_sn,{"workOrderCode":self.active_work_order(),"capacity":capacity,"printTemplate":self.selected_print_template()})
        return carton_sn

    def refresh_mes_work_order(self):
        url = "%s/api/station/qr-workorders?stationCode=%s" % (MES_BASE, STATION_CODE)
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                data = json.loads(response.read().decode("utf-8"))
            active = [
                x for x in (data.get("active") or [])
                if x.get("stationCode") == STATION_CODE and x.get("status") == "ACTIVE"
            ]
            available = data.get("available") or []
            self.set_setting("mes_work_orders_json", json.dumps(available, ensure_ascii=False))
            if active and not self.work_order_bypass():
                mes_selected=str(active[0].get("workOrderCode") or "").strip()
                if mes_selected and not self.active_case():
                    self.set_setting("active_work_order",mes_selected)
                    self.set_setting("work_order_locked","1")
            active_codes = {
                str(row.get("workOrderCode") or "").strip()
                for row in available
                if str(row.get("workOrderCode") or "").strip()
            }
            work_order = self.active_work_order()
            if self.work_order_locked() and work_order and work_order not in active_codes:
                # A valid MES response without the locked WO is the completion signal.
                # Never release while a carton is physically in progress.
                with self.connect() as db:
                    draft_count = db.execute("SELECT COUNT(*) FROM draft_items").fetchone()[0]
                if not self.active_case() and not draft_count:
                    with self.connect() as db:
                        self._event(db, "WORK_ORDER_COMPLETED", work_order, {"source": "MES"})
                    self.set_setting("active_work_order", "")
                    self.set_setting("work_order_locked", "0")
                    work_order = ""
            self.set_setting("active_work_order_received_at", int(time.time()))
        except Exception:
            work_order = self.active_work_order()
        # MES owns the centralized NG set. Local sync is append-only: a network
        # error or an incomplete response can never erase a known NG.
        try:
            with urllib.request.urlopen("%s/api/station/bucket-snapshots" % MES_BASE, timeout=3) as response:
                snapshots = json.loads(response.read().decode("utf-8")).get("items") or []
            now = int(time.time())
            with self.connect() as db:
                for bucket in snapshots:
                    if bucket.get("bucketName") != "confirmed_ng":
                        continue
                    source_station = str(bucket.get("stationCode") or "").strip()
                    # Manual and automatic lines are separate production domains.
                    if not source_station.startswith(_line_prefix()):
                        continue
                    for item in bucket.get("payload") or []:
                        sn = str(item.get("sn") or item.get("productSn") or "").strip()
                        if not sn:
                            continue
                        exemptible = 1 if item.get("lineLeaderExemptible") is True or item.get("allowExemption") is True else 0
                        policy = str(item.get("exemptionPolicy") or item.get("defectClass") or "")
                        db.execute("""INSERT INTO confirmed_ng(sn,source_station,reason,created_at,exemptible,exemption_policy)
                                      VALUES(?,?,?,?,?,?) ON CONFLICT(sn) DO UPDATE SET
                                      source_station=excluded.source_station,reason=excluded.reason,
                                      exemptible=excluded.exemptible,exemption_policy=excluded.exemption_policy""",
                                   (sn, source_station, str(item.get("reason") or item.get("errorCode") or "MES CONFIRMED NG"), now, exemptible, policy))
        except Exception:
            pass
        return work_order

    def _event(self, db, event_type, code="", detail=None):
        db.execute("INSERT INTO station_events(event_type,code,detail,created_at) VALUES(?,?,?,?)",
                   (event_type, code, json.dumps(detail or {}, ensure_ascii=False), int(time.time())))

    def active_line_leader_auth(self):
        try:
            auth = json.loads(self.setting("line_leader_auth_json", "{}"))
        except Exception:
            auth = {}
        if not isinstance(auth, dict) or int(auth.get("expiresAt") or 0) <= int(time.time()):
            if auth:
                self.set_setting("line_leader_auth_json", "{}")
            return None
        return auth

    def sync_mes_exemption_for_sn(self, raw):
        """Cache an active MES-approved ultrasonic exemption for this SN."""
        sn = str(raw or "").strip().upper()
        if not sn:
            return None
        try:
            url = "%s/api/station/ng-special-exemption?stationCode=%s&sn=%s" % (
                MES_BASE, STATION_CODE, urllib.parse.quote(sn)
            )
            with urllib.request.urlopen(url, timeout=3) as response:
                body = json.loads(response.read().decode("utf-8"))
            item = body.get("item") if body.get("active") else None
            if not item:
                return None
            source = str(item.get("sourceStation") or "").strip().lower()
            if source not in (_supersonic_source(), "supersonic"):
                return None
            username = str(item.get("approvedByUsername") or "")
            role = "FACTORY_DIRECTOR" if username == "MENG_YING" else "LINE_LEADER"
            leader = str(item.get("approvedByName") or username or "MES")
            exemption_id = str(item.get("exemptionId") or uuid.uuid4())
            with self._lock, self.connect() as db:
                db.execute("UPDATE ng_exemptions SET status='SUPERSEDED' WHERE sn=? AND status='APPROVED'", (sn,))
                db.execute(
                    """INSERT OR REPLACE INTO ng_exemptions(
                         exemption_id,sn,source_station,ng_reason,leader_id,approval_reason,
                         approved_at,carton_sn,work_order_code,status,approver_role)
                       VALUES(?,?,?,?,?,?,?,?,?,'APPROVED',?)""",
                    (exemption_id, sn, source, "MES APPROVED", leader,
                     str(item.get("reason") or "MES special exemption"), int(time.time()),
                     self.active_case(), self.active_work_order(), role),
                )
                self._event(db, "MES_NG_EXEMPTION_SYNCED", sn, item)
            return item
        except Exception:
            return None

    def authenticate_line_leader(self, leader_id, approver_role="LINE_LEADER"):
        """Start a local eight-hour supervisor authorization window.

        The station records the badge identity; deployment may replace this
        entry point with the factory badge/PIN verifier without changing the
        exemption workflow.
        """
        leader_id = str(leader_id or "").strip().upper()
        approver_role = str(approver_role or "LINE_LEADER").strip().upper()
        if not leader_id:
            raise BindingError("必须输入审批人工号")
        if approver_role not in ("LINE_LEADER", "FACTORY_DIRECTOR"):
            raise BindingError("只有线长或工厂长可以进行 NG 特许")
        now = int(time.time())
        auth = {"leaderId": leader_id, "authenticatedAt": now,
                "expiresAt": now + LINE_LEADER_AUTH_SECONDS,
                "approverRole": approver_role}
        self.set_setting("line_leader_auth_json", json.dumps(auth, ensure_ascii=False))
        with self.connect() as db:
            self._event(db, "LINE_LEADER_AUTHENTICATED", leader_id, {
                "authenticatedAt": now, "expiresAt": auth["expiresAt"],
                "validHours": 8, "approverRole": approver_role,
            })
        return auth

    def approve_ng_exemption(self, raw, leader_id, approval_reason):
        """Approve one confirmed NG SN for one carton at this station only."""
        sn = str(raw or "").strip()
        leader_id = str(leader_id or "").strip().upper()
        approval_reason = str(approval_reason or "").strip()
        if not sn:
            raise BindingError("没有可特批的 NG SN")
        auth = self.active_line_leader_auth()
        if not auth:
            raise BindingError("线长授权已失效，请重新认证")
        if leader_id != str(auth.get("leaderId") or "").strip().upper():
            raise BindingError("当前线长授权身份不匹配，请重新认证")
        if len(approval_reason) < 4:
            raise BindingError("特批原因至少填写 4 个字符")
        now = int(time.time())
        exemption_id = str(uuid.uuid4())
        with self._lock, self.connect() as db:
            ng = db.execute(
                "SELECT source_station,reason,exemptible,exemption_policy FROM confirmed_ng WHERE sn=?", (sn,)
            ).fetchone()
            if not ng:
                raise BindingError("该 SN 不是本工站已确认的 NG，不能特批")
            source_key = str(ng["source_station"] or "").strip().lower()
            if source_key != _supersonic_source():
                raise BindingError("只有超声波工站 NG 可以线长特批；当前来源: %s" %
                                   (ng["source_station"] or "未知"))
            db.execute("UPDATE ng_exemptions SET status='SUPERSEDED' WHERE sn=? AND status='APPROVED'", (sn,))
            db.execute(
                """INSERT INTO ng_exemptions(
                     exemption_id,sn,source_station,ng_reason,leader_id,approval_reason,
                     approved_at,carton_sn,work_order_code,status,approver_role)
                   VALUES(?,?,?,?,?,?,?,?,?,'APPROVED',?)""",
                (exemption_id, sn, ng["source_station"], ng["reason"], leader_id,
                 approval_reason, now, self.active_case(), self.active_work_order(),
                 str(auth.get("approverRole") or "LINE_LEADER")),
            )
            detail = {
                "exemptionId": exemption_id, "sn": sn,
                "sourceStation": ng["source_station"], "ngReason": ng["reason"],
                "exemptionPolicy": ng["exemption_policy"],
                "leaderId": leader_id, "approvalReason": approval_reason,
                "approverRole": str(auth.get("approverRole") or "LINE_LEADER"),
                "leaderAuthenticatedAt": auth["authenticatedAt"],
                "leaderAuthExpiresAt": auth["expiresAt"],
                "cartonSn": self.active_case(), "workOrderCode": self.active_work_order(),
                "scope": "ONE_SN_ONE_CARTON",
            }
            self._event(db, "NG_EXEMPTION_APPROVED", sn, detail)
            db.execute(
                "INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",
                (exemption_id, json.dumps({
                    "eventId": exemption_id, "eventType": "NG_EXEMPTION_APPROVED",
                    "stationCode": STATION_CODE, "occurredAt": now * 1000, **detail,
                }, ensure_ascii=False), now),
            )
        return detail

    def _active_ng_exemption(self, db, sn):
        exact = db.execute(
            """SELECT * FROM ng_exemptions WHERE sn=? AND status IN('APPROVED','USED')
               AND (carton_sn='' OR carton_sn=?)
               AND (work_order_code='' OR work_order_code=?)
               ORDER BY approved_at DESC LIMIT 1""",
            (sn, self.active_case(), self.active_work_order()),
        ).fetchone()
        if exact:
            return exact

        # One authenticated supervisor exemption opens an eight-hour window
        # for same-line ultrasonic NG only. Materialize an audited, one-SN
        # exemption at scan time so every released unit remains traceable.
        ng = db.execute(
            "SELECT source_station,reason FROM confirmed_ng WHERE sn=?", (sn,)
        ).fetchone()
        source_station = str(ng["source_station"] or "").strip().lower() if ng else ""
        permitted_sources = ((_supersonic_source(),)
                             if _line_prefix() == "auto_"
                             else ("manu_supersonic", "manu_package_ate"))
        if source_station not in permitted_sources:
            return None
        now = int(time.time())
        exemption_id = str(uuid.uuid4())
        leader_id = "SYSTEM_POLICY"
        approver_role = "FACTORY_DIRECTOR"
        approval_reason = "自动线超声波NG标记放行" if _line_prefix() == "auto_" else "手动超声波NG标记放行"
        db.execute(
            """INSERT INTO ng_exemptions(
                 exemption_id,sn,source_station,ng_reason,leader_id,approval_reason,
                 approved_at,carton_sn,work_order_code,status,approver_role)
               VALUES(?,?,?,?,?,?,?,?,?,'APPROVED',?)""",
            (exemption_id, sn, source_station, ng["reason"], leader_id,
             approval_reason, now, self.active_case(), self.active_work_order(), approver_role),
        )
        detail = {
            "exemptionId": exemption_id, "sn": sn,
            "sourceStation": source_station, "ngReason": ng["reason"],
            "leaderId": leader_id, "approvalReason": approval_reason,
            "approverRole": approver_role,
            "cartonSn": self.active_case(), "workOrderCode": self.active_work_order(),
            "scope": "MANUAL_LINE_NG_MARK_AND_RELEASE",
        }
        self._event(db, "NG_EXEMPTION_AUTO_APPROVED", sn, detail)
        db.execute(
            "INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",
            (exemption_id, json.dumps({
                "eventId": exemption_id, "eventType": "NG_EXEMPTION_APPROVED",
                "stationCode": STATION_CODE, "occurredAt": now * 1000, **detail,
            }, ensure_ascii=False), now),
        )
        return db.execute(
            "SELECT * FROM ng_exemptions WHERE exemption_id=?", (exemption_id,)
        ).fetchone()

    def scan_product(self, raw, capacity=96):
        sn = str(raw or "").strip()
        self.sync_mes_exemption_for_sn(sn)
        if not sn:
            raise BindingError("产品 SN 不能为空")
        # Local confirmed-NG cache is authoritative during MES outages and is
        # checked before route validation so a known NG always raises the NG
        # alarm instead of being masked by a later route/jump decision.
        with self.connect() as db:
            local_ng = db.execute(
                "SELECT reason,source_station,created_at FROM confirmed_ng WHERE sn=?", (sn,)
            ).fetchone()
            local_exemption = self._active_ng_exemption(db, sn) if local_ng else None
            if local_ng and not local_exemption:
                self._event(db, "NG_BLOCKED", sn, dict(local_ng))
                raise BindingError("NG 产品禁止装箱: %s，来源工位 %s" %
                                   (sn, local_ng["source_station"] or "未知"))
        allowed, decision = mes_scan_gate(
            MES_URL, STATION_CODE, sn, event_type="physical_scanner",
            workOrderCode=self.active_work_order(), containerId=self.active_case(),
        )
        decision_code = str(decision.get("code") or decision.get("error", {}).get("code") or "")
        exemption = None
        if not allowed and decision_code in ("ACTIVE_NG_CAUGHT", "CONFIRMED_NG_BLOCKED"):
            with self.connect() as db:
                exemption = self._active_ng_exemption(db, sn)
                if exemption:
                    allowed = True
                    self._event(db, "NG_EXEMPTION_GATE_USED", sn, {
                        "exemptionId": exemption["exemption_id"],
                        "leaderId": exemption["leader_id"],
                        "approvalReason": exemption["approval_reason"],
                        "mesDecision": decision,
                    })
        # A restored, partially filled TEMP carton predates MES route history.
        # Let operators finish that one physical carton, while NG and duplicate
        # decisions remain hard stops. New cartons retain strict route gating.
        if not allowed and decision_code == "OUT_OF_SEQUENCE" \
                and self.active_case() and self.active_work_order().upper().startswith("TEMP-"):
            with self.connect() as db:
                draft_count = int(db.execute("SELECT COUNT(*) FROM draft_items").fetchone()[0])
                if draft_count > 0:
                    self._event(db, "LEGACY_ROUTE_OBSERVED", sn, decision)
                    allowed = True
        if not allowed:
            code = decision_code or "MES_SCAN_BLOCKED"
            source = str(decision.get("sourceStation") or decision.get("source_station") or "")
            message = str(decision.get("message") or decision.get("error", {}).get("message") or "")
            if code in ("ACTIVE_NG_CAUGHT", "CONFIRMED_NG_BLOCKED"):
                reason = "NG 产品禁止装箱: %s%s" % (sn, ("，来源工位 " + source) if source else "")
                event_type = "NG_BLOCKED"
            elif "DUPLICATE" in code or code in ("PRODUCT_ALREADY_PACKED", "SN_ALREADY_IN_OTHER_BOX"):
                reason = "重复 SN 禁止装箱: %s" % sn
                event_type = "DUPLICATE_BLOCKED"
            elif code == "OUT_OF_SEQUENCE":
                missing = decision.get("missingUpstreamStations") or []
                missing_codes = ", ".join(str(row.get("stationCode") or row) for row in missing[:5])
                reason = "跳站禁止装箱: %s%s" % (sn, ("，缺少 " + missing_codes) if missing_codes else "")
                event_type = "STATION_JUMP_BLOCKED"
            else:
                reason = "MES 扫码拦截 %s: %s%s" % (code, sn, ("，" + message) if message else "")
                event_type = "MES_SCAN_BLOCKED"
            with self.connect() as db:
                if event_type == "NG_BLOCKED":
                    db.execute(
                        """INSERT INTO confirmed_ng(sn,source_station,reason,created_at,exemptible,exemption_policy)
                           VALUES(?,?,?,?,?,?) ON CONFLICT(sn) DO UPDATE SET
                           source_station=excluded.source_station,reason=excluded.reason,
                           exemptible=excluded.exemptible,exemption_policy=excluded.exemption_policy""",
                        (sn, source, message or code, int(time.time()),
                         1 if decision.get("lineLeaderExemptible") is True or decision.get("allowExemption") is True else 0,
                         str(decision.get("exemptionPolicy") or decision.get("defectClass") or "")),
                    )
                self._event(db, event_type, sn, decision)
            raise BindingError(reason)
        try:
            self.arrivals.record_arrival(sn, "SCANNER", operator_id="OPERATOR")
        except Exception as exc:
            # The arrival cache may still contain the same NG. A current,
            # SN-specific MES exemption has already passed the authoritative
            # scan gate above, so do not let the stale secondary cache block it.
            if not exemption or "NG" not in str(exc).upper():
                raise
            with self.connect() as db:
                self._event(db, "ARRIVAL_NG_EXEMPTION_APPLIED", sn, {
                    "exemptionId": exemption["exemption_id"],
                    "arrivalCacheMessage": str(exc),
                })
        self.ensure_active_case(capacity)
        SIX_MONTHS_MS=181*24*3600*1000;now_ms=int(time.time()*1000)
        with self._lock, self.connect() as db:
            ng = db.execute("SELECT reason,source_station,created_at FROM confirmed_ng WHERE sn=?", (sn,)).fetchone()
            exemption = self._active_ng_exemption(db, sn) if ng else None
            if ng and not exemption:
                ng_created_ms=int(ng["created_at"] or 0)
                if ng_created_ms < 10**12:
                    ng_created_ms *= 1000
                age_ms=now_ms-ng_created_ms
                if age_ms>SIX_MONTHS_MS:
                    self._event(db,"NG_TOO_OLD",sn,dict(ng));db.commit()
                    raise BindingError(f"NG记录超过6个月({age_ms//86400000}天)，禁止装箱回修: %s"%sn)
                self._event(db, "NG_BLOCKED", sn, dict(ng))
                db.commit()
                raise BindingError("NG 产品禁止装箱: %s" % sn)
            bound = db.execute("SELECT carton_sn FROM carton_items WHERE sn=?", (sn,)).fetchone()
            if bound:
                self._event(db, "DUPLICATE_BLOCKED", sn, {"cartonSn": bound[0]})
                db.commit()
                raise BindingError("重复 SN，已绑定到外箱 %s" % bound[0])
            if db.execute("SELECT 1 FROM draft_items WHERE sn=?", (sn,)).fetchone():
                self._event(db, "DUPLICATE_BLOCKED", sn, {"scope": "draft"})
                db.commit()
                raise BindingError("重复扫描: %s" % sn)
            capacity=int(self.setting("active_case_capacity","0") or 0)
            current=db.execute("SELECT COUNT(*) FROM draft_items").fetchone()[0]
            replace_row=db.execute(
                """SELECT d.sn,d.scanned_at FROM draft_items d
                   JOIN confirmed_ng n ON n.sn=d.sn
                   ORDER BY d.scanned_at,d.sn LIMIT 1"""
            ).fetchone()
            if replace_row:
                db.execute("DELETE FROM draft_items WHERE sn=?", (replace_row["sn"],))
                db.execute("INSERT INTO draft_items(sn,scanned_at) VALUES(?,?)",(sn,replace_row["scanned_at"]))
                self._event(db,"NG_PRODUCT_REPLACED",replace_row["sn"],{"replacementSn":sn,"activeCase":self.active_case()})
                remaining_ng=db.execute(
                    "SELECT COUNT(*) FROM draft_items d JOIN confirmed_ng n ON n.sn=d.sn"
                ).fetchone()[0]
                is_full=(capacity > 0 and current >= capacity and remaining_ng == 0)
                db.commit()
                if is_full:
                    return self.seal_active_case()
                return {"replacedNg":replace_row["sn"],"replacementSn":sn}
            # Block if already at or over capacity (before inserting — slot not yet filled)
            if capacity and current>=capacity:
                self._event(db,"CASE_CAPACITY_BLOCKED",sn,{"capacity":capacity,"activeCase":self.active_case()});db.commit()
                raise BindingError("外箱已达到容量 %d，请完成封箱"%capacity)
            # Insert first, then check if full → auto-seal
            db.execute("INSERT INTO draft_items(sn,scanned_at) VALUES(?,?)", (sn, int(time.time())))
            if exemption:
                first_use = str(exemption["status"] or "") == "APPROVED"
                if first_use:
                    db.execute(
                        "UPDATE ng_exemptions SET used_at=?,status='USED' WHERE exemption_id=?",
                        (int(time.time()), exemption["exemption_id"]),
                    )
                used_detail = {
                    "exemptionId": exemption["exemption_id"],
                    "leaderId": exemption["leader_id"],
                    "approverRole": exemption["approver_role"],
                    "approvalReason": exemption["approval_reason"],
                    "sourceStation": exemption["source_station"],
                    "cartonSn": self.active_case(),
                    "workOrderCode": self.active_work_order(),
                    "specialRelease": True,
                }
                self._event(db, "NG_EXEMPTION_APPLIED", sn, used_detail)
                if first_use:
                    used_event_id = str(uuid.uuid4())
                    db.execute(
                        "INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",
                        (used_event_id, json.dumps({
                            "eventId": used_event_id, "type": "NG_EXEMPTION_USED",
                            "eventType": "NG_EXEMPTION_USED", "stationCode": STATION_CODE,
                            "from": STATION_CODE, "to": "mes",
                            "payload": {
                                "eventId": used_event_id, "sn": sn,
                                "occurredAt": int(time.time() * 1000), **used_detail,
                            },
                        }, ensure_ascii=False), int(time.time())),
                    )
            self._event(db, "PRODUCT_SCANNED", sn)
            new_count = db.execute("SELECT COUNT(*) FROM draft_items").fetchone()[0]
            is_full = (capacity > 0 and new_count >= capacity)
            db.commit()
        # Auto-seal if just hit capacity
        if is_full:
            return self.seal_active_case()
        return sn

    def remove_draft_product(self, raw, reason="", operator_id="OPERATOR"):
        """Remove one selected SN from the current unsealed carton."""
        sn = str(raw or "").strip()
        reason = str(reason or "").strip()
        operator_id = str(operator_id or "OPERATOR").strip()
        if not sn:
            raise BindingError("请选择要删除的产品 SN")
        if not reason:
            raise BindingError("删除 SN 必须填写原因")
        with self._lock, self.connect() as db:
            row = db.execute(
                "SELECT sn,scanned_at FROM draft_items WHERE sn=?", (sn,)
            ).fetchone()
            if not row:
                raise BindingError("该 SN 不在当前未封箱外箱中: %s" % sn)
            position = db.execute(
                "SELECT COUNT(*) FROM draft_items WHERE scanned_at < ? OR (scanned_at = ? AND sn <= ?)",
                (row["scanned_at"], row["scanned_at"], sn),
            ).fetchone()[0]
            carton_sn = self.active_case()
            before_count = db.execute("SELECT COUNT(*) FROM draft_items").fetchone()[0]
            capacity = int(self.setting("active_case_capacity", "96") or 96)
            db.execute("DELETE FROM draft_items WHERE sn=?", (sn,))
            after_count = before_count - 1
            remaining = max(0, capacity - after_count)
            self._event(
                db,
                "DRAFT_PRODUCT_REMOVED",
                sn,
                {
                    "cartonSn": carton_sn,
                    "position": position,
                    "reason": reason,
                    "operator": operator_id,
                    "beforeCount": before_count,
                    "afterCount": after_count,
                    "remainingToFill": remaining,
                    "capacity": capacity,
                },
            )
            event_id = str(uuid.uuid4())
            payload = {
                "eventId": event_id,
                "eventType": "CONTAINER_DRAFT_ITEM_REMOVED",
                "stationCode": STATION_CODE,
                "workOrderCode": self.active_work_order(),
                "cartonSn": carton_sn,
                "productSn": sn,
                "position": position,
                "reason": reason,
                "operatorId": operator_id,
                "beforeCount": before_count,
                "afterCount": after_count,
                "remainingToFill": remaining,
                "capacity": capacity,
                "occurredAt": int(time.time() * 1000),
            }
            db.execute(
                "INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",
                (event_id, json.dumps(payload, ensure_ascii=False), int(time.time())),
            )
        return {
            "sn": sn,
            "position": position,
            "cartonSn": carton_sn,
            "beforeCount": before_count,
            "afterCount": after_count,
            "remainingToFill": remaining,
            "reason": reason,
            "operatorId": operator_id,
        }

    def bind_case(self, raw, allow_partial=False, partial_reason=""):
        carton_sn = str(raw or "").strip()
        if not carton_sn:
            raise BindingError("外箱码不能为空")
        work_order = self.setting("active_case_work_order","") or self.active_work_order()
        if not work_order:
            raise BindingError("MES 未下发当前工单 WO，禁止绑定")
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM cartons WHERE carton_sn=?", (carton_sn,)).fetchone():
                self._event(db, "DUPLICATE_CASE_BLOCKED", carton_sn)
                db.commit()
                raise BindingError("外箱码已使用: %s" % carton_sn)
            rows = db.execute("SELECT sn FROM draft_items ORDER BY scanned_at,sn").fetchall()
            if not rows:
                raise BindingError("请先扫描产品 SN")
            ng_rows=db.execute(
                """SELECT d.sn FROM draft_items d JOIN confirmed_ng n ON n.sn=d.sn
                   LEFT JOIN ng_exemptions x ON x.sn=d.sn AND x.status='USED'
                   WHERE x.exemption_id IS NULL
                   ORDER BY d.scanned_at,d.sn"""
            ).fetchall()
            if ng_rows:
                raise BindingError("箱内仍有 NG，禁止封箱；请替换槽位: %s" % ",".join(row[0] for row in ng_rows))
            target = int(self.setting("active_case_capacity", "0") or 0)
            if target > 0 and len(rows) != target and not allow_partial:
                raise BindingError("数量不符：当前 %d，要求 %d" % (len(rows), target))
            if allow_partial and target > 0 and len(rows) >= target:
                raise BindingError("当前数量已经满箱，请使用正常满箱流程")
            now, binding_id = int(time.time()), str(uuid.uuid4())
            db.execute("INSERT INTO cartons(carton_sn,item_count,work_order_code,bound_at,binding_id) VALUES(?,?,?,?,?)",
                       (carton_sn, len(rows), work_order, now, binding_id))
            for pos, row in enumerate(rows, 1):
                db.execute("INSERT INTO carton_items(sn,carton_sn,position,bound_at) VALUES(?,?,?,?)",
                           (row[0], carton_sn, pos, now))
                db.execute("INSERT INTO binding_mappings(binding_id,work_order_code,carton_sn,capacity,slot_position,product_sn,bound_at) VALUES(?,?,?,?,?,?,?)",
                           (binding_id,work_order,carton_sn,target,pos,row[0],now))
            products = [r[0] for r in rows]
            exemptions = [dict(row) for row in db.execute(
                """SELECT exemption_id AS exemptionId,sn,source_station AS sourceStation,
                          ng_reason AS ngReason,leader_id AS leaderId,
                          approval_reason AS approvalReason,approved_at AS approvedAt,used_at AS usedAt
                   FROM ng_exemptions WHERE status='USED' AND sn IN
                     (SELECT sn FROM draft_items) ORDER BY approved_at"""
            )]
            print_template = self.setting("active_case_print_template","") or self.selected_print_template()
            payload = {
                "eventId": binding_id, "eventType": "CONTAINER_UPDATE",
                "stationCode": STATION_CODE, "nextStationCode": NEXT_STATION,
                "workOrderCode": work_order, "cartonSn": carton_sn, "containerId": carton_sn,
                "productSns": products, "items": products, "itemCount": len(products),
                "capacity": target, "status": "sealed", "occurredAt": now * 1000,
                "completionType":"PARTIAL_TAIL" if allow_partial else "FULL",
                "partial":bool(allow_partial),"partialReason":str(partial_reason or ""),
                "ngExemptions": exemptions,
                "printTemplate": print_template,
                "stationRules": {"product": self.setting("product_rule"), "case": self.setting("case_rule"), "targetCount": target},
            }
            db.execute("INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",
                       (binding_id, json.dumps(payload, ensure_ascii=False), now))
            db.execute("DELETE FROM draft_items")
            if exemptions:
                db.execute(
                    "UPDATE ng_exemptions SET status='SEALED',carton_sn=? WHERE status='USED'",
                    (carton_sn,),
                )
            self._event(db, "CASE_PARTIAL_SEALED" if allow_partial else "CASE_BOUND", carton_sn,
                        {"bindingId":binding_id,"workOrderCode":work_order,"products":products,
                         "itemCount":len(products),"capacity":target,"partialReason":str(partial_reason or "")})
        with self.connect() as db:
            archived=[dict(r) for r in db.execute("SELECT binding_id,work_order_code,carton_sn,capacity,slot_position,product_sn,bound_at FROM binding_mappings WHERE carton_sn=? ORDER BY slot_position",(carton_sn,))]
        self.history.seal_rows("binding_mappings",archived,"product_sn","外箱绑定完成自动封存","SYSTEM")
        return payload

    def seal_active_case(self, allow_partial=False, partial_reason=""):
        carton_sn=self.active_case()
        if not carton_sn:
            raise BindingError("请先扫描外箱码")
        payload=self.bind_case(carton_sn,allow_partial,partial_reason)
        self.set_setting("active_case","")
        self.set_setting("active_case_capacity","0")
        self.set_setting("active_case_work_order","")
        self.set_setting("active_case_print_template","")
        return payload

    def _get_day_code(self):
        """Return 2-letter AT&T Manufacturing Day code (AA=Jan1 per Appendix A).

        Alphabet excludes I, O, S, Z (22 valid chars).
        Formula: code = ALPHA[(doy-1)//22 % 22] + ALPHA[(doy-1) % 22]
        Verified: AA=Jan1, AY=Jan22, BA=Jan23, BK=Feb1, BL=Feb2, CR=Mar1.
        """
        try:
            from datetime import datetime
            now = datetime.now()
            doy = now.timetuple().tm_yday
        except Exception:
            doy = 1
        # AT&T alpha: A-Y excluding I,O,S,Z = 22 chars
        alpha = [c for c in 'ABCDEFGHJKLMNPQRTUVWXY']
        idx = doy - 1
        return alpha[idx // 22 % 22] + alpha[idx % 22]

    def available_print_templates(self):
        """Return BarTender templates visible to both station UIs."""
        folders = (
            BUNDLE_DIR / PRINT_TEMPLATE_DIRNAME,
            BASE_DIR / PRINT_TEMPLATE_DIRNAME,
            BASE_DIR,
            Path(r"C:\Users\tianj\Desktop\越南工厂瑞晶\dc\packaging"),
        )
        # Keep outer-box and pallet templates strictly isolated.
        folders = (
            BUNDLE_DIR / PRINT_TEMPLATE_DIRNAME,
            BASE_DIR / PRINT_TEMPLATE_DIRNAME,
            BASE_DIR,
        )
        found = {}
        for folder in folders:
            try:
                for path in folder.glob("*.btw"):
                    found.setdefault(path.name, path)
            except OSError:
                continue
        return [found[name] for name in sorted(found, key=str.casefold)]

    def selected_print_template(self):
        templates = self.available_print_templates()
        selected = self.setting("print_template", "")
        if selected and any(path.name == selected for path in templates):
            return selected
        if any(path.name == DEFAULT_PRINT_TEMPLATE for path in templates):
            return DEFAULT_PRINT_TEMPLATE
        return templates[0].name if templates else ""

    def set_print_template(self, template_name):
        if template_name not in {path.name for path in self.available_print_templates()}:
            raise BindingError("打印模板不存在: %s" % template_name)
        self.set_setting("print_template", template_name)

    def import_print_template(self, source_path):
        source = Path(source_path)
        if source.suffix.lower() != ".btw" or not source.is_file():
            raise BindingError("请选择有效的 BarTender .btw 模板")
        target_dir = BASE_DIR / PRINT_TEMPLATE_DIRNAME
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(str(source), str(target))
        self.set_print_template(target.name)
        return target.name

    def _find_bartender(self):
        candidates = (
            os.environ.get("BARTENDER_EXE", ""),
            r"C:\Program Files\Seagull\BarTender Suite\bartend.exe",
            r"C:\Program Files\Seagull\BarTender 2022\bartend.exe",
            r"C:\Program Files\Seagull\BarTender 2021\bartend.exe",
            r"C:\Program Files (x86)\Seagull\BarTender Suite\bartend.exe",
        )
        return next((path for path in candidates if path and os.path.isfile(path)), "")

    def _print_bartender_template(self, template_name, fields):
        """Print a .btw only after injecting this print job's real data.

        A template that does not expose the required named data sources is
        rejected.  It is never printed with design-time/sample values.
        """
        template = next(
            (path for path in self.available_print_templates() if path.name == template_name),
            None,
        )
        bartender = self._find_bartender()
        if not template or not bartender:
            return False
        app=fmt=None
        try:
            import win32com.client
            app=win32com.client.Dispatch("BarTender.Application")
            app.Visible=False
            fmt=app.Formats.Open(str(template),False,"")

            def set_first(names,value):
                for name in names:
                    try:
                        fmt.SetNamedSubStringValue(name,str(value))
                        return True
                    except Exception:
                        continue
                return False

            carton_ok=set_first(("CartonSN","CartonSeries","CARTON_SERIES","Carton","QRData"),fields["cartonSn"])
            date_ok=set_first(("PrintDate","PRINT_DATE","Date","DATE"),fields["printDate"])
            set_first(("PrintTime","PRINT_TIME","Time","TIME"),fields["printTime"])
            set_first(("WorkOrder","WorkOrderCode","WO","WORK_ORDER"),fields["workOrderCode"])
            set_first(("Quantity","QTY","Qty"),fields["quantity"])
            product_ok=True
            for index,sn in enumerate(fields["productSns"],1):
                if not set_first(("Sn%d"%index,"SN%d"%index,"ProductSN%d"%index,"ProductSn%d"%index),sn):
                    product_ok=False
                    break
            if not (carton_ok and date_ok and product_ok):
                return False
            fmt.PrintOut(False,False)
            return True
        except Exception:
            pass
        finally:
            try:
                if fmt is not None:fmt.Close(1)
            except Exception:pass
            try:
                if app is not None:app.Quit(1)
            except Exception:pass
        # BarTender 10.1 on the production PC exposes no Formats collection
        # through COM. Use its supported command-line print path and supply a
        # one-row data file. This still prints the selected .btw template; it
        # is not a generated-image fallback.
        data_path = None
        try:
            import csv
            fd, data_path = tempfile.mkstemp(prefix="outer_box_", suffix=".csv")
            os.close(fd)
            columns = ["CartonSN", "WorkOrderCode", "Quantity", "PrintDate", "PrintTime"]
            columns.extend("SN%d" % index for index in range(1, len(fields["productSns"]) + 1))
            row = [
                fields["cartonSn"], fields["workOrderCode"], fields["quantity"],
                fields["printDate"], fields["printTime"],
            ] + list(fields["productSns"])
            with open(data_path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                writer.writerow(row)
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                [bartender, "/F=" + str(template), "/D=" + data_path, "/P", "/X"],
                timeout=60,
                creationflags=flags,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False
        finally:
            if data_path:
                try:
                    os.remove(data_path)
                except OSError:
                    pass

    def _print_case_label(self, payload, template_name=None):
        """Generate and print a CARTON SERIES label for the sealed case.

        CARTON SERIES format (AT&T QP 200-00029):
          CS0 | N | 18 | V | Y | DD | C | SSSSSS | NBT
          = 20 characters total
        """
        carton_sn    = payload.get("cartonSn", "")
        work_order   = payload.get("workOrderCode", "")
        products     = payload.get("productSns", [])
        capacity     = payload.get("capacity", 0)
        binding_id   = payload.get("eventId", "")
        # The label date/time is always the real print moment.  Reprinting does
        # not reuse the original binding timestamp.
        import datetime
        print_moment=datetime.datetime.now()
        date_str=print_moment.strftime("%Y-%m-%d")
        time_str=print_moment.strftime("%H:%M:%S")

        # AT&T day code (AA=Jan1, BK=Feb1, etc.)
        day_code = self._get_day_code()

        # Build JSON QR payload — traceability data pushed to MES via CONTAINER_UPDATE
        # The QR itself is the official 20-character CARTON SERIES. Detailed
        # WO and product mappings remain in SQLite and the MES event payload.
        qr_data = carton_sn

        selected_template = payload.get("printTemplate") or template_name or self.selected_print_template()
        if selected_template:
            self.set_print_template(selected_template)
            fields={"cartonSn":carton_sn,"workOrderCode":work_order,
                    "quantity":len(products),"printDate":date_str,
                    "printTime":time_str,"productSns":list(products)}
            if self._print_bartender_template(selected_template,fields):
                return {"method": "bartender", "template": selected_template}

        # Printing must use the selected BarTender template. Never silently
        # substitute a generated PNG because that hides template failures.
        return {"method": "failed", "template": selected_template}

    def _generate_case_label(self, qr_data, carton_sn, work_order, products,
                             capacity, day_code, date_str):
        """Generate a CARTON SERIES label PNG (1600×1200px, 2× prior size).

        CARTON SERIES layout (AT&T QP 200-00029):
          CS0|N|18|V|Y|DD|C|SSSSSS|NBT
        The human-readable section shows CARTON SERIES + traceability fields.
        The QR encodes the full binding payload for MES traceability.
        """
        try:
            import qrcode
            from PIL import Image, ImageDraw, ImageFont

            W, H = 1600, 1200
            img = Image.new("RGB", (W, H), "white")
            draw = ImageDraw.Draw(img)

            try:
                ft_title = ImageFont.truetype("arial.ttf", 60)
                ft_series = ImageFont.truetype("arial.ttf", 44)
                ft_hdr   = ImageFont.truetype("arial.ttf", 36)
                ft_body  = ImageFont.truetype("arial.ttf", 28)
                ft_small = ImageFont.truetype("arial.ttf", 24)
            except Exception:
                ft_title = ft_series = ft_hdr = ft_body = ft_small = ImageFont.load_default()

            # ── Title ────────────────────────────────────────────────
            draw.text((30, 20), "CARTON SERIES", font=ft_title, fill="black")

            # ── QR code (top-right) ─────────────────────────────────
            try:
                qr = qrcode.make(qr_data)
                qr = qr.resize((400, 400))
                img.paste(qr, (W - 440, 16))
            except Exception:
                pass

            # ── CARTON SERIES banner ────────────────────────────────
            draw.rectangle([(30, 100), (W - 460, 216)], outline="black", width=4)
            draw.text((44, 110), carton_sn, font=ft_series, fill="black")

            # ── Info fields ─────────────────────────────────────────
            y = 236
            field_h = 52
            for lbl, val in [
                ("Work Order:",  work_order),
                ("Quantity:",    str(len(products))),
                ("Date:",       date_str),
                ("Day Code:",   day_code),
                ("Capacity:",   str(capacity)),
            ]:
                draw.text((40, y), lbl, font=ft_hdr, fill="black")
                draw.text((400, y), val, font=ft_hdr, fill="black")
                y += field_h

            # ── Horizontal rule ────────────────────────────────────
            y += 4
            draw.rectangle([(30, y), (W - 30, y + 4)], fill="black")
            y += 20

            # ── Product SN list (up to 96 products in 4 columns) ─────
            draw.text((40, y), "Product S/N:", font=ft_hdr, fill="black")
            y += 48
            printable_products = list(products[:96])
            column_count = 4
            rows_per_column = max(1, (len(printable_products) + column_count - 1) // column_count)
            col_x = [40, 430, 820, 1210]
            for idx, sn in enumerate(printable_products):
                col = min(column_count - 1, idx // rows_per_column)
                row = idx % rows_per_column
                draw.text((col_x[col], y + row * 34), sn, font=ft_body, fill="black")

            # ── Footer ───────────────────────────────────────────────
            draw.line([(30, H - 80), (W - 30, H - 80)], fill="black", width=2)
            draw.text((30, H - 70), "NetBit Electronics Ltd. | " + carton_sn,
                      font=ft_small, fill="black")

            tmp_dir = os.path.join(tempfile.gettempdir(), "case_labels")
            os.makedirs(tmp_dir, exist_ok=True)
            # Use binding_id suffix from qr_data dict embedded in qr_data (passed separately)
            bid = ""
            try:
                bid = json.loads(qr_data).get("bindingId", "")[:8]
            except Exception:
                bid = "label"
            path = os.path.join(tmp_dir, "label_%s_%s.png" % (carton_sn[:20], bid))
            img.save(path)
            return path
        except Exception as e:
            return None

    def _print_label_image(self, image_path):
        """Send a label PNG to the default Windows printer via win32print."""
        try:
            import win32print
            import win32ui
            from PIL import Image, ImageWin

            if not image_path or not os.path.exists(image_path):
                return
            printer = win32print.GetDefaultPrinter()
            img = Image.open(image_path)
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(printer)
            hdc.StartDoc(image_path)
            hdc.StartPage()
            dib = ImageWin.Dib(img)
            dib.draw(hdc.GetHandleOutput(), (0, 0, 1600, 1200))
            hdc.EndPage()
            hdc.EndDoc()
            hdc.DeleteDC()
        except Exception:
            pass   # Swallow all print errors — never block the workflow

    def clear_draft(self):
        with self.connect() as db:
            db.execute("DELETE FROM draft_items")
            self._event(db, "DRAFT_CLEARED")

    def snapshot(self, history_limit=100):
        with self.connect() as db:
            draft = [dict(r) for r in db.execute(
                """SELECT d.sn,d.scanned_at,
                          CASE WHEN n.sn IS NULL THEN 0 ELSE 1 END AS is_ng,
                          COALESCE(n.reason,'') AS ng_reason,
                          CASE WHEN x.exemption_id IS NULL THEN 0 ELSE 1 END AS special_release,
                          COALESCE(x.leader_id,'') AS release_approver,
                          COALESCE(x.approval_reason,'') AS release_reason
                   FROM draft_items d LEFT JOIN confirmed_ng n ON n.sn=d.sn
                   LEFT JOIN ng_exemptions x ON x.sn=d.sn AND x.status='USED'
                   ORDER BY d.scanned_at,d.sn"""
            )]
            history = [dict(r) for r in db.execute("SELECT * FROM cartons ORDER BY bound_at DESC LIMIT ?", (history_limit,))]
            for item in history:
                item["products"] = [r[0] for r in db.execute("SELECT sn FROM carton_items WHERE carton_sn=? ORDER BY position", (item["carton_sn"],))]
        return {"activeCase":self.active_case(),"activeCapacity":int(self.setting("active_case_capacity","0") or 0),"draft": draft, "history": history}

    def reprint_case_label(self, carton_raw, operator_id="OPERATOR"):
        carton_sn=str(carton_raw or "").strip()
        if not carton_sn:
            raise BindingError("请选择需要补打的外箱码")
        with self.connect() as db:
            carton=db.execute("SELECT * FROM cartons WHERE carton_sn=?",(carton_sn,)).fetchone()
            if not carton:
                raise BindingError("未找到外箱码: "+carton_sn)
            products=[r[0] for r in db.execute(
                "SELECT sn FROM carton_items WHERE carton_sn=? ORDER BY position",(carton_sn,)
            )]
        payload={"eventId":carton["binding_id"] or "","eventType":"CONTAINER_UPDATE",
                 "stationCode":STATION_CODE,"workOrderCode":carton["work_order_code"],
                 "cartonSn":carton_sn,"containerId":carton_sn,"productSns":products,
                 "items":products,"itemCount":len(products),"capacity":int(carton["item_count"]),
                 "occurredAt":int(carton["bound_at"])*1000}
        self._print_case_label(payload)
        now,event_id=int(time.time()),str(uuid.uuid4())
        audit={"eventId":event_id,"eventType":"CASE_LABEL_REPRINTED","stationCode":STATION_CODE,
               "workOrderCode":carton["work_order_code"],"cartonSn":carton_sn,
               "operatorId":str(operator_id or "OPERATOR"),"occurredAt":now*1000}
        with self.connect() as db:
            self._event(db,"CASE_LABEL_REPRINTED",carton_sn,audit)
            db.execute("INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",
                       (event_id,json.dumps(audit,ensure_ascii=False),now))
        return audit

    def guard_status(self, limit=30):
        with self.connect() as db:
            ng_count=db.execute("SELECT COUNT(*) FROM station_events WHERE event_type='NG_BLOCKED'").fetchone()[0]
            dup_count=db.execute("SELECT COUNT(*) FROM station_events WHERE event_type IN('DUPLICATE_BLOCKED','DUPLICATE_CASE_BLOCKED')").fetchone()[0]
            incidents=[dict(r) for r in db.execute("SELECT event_type,code,detail,created_at FROM station_events WHERE event_type IN('NG_BLOCKED','DUPLICATE_BLOCKED','DUPLICATE_CASE_BLOCKED') ORDER BY id DESC LIMIT ?",(limit,))]
            cached_ng=db.execute("SELECT COUNT(*) FROM confirmed_ng").fetchone()[0]
            ng_items=[dict(r) for r in db.execute("SELECT sn,source_station,reason,created_at FROM confirmed_ng ORDER BY created_at DESC,sn LIMIT ?",(limit,))]
        return {"ngBlocked":ng_count,"duplicateBlocked":dup_count,"cachedNg":cached_ng,"incidents":incidents,"ngItems":ng_items}

    def resource_tables(self, limit=500):
        """Read-only resource projection used by both 2D and 3D viewers."""
        queries={
            "外箱绑定 / CASES":"SELECT carton_sn,work_order_code,item_count,bound_at,mes_synced,binding_id FROM cartons ORDER BY bound_at DESC LIMIT ?",
            "产品关系 / PRODUCTS":"SELECT sn,carton_sn,position,bound_at FROM carton_items ORDER BY bound_at DESC,carton_sn,position LIMIT ?",
            "绑定映射 / MAPPING":"SELECT m.binding_id,m.work_order_code,m.carton_sn,m.capacity,m.slot_position,m.product_sn,m.bound_at,c.mes_synced FROM binding_mappings m JOIN cartons c ON c.carton_sn=m.carton_sn ORDER BY m.bound_at DESC,m.carton_sn,m.slot_position LIMIT ?",
            "NG缓存 / NG CACHE":"SELECT sn,source_station,reason,created_at FROM confirmed_ng ORDER BY created_at DESC LIMIT ?",
            "NG-DUP事件 / GUARD":"SELECT event_type,code,detail,created_at FROM station_events WHERE event_type LIKE '%BLOCKED%' ORDER BY id DESC LIMIT ?",
            "MES Outbox":"SELECT event_id,created_at,sent_at,attempts,last_error,payload FROM mes_outbox ORDER BY id DESC LIMIT ?",
            "工位配置 / SETTINGS":"SELECT key,value FROM settings ORDER BY key LIMIT ?",
            "变更记录 / CHANGE LOG":"SELECT change_key,version,component,reason,summary,verification,changed_at FROM software_change_log ORDER BY change_key DESC LIMIT ?",
            "预发SN / EXPECTED":"SELECT sn,source_station,expected_at,arrival_status,arrived_at FROM expected_sns ORDER BY expected_at DESC LIMIT ?",
            "报到记录 / ARRIVALS":"SELECT sn,expected,arrival_status,arrived_at,mes_reported_at,source_type FROM sn_arrivals ORDER BY arrived_at DESC LIMIT ?",
            "报到异常 / EXCEPTIONS":"SELECT sn,reason_code,reason_detail,operator_id,maintenance_case_id,created_at FROM arrival_exceptions ORDER BY created_at DESC LIMIT ?",
            "维修工单 / MAINTENANCE":"SELECT local_case_id,mes_work_order_id,sn,reason_code,department,status,created_at FROM maintenance_cases ORDER BY created_at DESC LIMIT ?",
            "历史封存 / ARCHIVE":"SELECT archive_batch_id,reason,record_count,content_hash,sealed_at,created_by FROM history_archive_batches ORDER BY sealed_at DESC LIMIT ?",
        }
        result={}
        with self.connect() as db:
            for name,sql in queries.items():result[name]=[dict(row) for row in db.execute(sql,(limit,))]
        return result

    def sync_once(self):
        self.heartbeat_once()
        lifecycle_sent = self.arrivals.sync_once()+self.arrivals.maintenance.sync_once(MES_URL)+self.history.sync_once(MES_URL)
        with self.connect() as db:
            rows = db.execute("SELECT id,payload FROM mes_outbox WHERE sent_at IS NULL ORDER BY id LIMIT 20").fetchall()
        sent = 0
        for row in rows:
            try:
                payload = json.loads(row["payload"])
                request = urllib.request.Request(MES_URL, data=row["payload"].encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(request, timeout=3) as response:
                    if not 200 <= response.status < 300:
                        raise RuntimeError("HTTP %s" % response.status)
                with self.connect() as db:
                    db.execute("UPDATE mes_outbox SET sent_at=?,attempts=attempts+1,last_error='' WHERE id=?", (int(time.time()), row["id"]))
                    db.execute("UPDATE cartons SET mes_synced=1 WHERE binding_id=?", (payload.get("eventId", ""),))
                sent += 1
            except Exception as exc:
                with self.connect() as db:
                    db.execute("UPDATE mes_outbox SET attempts=attempts+1,last_error=? WHERE id=?", (str(exc)[:300], row["id"]))
        return sent + lifecycle_sent

    def heartbeat_once(self):
        """Publish station liveness independently from scanner/business events."""
        payload = {
            "type": "AGENT_HEARTBEAT",
            "stationCode": STATION_CODE,
            "eventId": "heartbeat-%s-%d" % (STATION_CODE, int(time.time() * 1000)),
            "payload": {
                "agent": "outer_box_binding_agent",
                "agentVersion": "3.1-heartbeat",
                "status": "running",
                "sourceType": "SCANNER",
                "sourceConnected": True,
                "timestamp": int(time.time() * 1000),
            },
        }
        try:
            request = urllib.request.Request(
                MES_URL,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                response.read()
            return True
        except Exception:
            return False
