# -*- coding: utf-8 -*-
"""AOI authority: MySQL detection_board → SQLite → MES outbox."""
from __future__ import annotations
import json,os,sqlite3,sys,threading,time,urllib.error,urllib.request
from pathlib import Path

BASE=Path(__file__).resolve().parent;MANUAL=BASE.parent
if str(MANUAL) not in sys.path:sys.path.insert(0,str(MANUAL))
MANUAL_LINE=BASE.parent.parent/'002-自动线'
if str(MANUAL_LINE) not in sys.path and MANUAL_LINE.exists():sys.path.insert(1,str(MANUAL_LINE))
from station_arrival_core import StationArrivalStore
from station_history_core import StationHistoryArchive

STATION_CODE='auto_aio'
NEXT_STATION='auto_fct'
DEFAULT_DB=BASE/'aoi_quality.db'
DEFAULT_MES=os.environ.get('MES_API','http://192.168.6.155:8080/api').rstrip('/')
DEFAULT_MYSQL=dict(host='127.0.0.1',port=3306,user='root',password='root1234',
                   database='pcb_detection',charset='utf8mb4',connect_timeout=5,read_timeout=5)

class AoiError(RuntimeError):pass

class AoiCore:
    def __init__(self,db_path=DEFAULT_DB,mes_api=DEFAULT_MES,mysql_config=None):
        self.db_path=Path(db_path);self.db_path.parent.mkdir(parents=True,exist_ok=True)
        self.mes_api=mes_api;self.mysql_config=mysql_config or dict(DEFAULT_MYSQL)
        self.lock=threading.RLock()
        self.init_db()

    def connect(self):
        db=sqlite3.connect(str(self.db_path),timeout=30);db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL');return db

    def init_db(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sn_records(sn TEXT PRIMARY KEY,first_seen_at INTEGER NOT NULL,last_seen_at INTEGER NOT NULL,scan_count INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS confirmed_ng(sn TEXT PRIMARY KEY,source_station TEXT,batch_id TEXT,defect_code TEXT,status TEXT NOT NULL DEFAULT 'blocked',updated_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS detection_log(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,decision TEXT NOT NULL,detected_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS mysql_sync_state(source_name TEXT PRIMARY KEY,last_id INTEGER NOT NULL DEFAULT 0,updated_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS aoi_outbox(event_id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at INTEGER NOT NULL,sent_at INTEGER,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS software_change_log(id INTEGER PRIMARY KEY AUTOINCREMENT,change_id TEXT UNIQUE NOT NULL,version TEXT NOT NULL,component TEXT NOT NULL,reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at INTEGER NOT NULL);
            CREATE TRIGGER IF NOT EXISTS aoi_ng_no_delete BEFORE DELETE ON confirmed_ng BEGIN SELECT RAISE(ABORT,'AOI evidence cannot be deleted');END;
            CREATE TRIGGER IF NOT EXISTS aoi_change_no_update BEFORE UPDATE ON software_change_log BEGIN SELECT RAISE(ABORT,'software history is immutable');END;
            CREATE TRIGGER IF NOT EXISTS aoi_change_no_delete BEFORE DELETE ON software_change_log BEGIN SELECT RAISE(ABORT,'software history is immutable');END;
            """)
            db.execute("INSERT OR IGNORE INTO software_change_log VALUES(NULL,?,?,?,?,?,?,?)",
                       ('AOI-CORE-001','1.0.0','Core','Migrate to Core/2D/3D unified architecture',
                        'MySQL detection_board → SQLite + MES outbox + arrival + history',
                        'mysql sync, NG/DUP detect, heartbeat',int(time.time()*1000)))

    def post_event(self,event_type,payload,db=None):
        if str(event_type).upper() in {"NG_DEFECT", "NG_CONFIRMED"}:
            payload = dict(payload, sourceLine="AUTO_LINE", sourceProcessDomain="AUTO_LINE",
                           sourceLineCode="L002", sourceAuto=True)
        body=json.dumps({'type':event_type,'stationCode':STATION_CODE,'payload':payload},ensure_ascii=False)
        if db is None:
            with self.connect() as db:
                db.execute('INSERT INTO aoi_outbox(event_id,payload,created_at) VALUES(?,?,?)',
                           (f'aoi-{int(time.time()*1000)}',body,int(time.time()*1000)))
        else:
            # Write on the caller's open connection so the outbox insert is not
            # blocked by the caller's own write transaction (nested writer).
            db.execute('INSERT INTO aoi_outbox(event_id,payload,created_at) VALUES(?,?,?)',
                       (f'aoi-{int(time.time()*1000)}',body,int(time.time()*1000)))
        try:
            req=urllib.request.Request(self.mes_api+'/pda/events',data=body.encode('utf-8'),
                headers={'Content-Type':'application/json'},method='POST')
            urllib.request.urlopen(req,timeout=3).read()
            return True
        except Exception:return False

    def check_scan(self,sn):
        code=str(sn or '').strip().upper()
        if not code:raise AoiError('SN 不能为空')
        SIX_MONTHS_MS=181*24*3600*1000;now_ms=int(time.time()*1000)
        with self.connect() as db:
            ng=db.execute('SELECT updated_at FROM confirmed_ng WHERE UPPER(sn)=UPPER(?) LIMIT 1',(code,)).fetchone()
            cnt=db.execute('SELECT scan_count FROM sn_records WHERE UPPER(sn)=UPPER(?)',(code,)).fetchone()
        if ng:
            age_ms=now_ms-ng[0];too_old=age_ms>SIX_MONTHS_MS
            blocked=True
            status='NG_TOO_OLD' if too_old else 'CONFIRMED_NG'
            detail=f'NG记录超过6个月({age_ms//86400000}天)，禁止回修' if too_old else '本地已标记 NG'
        elif cnt and cnt[0]>1:blocked=False;status,detail='DUPLICATE_MARKED',f'本站已有 {cnt[0]} 次扫描'
        else:blocked=False;status,detail='CLEAR','无 NG/重复记录'
        return {'sn':code,'status':status,'detail':detail,'blocked':blocked}

    def process_mysql(self,batch_limit=500):
        try:import pymysql
        except ImportError:return 0,0,'pymysql not installed'
        now=int(time.time()*1000)
        with self.connect() as db:
            row=db.execute("SELECT last_id FROM mysql_sync_state WHERE source_name='aoi_detection_board'").fetchone()
            last_id=int(row[0]) if row else 0
        try:
            cfg=dict(self.mysql_config);cfg['cursorclass']=pymysql.cursors.DictCursor
            with pymysql.connect(**cfg) as mysql:
                with mysql.cursor() as cursor:
                    if row is None:
                        # Startup watermark: never replay history.  Persist the
                        # current MAX(id) as the baseline and return silently;
                        # only a newly inserted row (id > baseline) can alarm.
                        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM detection_board")
                        baseline=int(cursor.fetchone()[0] or 0)
                        with self.connect() as db:
                            db.execute('INSERT OR REPLACE INTO mysql_sync_state VALUES (?,?,?)',
                                       ('aoi_detection_board',baseline,now))
                        return baseline,0,None
                    cursor.execute("SELECT id,number,pass,finish_time,bcr_codes,total,ng FROM detection_board WHERE id>%s ORDER BY id LIMIT %s",(last_id,batch_limit))
                    rows=cursor.fetchall()
        except Exception as ex:
            return last_id,0,f'MySQL 读取失败: {ex}'
        if not rows:return last_id,0,None
        added=0
        with self.connect() as db:
            for row in rows:
                row_id=int(row['id'])
                sn=str(row.get('number') or row.get('bcr_codes') or '').strip().upper()
                if not sn:
                    last_id=row_id;continue
                old=db.execute('SELECT scan_count FROM sn_records WHERE UPPER(sn)=UPPER(?)',(sn,)).fetchone()
                if old:
                    db.execute('UPDATE sn_records SET last_seen_at=?,scan_count=scan_count+1 WHERE UPPER(sn)=UPPER(?)',(now,sn))
                    decision='DUPLICATE_BLOCKED'
                    self.post_event('DUPLICATE_SN',{'sn':sn,'batchId':f'AOI-MYSQL-{sn}','sourceRowId':row_id})
                else:
                    db.execute('INSERT INTO sn_records VALUES (?,?,?,1)',(sn,now,now))
                    if not bool(row.get('pass')):
                        decision='CONFIRMED_NG'
                        db.execute("INSERT OR REPLACE INTO confirmed_ng VALUES (?, 'auto_aio', ?, 'AOI_NG', 'blocked', ?)",
                                   (sn,f'AOI-{row_id}',now))
                        self.post_event('NG_DEFECT',{'mainSn':sn,'batchId':f'AOI-{row_id}','sourceRowId':row_id,
                            'subBoards':[{'sn':sn,'slot':1,'result':'NG','isConfirmedNG':True,'defectCode':'AOI_NG'}]},db=db)
                    else:
                        decision='PASS'
                db.execute('INSERT INTO detection_log(sn,decision,detected_at) VALUES (?,?,?)',(sn,decision,now))
                last_id=row_id;added+=1
            db.execute('INSERT OR REPLACE INTO mysql_sync_state VALUES (?,?,?)',('aoi_detection_board',last_id,now))
        return last_id,added,None

    def heartbeat(self):
        try:
            body=json.dumps({'type':'AGENT_HEARTBEAT','stationCode':STATION_CODE,
                'payload':{'agent':'aoi_core','status':'running',
                           'sourceConnected':self.db_path.exists(),
                           'source':'mysql','timestamp':int(time.time()*1000)}},ensure_ascii=False).encode('utf-8')
            req=urllib.request.Request(self.mes_api+'/pda/events',data=body,
                headers={'Content-Type':'application/json'},method='POST')
            urllib.request.urlopen(req,timeout=3).read()
            return True
        except Exception:return False

    def sync_outbox(self,limit=20):
        sent=0
        with self.connect() as db:
            rows=db.execute('SELECT * FROM aoi_outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT ?',(limit,)).fetchall()
        for row in rows:
            try:
                req=urllib.request.Request(self.mes_api+'/pda/events',data=row['payload'].encode('utf-8'),
                    headers={'Content-Type':'application/json'},method='POST')
                urllib.request.urlopen(req,timeout=5).read()
                with self.connect() as db:
                    db.execute('UPDATE aoi_outbox SET sent_at=?,attempts=attempts+1,last_error="" WHERE event_id=?',
                               (int(time.time()*1000),row['event_id']))
                sent+=1
            except Exception as ex:
                with self.connect() as db:
                    db.execute('UPDATE aoi_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?',
                               (str(ex)[:300],row['event_id']))
                break
        return sent

    def snapshot(self,limit=200):
        with self.connect() as db:
            total=db.execute('SELECT COUNT(*) FROM sn_records').fetchone()[0]
            confirmed=db.execute("SELECT COUNT(*) FROM confirmed_ng WHERE status='blocked'").fetchone()[0]
            duplicates=db.execute("SELECT COUNT(*) FROM detection_log WHERE decision='DUPLICATE_BLOCKED'").fetchone()[0]
            passed=db.execute("SELECT COUNT(*) FROM detection_log WHERE decision='PASS'").fetchone()[0]
            recent=[dict(r) for r in db.execute('SELECT * FROM detection_log ORDER BY id DESC LIMIT ?',(limit,))]
            outbox=[dict(r) for r in db.execute('SELECT * FROM aoi_outbox ORDER BY created_at DESC LIMIT ?',(limit,))]
            changes=[dict(r) for r in db.execute('SELECT * FROM software_change_log ORDER BY id DESC')]
            state_row=db.execute("SELECT last_id,updated_at FROM mysql_sync_state WHERE source_name='aoi_detection_board'").fetchone()
        return {'total':total,'confirmed':confirmed,'duplicates':duplicates,'passed':passed,
                'recent':recent,'outbox':outbox,'changes':changes,
                'mysql_last_id':state_row['last_id'] if state_row else 0,
                'mysql_last_sync_at':state_row['updated_at'] if state_row else None,
                'station_code':STATION_CODE,'next_station':NEXT_STATION,
                'mes_api':self.mes_api,'db_path':str(self.db_path)}
