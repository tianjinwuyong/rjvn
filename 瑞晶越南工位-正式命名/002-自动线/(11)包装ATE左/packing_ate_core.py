# -*- coding: utf-8 -*-
"""Authoritative business/data core for Packaging ATE.

Both UIs call this module. Excel is the only source of test results; scanner
input only checks duplicate/NG status. Production records flow local -> MES.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
MANUAL_LINE_DIR = BASE_DIR.parent
if str(MANUAL_LINE_DIR) not in sys.path:
    sys.path.insert(0, str(MANUAL_LINE_DIR))
SHARED_004 = BASE_DIR.parent.parent / "002-自动线"
if str(SHARED_004) not in sys.path and SHARED_004.exists():
    sys.path.insert(1, str(SHARED_004))
from station_excel_safe import load_workbook
from station_arrival_core import ArrivalError, StationArrivalStore
from station_history_core import StationHistoryArchive
from station_retest import claim_duplicate_retest, consume_retest_result
DB_PATH = BASE_DIR / "packing_ate_agent.db"
WATCH_DIR = Path(r"D:\ATS\测试报表")
MES_URL = os.environ.get("MES_API_URL", "http://192.168.6.155:8080/api/pda/events")
STATION_CODE = "auto_package_ate"
NEXT_STATION = "auto_case_binding"


class PackingAteError(RuntimeError):
    pass


ALIASES = {
    "result": {"RESULT", "TESTRESULT", "测试结果", "结果"},
    "channel": {"CHANNEL", "CH", "POSITION", "SLOT", "STATION", "通道", "位置", "工位"},
    "sn": {"BARCODE", "SN", "SERIALNUMBER", "SERIALNO", "条码", "序列号"},
    "time": {"TIME", "TESTTIME", "DATETIME", "测试时间", "时间"},
    "error": {"ERRORCODE", "ERROR", "FAILITEM", "NGITEM", "错误代码", "不良项目"},
}


def _norm(value):
    return "".join(str(value or "").strip().upper().split()).replace("_", "")


def read_ate_rows(path: Path):
    """Parse tester rows without imposing MES barcode/channel format rules."""
    wb = load_workbook(str(path), read_only=True, data_only=True)
    try:
        ws = wb.active
        header = None
        header_row = 0
        for row_no, row in enumerate(ws.iter_rows(min_row=1, max_row=100, values_only=True), 1):
            cells = [_norm(v) for v in row]
            found = {}
            for field, names in ALIASES.items():
                for index, value in enumerate(cells):
                    if value in names:
                        found[field] = index
                        break
            if {"result", "sn", "time"}.issubset(found):
                header, header_row = found, row_no
                break
        parsed = []
        if not header:
            return parsed
        for row_no, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), header_row + 1):
            values = list(row)
            def val(field, default=""):
                idx = header.get(field)
                return values[idx] if idx is not None and idx < len(values) else default
            sn = str(val("sn") or "").strip().upper()
            result = str(val("result") or "").strip().upper()
            test_time = str(val("time") or "").strip()
            if not sn or not test_time or result not in {"PASS", "FAIL", "NG"}:
                continue
            channel = str(val("channel") or "").strip().upper() or str(row_no - header_row)
            side = channel[:1] if channel[:1] in {"L", "R"} else "S"
            parsed.append({"source_row": row_no, "sn": sn, "result": "FAIL" if result == "NG" else result,
                           "channel": channel, "side": side, "test_time": test_time,
                           "error_code": str(val("error") or "").strip()})
        return parsed
    finally:
        wb.close()


class PackingAteCore:
    def __init__(self, db_path=DB_PATH, watch_dir=WATCH_DIR):
        self.db_path = Path(db_path)
        self.watch_dir = Path(watch_dir)
        self.lock = threading.RLock()
        self.init_db()
        self.arrivals = StationArrivalStore(self.db_path, STATION_CODE, MES_URL)
        self.history = StationHistoryArchive(self.db_path, STATION_CODE)

    def connect(self):
        db = sqlite3.connect(str(self.db_path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def init_db(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS ate_results(
              id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT NOT NULL, source_row INTEGER NOT NULL,
              test_cycle_id TEXT NOT NULL, side TEXT NOT NULL, channel TEXT NOT NULL, sn TEXT NOT NULL,
              result TEXT NOT NULL, error_code TEXT NOT NULL DEFAULT '', test_time TEXT NOT NULL,
              duplicate INTEGER NOT NULL DEFAULT 0, mes_synced INTEGER NOT NULL DEFAULT 0,
              maintenance_status TEXT NOT NULL DEFAULT '', maintenance_work_order TEXT NOT NULL DEFAULT '',
              created_at INTEGER NOT NULL, UNIQUE(source_file,source_row));
            CREATE INDEX IF NOT EXISTS idx_packing_ate_sn ON ate_results(sn);
            CREATE TABLE IF NOT EXISTS ingest_checkpoint(source_file TEXT PRIMARY KEY,last_source_row INTEGER NOT NULL DEFAULT 0,updated_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS confirmed_ng(sn TEXT PRIMARY KEY,reason TEXT NOT NULL DEFAULT '',source_station TEXT NOT NULL DEFAULT '',received_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS scanner_checks(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,status TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS blocked_incoming_ng(id INTEGER PRIMARY KEY AUTOINCREMENT,source_file TEXT NOT NULL,source_row INTEGER NOT NULL,sn TEXT NOT NULL,reason TEXT NOT NULL,blocked_at INTEGER NOT NULL,UNIQUE(source_file,source_row));
            CREATE TABLE IF NOT EXISTS mes_outbox(event_id TEXT PRIMARY KEY,event_json TEXT NOT NULL,sent_at INTEGER,retry_count INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS software_change_log(id INTEGER PRIMARY KEY AUTOINCREMENT,change_id TEXT NOT NULL UNIQUE,version TEXT NOT NULL,component TEXT NOT NULL,reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at INTEGER NOT NULL);
            CREATE TRIGGER IF NOT EXISTS software_change_log_no_update BEFORE UPDATE ON software_change_log BEGIN SELECT RAISE(ABORT,'software_change_log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS software_change_log_no_delete BEFORE DELETE ON software_change_log BEGIN SELECT RAISE(ABORT,'software_change_log is append-only'); END;
            """)
            db.execute("INSERT OR IGNORE INTO settings VALUES('watch_dir',?)", (str(self.watch_dir),))
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",
                       ("PACK-CORE-001","4.0.0","Core","统一所有工站为 Core + 2D + 3D，并消除对组装 ATE 的运行时耦合",
                        "包装 ATE 独立 Core；Excel 唯一产生测试结果；扫码只检查 NG/重复；本地 SQLite 向 MES 发送", "compile + parser + SQLite integration tests", int(time.time()*1000)))
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",
                       ("PACK-CORE-002","4.1.0","Arrival","每个真实到站SN必须完成报到；未报到必须记录原因和时间",
                        "接入全线expected_sns、sn_arrivals、arrival_exceptions及独立持久化报到outbox；2D/3D增加预发、报到和原因页面", "expected/unexpected/duplicate/exception/immutable evidence tests", int(time.time()*1000)))
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",
                       ("PACK-CORE-003","4.1.1","Arrival","重复报到、延迟报到和提前报到必须说明原因",
                        "三种异常自动追加原因、操作员、关联报到ID和时间差，并通过报到outbox同步MES", "duplicate/delayed/early automatic reason tests", int(time.time()*1000)))
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",
                       ("PACK-CORE-004","4.2.0","Archive/Maintenance","全部历史需要封存并与维修闭环关联",
                        "测试历史进入不可篡改SHA-256哈希链；每个报到异常自动创建本地维修工单和追加式工单事件", "archive hash-chain and exception-maintenance linkage tests", int(time.time()*1000)))

    def set_watch_dir(self, path):
        self.watch_dir = Path(path)
        with self.connect() as db:
            db.execute("INSERT INTO settings(key,value) VALUES('watch_dir',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(self.watch_dir),))

    def latest_files(self):
        if not self.watch_dir.exists():
            return []
        files = []
        for path in self.watch_dir.rglob("*.xlsx"):
            upper = str(path).upper()
            if path.name.startswith("~$") or "\\统计\\" in upper or path.name.lower() in {"report_collect.xlsx", "report_multi.xlsx"}:
                continue
            if any(token in upper for token in ("ASSEMBLY-ATE-SIM", "HIVOLT-ATE-SIM", "\\AGING\\")):
                continue
            try:
                if path.stat().st_size:
                    files.append(path)
            except OSError:
                pass
        return sorted(files, key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)

    def ingest_file(self, path, allow_partial=False):
        path = Path(path)
        rows = read_ate_rows(path)
        with self.connect() as db:
            cp = db.execute("SELECT last_source_row FROM ingest_checkpoint WHERE source_file=?", (str(path),)).fetchone()
        last_row = int(cp[0]) if cp else 0
        pending_rows = [row for row in rows if row["source_row"] > last_row]
        if pending_rows and len(pending_rows) < 8 and not allow_partial:
            return []
        inserted = []
        for row in pending_rows:
            try:
                if self._save_row(path, row):
                    inserted.append(row)
            except ArrivalError as exc:
                with self.connect() as db:
                    db.execute("INSERT OR IGNORE INTO blocked_incoming_ng(source_file,source_row,sn,reason,blocked_at) VALUES(?,?,?,?,?)",
                               (str(path),row["source_row"],row["sn"],str(exc),int(time.time()*1000)))
        if rows:
            maximum = max(r["source_row"] for r in rows)
            with self.connect() as db:
                db.execute("INSERT INTO ingest_checkpoint VALUES(?,?,?) ON CONFLICT(source_file) DO UPDATE SET last_source_row=excluded.last_source_row,updated_at=excluded.updated_at", (str(path), maximum, int(time.time()*1000)))
        return inserted

    def ingest_once(self):
        added, errors = [], []
        try:self.arrivals.refresh_manifest()
        except Exception as exc:errors.append({"file":"MES expected manifest","error":f"{type(exc).__name__}: {exc}"})
        for path in self.latest_files():
            try:
                added.extend(self.ingest_file(path))
            except Exception as exc:
                errors.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})
        self.archive_pending("自动封存新增包装ATE测试历史", "SYSTEM")
        return {"added": added, "errors": errors}

    def ingest_partial_once(self):
        """Manually accept the newest incomplete ATE result set (1-7 new rows)."""
        errors = []
        for path in self.latest_files():
            try:
                rows = read_ate_rows(path)
                with self.connect() as db:
                    cp = db.execute(
                        "SELECT last_source_row FROM ingest_checkpoint WHERE source_file=?",
                        (str(path),),
                    ).fetchone()
                last_row = int(cp[0]) if cp else 0
                pending = [row for row in rows if row["source_row"] > last_row]
                if 1 <= len(pending) < 8:
                    added = self.ingest_file(path, allow_partial=True)
                    self.archive_pending("操作员确认部分ATE测试历史", "OPERATOR")
                    return {"added": added, "errors": [], "file": str(path)}
            except Exception as exc:
                errors.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})
        return {"added": [], "errors": errors, "file": ""}

    def archive_pending(self,reason,actor):
        with self.connect() as db:
            rows=[dict(r) for r in db.execute("SELECT id,source_file,source_row,test_cycle_id,side,channel,sn,result,error_code,test_time,duplicate,created_at FROM ate_results ORDER BY id")]
        return self.history.seal_rows("ate_results",rows,"id",reason,actor) if rows else None

    def _save_row(self, path, row):
        cycle = f'{row["test_time"]}|{row["side"]}'
        now = int(time.time()*1000)
        self.arrivals.record_arrival(row["sn"], "EXCEL", f'{path}#{row["source_row"]}', arrived_at=now)
        with self.lock, self.connect() as db:
            duplicate = bool(db.execute("SELECT 1 FROM ate_results WHERE sn=? LIMIT 1", (row["sn"],)).fetchone())
            retest_authorized = bool(duplicate and consume_retest_result(
                STATION_CODE, row["sn"], row["result"], {"sourceFile": str(path)}))
            try:
                db.execute("INSERT INTO ate_results(source_file,source_row,test_cycle_id,side,channel,sn,result,error_code,test_time,duplicate,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                           (str(path),row["source_row"],cycle,row["side"],row["channel"],row["sn"],row["result"],row["error_code"],row["test_time"],int(duplicate),now))
            except sqlite3.IntegrityError:
                return False
            payload = {"type":"SN_SCAN" if row["result"]=="PASS" else "NG_DEFECT","stationCode":STATION_CODE,
                       "payload":{"sn":row["sn"],"result":row["result"],"channel":row["channel"],"side":row["side"],
                                  "testCycleId":cycle,"testTime":row["test_time"],"errorCode":row["error_code"],"duplicate":duplicate,
                                  "retestAuthorized":retest_authorized,"operatorConfirmedRetest":retest_authorized,
                                  "eventType":"packing_ate_xlsx","sourceStationCode":STATION_CODE,"sourceLine":"AUTO_LINE","sourceProcessDomain":"AUTO_LINE","sourceLineCode":"L002","sourceAuto":True,"destinationStationCode":NEXT_STATION}}
            db.execute("INSERT INTO mes_outbox VALUES(?,?,NULL,0,'',?)", (str(uuid.uuid4()),json.dumps(payload,ensure_ascii=False),now))
        return True

    def check_scan(self, raw):
        sn = str(raw or "").strip().upper()
        try:
            self.arrivals.assert_scan_allowed(sn)
        except ArrivalError as exc:
            detail = str(exc)
            with self.connect() as db:
                db.execute("INSERT INTO scanner_checks(sn,status,detail,created_at) VALUES(?,?,?,?)",
                           (sn,"UPSTREAM_NG",detail,int(time.time()*1000)))
            return {"sn":sn,"status":"UPSTREAM_NG","detail":detail,"blocked":True,
                    "voice":"上游工站不良，禁止包装测试"}
        if not sn:
            raise PackingAteError("SN 不能为空")
        SIX_MONTHS_MS=181*24*3600*1000;now_ms=int(time.time()*1000)
        with self.connect() as db:
            ng = db.execute("SELECT reason,source_station,received_at FROM confirmed_ng WHERE sn=?", (sn,)).fetchone()
            previous = db.execute("SELECT result,test_time,channel FROM ate_results WHERE sn=? ORDER BY id DESC LIMIT 1", (sn,)).fetchone()
            if ng:
                age_ms=now_ms-ng["received_at"];too_old=age_ms>SIX_MONTHS_MS
                status = "NG_TOO_OLD" if too_old else "NG"
                detail = f'NG记录超过6个月({age_ms//86400000}天)，禁止回修' if too_old else (ng["reason"] or "")
            else:
                status = "DUPLICATE" if previous else "CLEAR"
                detail = f'{previous["result"]} {previous["test_time"]} {previous["channel"]}' if previous else ""
                if previous and claim_duplicate_retest(STATION_CODE, sn):
                    status, detail = "RETEST_AUTHORIZED", "操作员已确认复检；保留原历史"
            db.execute("INSERT INTO scanner_checks(sn,status,detail,created_at) VALUES(?,?,?,?)", (sn,status,detail,int(time.time()*1000)))
        return {"sn":sn,"status":status,"detail":detail,"blocked":status in {"NG","NG_TOO_OLD","DUPLICATE"}}

    def snapshot(self, limit=1000):
        with self.connect() as db:
            results=[dict(r) for r in db.execute("SELECT * FROM ate_results ORDER BY id DESC LIMIT ?",(limit,))]
            checks=[dict(r) for r in db.execute("SELECT * FROM scanner_checks ORDER BY id DESC LIMIT 200")]
            outbox=[dict(r) for r in db.execute("SELECT * FROM mes_outbox ORDER BY created_at DESC LIMIT 500")]
            ng=[dict(r) for r in db.execute("SELECT * FROM confirmed_ng ORDER BY received_at DESC LIMIT 500")]
            changes=[dict(r) for r in db.execute("SELECT * FROM software_change_log ORDER BY id DESC")]
        arrival=self.arrivals.snapshot(limit)
        return {"results":results,"checks":checks,"outbox":outbox,"ng":ng,"changes":changes,"arrival":arrival,"history":self.history.snapshot(),"maintenance":self.arrivals.maintenance.snapshot(),
                "watch_dir":str(self.watch_dir),"source_connected":self.watch_dir.exists()}

    def sync_once(self, limit=20):
        arrival_sent=self.arrivals.sync_once(limit)
        history_sent=self.history.sync_once(MES_URL,limit)
        maintenance_sent=self.arrivals.maintenance.sync_once(MES_URL,limit)
        with self.connect() as db:
            pending=db.execute("SELECT event_id,event_json FROM mes_outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT ?",(limit,)).fetchall()
        sent=0
        for item in pending:
            try:
                req=urllib.request.Request(MES_URL,data=item["event_json"].encode("utf-8"),headers={"Content-Type":"application/json"},method="POST")
                with urllib.request.urlopen(req,timeout=4) as response:
                    response.read()
                payload=json.loads(item["event_json"]).get("payload",{})
                with self.connect() as db:
                    db.execute("UPDATE mes_outbox SET sent_at=?,retry_count=retry_count+1,last_error='' WHERE event_id=?",(int(time.time()*1000),item["event_id"]))
                    db.execute("UPDATE ate_results SET mes_synced=1 WHERE sn=? AND test_cycle_id=?",(payload.get("sn",""),payload.get("testCycleId","")))
                sent += 1
            except urllib.error.HTTPError as exc:
                if exc.code == 409:
                    with self.connect() as db:
                        db.execute("UPDATE mes_outbox SET sent_at=?,retry_count=retry_count+1,last_error='MES already exists (409)' WHERE event_id=?",(int(time.time()*1000),item["event_id"]))
                    sent += 1
                else:
                    self._sync_error(item["event_id"], exc)
            except Exception as exc:
                self._sync_error(item["event_id"], exc)
        return sent + arrival_sent + history_sent + maintenance_sent

    def _sync_error(self, event_id, exc):
        with self.connect() as db:
            db.execute("UPDATE mes_outbox SET retry_count=retry_count+1,last_error=? WHERE event_id=?",(str(exc)[:300],event_id))
