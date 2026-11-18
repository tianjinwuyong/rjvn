# -*- coding: utf-8 -*-
"""Local maintenance linkage for station arrival/production exceptions."""
from __future__ import annotations
import json,sqlite3,time,urllib.request,uuid
from pathlib import Path

ROUTING={"DEVICE_FAILURE":"EQUIPMENT","BARCODE_UNREADABLE":"EQUIPMENT","MES_OFFLINE":"IT_MES","DELAYED_REPORT":"IT_MES","DUPLICATE_REPORT":"QUALITY_PROCESS","EARLY_REPORT":"QUALITY_PROCESS","EMERGENCY_RELEASE":"QUALITY_AUDIT","NG_DEFECT":"PRODUCT_REPAIR"}

class StationMaintenanceStore:
    def __init__(self,db_path,station_code):self.db_path=Path(db_path);self.station_code=str(station_code).lower();self.init_db()
    def connect(self):db=sqlite3.connect(str(self.db_path),timeout=30);db.row_factory=sqlite3.Row;db.execute("PRAGMA journal_mode=WAL");return db
    def init_db(self):
        with self.connect() as db:db.executescript("""
        CREATE TABLE IF NOT EXISTS maintenance_cases(
          local_case_id TEXT PRIMARY KEY,mes_work_order_id TEXT UNIQUE,station_code TEXT NOT NULL,sn TEXT NOT NULL,
          exception_id TEXT,arrival_id TEXT,reason_code TEXT NOT NULL,department TEXT NOT NULL,status TEXT NOT NULL,
          created_at INTEGER NOT NULL,mes_created_at INTEGER,closed_at INTEGER);
        CREATE TABLE IF NOT EXISTS maintenance_case_events(
          event_id TEXT PRIMARY KEY,local_case_id TEXT NOT NULL,event_type TEXT NOT NULL,detail TEXT NOT NULL,
          actor_id TEXT NOT NULL,occurred_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS maintenance_outbox(
          event_id TEXT PRIMARY KEY,local_case_id TEXT NOT NULL,payload TEXT NOT NULL,created_at INTEGER NOT NULL,
          sent_at INTEGER,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '');
        CREATE TRIGGER IF NOT EXISTS maintenance_cases_evidence_no_update BEFORE UPDATE OF local_case_id,station_code,sn,exception_id,arrival_id,reason_code,department,created_at ON maintenance_cases BEGIN SELECT RAISE(ABORT,'maintenance case evidence is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS maintenance_cases_no_delete BEFORE DELETE ON maintenance_cases BEGIN SELECT RAISE(ABORT,'maintenance cases cannot be deleted'); END;
        CREATE TRIGGER IF NOT EXISTS maintenance_events_no_update BEFORE UPDATE ON maintenance_case_events BEGIN SELECT RAISE(ABORT,'maintenance events are append-only'); END;
        CREATE TRIGGER IF NOT EXISTS maintenance_events_no_delete BEFORE DELETE ON maintenance_case_events BEGIN SELECT RAISE(ABORT,'maintenance events are append-only'); END;
        """)
    def open_for_exception(self,sn,reason_code,reason_detail,actor_id,exception_id=None,arrival_id=None,local_case_id=None,connection=None):
        reason=str(reason_code).upper();department=ROUTING.get(reason,"QUALITY_PROCESS");now=int(time.time()*1000);case=local_case_id or str(uuid.uuid4());event=str(uuid.uuid4())
        payload={"type":"MAINTENANCE_CASE_OPEN","stationCode":self.station_code,"payload":{"localCaseId":case,"sn":str(sn).upper(),"exceptionId":exception_id,"arrivalId":arrival_id,"reasonCode":reason,"reasonDetail":reason_detail,"department":department,"actorId":actor_id,"createdAt":now}}
        if connection is not None:
            db=connection;db.execute("INSERT INTO maintenance_cases VALUES(?,NULL,?,?,?,?,?,?,'OPEN',?,NULL,NULL)",(case,self.station_code,str(sn).upper(),exception_id,arrival_id,reason,department,now));db.execute("INSERT INTO maintenance_case_events VALUES(?,?,?,?,?,?)",(event,case,"OPENED",str(reason_detail),str(actor_id),now));db.execute("INSERT INTO maintenance_outbox VALUES(?,?,?, ?,NULL,0,'')",(event,case,json.dumps(payload,ensure_ascii=False),now))
        else:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE");db.execute("INSERT INTO maintenance_cases VALUES(?,NULL,?,?,?,?,?,?,'OPEN',?,NULL,NULL)",(case,self.station_code,str(sn).upper(),exception_id,arrival_id,reason,department,now));db.execute("INSERT INTO maintenance_case_events VALUES(?,?,?,?,?,?)",(event,case,"OPENED",str(reason_detail),str(actor_id),now));db.execute("INSERT INTO maintenance_outbox VALUES(?,?,?, ?,NULL,0,'')",(event,case,json.dumps(payload,ensure_ascii=False),now))
        return case
    def append_event(self,case,event_type,detail,actor_id):
        if not str(detail).strip() or not str(actor_id).strip():raise ValueError("maintenance event detail and actor required")
        now=int(time.time()*1000);event=str(uuid.uuid4());payload={"type":"MAINTENANCE_CASE_EVENT","stationCode":self.station_code,"payload":{"localCaseId":case,"eventId":event,"eventType":str(event_type).upper(),"detail":detail,"actorId":actor_id,"occurredAt":now}}
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM maintenance_cases WHERE local_case_id=?",(case,)).fetchone():raise ValueError("maintenance case not found")
            db.execute("INSERT INTO maintenance_case_events VALUES(?,?,?,?,?,?)",(event,case,str(event_type).upper(),str(detail),str(actor_id),now));db.execute("INSERT INTO maintenance_outbox VALUES(?,?,?, ?,NULL,0,'')",(event,case,json.dumps(payload,ensure_ascii=False),now))
        return event
    def snapshot(self,limit=500):
        with self.connect() as db:return {"cases":[dict(r) for r in db.execute("SELECT * FROM maintenance_cases ORDER BY created_at DESC LIMIT ?",(limit,))],"events":[dict(r) for r in db.execute("SELECT * FROM maintenance_case_events ORDER BY occurred_at DESC LIMIT ?",(limit,))]}
    def sync_once(self,mes_url,limit=20):
        with self.connect() as db:rows=db.execute("SELECT * FROM maintenance_outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT ?",(limit,)).fetchall()
        sent=0
        for row in rows:
            try:
                req=urllib.request.Request(mes_url,data=row["payload"].encode(),headers={"Content-Type":"application/json"},method="POST")
                with urllib.request.urlopen(req,timeout=4) as response:reply=json.loads(response.read().decode() or "{}")
                with self.connect() as db:
                    db.execute("UPDATE maintenance_outbox SET sent_at=?,attempts=attempts+1,last_error='' WHERE event_id=?",(int(time.time()*1000),row["event_id"]))
                    if reply.get("mesWorkOrderId") is not None:db.execute("UPDATE maintenance_cases SET mes_work_order_id=?,mes_created_at=?,status=? WHERE local_case_id=?",(str(reply["mesWorkOrderId"]),int(time.time()*1000),str(reply.get("status") or "OPEN"),row["local_case_id"]))
                sent+=1
            except Exception as exc:
                with self.connect() as db:db.execute("UPDATE maintenance_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?",(str(exc)[:300],row["event_id"]))
        return sent

