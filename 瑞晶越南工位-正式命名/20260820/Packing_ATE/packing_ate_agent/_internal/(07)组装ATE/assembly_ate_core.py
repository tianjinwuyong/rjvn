# -*- coding: utf-8 -*-
"""Authoritative business/data core for Assembly ATE.

Both UIs call this module. Excel is the only source of test results; scanner
input only checks duplicate/NG status. Production records flow local -> MES.
"""
from __future__ import annotations

import json
import random
from station_retest import consume_retest_result
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
from station_excel_safe import load_workbook
from station_arrival_core import ArrivalError, StationArrivalStore
from station_history_core import StationHistoryArchive
DB_PATH = Path(os.environ.get("ATE_DB_PATH", str(BASE_DIR / "assembly_ate_agent.db")))
WATCH_DIR = Path(os.environ.get("ATE_WATCH_DIR", os.environ.get("ASSEMBLY_ATE_WATCH_DIR", r"D:\ATS\测试报表")))
MES_URL = os.environ.get("MES_API_URL", "http://192.168.6.155:8080/api/pda/events")
STATION_CODE = os.environ.get("ATE_STATION_CODE", "manu_assem_ate")
NEXT_STATION = os.environ.get("ATE_NEXT_STATION", "manu_supersonic")


class AssemblyAteError(RuntimeError):
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


def _parse_ate_matrix(matrix):
    """Parse rows from CSV/legacy XLS using the same ATE column rules."""
    header = None
    header_row = 0
    for row_no, row in enumerate(matrix[:100], 1):
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
    if not header:
        return []
    parsed = []
    for row_no, row in enumerate(matrix[header_row:], header_row + 1):
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


def _read_legacy_xls_matrix(path):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    workbook = None
    try:
        workbook = win32com.client.GetObject(str(Path(path).resolve()))
        values = workbook.Worksheets(1).UsedRange.Value
        if values is None:
            return []
        if not isinstance(values, tuple):
            return [[values]]
        if values and not isinstance(values[0], tuple):
            return [list(values)]
        return [list(row) for row in values]
    finally:
        workbook = None
        pythoncom.CoUninitialize()


def read_ate_rows(path: Path):
    """Parse tester rows without imposing MES barcode/channel format rules."""
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        import csv
        for encoding in ("utf-8-sig", "gb18030", "cp1252"):
            try:
                with open(path, "r", encoding=encoding, newline="") as handle:
                    return _parse_ate_matrix(list(csv.reader(handle)))
            except UnicodeDecodeError:
                continue
        return []
    if suffix == ".xls":
        try:
            return _parse_ate_matrix(_read_legacy_xls_matrix(path))
        except Exception:
            return []
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


class AssemblyAteCore:
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
            CREATE INDEX IF NOT EXISTS idx_assembly_ate_sn ON ate_results(sn);
            CREATE TABLE IF NOT EXISTS ng_records(
              id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT NOT NULL, source_row INTEGER NOT NULL,
              sn TEXT NOT NULL, side TEXT NOT NULL, channel TEXT NOT NULL, result TEXT NOT NULL,
              error_code TEXT NOT NULL DEFAULT '', test_time TEXT NOT NULL, created_at INTEGER NOT NULL,
              mes_synced INTEGER NOT NULL DEFAULT 0, UNIQUE(source_file,source_row));
            CREATE INDEX IF NOT EXISTS idx_assembly_ng_sn ON ng_records(sn);
            INSERT OR IGNORE INTO ng_records(source_file,source_row,sn,side,channel,result,error_code,test_time,created_at,mes_synced)
              SELECT source_file,source_row,sn,side,channel,result,error_code,test_time,created_at,mes_synced
              FROM ate_results WHERE result='FAIL';
            CREATE TABLE IF NOT EXISTS ingest_checkpoint(source_file TEXT PRIMARY KEY,last_source_row INTEGER NOT NULL DEFAULT 0,updated_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS confirmed_ng(sn TEXT PRIMARY KEY,reason TEXT NOT NULL DEFAULT '',source_station TEXT NOT NULL DEFAULT '',received_at INTEGER NOT NULL);
            INSERT OR IGNORE INTO confirmed_ng(sn,reason,source_station,received_at)
              SELECT sn, 'Assembly ATE NG: ' || error_code, 'manu_assem_ate', created_at FROM ng_records WHERE result='FAIL';
            CREATE TABLE IF NOT EXISTS scanner_checks(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,status TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS blocked_incoming_ng(id INTEGER PRIMARY KEY AUTOINCREMENT,source_file TEXT NOT NULL,source_row INTEGER NOT NULL,sn TEXT NOT NULL,reason TEXT NOT NULL,blocked_at INTEGER NOT NULL,UNIQUE(source_file,source_row));
            CREATE TABLE IF NOT EXISTS mes_outbox(event_id TEXT PRIMARY KEY,event_json TEXT NOT NULL,sent_at INTEGER,retry_count INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS software_change_log(id INTEGER PRIMARY KEY AUTOINCREMENT,change_id TEXT NOT NULL UNIQUE,version TEXT NOT NULL,component TEXT NOT NULL,reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at INTEGER NOT NULL);
            CREATE TRIGGER IF NOT EXISTS software_change_log_no_update BEFORE UPDATE ON software_change_log BEGIN SELECT RAISE(ABORT,'software_change_log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS software_change_log_no_delete BEFORE DELETE ON software_change_log BEGIN SELECT RAISE(ABORT,'software_change_log is append-only'); END;
            """)
            db.execute("INSERT INTO settings(key,value) VALUES('watch_dir',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(self.watch_dir),))
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",
                       ("ASSEMBLY-CORE-001","4.0.0","Core","统一所有工站为 Core + 2D + 3D，并消除对组装 ATE 的运行时耦合",
                        "组装 ATE 独立 Core；Excel 唯一产生测试结果；扫码只检查 NG/重复；本地 SQLite 向 MES 发送", "compile + parser + SQLite integration tests", int(time.time()*1000)))
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",
                       ("ASSEMBLY-CORE-002","4.1.0","Arrival","每个真实到站SN必须完成报到；未报到必须记录原因和时间",
                        "接入全线expected_sns、sn_arrivals、arrival_exceptions及独立持久化报到outbox；2D/3D增加预发、报到和原因页面", "expected/unexpected/duplicate/exception/immutable evidence tests", int(time.time()*1000)))
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",
                       ("ASSEMBLY-CORE-003","4.1.1","Arrival","重复报到、延迟报到和提前报到必须说明原因",
                        "三种异常自动追加原因、操作员、关联报到ID和时间差，并通过报到outbox同步MES", "duplicate/delayed/early automatic reason tests", int(time.time()*1000)))
            db.execute("INSERT OR IGNORE INTO software_change_log(change_id,version,component,reason,summary,verification,changed_at) VALUES(?,?,?,?,?,?,?)",
                       ("ASSEMBLY-CORE-004","4.2.0","Archive/Maintenance","全部历史需要封存并与维修闭环关联",
                        "测试历史进入不可篡改SHA-256哈希链；每个报到异常自动创建本地维修工单和追加式工单事件", "archive hash-chain and exception-maintenance linkage tests", int(time.time()*1000)))

    def set_watch_dir(self, path):
        self.watch_dir = Path(path)
        with self.connect() as db:
            db.execute("INSERT INTO settings(key,value) VALUES('watch_dir',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(self.watch_dir),))

    def latest_files(self):
        if not self.watch_dir.exists():
            return []
        files = []
        # ATE stations may export XLSX, XLSM, or CSV depending on the
        # operator/tester configuration. The old watcher only saw XLSX.
        paths = []
        for pattern in ("*.xlsx", "*.xlsm", "*.xls", "*.csv"):
            paths.extend(self.watch_dir.rglob(pattern))
        for path in paths:
            upper = str(path).upper()
            if path.name.startswith("~$") or "\\统计\\" in upper or path.name.lower() in {"report_collect.xlsx", "report_multi.xlsx"}:
                continue
            if any(token in upper for token in ("HIVOLT-ATE-SIM", "PACKING-ATE-SIM", "\\AGING\\")):
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
        mes_expected_sns, mes_ng_sns = [], []
        manifest_started = int(time.time() * 1000)
        try:
            self.arrivals.refresh_manifest()
            with self.arrivals.connect() as db:
                mes_expected_sns = [str(row[0]) for row in db.execute(
                    "SELECT sn FROM expected_sns WHERE station_code=? AND expected_at>=? ORDER BY expected_at DESC",
                    (STATION_CODE, manifest_started))]
        except Exception as exc:errors.append({"file":"MES expected manifest","error":f"{type(exc).__name__}: {exc}"})
        ng_started = int(time.time() * 1000)
        try:
            self.arrivals.refresh_active_ng()
            with self.arrivals.connect() as db:
                mes_ng_sns = [str(row[0]) for row in db.execute(
                    "SELECT sn FROM mes_active_ng_cache WHERE synced_at>=? ORDER BY synced_at DESC",
                    (ng_started,))]
        except Exception as exc:errors.append({"file":"MES confirmed NG","error":f"{type(exc).__name__}: {exc}"})
        for path in self.latest_files():
            try:
                # Excel reports may arrive one row at a time. The previous
                # eight-row gate left new recordings invisible until a manual
                # partial-ingest action was pressed. read_ate_rows already
                # returns only complete rows, so ingest every new row here.
                added.extend(self.ingest_file(path, allow_partial=True))
            except Exception as exc:
                errors.append({"file": str(path), "error": f"{type(exc).__name__}: {exc}"})
        if added:
            self.archive_pending("自动封存新增组装ATE测试历史", "SYSTEM")
        return {"added": added, "errors": errors, "mes_expected_sns": mes_expected_sns, "mes_ng_sns": mes_ng_sns}

    def refresh_mes_only(self):
        """Refresh MES manifests/NG without scanning the Excel history."""
        expected, ng = [], []
        manifest_started = int(time.time() * 1000)
        self.arrivals.refresh_manifest()
        with self.arrivals.connect() as db:
            expected = [str(row[0]) for row in db.execute(
                "SELECT sn FROM expected_sns WHERE station_code=? AND expected_at>=? ORDER BY expected_at DESC",
                (STATION_CODE, manifest_started))]
        ng_started = int(time.time() * 1000)
        self.arrivals.refresh_active_ng()
        with self.arrivals.connect() as db:
            ng = [str(row[0]) for row in db.execute(
                "SELECT sn FROM mes_active_ng_cache WHERE synced_at>=? ORDER BY synced_at DESC",
                (ng_started,))]
        return {"mes_expected_sns": expected, "mes_ng_sns": ng}

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
            rows=[dict(r) for r in db.execute("SELECT id,source_file,source_row,test_cycle_id,side,channel,sn,result,error_code,test_time,duplicate,created_at FROM ate_results WHERE sn NOT LIKE 'SIM-%' ORDER BY id")]
        return self.history.seal_rows("ate_results",rows,"id",reason,actor) if rows else None

    def _save_row(self, path, row):
        cycle = f'{row["test_time"]}|{row["side"]}'
        now = int(time.time()*1000)
        self.arrivals.record_arrival(row["sn"], "EXCEL", f'{path}#{row["source_row"]}', arrived_at=now)
        with self.lock, self.connect() as db:
            duplicate = bool(db.execute("SELECT 1 FROM ate_results WHERE sn=? LIMIT 1", (row["sn"],)).fetchone())
            try:
                db.execute("INSERT INTO ate_results(source_file,source_row,test_cycle_id,side,channel,sn,result,error_code,test_time,duplicate,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                           (str(path),row["source_row"],cycle,row["side"],row["channel"],row["sn"],row["result"],row["error_code"],row["test_time"],int(duplicate),now))
            except sqlite3.IntegrityError:
                return False
            if row["result"] == "FAIL":
                db.execute("INSERT OR IGNORE INTO ng_records(source_file,source_row,sn,side,channel,result,error_code,test_time,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                           (str(path), row["source_row"], row["sn"], row["side"], row["channel"], row["result"], row["error_code"], row["test_time"], now))
            if row["result"] == "FAIL":
                db.execute("INSERT OR IGNORE INTO confirmed_ng(sn,reason,source_station,received_at) VALUES(?,?,?,?)",
                           (row["sn"], f'Assembly ATE NG: {row["error_code"]}'.strip(), STATION_CODE, now))
            payload = {"type":"SN_SCAN" if row["result"]=="PASS" else "NG_DEFECT","stationCode":STATION_CODE,
                       "payload":{"sn":row["sn"],"result":row["result"],"channel":row["channel"],"side":row["side"],
                                  "testCycleId":cycle,"testTime":row["test_time"],"errorCode":row["error_code"],"duplicate":duplicate,
                                  "eventType":"assembly_ate_xlsx","sourceStationCode":STATION_CODE,"destinationStationCode":NEXT_STATION}}
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
                    "voice":"上游工站不良，禁止测试"}
        if not sn:
            raise AssemblyAteError("SN 不能为空")
        SIX_MONTHS_MS=181*24*3600*1000;now_ms=int(time.time()*1000)
        with self.connect() as db:
            ng = db.execute("SELECT reason,source_station,received_at FROM confirmed_ng WHERE sn=?", (sn,)).fetchone()
            previous = db.execute("SELECT result,test_time,channel FROM ate_results WHERE sn=? ORDER BY id DESC LIMIT 1", (sn,)).fetchone()
            arrival_previous = db.execute("SELECT arrival_status,arrived_at FROM sn_arrivals WHERE station_code=? AND sn=?", (STATION_CODE, sn)).fetchone()
            if ng:
                age_ms=now_ms-ng["received_at"];too_old=age_ms>SIX_MONTHS_MS
                status = "NG_TOO_OLD" if too_old else "NG"
                detail = f'NG记录超过6个月({age_ms//86400000}天)，禁止回修' if too_old else (ng["reason"] or "")
            else:
                status = "DUPLICATE" if (previous or arrival_previous) else "CLEAR"
                detail = (f'{previous["result"]} {previous["test_time"]} {previous["channel"]}' if previous
                          else f'已登记于 {arrival_previous["arrived_at"]}' if arrival_previous else "")
                if status == "DUPLICATE" and consume_retest_result(STATION_CODE, sn, "AUTHORIZED", detail):
                    status = "RETEST_AUTHORIZED"
                    detail = f"Retest authorized: {detail}"
            db.execute("INSERT INTO scanner_checks(sn,status,detail,created_at) VALUES(?,?,?,?)", (sn,status,detail,int(time.time()*1000)))
        # Register the first scan immediately; a later scan is detected above
        # from sn_arrivals even when the tester file has not arrived yet.
        if status != "DUPLICATE" and status != "RETEST_AUTHORIZED":
            self.arrivals.record_arrival(sn, "SCANNER", "manual-scanner")
        return {"sn":sn,"status":status,"detail":detail,"blocked":status in {"NG","NG_TOO_OLD","DUPLICATE"}}

    def snapshot(self, limit=1000):
        with self.connect() as db:
            results=[dict(r) for r in db.execute("SELECT * FROM ate_results ORDER BY id DESC LIMIT ?",(limit,))]
            ng_records=[dict(r) for r in db.execute("SELECT * FROM ng_records ORDER BY id DESC LIMIT ?",(limit,))]
            checks=[dict(r) for r in db.execute("SELECT * FROM scanner_checks ORDER BY id DESC LIMIT 200")]
            outbox=[dict(r) for r in db.execute("SELECT * FROM mes_outbox ORDER BY created_at DESC LIMIT 500")]
            ng=[dict(r) for r in db.execute("SELECT * FROM confirmed_ng ORDER BY received_at DESC LIMIT 500")]
            changes=[dict(r) for r in db.execute("SELECT * FROM software_change_log ORDER BY id DESC")]
        with self.arrivals.connect() as db:
            week_start = int(time.time() * 1000) - 7 * 24 * 3600 * 1000
            mes_ng_cache=[dict(r) for r in db.execute("SELECT sn,source_station,reason,synced_at FROM mes_active_ng_cache WHERE synced_at>=? ORDER BY synced_at DESC, CASE WHEN reason LIKE '%TEST%' OR reason LIKE '%AGENT%' OR reason LIKE '%MES%' THEN 0 ELSE 1 END, sn DESC LIMIT 500", (week_start,))]
        arrival=self.arrivals.snapshot(limit)
        return {"results":results,"ng_records":ng_records,"checks":checks,"outbox":outbox,"ng":ng,"mes_ng_cache":mes_ng_cache,"changes":changes,"arrival":arrival,"history":self.history.snapshot(),"maintenance":self.arrivals.maintenance.snapshot(),
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
                    db.execute("UPDATE ng_records SET mes_synced=1 WHERE sn=? AND test_time=?", (payload.get("sn", ""), payload.get("testTime", "")))
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

    def simulate_excel_row(self, side, index):
        """Append one temporary PASS row to the newest real ATE Excel table."""
        from openpyxl import load_workbook
        paths = self.latest_files()
        if not paths:
            raise AssemblyAteError(f"没有找到实时 ATE 表: {self.watch_dir}")
        path = paths[0]
        wb = load_workbook(path)
        try:
            ws = wb[wb.sheetnames[0]]
            header_row = None
            headers = {}
            for row_no in range(1, min(ws.max_row, 120) + 1):
                values = {str(ws.cell(row_no, col).value or "").strip().upper(): col for col in range(1, ws.max_column + 1)}
                if {"RESULT", "CHANNEL", "BARCODE", "TIME"}.issubset(values):
                    header_row, headers = row_no, values
                    break
            if not header_row:
                raise AssemblyAteError(f"无法识别 ATE 表头: {path.name}")
            row_no = ws.max_row + 1
            now = int(time.time() * 1000)
            sn = f"SIM-{side}-{now}-{index:02d}"
            result = "FAIL" if random.random() < 0.25 else "PASS"
            values = {"RESULT": result, "CHANNEL": f"{side}{index}", "BARCODE": sn,
                      "TIME": time.strftime("%Y-%m-%d/%H:%M:%S"),
                      "ERRORCODE": f"SIM-NG-{random.randint(100, 999)}" if result == "FAIL" else "0"}
            for key, value in values.items():
                if key in headers:
                    ws.cell(row_no, headers[key]).value = value
            wb.save(path)
            return {"path": str(path), "row": row_no, "sn": sn, "channel": f"{side}{index}"}
        finally:
            wb.close()

    def simulate_excel_rows(self, side, count=8):
        """Append a complete L8 or R8 group in one Excel write."""
        from openpyxl import load_workbook
        paths = self.latest_files()
        if not paths:
            raise AssemblyAteError(f"没有找到实时 ATE 表: {self.watch_dir}")
        path = paths[0]
        wb = load_workbook(path)
        records = []
        try:
            ws = wb[wb.sheetnames[0]]
            headers = {}
            for row_no in range(1, min(ws.max_row, 120) + 1):
                values = {str(ws.cell(row_no, col).value or "").strip().upper(): col for col in range(1, ws.max_column + 1)}
                if {"RESULT", "CHANNEL", "BARCODE", "TIME"}.issubset(values):
                    headers = values
                    break
            if not headers:
                raise AssemblyAteError(f"无法识别 ATE 表头: {path.name}")
            now = int(time.time() * 1000)
            for index in range(1, count + 1):
                row_no = ws.max_row + 1
                sn = f"SIM-{side}-{now}-{index:02d}"
                result = "FAIL" if random.random() < 0.25 else "PASS"
                values = {"RESULT": result, "CHANNEL": f"{side}{index}", "BARCODE": sn,
                          "TIME": time.strftime("%Y-%m-%d/%H:%M:%S"),
                          "ERRORCODE": f"SIM-NG-{random.randint(100, 999)}" if result == "FAIL" else "0"}
                for key, value in values.items():
                    if key in headers:
                        ws.cell(row_no, headers[key]).value = value
                records.append({"path": str(path), "row": row_no, "sn": sn, "channel": f"{side}{index}", "result": result})
            wb.save(path)
            return records
        finally:
            wb.close()

    def clear_simulation(self, records):
        from openpyxl import load_workbook
        grouped = {}
        for record in records:
            grouped.setdefault(record["path"], []).append(record["row"])
        for path, rows in grouped.items():
            workbook = load_workbook(path)
            try:
                ws = workbook[workbook.sheetnames[0]]
                for row_no in sorted(rows, reverse=True):
                    ws.delete_rows(row_no, 1)
                with self.connect() as db:
                    db.execute("UPDATE ingest_checkpoint SET last_source_row=?,updated_at=? WHERE source_file=?",
                               (ws.max_row, int(time.time() * 1000), path))
                workbook.save(path)
            finally:
                workbook.close()
        with self.connect() as db:
            sns = [record["sn"] for record in records]
            for record in records:
                db.execute("DELETE FROM ate_results WHERE source_file=? AND source_row=?", (record["path"], record["row"]))
            db.execute("DELETE FROM mes_outbox WHERE event_json LIKE '%assembly_ate_simulation%'")
            for sn in sns:
                db.execute("DELETE FROM ng_records WHERE sn=?", (sn,))
                db.execute("DELETE FROM confirmed_ng WHERE sn=?", (sn,))

    def simulate_mes_downstream(self):
        now = int(time.time() * 1000)
        expected = [f"SIM-MES-NEW-{i:02d}" for i in range(1, 9)]
        ng = [f"SIM-MES-NG-{i:02d}" for i in range(1, 3)]
        with self.arrivals.connect() as db:
            for index, sn in enumerate(expected, 1):
                db.execute("INSERT OR REPLACE INTO expected_sns(station_code,sn,source_station,production_date,expected_at,manifest_version,arrival_status,arrived_at) VALUES(?,?,?,?,?,?,?,NULL)", (STATION_CODE, sn, "MES_SIMULATION", "", now + index, 999999, "EXPECTED"))
            for index, sn in enumerate(ng, 1):
                db.execute("INSERT OR REPLACE INTO mes_active_ng_cache(sn,source_station,reason,snapshot_version,synced_at) VALUES(?,?,?,?,?)", (sn, "MES_SIMULATION", "SIMULATED_MES_NG", 999999, now + index))
        return expected, ng

    def clear_mes_simulation(self, expected, ng):
        with self.arrivals.connect() as db:
            for sn in expected:
                db.execute("DELETE FROM expected_sns WHERE station_code=? AND sn=?", (STATION_CODE, sn))
            for sn in ng:
                db.execute("DELETE FROM mes_active_ng_cache WHERE sn=?", (sn,))

    def _sync_error(self, event_id, exc):
        with self.connect() as db:
            db.execute("UPDATE mes_outbox SET retry_count=retry_count+1,last_error=? WHERE event_id=?",(str(exc)[:300],event_id))
