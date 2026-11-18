# -*- coding: utf-8 -*-
"""Shared authoritative core for the pallet-binding station."""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.parse
import uuid
from pathlib import Path

# A PyInstaller one-file application extracts bundled modules into a temporary
# _MEI directory. Keep production SQLite beside the installed EXE so pallet
# history survives process and computer restarts.
BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
PRINT_TEMPLATE_DIRNAME = "print_templates"
DEFAULT_PRINT_TEMPLATE = "EPS18R1G_BALLET_PRY.btw"
MANUAL_LINE_DIR=BASE_DIR.parent
if str(MANUAL_LINE_DIR) not in sys.path:sys.path.insert(0,str(MANUAL_LINE_DIR))
from station_arrival_core import StationArrivalStore
from station_history_core import StationHistoryArchive
DB_PATH = BASE_DIR / "pallet_binding.db"
STATION_CODE = "manu_pallet_binding"
MES_URL = os.environ.get("MES_API_URL", "http://192.168.6.155:8080/api/pda/events")
MES_BASE = MES_URL.split("/api/", 1)[0]


class PalletError(RuntimeError):
    pass


class PalletBindingStore:
    CARTON_CODE_RE=re.compile(r"^CSO(?:N18|N36|N48)V[0-9][ABCDEFGHJKLMNPQRTUVWXY]{2}C[0-9]{6}NBT$")
    def __init__(self, db_path=DB_PATH):
        self.db_path = Path(db_path)
        self.lock = threading.RLock()
        self.init_db()
        self.arrivals=StationArrivalStore(self.db_path,STATION_CODE,MES_URL)
        self.history=StationHistoryArchive(self.db_path,STATION_CODE)

    def connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def init_db(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS known_cartons(
              carton_sn TEXT PRIMARY KEY, source_station TEXT NOT NULL DEFAULT 'manu_case_binding',
              item_count INTEGER NOT NULL DEFAULT 0, work_order_code TEXT NOT NULL DEFAULT '', received_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS confirmed_ng(
              code TEXT PRIMARY KEY, code_type TEXT NOT NULL DEFAULT 'CARTON',
              reason TEXT NOT NULL DEFAULT '', source_station TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pallets(
              pallet_sn TEXT PRIMARY KEY, target_cartons INTEGER NOT NULL,
              work_order_code TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN('OPEN','SEALED')),
              created_at INTEGER NOT NULL, sealed_at INTEGER, binding_id TEXT UNIQUE,
              mes_synced INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS pallet_cartons(
              carton_sn TEXT PRIMARY KEY,
              pallet_sn TEXT NOT NULL REFERENCES pallets(pallet_sn),
              position INTEGER NOT NULL, upstream_verified INTEGER NOT NULL DEFAULT 0,
              added_at INTEGER NOT NULL, UNIQUE(pallet_sn,position)
            );
            CREATE TABLE IF NOT EXISTS station_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,
              code TEXT NOT NULL DEFAULT '',detail TEXT NOT NULL DEFAULT '{}',created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mes_outbox(
              id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,
              payload TEXT NOT NULL,created_at INTEGER NOT NULL,sent_at INTEGER,
              attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS software_change_log(id INTEGER PRIMARY KEY AUTOINCREMENT,change_id TEXT NOT NULL UNIQUE,version TEXT NOT NULL,component TEXT NOT NULL,reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at INTEGER NOT NULL);
            CREATE TRIGGER IF NOT EXISTS pallet_change_no_update BEFORE UPDATE ON software_change_log BEGIN SELECT RAISE(ABORT,'software change history is immutable'); END;
            CREATE TRIGGER IF NOT EXISTS pallet_change_no_delete BEFORE DELETE ON software_change_log BEGIN SELECT RAISE(ABORT,'software change history is immutable'); END;
            """)
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('default_target_cartons','20')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('pallet_rule','station scanner rule')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('carton_rule','station scanner rule')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('active_work_order','')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('active_work_order_received_at','0')")
            db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('work_order_bypass','0')")
            known_cols={row[1] for row in db.execute("PRAGMA table_info(known_cartons)")}
            pallet_cols={row[1] for row in db.execute("PRAGMA table_info(pallets)")}
            if "work_order_code" not in known_cols:
                db.execute("ALTER TABLE known_cartons ADD COLUMN work_order_code TEXT NOT NULL DEFAULT ''")
            if "work_order_code" not in pallet_cols:
                db.execute("ALTER TABLE pallets ADD COLUMN work_order_code TEXT NOT NULL DEFAULT ''")
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",("PALLET-001","2.1.0","lifecycle","Every scanned carton needs an explainable arrival, archive and maintenance evidence chain","Added mandatory arrival reporting, immutable pallet-carton archive and automatic maintenance linkage","one-carton pallet lifecycle integration passed",int(time.time()*1000)))

    def setting(self, key, default=""):
        with self.connect() as db:
            row=db.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        return row[0] if row else default

    def set_setting(self,key,value):
        with self.connect() as db:db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))

    def active_work_order(self):
        return self.setting("active_work_order","")

    def work_order_bypass(self):
        return self.setting("work_order_bypass","0")=="1"

    def set_work_order_bypass(self,enabled):
        self.set_setting("work_order_bypass","1" if enabled else "0")
        return bool(enabled)

    def work_order_codes(self):
        try:
            rows=json.loads(self.setting("mes_work_orders_json","[]"))
        except Exception:
            rows=[]
        return [str(row.get("workOrderCode") or "").strip() for row in rows if str(row.get("workOrderCode") or "").strip()]

    def select_work_order(self, work_order_code):
        code=str(work_order_code or "").strip()
        if not code or code not in self.work_order_codes():
            raise PalletError("请选择MES提供的真实工单WO")
        self.set_setting("active_work_order",code)
        body=json.dumps({"stationCode":STATION_CODE,"workOrderCode":code,"selectedBy":"OPERATOR"}).encode("utf-8")
        request=urllib.request.Request("%s/api/station/active-workorder"%MES_BASE,data=body,headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(request,timeout=5) as response:response.read()
        with self.connect() as db:self._event(db,"WORK_ORDER_SELECTED",code,{"source":"MES_DROPDOWN"})
        return code

    def refresh_mes_context(self):
        try:
            url="%s/api/station/qr-workorders?stationCode=%s"%(MES_BASE,STATION_CODE)
            with urllib.request.urlopen(url,timeout=3) as response:data=json.loads(response.read().decode("utf-8"))
            self.set_setting("mes_work_orders_json",json.dumps(data.get("available") or [],ensure_ascii=False))
            active=data.get("active") or [];row=next((x for x in active if x.get("stationCode")==STATION_CODE and x.get("status")=="ACTIVE"),None)
            work_order=str((row or {}).get("workOrderCode") or "").strip();self.set_setting("active_work_order",work_order);self.set_setting("active_work_order_received_at",int(time.time()))
            boxes_url="%s/api/station/packaging-boxes"%MES_BASE
            with urllib.request.urlopen(boxes_url,timeout=3) as response:boxes=json.loads(response.read().decode("utf-8")).get("items") or []
            with self.connect() as db:
                for box in boxes:
                    db.execute("INSERT INTO known_cartons(carton_sn,item_count,work_order_code,received_at) VALUES(?,?,?,?) ON CONFLICT(carton_sn) DO UPDATE SET item_count=excluded.item_count,work_order_code=excluded.work_order_code,received_at=excluded.received_at",(str(box.get("containerId") or ""),int(box.get("currentCount") or 0),str(box.get("workOrderCode") or ""),int(time.time())))
            self.arrivals.apply_manifest([{"sn":str(box.get("containerId") or ""),"sourceStation":"manu_case_binding"} for box in boxes],int(time.time()*1000))
            return work_order
        except Exception:return self.active_work_order()

    def _event(self,db,event_type,code="",detail=None):
        db.execute("INSERT INTO station_events(event_type,code,detail,created_at) VALUES(?,?,?,?)",
                   (event_type,code,json.dumps(detail or {},ensure_ascii=False),int(time.time())))

    def _generate_pallet_code(self):
        """Generate the pallet code internally; operators never enter it."""
        stamp=time.strftime("%Y%m%d%H%M%S")
        return "PLT%s%s"%(stamp,uuid.uuid4().hex[:4].upper())

    def create_pallet(self, raw="", target=None):
        pallet=str(raw or "").strip() or self._generate_pallet_code()
        work_order=self.active_work_order()
        if not work_order and not self.work_order_bypass(): raise PalletError("MES 未下发当前工单 WO，禁止建立栈板")
        if not work_order: work_order="TEMP-NO-WO"
        try: target=int(target or self.setting("default_target_cartons","20"))
        except ValueError: raise PalletError("目标箱数必须是整数")
        if target < 1: raise PalletError("目标箱数必须大于 0")
        SIX_MONTHS_MS=181*24*3600*1000;now_ms=int(time.time()*1000)
        with self.lock,self.connect() as db:
            row=db.execute("SELECT status FROM pallets WHERE pallet_sn=?",(pallet,)).fetchone()
            if row: raise PalletError("栈板码已存在，状态: %s"%row[0])
            ng=db.execute("SELECT created_at FROM confirmed_ng WHERE code=?",(pallet,)).fetchone()
            if ng:
                age_ms=now_ms-ng[0]
                if age_ms>SIX_MONTHS_MS:
                    raise PalletError(f"NG栈板码超过6个月({age_ms//86400000}天)，禁止使用: {pallet}")
                raise PalletError("NG 栈板码禁止使用: "+pallet)
            db.execute("INSERT INTO pallets(pallet_sn,target_cartons,work_order_code,status,created_at) VALUES(?,?,?,'OPEN',?)",(pallet,target,work_order,int(time.time())))
            self._event(db,"PALLET_OPENED",pallet,{"targetCartons":target,"workOrderCode":work_order})
        return pallet

    def add_carton(self,pallet_raw,carton_raw):
        pallet,carton=str(pallet_raw or "").strip(),str(carton_raw or "").strip().upper()
        SIX_MONTHS_MS=181*24*3600*1000
        now_ms=int(time.time()*1000)
        if not pallet or not carton: raise PalletError("请先选择栈板并扫描外箱码")
        if not self.CARTON_CODE_RE.fullmatch(carton):
            with self.connect() as db:
                self._event(db,"INVALID_CARTON_CODE_REJECTED",carton,{
                    "reason":"CARTON_CODE_RULE_MISMATCH",
                    "requiredFormat":"CSO+(N18|N36|N48)+V+Y+DD+C+6DIGITS+NBT",
                    "requiredLength":20,
                })
            raise PalletError("外箱码格式错误，禁止加入栈板: "+carton)
        self.arrivals.record_arrival(carton,"SCANNER",operator_id="OPERATOR")
        with self.lock,self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p=db.execute("SELECT status,target_cartons,work_order_code FROM pallets WHERE pallet_sn=?",(pallet,)).fetchone()
            if not p: raise PalletError("栈板不存在，请先建立栈板")
            if p["status"]!="OPEN": raise PalletError("栈板已经封板，禁止增加外箱")
            ng=db.execute("SELECT reason,created_at FROM confirmed_ng WHERE code=?",(carton,)).fetchone()
            if ng:
                age_ms=now_ms-ng["created_at"]
                if age_ms>SIX_MONTHS_MS:
                    self._event(db,"NG_TOO_OLD",carton,{"reason":ng["reason"],"age_days":age_ms//86400000})
                    raise PalletError(f"NG外箱超过6个月({age_ms//86400000}天)，禁止入栈: {carton}")
                self._event(db,"NG_BLOCKED",carton,{"reason":ng["reason"]})
                raise PalletError("NG 外箱禁止入栈: "+carton)
            old=db.execute("SELECT pallet_sn FROM pallet_cartons WHERE carton_sn=?",(carton,)).fetchone()
            if old:
                self._event(db,"DUPLICATE_BLOCKED",carton,{"palletSn":old[0]})
                raise PalletError("重复外箱，已属于栈板 %s"%old[0])
            count=db.execute("SELECT COUNT(*) FROM pallet_cartons WHERE pallet_sn=?",(pallet,)).fetchone()[0]
            # Block if already at or over capacity (before inserting — slot not yet filled)
            if count>=p["target_cartons"]: raise PalletError("栈板已达到目标箱数，请确认封板")
            known=db.execute("SELECT work_order_code FROM known_cartons WHERE carton_sn=?",(carton,)).fetchone()
            verified=1 if known else 0
            if known and known["work_order_code"] and known["work_order_code"] != p["work_order_code"]:
                self._event(db,"WORK_ORDER_MISMATCH_BLOCKED",carton,{"palletWorkOrder":p["work_order_code"],"cartonWorkOrder":known["work_order_code"]})
                raise PalletError("工单不一致：栈板 %s，外箱 %s"%(p["work_order_code"],known["work_order_code"]))
            db.execute("INSERT INTO pallet_cartons(carton_sn,pallet_sn,position,upstream_verified,added_at) VALUES(?,?,?,?,?)",
                       (carton,pallet,count+1,verified,int(time.time())))
            self._event(db,"CARTON_ADDED",carton,{"palletSn":pallet,"workOrderCode":p["work_order_code"],"position":count+1,"upstreamVerified":bool(verified),"sequenceFlag":None if verified else "UPSTREAM_NOT_CONFIRMED"})
            new_count = db.execute("SELECT COUNT(*) FROM pallet_cartons WHERE pallet_sn=?",(pallet,)).fetchone()[0]
            is_full = (new_count >= p["target_cartons"])
            remaining = p["target_cartons"] - new_count
        # Auto-seal if just hit capacity
        if is_full:
            return self.seal_pallet(pallet)
        return {"cartonSn":carton,"position":count+1,"verified":bool(verified),"remaining":remaining}

    def remove_carton(self,pallet_raw,carton_raw,reason="BROKEN_BOX"):
        pallet,carton=str(pallet_raw or "").strip(),str(carton_raw or "").strip()
        reason=str(reason or "").strip()
        if not pallet or not carton: raise PalletError("请选择需要移除的破损外箱")
        if not reason: raise PalletError("必须填写移除原因")
        now,event_id=int(time.time()),str(uuid.uuid4())
        with self.lock,self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p=db.execute("SELECT status,target_cartons,work_order_code FROM pallets WHERE pallet_sn=?",(pallet,)).fetchone()
            if not p: raise PalletError("栈板不存在")
            if p["status"]!="OPEN": raise PalletError("已封板栈板禁止删除外箱")
            row=db.execute("SELECT position FROM pallet_cartons WHERE pallet_sn=? AND carton_sn=?",(pallet,carton)).fetchone()
            if not row: raise PalletError("该外箱不在当前栈板中")
            old_position=int(row["position"])
            before_count=db.execute("SELECT COUNT(*) FROM pallet_cartons WHERE pallet_sn=?",(pallet,)).fetchone()[0]
            db.execute("DELETE FROM pallet_cartons WHERE pallet_sn=? AND carton_sn=?",(pallet,carton))
            db.execute("UPDATE pallet_cartons SET position=position-1 WHERE pallet_sn=? AND position>?",(pallet,old_position))
            after_count=before_count-1
            remaining=int(p["target_cartons"])-after_count
            detail={"palletSn":pallet,"cartonSn":carton,"workOrderCode":p["work_order_code"],
                    "oldPosition":old_position,"reason":reason,"operatorId":"OPERATOR",
                    "beforeCount":before_count,"afterCount":after_count,
                    "remaining":remaining,"remainingToFill":remaining,"capacity":int(p["target_cartons"])}
            self._event(db,"BROKEN_CARTON_REMOVED",carton,detail)
            payload={"eventId":event_id,"eventType":"PALLET_CARTON_REMOVED","stationCode":STATION_CODE,
                     "occurredAt":now*1000,**detail}
            db.execute("INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",
                       (event_id,json.dumps(payload,ensure_ascii=False),now))
        return payload

    def seal_pallet(self,raw,allow_partial=False,partial_reason=""):
        pallet=str(raw or "").strip()
        with self.lock,self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p=db.execute("SELECT * FROM pallets WHERE pallet_sn=?",(pallet,)).fetchone()
            if not p: raise PalletError("栈板不存在")
            if p["status"]=="SEALED": raise PalletError("栈板已经封板")
            rows=db.execute("SELECT carton_sn,upstream_verified FROM pallet_cartons WHERE pallet_sn=? ORDER BY position",(pallet,)).fetchall()
            if not rows: raise PalletError("空栈板不能封板")
            if len(rows)!=p["target_cartons"] and not allow_partial: raise PalletError("箱数不符：当前 %d，目标 %d"%(len(rows),p["target_cartons"]))
            if allow_partial and len(rows)>=p["target_cartons"]: raise PalletError("当前数量已经满栈，请使用正常满栈流程")
            now,event_id=int(time.time()),str(uuid.uuid4())
            cartons=[r["carton_sn"] for r in rows];unverified=[r["carton_sn"] for r in rows if not r["upstream_verified"]]
            payload={"eventId":event_id,"eventType":"PALLET_BINDING_COMPLETED","stationCode":STATION_CODE,
                     "palletSn":pallet,"workOrderCode":p["work_order_code"],"cartonSns":cartons,"cartonCount":len(cartons),"occurredAt":now*1000,
                     "sequenceFlags":[{"cartonSn":x,"flag":"UPSTREAM_NOT_CONFIRMED"} for x in unverified],
                     "completionType":"PARTIAL_TAIL" if allow_partial else "FULL",
                     "partial":bool(allow_partial),"partialReason":str(partial_reason or ""),
                     "stationRules":{"pallet":self.setting("pallet_rule"),"carton":self.setting("carton_rule"),"targetCartons":p["target_cartons"]}}
            db.execute("UPDATE pallets SET status='SEALED',sealed_at=?,binding_id=? WHERE pallet_sn=?",(now,event_id,pallet))
            db.execute("INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",(event_id,json.dumps(payload,ensure_ascii=False),now))
            self._event(db,"PALLET_PARTIAL_SEALED" if allow_partial else "PALLET_SEALED",pallet,
                        {"cartons":cartons,"unverified":unverified,"cartonCount":len(cartons),
                         "targetCartons":p["target_cartons"],"partialReason":str(partial_reason or "")})
        with self.connect() as db:archived=[dict(r) for r in db.execute("SELECT carton_sn,pallet_sn,position,upstream_verified,added_at FROM pallet_cartons WHERE pallet_sn=? ORDER BY position",(pallet,))]
        self.history.seal_rows("pallet_cartons",archived,"carton_sn","栈板绑定完成自动封存","SYSTEM")
        return payload

    def snapshot(self,limit=100):
        with self.connect() as db:
            pallets=[dict(r) for r in db.execute("SELECT p.*,(SELECT COUNT(*) FROM pallet_cartons c WHERE c.pallet_sn=p.pallet_sn) carton_count FROM pallets p ORDER BY created_at DESC LIMIT ?",(limit,))]
            for p in pallets:p["cartons"]=[dict(r) for r in db.execute("SELECT * FROM pallet_cartons WHERE pallet_sn=? ORDER BY position",(p["pallet_sn"],))]
        return pallets

    def reprint_pallet_label(self,pallet_raw,operator_id="OPERATOR"):
        pallet=str(pallet_raw or "").strip()
        if not pallet: raise PalletError("请选择需要补打的栈板码")
        with self.connect() as db:
            p=db.execute("SELECT * FROM pallets WHERE pallet_sn=?",(pallet,)).fetchone()
            if not p: raise PalletError("未找到栈板码: "+pallet)
            if p["status"]!="SEALED": raise PalletError("只有已满栈封板的标签可以补打")
            cartons=[r[0] for r in db.execute(
                "SELECT carton_sn FROM pallet_cartons WHERE pallet_sn=? ORDER BY position",(pallet,)
            )]
            payload={"eventId":p["binding_id"] or "","eventType":"PALLET_BINDING_COMPLETED",
                     "stationCode":STATION_CODE,"palletSn":pallet,
                     "workOrderCode":p["work_order_code"],"cartonSns":cartons,
                     "cartonCount":len(cartons),"occurredAt":int(p["sealed_at"] or time.time())*1000,
                     "stationRules":{"targetCartons":int(p["target_cartons"])}}
        self._print_pallet_label(payload)
        now,event_id=int(time.time()),str(uuid.uuid4())
        audit={"eventId":event_id,"eventType":"PALLET_LABEL_REPRINTED","stationCode":STATION_CODE,
               "palletSn":pallet,"workOrderCode":p["work_order_code"],
               "operatorId":str(operator_id or "OPERATOR"),"occurredAt":now*1000}
        with self.connect() as db:
            self._event(db,"PALLET_LABEL_REPRINTED",pallet,audit)
            db.execute("INSERT INTO mes_outbox(event_id,payload,created_at) VALUES(?,?,?)",
                       (event_id,json.dumps(audit,ensure_ascii=False),now))
        return audit

    def search_pallets(self,term="",limit=500):
        needle=str(term or "").strip().upper()
        rows=self.snapshot(limit)
        if not needle:return [row for row in rows if row["status"]=="SEALED"]
        matched=[row for row in rows if row["status"]=="SEALED" and (
            needle in row["pallet_sn"].upper() or
            any(needle in str(box["carton_sn"]).upper() for box in row["cartons"])
        )]
        if matched:return matched
        # Product SN -> MES lineage -> outer box -> pallet. MES is used only to
        # resolve the identity; the printable payload still comes from local
        # immutable pallet history.
        try:
            url="%s/api/mes/lineage/%s"%(MES_BASE,urllib.parse.quote(needle,safe=""))
            with urllib.request.urlopen(url,timeout=5) as response:
                lineage=json.loads(response.read().decode("utf-8"))
            pallet_codes={str(item.get("palletCode") or "").upper() for item in lineage.get("pallets") or []}
            return [row for row in rows if row["status"]=="SEALED" and row["pallet_sn"].upper() in pallet_codes]
        except Exception:
            return []

    def resource_tables(self,limit=500):
        queries={
          "栈板 / PALLETS":"SELECT * FROM pallets ORDER BY created_at DESC LIMIT ?",
          "绑定映射 / MAPPING":"SELECT * FROM pallet_cartons ORDER BY added_at DESC LIMIT ?",
          "预发SN / EXPECTED":"SELECT sn,source_station,expected_at,arrival_status,arrived_at FROM expected_sns ORDER BY expected_at DESC LIMIT ?",
          "报到记录 / ARRIVALS":"SELECT sn,expected,arrival_status,arrived_at,mes_reported_at,source_type FROM sn_arrivals ORDER BY arrived_at DESC LIMIT ?",
          "报到异常 / EXCEPTIONS":"SELECT sn,reason_code,reason_detail,operator_id,maintenance_case_id,created_at FROM arrival_exceptions ORDER BY created_at DESC LIMIT ?",
          "维修工单 / MAINTENANCE":"SELECT local_case_id,mes_work_order_id,sn,reason_code,department,status,created_at FROM maintenance_cases ORDER BY created_at DESC LIMIT ?",
          "历史封存 / ARCHIVE":"SELECT archive_batch_id,reason,record_count,content_hash,sealed_at,created_by FROM history_archive_batches ORDER BY sealed_at DESC LIMIT ?",
          "MES Outbox":"SELECT event_id,created_at,sent_at,attempts,last_error FROM mes_outbox ORDER BY id DESC LIMIT ?",
          "修改记录 / CHANGE LOG":"SELECT change_id,version,component,reason,summary,verification,changed_at FROM software_change_log ORDER BY id DESC LIMIT ?"}
        with self.connect() as db:return {name:[dict(r) for r in db.execute(sql,(limit,))] for name,sql in queries.items()}

    def sync_once(self):
        self.heartbeat_once()
        lifecycle_sent=self.arrivals.sync_once()+self.arrivals.maintenance.sync_once(MES_URL)+self.history.sync_once(MES_URL)
        with self.connect() as db: rows=db.execute("SELECT id,payload FROM mes_outbox WHERE sent_at IS NULL ORDER BY id LIMIT 20").fetchall()
        sent=0
        for row in rows:
            try:
                payload=json.loads(row["payload"]);request=urllib.request.Request(MES_URL,data=row["payload"].encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")
                with urllib.request.urlopen(request,timeout=3) as response:
                    if not 200<=response.status<300:raise RuntimeError("HTTP %s"%response.status)
                with self.connect() as db:
                    db.execute("UPDATE mes_outbox SET sent_at=?,attempts=attempts+1,last_error='' WHERE id=?",(int(time.time()),row["id"]))
                    db.execute("UPDATE pallets SET mes_synced=1 WHERE binding_id=?",(payload.get("eventId",""),))
                sent+=1
            except Exception as exc:
                with self.connect() as db:db.execute("UPDATE mes_outbox SET attempts=attempts+1,last_error=? WHERE id=?",(str(exc)[:300],row["id"]))
        return sent+lifecycle_sent

    def heartbeat_once(self):
        """Publish station liveness independently from scanner/business events."""
        payload={
          "type":"AGENT_HEARTBEAT",
          "stationCode":STATION_CODE,
          "eventId":"heartbeat-%s-%d"%(STATION_CODE,int(time.time()*1000)),
          "payload":{
            "agent":"pallet_binding_agent",
            "agentVersion":"3.1-heartbeat",
            "status":"running",
            "sourceType":"SCANNER",
            "sourceConnected":True,
            "timestamp":int(time.time()*1000),
          },
        }
        try:
            request=urllib.request.Request(MES_URL,data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")
            with urllib.request.urlopen(request,timeout=3) as response:response.read()
            return True
        except Exception:return False

    def _get_day_code(self):
        """Return 2-letter AT&T Manufacturing Day code (AA=Jan1 per Appendix A).

        Alphabet excludes I, O, S, Z (22 valid chars).
        Formula: code = ALPHA[(doy-1)//22%22] + ALPHA[(doy-1)%22]
        Verified: AA=Jan1, AY=Jan22, BA=Jan23, BK=Feb1, BL=Feb2, CR=Mar1.
        """
        try:
            from datetime import datetime
            doy = datetime.now().timetuple().tm_yday
        except Exception:
            doy = 1
        alpha = [c for c in 'ABCDEFGHJKLMNPQRTUVWXY']
        idx = doy - 1
        return alpha[idx // 22 % 22] + alpha[idx % 22]

    def available_print_templates(self):
        found = {}
        for folder in (
            BUNDLE_DIR / PRINT_TEMPLATE_DIRNAME,
            BASE_DIR / PRINT_TEMPLATE_DIRNAME,
            BASE_DIR,
        ):
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
            raise PalletError("打印模板不存在: %s" % template_name)
        self.set_setting("print_template", template_name)

    def import_print_template(self, source_path):
        source = Path(source_path)
        if source.suffix.lower() != ".btw" or not source.is_file():
            raise PalletError("请选择有效的 BarTender .btw 模板")
        target_dir = BASE_DIR / PRINT_TEMPLATE_DIRNAME
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(str(source), str(target))
        self.set_print_template(target.name)
        return target.name

    def _print_bartender_template(self, template_name, fields):
        template = next((p for p in self.available_print_templates() if p.name == template_name), None)
        if not template:
            return False
        app = fmt = None
        try:
            import win32com.client
            app = win32com.client.Dispatch("BarTender.Application")
            app.Visible = False
            fmt = app.Formats.Open(str(template), False, "")

            def set_first(names, value):
                for name in names:
                    try:
                        fmt.SetNamedSubStringValue(name, str(value))
                        return True
                    except Exception:
                        continue
                return False

            pallet_ok = set_first(
                ("PalletSN", "PalletSeries", "PALLET_SERIES", "Pallet", "QRData"),
                fields["palletSn"],
            )
            date_ok = set_first(("PrintDate", "PRINT_DATE", "Date", "DATE"), fields["printDate"])
            set_first(("PrintTime", "PRINT_TIME", "Time", "TIME"), fields["printTime"])
            set_first(("WorkOrder", "WorkOrderCode", "WO", "WORK_ORDER"), fields["workOrderCode"])
            set_first(("Quantity", "QTY", "Qty", "CartonCount"), fields["quantity"])
            for index, carton in enumerate(fields["cartonSns"], 1):
                set_first(
                    ("Carton%d" % index, "CARTON%d" % index, "CartonSN%d" % index),
                    carton,
                )
            if not (pallet_ok and date_ok):
                return False
            fmt.PrintOut(False, False)
            return True
        except Exception:
            return False
        finally:
            try:
                if fmt is not None:
                    fmt.Close(1)
            except Exception:
                pass
            try:
                if app is not None:
                    app.Quit(1)
            except Exception:
                pass

    def _print_pallet_label(self, payload):
        """Generate and print a PALLET ID label for the sealed pallet.

        PALLET ID format (AT&T QP 200-00029, Table 4):
          NB | TN | 18 | V | Y | DD | SSSS
          = 14 characters total
        """
        pallet_sn   = payload.get("palletSn", "")
        work_order  = payload.get("workOrderCode", "")
        cartons     = payload.get("cartonSns", [])
        carton_cnt  = payload.get("cartonCount", 0)
        target_cnt = (payload.get("stationRules") or {}).get("targetCartons", 0)
        binding_id = payload.get("eventId", "")
        # Label date is the actual print/reprint moment, not the binding time.
        from datetime import datetime
        print_moment = datetime.now()
        date_str = print_moment.strftime("%Y-%m-%d %H:%M:%S")
        occurred_at = payload.get("occurredAt") or int(print_moment.timestamp() * 1000)

        day_code = self._get_day_code()

        # JSON QR payload — traceability data for MES
        qr_data = json.dumps({
            "palletSn":    pallet_sn,
            "workOrderCode": work_order,
            "bindingId":    binding_id,
            "cartonSns":    cartons,
            "cartonCount":  carton_cnt,
            "targetCartons": target_cnt,
            "occurredAt":   occurred_at,
        }, ensure_ascii=False)

        selected_template = payload.get("printTemplate") or self.selected_print_template()
        if selected_template and self._print_bartender_template(selected_template, {
            "palletSn": pallet_sn,
            "workOrderCode": work_order,
            "cartonSns": cartons,
            "quantity": carton_cnt,
            "printDate": print_moment.strftime("%Y-%m-%d"),
            "printTime": print_moment.strftime("%H:%M:%S"),
        }):
            return {"method": "bartender", "template": selected_template}

        img_path = self._generate_pallet_label(
            qr_data, pallet_sn, work_order, cartons,
            carton_cnt, target_cnt, day_code, date_str, binding_id
        )
        if img_path:
            self._print_label_image(img_path)
            return {"method": "fallback", "template": selected_template, "image": img_path}
        return {"method": "failed", "template": selected_template}

    def _generate_pallet_label(self, qr_data, pallet_sn, work_order, cartons,
                               carton_cnt, target_cnt, day_code, date_str, binding_id):
        """Generate a PALLET ID label PNG (800×600px).

        PALLET ID layout (AT&T QP 200-00029):
          NB|TN|18|V|Y|DD|SSSS
        Label shows PALLET ID + all contained carton series + QR.
        """
        try:
            import qrcode
            from PIL import Image, ImageDraw, ImageFont

            W, H = 800, 600
            img = Image.new("RGB", (W, H), "white")
            draw = ImageDraw.Draw(img)

            try:
                ft_title  = ImageFont.truetype("arial.ttf", 30)
                ft_pallet = ImageFont.truetype("arial.ttf", 22)
                ft_hdr    = ImageFont.truetype("arial.ttf", 18)
                ft_body   = ImageFont.truetype("arial.ttf", 14)
                ft_small  = ImageFont.truetype("arial.ttf", 12)
            except Exception:
                ft_title = ft_pallet = ft_hdr = ft_body = ft_small = ImageFont.load_default()

            # ── Title ────────────────────────────────────────────────
            draw.text((15, 10), "PALLET ID", font=ft_title, fill="black")

            # ── QR code (top-right) ─────────────────────────────────
            try:
                qr = qrcode.make(qr_data)
                qr = qr.resize((200, 200))
                img.paste(qr, (W - 220, 8))
            except Exception:
                pass

            # ── PALLET ID banner ────────────────────────────────────
            draw.rectangle([(15, 50), (W - 230, 108)], outline="black", width=2)
            draw.text((22, 55), pallet_sn, font=ft_pallet, fill="black")

            # ── Info fields ─────────────────────────────────────────
            y = 118
            for lbl, val in [
                ("Work Order:",   work_order),
                ("Cartons:",     "%d / %d" % (carton_cnt, target_cnt)),
                ("Date:",        date_str),
                ("Day Code:",    day_code),
            ]:
                draw.text((20, y), lbl, font=ft_hdr, fill="black")
                draw.text((200, y), val, font=ft_hdr, fill="black")
                y += 28

            # ── Horizontal rule ────────────────────────────────────
            y += 4
            draw.rectangle([(15, y), (W - 15, y + 2)], fill="black")
            y += 10

            # ── Carton series list ────────────────────────────────
            draw.text((20, y), "Carton Series:", font=ft_hdr, fill="black")
            y += 24
            col_x = [20, W // 2 + 10]
            sn_per_col = max(1, (len(cartons) + 1) // 2)
            for idx, cs in enumerate(cartons[:40]):
                col = 0 if idx < sn_per_col else 1
                row = idx if col == 0 else idx - sn_per_col
                draw.text((col_x[col], y + row * 18), cs, font=ft_body, fill="black")

            # ── Footer ───────────────────────────────────────────────
            draw.line([(15, H - 40), (W - 15, H - 40)], fill="black", width=1)
            draw.text((15, H - 35),
                      "NetBit Electronics Ltd. | " + pallet_sn,
                      font=ft_small, fill="black")

            tmp_dir = os.path.join(tempfile.gettempdir(), "pallet_labels")
            os.makedirs(tmp_dir, exist_ok=True)
            bid = binding_id[:8] if binding_id else "label"
            path = os.path.join(tmp_dir, "pallet_%s_%s.png" % (pallet_sn[:14], bid))
            img.save(path)
            return path
        except Exception:
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
            dib.draw(hdc.GetHandleOutput(), (0, 0, 800, 600))
            hdc.EndPage()
            hdc.EndDoc()
            hdc.DeleteDC()
        except Exception:
            pass   # Never block the workflow
