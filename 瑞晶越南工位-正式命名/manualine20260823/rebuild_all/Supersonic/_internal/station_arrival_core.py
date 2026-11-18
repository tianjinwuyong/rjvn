# -*- coding: utf-8 -*-
"""Shared local expected-SN and mandatory arrival-reporting capability.

Station production databases remain authoritative.  This component adds a
uniform, append-only arrival ledger and durable outbox to each station DB.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from station_maintenance_core import StationMaintenanceStore


ARRIVAL_STATES = {"ARRIVED_LOCAL", "REPORTED", "UNEXPECTED_REPORTED", "REPORT_FAILED"}
EXCEPTION_REASONS = {"DUPLICATE_REPORT", "DELAYED_REPORT", "EARLY_REPORT", "SEQUENCE_JUMP", "CONFIRMED_NG", "MES_OFFLINE", "DEVICE_FAILURE", "BARCODE_UNREADABLE", "EMERGENCY_RELEASE", "DATA_CORRECTION", "OTHER"}

# Production station flow sequence and per-station allowed next stations.
# Products must follow this order; skipping a station triggers SEQUENCE_JUMP.
# AOI and ICT are parallel paths converging at FCT.
STATION_NEXT = {
    None: ['auto_pda'],                                 # First arrival must be PDA
    'auto_pda': ['auto_aoi', 'auto_ict'],
    'auto_aoi': ['auto_fct'],
    'auto_ict': ['auto_fct'],
    'auto_fct': ['auto_depanel'],
    'auto_depanel': ['auto_shellbinding'],
    'auto_shellbinding': ['auto_assem_ate'],
    'auto_assem_ate': ['auto_supersonic'],
    'auto_supersonic': ['auto_agingcab'],
    'auto_agingcab': ['auto_hivolt_ate'],
    'auto_hivolt_ate': ['auto_package_ate'],
    'auto_package_ate': ['auto_case_binding'],
    'auto_case_binding': ['auto_pallet_binding'],
    'auto_pallet_binding': [],
}
MANUAL_STATION_NEXT = {
    None: ['manu_pda'],
    'manu_pda': ['manu_aio', 'manu_ict'],
    'manu_aio': ['manu_fct'],
    'manu_ict': ['manu_fct'],
    'manu_fct': ['manu_depanel'],
    'manu_depanel': ['manu_shellbinding'],
    'manu_shellbinding': ['manu_assem_ate'],
    'manu_assem_ate': ['manu_supersonic'],
    'manu_assembly_ate': ['manu_supersonic'],
    'manu_supersonic': ['manu_agingcab'],
    'manu_agingcab': ['manu_hivolt_ate'],
    'manu_hivolt_ate': ['manu_package_ate'],
    'manu_package_ate': ['manu_case_binding'],
    'manu_case_binding': ['manu_pallet_binding'],
    'manu_pallet_binding': [],
}
# Linear order index used for rework-backward detection
STATION_ORDER = ['auto_pda', 'auto_aoi', 'auto_ict', 'auto_fct', 'auto_depanel',
    'auto_shellbinding', 'auto_assem_ate', 'auto_supersonic', 'auto_agingcab',
    'auto_hivolt_ate', 'auto_package_ate', 'auto_case_binding', 'auto_pallet_binding']
MANUAL_STATION_ORDER = ['manu_pda', 'manu_aio', 'manu_ict', 'manu_fct', 'manu_depanel',
    'manu_shellbinding', 'manu_assem_ate', 'manu_supersonic', 'manu_agingcab',
    'manu_hivolt_ate', 'manu_package_ate', 'manu_case_binding', 'manu_pallet_binding']
STATION_ORDER = STATION_ORDER + MANUAL_STATION_ORDER
STATION_INDEX = {code: i for i, code in enumerate(STATION_ORDER)}


class ArrivalError(RuntimeError):
    pass


class StationArrivalStore:
    def __init__(self, db_path, station_code, mes_url, delayed_report_ms=60000):
        self.db_path=Path(db_path);self.station_code=str(station_code).strip().lower();self.mes_url=str(mes_url)
        self.delayed_report_ms=max(0,int(delayed_report_ms))
        self._last_manifest_refresh=0
        self._last_ng_refresh=0
        self._ng_sync_version=0
        if not self.station_code:raise ValueError("station_code required")
        self.init_db()
        self.maintenance=StationMaintenanceStore(self.db_path,self.station_code)

    def connect(self):
        db=sqlite3.connect(str(self.db_path),timeout=30);db.row_factory=sqlite3.Row;db.execute("PRAGMA journal_mode=WAL");return db

    def init_db(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS expected_sns(
              station_code TEXT NOT NULL,sn TEXT NOT NULL,source_station TEXT NOT NULL DEFAULT '',
              production_date TEXT NOT NULL DEFAULT '',expected_at INTEGER NOT NULL,
              manifest_version INTEGER NOT NULL DEFAULT 0,arrival_status TEXT NOT NULL DEFAULT 'EXPECTED',
              arrived_at INTEGER,PRIMARY KEY(station_code,sn));
            CREATE TABLE IF NOT EXISTS sn_arrivals(
              arrival_id TEXT PRIMARY KEY,sn TEXT NOT NULL,station_code TEXT NOT NULL,expected INTEGER NOT NULL,
              arrival_status TEXT NOT NULL,arrived_at INTEGER NOT NULL,local_saved_at INTEGER NOT NULL,
              report_attempted_at INTEGER,mes_reported_at INTEGER,operator_id TEXT NOT NULL DEFAULT '',
              source_type TEXT NOT NULL,source_record_id TEXT NOT NULL DEFAULT '',exception_reason TEXT NOT NULL DEFAULT '',
              UNIQUE(station_code,sn));
            CREATE TABLE IF NOT EXISTS arrival_exceptions(
              exception_id TEXT PRIMARY KEY,sn TEXT NOT NULL,station_code TEXT NOT NULL,arrival_id TEXT,
              reason_code TEXT NOT NULL,reason_detail TEXT NOT NULL,operator_id TEXT NOT NULL,
              supervisor_id TEXT NOT NULL DEFAULT '',maintenance_case_id TEXT,created_at INTEGER NOT NULL,mes_synced INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sn_arrival_outbox(
              event_id TEXT PRIMARY KEY,arrival_id TEXT,event_type TEXT NOT NULL,payload TEXT NOT NULL,
              created_at INTEGER NOT NULL,first_attempt_at INTEGER,last_attempt_at INTEGER,sent_at INTEGER,
              attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS mes_active_ng_cache(
              sn TEXT PRIMARY KEY,source_station TEXT NOT NULL DEFAULT '',reason TEXT NOT NULL DEFAULT '',
              snapshot_version INTEGER NOT NULL DEFAULT 0,synced_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS mes_ng_cache_history(
              id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,source_station TEXT NOT NULL DEFAULT '',
              reason TEXT NOT NULL DEFAULT '',action TEXT NOT NULL,snapshot_version INTEGER NOT NULL DEFAULT 0,
              recorded_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS scan_interceptions(
              id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,station_code TEXT NOT NULL,
              interception_type TEXT NOT NULL,source_station TEXT NOT NULL DEFAULT '',reason TEXT NOT NULL DEFAULT '',
              intercepted_at INTEGER NOT NULL,mes_synced INTEGER NOT NULL DEFAULT 0);
            CREATE TRIGGER IF NOT EXISTS sn_arrivals_no_delete BEFORE DELETE ON sn_arrivals BEGIN SELECT RAISE(ABORT,'sn_arrivals cannot be deleted'); END;
            CREATE TRIGGER IF NOT EXISTS sn_arrivals_evidence_no_update BEFORE UPDATE OF sn,station_code,expected,arrived_at,local_saved_at,operator_id,source_type,source_record_id ON sn_arrivals BEGIN SELECT RAISE(ABORT,'arrival evidence is immutable'); END;
            CREATE TRIGGER IF NOT EXISTS arrival_exceptions_no_update BEFORE UPDATE ON arrival_exceptions BEGIN SELECT RAISE(ABORT,'arrival exceptions are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS arrival_exceptions_no_delete BEFORE DELETE ON arrival_exceptions BEGIN SELECT RAISE(ABORT,'arrival exceptions are append-only'); END;
            """)
            # Preserve older expected-SN caches without treating them as arrivals.
            old={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "mes_expected_sns" in old:
                cols={r[1] for r in db.execute("PRAGMA table_info(mes_expected_sns)")}
                if {"station_code","sn"}.issubset(cols):
                    source="source_station" if "source_station" in cols else "''"
                    prod="production_date" if "production_date" in cols else "''"
                    version="manifest_version" if "manifest_version" in cols else "0"
                    synced="synced_at" if "synced_at" in cols else str(int(time.time()*1000))
                    db.execute(f"INSERT OR IGNORE INTO expected_sns(station_code,sn,source_station,production_date,expected_at,manifest_version) SELECT LOWER(station_code),UPPER(sn),{source},{prod},{synced},{version} FROM mes_expected_sns WHERE TRIM(sn)<>''")
            exception_cols={r[1] for r in db.execute("PRAGMA table_info(arrival_exceptions)")}
            if "maintenance_case_id" not in exception_cols:db.execute("ALTER TABLE arrival_exceptions ADD COLUMN maintenance_case_id TEXT")

    def apply_manifest(self, items, version=0, received_at=None):
        now=int(received_at or time.time()*1000);count=0
        with self.connect() as db:
            for item in items or []:
                sn=str(item.get("sn") or "").strip().upper()
                if not sn:continue
                db.execute("INSERT INTO expected_sns(station_code,sn,source_station,production_date,expected_at,manifest_version) VALUES(?,?,?,?,?,?) ON CONFLICT(station_code,sn) DO UPDATE SET source_station=excluded.source_station,production_date=excluded.production_date,manifest_version=MAX(expected_sns.manifest_version,excluded.manifest_version)",
                           (self.station_code,sn,str(item.get("sourceStation") or ""),str(item.get("productionDate") or ""),now,int(version or 0)));count+=1
        return count

    def refresh_manifest(self,minimum_interval_ms=10000):
        now=int(time.time()*1000)
        if now-self._last_manifest_refresh<int(minimum_interval_ms):return 0
        self._last_manifest_refresh=now
        base=self.mes_url.split("/api/",1)[0]
        url=f"{base}/api/station/expected-sns?stationCode={self.station_code}"
        with urllib.request.urlopen(url,timeout=4) as response:data=json.loads(response.read().decode("utf-8"))
        return self.apply_manifest(data.get("items") or [],data.get("version") or 0,now)

    def refresh_active_ng(self, minimum_interval_ms=5000):
        """Append authenticated MES NG rows to the local blocking cache.

        This is the same authenticated 8080/versioned path used by QR Binding.
        The old implementation queried unauthenticated ``bucket-snapshots``;
        remote stations commonly received 401 and therefore missed NG rows.
        """
        now=int(time.time()*1000)
        if now-self._last_ng_refresh<int(minimum_interval_ms):
            return 0
        self._last_ng_refresh=now
        from station_sn_client import fetch_confirmed_ng
        snapshot=fetch_confirmed_ng(self._ng_sync_version)
        self._ng_sync_version=int(snapshot.get("version") or self._ng_sync_version)
        rows=[]
        for item in snapshot.get("items") or []:
            if not isinstance(item,dict):
                continue
            source=str(item.get("sourceStationCode") or item.get("sourceStation") or "MES")
            reason=str(item.get("defectCode") or item.get("defectDescription") or item.get("reason") or "MES CONFIRMED NG")
            identities=[]
            for key in ("sn","mainSn","productSn","pcbaSn","boardSn"):
                code=str(item.get(key) or "").strip().upper()
                if code and code not in identities:
                    identities.append(code)
            rows.extend((code,source,reason,self._ng_sync_version,now) for code in identities)
        if not rows:
            return 0
        with self.connect() as db:
            # ``synced_at`` is the first time this SN entered the local cache.
            # Do not renew old rows when MES sends a changed snapshot; only
            # genuinely new NGs should receive the current cache timestamp.
            db.executemany("INSERT INTO mes_active_ng_cache(sn,source_station,reason,snapshot_version,synced_at) VALUES(?,?,?,?,?) ON CONFLICT(sn) DO UPDATE SET source_station=excluded.source_station,reason=excluded.reason,snapshot_version=excluded.snapshot_version,synced_at=mes_active_ng_cache.synced_at", rows)
            db.executemany("INSERT INTO mes_ng_cache_history(sn,source_station,reason,action,snapshot_version,recorded_at) SELECT ?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM mes_ng_cache_history WHERE sn=? AND action='ACTIVE_NG_ADDED')", [(sn,source,reason,"ACTIVE_NG_ADDED",row_version,now,sn) for sn,source,reason,row_version,_ in rows])
        return len(rows)

    def _shared_local_ng(self, code):
        """Read the common agent's already-synchronized NG cache locally."""
        candidates = [
            self.db_path.parent / "data" / "common_agent.sqlite",
            self.db_path.parent / "_internal" / "data" / "common_agent.sqlite",
            self.db_path.parent.parent / "data" / "common_agent.sqlite",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                with sqlite3.connect(str(path), timeout=2) as shared:
                    row = shared.execute(
                        "SELECT source,reason FROM station_ng WHERE UPPER(sn)=? AND status='ACTIVE' LIMIT 1",
                        (code,),
                    ).fetchone()
                if row:
                    return {"source_station": row[0] or "MES", "reason": row[1] or "MES CONFIRMED NG"}
            except Exception:
                continue
        return None

    def assert_scan_allowed(self, sn, operator_id=""):
        """Hard gate used by every station arrival/scan before station work starts."""
        code=str(sn or "").strip().upper()
        # Scan handlers run on the UI thread.  Never perform the MES HTTP
        # refresh here: a slow/unreachable MES server must not freeze the
        # station.  The common background synchronizer refreshes this cache;
        # this gate only reads the last complete local snapshot.
        with self.connect() as db:
            ng=db.execute("SELECT source_station,reason,snapshot_version,synced_at FROM mes_active_ng_cache WHERE sn=?",(code,)).fetchone()
            if not ng:
                shared = self._shared_local_ng(code)
                if not shared:
                    return True
                source = shared["source_station"]
                reason = shared["reason"]
            else:
                source = ng["source_station"]
                reason = ng["reason"]
            now=int(time.time()*1000)
            db.execute("INSERT INTO scan_interceptions(sn,station_code,interception_type,source_station,reason,intercepted_at) VALUES(?,?,?,?,?,?)",
                       (code,self.station_code,"CONFIRMED_NG",source,reason,now))
        detail=f'CONFIRMED NG from {source}: {reason}'
        self._send_mes_alert(code,detail,str(operator_id or "SYSTEM"),"CONFIRMED_NG")
        raise ArrivalError(f"NG 产品禁止进入本站：{code}；来源 {source}；{reason}")

    def _get_last_station(self, db, sn, exclude_station=''):
        """Return the most recent station this SN visited before exclude_station, or None if unknown."""
        excl = str(exclude_station or '').lower()
        q = "SELECT station_code FROM sn_arrivals WHERE sn=?"
        params = [sn]
        if excl:
            q += " AND station_code!=?"
            params.append(excl)
        q += " ORDER BY arrived_at DESC LIMIT 1"
        if db is None:
            with self.connect() as c:
                row=c.execute(q, params).fetchone()
                return row[0] if row else None
        row=db.execute(q, params).fetchone()
        return row[0] if row else None

    def _validate_sequence(self, sn, station_code, db=None):
        """Check whether this SN arriving at station_code follows the production flow.
        
        Returns (valid: bool, detail: str).
          valid=True  → normal forward flow, re-scan, or rework return
          valid=False → skipped stations (SEQUENCE_JUMP)
        detail lists exactly which stations were skipped, if any.
        """
        station_code = str(station_code or '').strip().lower()
        route = MANUAL_STATION_NEXT if station_code.startswith('manu_') else STATION_NEXT
        last=self._get_last_station(db, sn, station_code)
        if last is None:
            allowed=route.get(None, [])
            if station_code in allowed:
                return True, 'first arrival at PDA'
            return False, f'跳过起始工位PDA，不允许直接到达{station_code}'
        if station_code==last:
            return True, 'same station re-scan'
        # Backward (rework return) — allowed
        last_idx=STATION_INDEX.get(last)
        cur_idx=STATION_INDEX.get(station_code)
        if last_idx is not None and cur_idx is not None and cur_idx<last_idx:
            return True, f'rework return from {last} to {station_code}'
        # Forward — check allowed next stations
        allowed=route.get(last, [])
        if station_code in allowed:
            return True, f'normal forward {last} -> {station_code}'
        # Compute skipped stations from linear order
        skipped=[]
        if last_idx is not None and cur_idx is not None:
            for stn in STATION_ORDER:
                si=STATION_INDEX[stn]
                if si>last_idx and si<cur_idx:
                    skipped.append(stn)
        if not skipped and allowed:
            skipped=[s for s in allowed if s!=station_code]
        if skipped:
            return False, f'跳站: 跳过{",".join(skipped)}，从{last}直接扫到{station_code}，请返回{allowed[0]}扫码'
        if allowed:
            return False, f'跳站: 从{last}不可直接扫{station_code}，请先去{allowed[0]}扫码'
        return False, f'已在终点站{station_code}，不可再向前跳转'

    def record_arrival(self, sn, source_type, source_record_id="", operator_id="", arrived_at=None):
        code=str(sn or "").strip().upper()
        if not code:raise ArrivalError("SN required for mandatory arrival report")
        source=str(source_type or "").strip().upper()
        if not source:raise ArrivalError("source_type required for mandatory arrival report")
        # Canonical rule: the very next station blocks an active NG before it can
        # be recorded, tested, bound, packed or otherwise processed.
        self.assert_scan_allowed(code,operator_id)
        now=int(time.time()*1000);actual=int(arrived_at or now)
        duplicate_result=None;seq_valid=True;seq_detail=''
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old=db.execute("SELECT * FROM sn_arrivals WHERE station_code=? AND sn=?",(self.station_code,code)).fetchone()
            if old:
                duplicate_result={**dict(old),"duplicate":True}
            else:
                expected=bool(db.execute("SELECT 1 FROM expected_sns WHERE station_code=? AND sn=?",(self.station_code,code)).fetchone())
                arrival_id=str(uuid.uuid4());event_id=str(uuid.uuid4());status="ARRIVED_LOCAL"
                db.execute("INSERT INTO sn_arrivals(arrival_id,sn,station_code,expected,arrival_status,arrived_at,local_saved_at,operator_id,source_type,source_record_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (arrival_id,code,self.station_code,int(expected),status,actual,now,str(operator_id or ""),source,str(source_record_id or "")))
                db.execute("UPDATE expected_sns SET arrival_status='ARRIVED_LOCAL',arrived_at=? WHERE station_code=? AND sn=?",(actual,self.station_code,code))
                payload={"type":"SN_ARRIVAL_REPORT","stationCode":self.station_code,"payload":{"arrivalId":arrival_id,"sn":code,"expected":expected,"arrivalStatus":status,"arrivedAt":actual,"localSavedAt":now,"sourceType":source,"sourceRecordId":str(source_record_id or ""),"operatorId":str(operator_id or "")}}
                db.execute("INSERT INTO sn_arrival_outbox(event_id,arrival_id,event_type,payload,created_at) VALUES(?,?,?,?,?)",(event_id,arrival_id,"SN_ARRIVAL_REPORT",json.dumps(payload,ensure_ascii=False),now))
                # Sequence validation inside the transaction
                seq_valid, seq_detail = self._validate_sequence(code, self.station_code, db)
        if duplicate_result:
            self.record_exception(code,"DUPLICATE_REPORT",f'duplicate of arrival {duplicate_result["arrival_id"]} at {duplicate_result["arrived_at"]}',str(operator_id or "SYSTEM"),arrival_id=duplicate_result["arrival_id"])
            return {**duplicate_result,"sequence_valid":True,"sequence_detail":"duplicate - already scanned at this station"}
        if not expected:
            self.record_exception(code,"EARLY_REPORT","SN reported before MES expected-SN manifest contained it",str(operator_id or "SYSTEM"),arrival_id=arrival_id)
        if not seq_valid:
            self.record_exception(code,"SEQUENCE_JUMP",seq_detail,str(operator_id or "SYSTEM"),arrival_id=arrival_id)
            # Alert delivery is best-effort; never hold up local SQL/result
            # ingestion while MES is slow or unavailable.
            threading.Thread(target=self._send_mes_alert,args=(code,seq_detail,str(operator_id or "")),daemon=True).start()
        return {"arrival_id":arrival_id,"sn":code,"station_code":self.station_code,"expected":expected,
                "arrival_status":status,"arrived_at":actual,"local_saved_at":now,"duplicate":False,
                "sequence_valid":seq_valid,"sequence_detail":seq_detail}

    def _send_mes_alert(self, sn, detail, operator_id, alert_type="SEQUENCE_JUMP"):
        """Send a jump-alert event to MES pda/events endpoint."""
        try:
            base=self.mes_url.split("/api/",1)[0] if "/api/" in self.mes_url else self.mes_url
            url=f"{base}/api/pda/events"
            payload={
                "stationCode":self.station_code,"type":"ALERT","alertType":alert_type,
                "payload":{"sn":sn,"detail":detail,"operatorId":operator_id,
                           "stationCode":self.station_code,"timestamp":int(time.time()*1000)}}
            req=urllib.request.Request(url,data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
                                       headers={"Content-Type":"application/json"},method="POST")
            urllib.request.urlopen(req,timeout=3)
        except Exception:
            pass  # MES alert is best-effort; local exception record is authoritative

    def record_exception(self, sn, reason_code, reason_detail, operator_id, supervisor_id="", arrival_id=None):
        code=str(reason_code or "").strip().upper();detail=str(reason_detail or "").strip();operator=str(operator_id or "").strip()
        if code not in EXCEPTION_REASONS:raise ArrivalError("invalid arrival exception reason")
        if not detail:raise ArrivalError("reason_detail required when arrival is not reported")
        if not operator:raise ArrivalError("operator_id required when arrival is not reported")
        if code=="EMERGENCY_RELEASE" and not str(supervisor_id or "").strip():raise ArrivalError("supervisor_id required for emergency release")
        now=int(time.time()*1000);exception_id=str(uuid.uuid4());event_id=str(uuid.uuid4());case_id=str(uuid.uuid4());sn=str(sn or "").strip().upper()
        payload={"type":"SN_ARRIVAL_EXCEPTION","stationCode":self.station_code,"payload":{"exceptionId":exception_id,"arrivalId":arrival_id,"maintenanceCaseId":case_id,"sn":sn,"reasonCode":code,"reasonDetail":detail,"operatorId":operator,"supervisorId":str(supervisor_id or ""),"createdAt":now}}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO arrival_exceptions(exception_id,sn,station_code,arrival_id,reason_code,reason_detail,operator_id,supervisor_id,maintenance_case_id,created_at,mes_synced) VALUES(?,?,?,?,?,?,?,?,?,?,0)",(exception_id,sn,self.station_code,arrival_id,code,detail,operator,str(supervisor_id or ""),case_id,now))
            self.maintenance.open_for_exception(sn,code,detail,operator,exception_id,arrival_id,case_id,db)
            db.execute("INSERT INTO sn_arrival_outbox(event_id,arrival_id,event_type,payload,created_at) VALUES(?,?,?,?,?)",(event_id,arrival_id,"SN_ARRIVAL_EXCEPTION",json.dumps(payload,ensure_ascii=False),now))
        return exception_id

    def sync_once(self, limit=20):
        with self.connect() as db:rows=db.execute("SELECT * FROM sn_arrival_outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT ?",(limit,)).fetchall()
        sent=0
        for row in rows:
            attempted=int(time.time()*1000)
            if row["event_type"]=="SN_ARRIVAL_REPORT" and row["arrival_id"]:
                with self.connect() as db:
                    arrival=db.execute("SELECT sn,arrived_at,operator_id FROM sn_arrivals WHERE arrival_id=?",(row["arrival_id"],)).fetchone()
                    delayed=arrival and attempted-int(arrival["arrived_at"])>self.delayed_report_ms
                    noted=delayed and db.execute("SELECT 1 FROM arrival_exceptions WHERE arrival_id=? AND reason_code='DELAYED_REPORT'",(row["arrival_id"],)).fetchone()
                if delayed and not noted:
                    self.record_exception(arrival["sn"],"DELAYED_REPORT",f'MES report attempted {attempted-int(arrival["arrived_at"])} ms after arrival',arrival["operator_id"] or "SYSTEM",arrival_id=row["arrival_id"])
            try:
                req=urllib.request.Request(self.mes_url,data=row["payload"].encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")
                with urllib.request.urlopen(req,timeout=4) as response:
                    response_body=json.loads(response.read().decode("utf-8") or "{}")
                mes_value=response_body.get("mesReportedAt") or (response_body.get("arrival") or {}).get("mesReportedAt")
                mes_reported=attempted
                if mes_value:
                    try:
                        from datetime import datetime
                        mes_reported=int(datetime.fromisoformat(str(mes_value).replace("Z","+00:00")).timestamp()*1000)
                    except (TypeError,ValueError):
                        mes_reported=attempted
                with self.connect() as db:
                    db.execute("UPDATE sn_arrival_outbox SET first_attempt_at=COALESCE(first_attempt_at,?),last_attempt_at=?,sent_at=?,attempts=attempts+1,last_error='' WHERE event_id=?",(attempted,attempted,attempted,row["event_id"]))
                    if row["arrival_id"]:
                        status="UNEXPECTED_REPORTED" if db.execute("SELECT expected FROM sn_arrivals WHERE arrival_id=?",(row["arrival_id"],)).fetchone()[0]==0 else "REPORTED"
                        db.execute("UPDATE sn_arrivals SET arrival_status=?,report_attempted_at=COALESCE(report_attempted_at,?),mes_reported_at=? WHERE arrival_id=?",(status,attempted,mes_reported,row["arrival_id"]))
                        db.execute("UPDATE expected_sns SET arrival_status=?,arrived_at=COALESCE(arrived_at,?) WHERE station_code=? AND sn=(SELECT sn FROM sn_arrivals WHERE arrival_id=?)",(status,attempted,self.station_code,row["arrival_id"]))
                sent+=1
            except urllib.error.HTTPError as exc:
                if exc.code==409:
                    with self.connect() as db:db.execute("UPDATE sn_arrival_outbox SET first_attempt_at=COALESCE(first_attempt_at,?),last_attempt_at=?,sent_at=?,attempts=attempts+1,last_error='MES idempotent conflict (409)' WHERE event_id=?",(attempted,attempted,attempted,row["event_id"]))
                    sent+=1
                else:self._error(row,attempted,exc)
            except Exception as exc:self._error(row,attempted,exc)
        return sent

    def _error(self,row,attempted,exc):
        with self.connect() as db:
            db.execute("UPDATE sn_arrival_outbox SET first_attempt_at=COALESCE(first_attempt_at,?),last_attempt_at=?,attempts=attempts+1,last_error=? WHERE event_id=?",(attempted,attempted,str(exc)[:300],row["event_id"]))
            if row["arrival_id"]:db.execute("UPDATE sn_arrivals SET arrival_status='REPORT_FAILED',report_attempted_at=COALESCE(report_attempted_at,?) WHERE arrival_id=?",(attempted,row["arrival_id"]))

    def snapshot(self,limit=1000):
        with self.connect() as db:
            return {"expected":[dict(r) for r in db.execute("SELECT * FROM expected_sns WHERE station_code=? ORDER BY expected_at DESC LIMIT ?",(self.station_code,limit))],
                    "arrivals":[dict(r) for r in db.execute("SELECT * FROM sn_arrivals WHERE station_code=? ORDER BY arrived_at DESC LIMIT ?",(self.station_code,limit))],
                    "exceptions":[dict(r) for r in db.execute("SELECT * FROM arrival_exceptions WHERE station_code=? ORDER BY created_at DESC LIMIT ?",(self.station_code,limit))],
                    "outbox":[dict(r) for r in db.execute("SELECT * FROM sn_arrival_outbox ORDER BY created_at DESC LIMIT ?",(limit,))]}
