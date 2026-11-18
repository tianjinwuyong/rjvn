# -*- coding: utf-8 -*-
"""PDA authority: work-order binding, NG-cache mirror, durable outbox."""
from __future__ import annotations
import json,os,sqlite3,sys,threading,time,urllib.error,urllib.request
from pathlib import Path

BASE=Path(__file__).resolve().parent;MANUAL=BASE.parent
if str(MANUAL) not in sys.path:sys.path.insert(0,str(MANUAL))
AUTO=MANUAL.parent/'002-自动线'
if AUTO.exists() and str(AUTO) not in sys.path:sys.path.insert(0,str(AUTO))
from station_arrival_core import StationArrivalStore
from station_history_core import StationHistoryArchive

STATION_CODE='manu_pda'
NEXT_STATION='manu_ict'
DEFAULT_DB=BASE/'pda_ng_cache.db'
DEFAULT_MES=os.environ.get('MES_API','http://192.168.6.155:8080/api').rstrip('/')

class PdaError(RuntimeError):pass

class PdaCore:
    def __init__(self,db_path=DEFAULT_DB,mes_api=DEFAULT_MES):
        self.db_path=Path(db_path);self.db_path.parent.mkdir(parents=True,exist_ok=True)
        self.mes_api=mes_api;self.lock=threading.RLock()
        self.init_db()

    def connect(self):
        db=sqlite3.connect(str(self.db_path),timeout=30);db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL');return db

    def init_db(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS mes_confirmed_ng_cache(sn TEXT PRIMARY KEY,source_station TEXT,batch_id TEXT,payload TEXT NOT NULL,registry_version INTEGER NOT NULL DEFAULT 0,synced_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS binding_log(id INTEGER PRIMARY KEY AUTOINCREMENT,work_order_code TEXT NOT NULL,qr_code TEXT NOT NULL,bound_by TEXT,bound_at INTEGER NOT NULL,mes_synced INTEGER NOT NULL DEFAULT 0,detail TEXT);
            CREATE TABLE IF NOT EXISTS live_scans(id INTEGER PRIMARY KEY AUTOINCREMENT,time_ms INTEGER NOT NULL,sn TEXT NOT NULL,destination_station TEXT,scan_type TEXT,source TEXT,received_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS duplicate_events(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,detected_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS pda_outbox(event_id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at INTEGER NOT NULL,sent_at INTEGER,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS software_change_log(id INTEGER PRIMARY KEY AUTOINCREMENT,change_id TEXT UNIQUE NOT NULL,version TEXT NOT NULL,component TEXT NOT NULL,reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at INTEGER NOT NULL);
            CREATE TRIGGER IF NOT EXISTS pda_binding_no_delete BEFORE DELETE ON binding_log BEGIN SELECT RAISE(ABORT,'PDA binding log is immutable');END;
            CREATE TRIGGER IF NOT EXISTS pda_change_no_update BEFORE UPDATE ON software_change_log BEGIN SELECT RAISE(ABORT,'software history is immutable');END;
            CREATE TRIGGER IF NOT EXISTS pda_change_no_delete BEFORE DELETE ON software_change_log BEGIN SELECT RAISE(ABORT,'software history is immutable');END;
            """)
            db.execute("INSERT OR IGNORE INTO software_change_log VALUES(NULL,?,?,?,?,?,?,?)",
                       ('PDA-CORE-001','1.0.0','Core','Migrate to Core/2D/3D unified architecture',
                        'Work order binding + NG cache mirror + heartbeat; outbox + arrival + history',
                        'bind, scan, heartbeat, ng-cache sync',int(time.time()*1000)))

    def post_event(self,event_type,payload):
        body=json.dumps({'type':event_type,'stationCode':STATION_CODE,'payload':payload},ensure_ascii=False)
        with self.connect() as db:
            db.execute('INSERT INTO pda_outbox(event_id,payload,created_at) VALUES(?,?,?)',
                       (f'pda-{int(time.time()*1000)}',body,int(time.time()*1000)))
        try:
            req=urllib.request.Request(self.mes_api+'/pda/events',data=body.encode('utf-8'),
                headers={'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req,timeout=5) as r:r.read()
            with self.connect() as db:
                db.execute('UPDATE pda_outbox SET sent_at=? WHERE event_id=(SELECT event_id FROM pda_outbox ORDER BY created_at DESC LIMIT 1)',
                           (int(time.time()*1000),))
            return True
        except Exception as ex:
            with self.connect() as db:
                db.execute('UPDATE pda_outbox SET attempts=attempts+1,last_error=? WHERE event_id=(SELECT event_id FROM pda_outbox ORDER BY created_at DESC LIMIT 1)',
                           (str(ex)[:300],))
            return False

    def check_scan(self,sn):
        code=str(sn or '').strip().upper()
        if not code:raise PdaError('SN 不能为空')
        SIX_MONTHS_MS=181*24*3600*1000
        now_ms=int(time.time()*1000)
        with self.connect() as db:
            cached=db.execute('SELECT synced_at FROM mes_confirmed_ng_cache WHERE UPPER(sn)=UPPER(?) LIMIT 1',(code,)).fetchone()
            previous=db.execute('SELECT 1 FROM live_scans WHERE UPPER(sn)=UPPER(?) LIMIT 1',(code,)).fetchone()
        if cached:
            age_ms=now_ms-cached[0];too_old=age_ms>SIX_MONTHS_MS
            blocked=True
            status='NG_TOO_OLD' if too_old else 'CONFIRMED_NG'
            detail=f'NG记录超过6个月({age_ms//86400000}天)，禁止回修' if too_old else 'MES 缓存中存在 NG'
        elif previous:
            with self.connect() as db:
                db.execute('INSERT INTO duplicate_events(sn,detected_at) VALUES(?,?)',(code,now_ms))
            self.post_event('DUPLICATE_SN',{'sn':code,'destinationStation':NEXT_STATION,'reason':'PDA local scan already registered'})
            blocked=True;status='DUPLICATE';detail='本站已登记此 SN，禁止重复流转'
        else:
            blocked=False;status='CLEAR';detail='MES 缓存无 NG 记录'
        return {'sn':code,'status':status,'detail':detail,'blocked':blocked}

    def bind_workorder(self,work_order,qr_code,bound_by='PDA_OPERATOR'):
        work_order=str(work_order or '').strip()
        qr_code=str(qr_code or '').strip().upper()
        if not work_order or not qr_code:raise PdaError('工单号和二维码不能为空')
        # Active work order
        try:
            body=json.dumps({'stationCode':STATION_CODE,'workOrderCode':work_order,'selectedBy':bound_by},ensure_ascii=False).encode('utf-8')
            req=urllib.request.Request(self.mes_api+'/station/active-workorder',data=body,
                headers={'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req,timeout=6) as r:r.read()
        except urllib.error.HTTPError as ex:
            raise PdaError(f'active-workorder 失败: HTTP {ex.code}')
        # Bind QR
        try:
            body=json.dumps({'stationCode':STATION_CODE,'workOrderCode':work_order,
                'qrCode':qr_code,'qrType':'INCOMING_QR','boundBy':bound_by,
                'detail':{'source':'pda_incoming'}},ensure_ascii=False).encode('utf-8')
            req=urllib.request.Request(self.mes_api+'/station/qr-workorders/bind',data=body,
                headers={'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req,timeout=6) as r:result=json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as ex:
            raise PdaError(f'qr-workorders/bind 失败: HTTP {ex.code}')
        with self.connect() as db:
            db.execute('INSERT INTO binding_log(work_order_code,qr_code,bound_by,bound_at,mes_synced,detail) VALUES(?,?,?,?,1,?)',
                       (work_order,qr_code,bound_by,int(time.time()*1000),json.dumps(result,ensure_ascii=False)))
            db.execute('INSERT INTO live_scans(time_ms,sn,destination_station,scan_type,source,received_at) VALUES(?,?,?,?,?,?)',
                       (int(time.time()*1000),qr_code,NEXT_STATION,'QR_BIND','pda',int(time.time()*1000)))
        return result

    def sync_ng_cache(self,limit=500):
        try:
            url=self.mes_api.replace('/api','')+'/api/station/ng-guard'
            with urllib.request.urlopen(url,timeout=8) as r:data=json.loads(r.read().decode('utf-8'))
            now=int(time.time()*1000);version=int(data.get('version') or 0)
            rows=[]
            for item in data.get('items') or []:
                sn=str(item.get('sn') or '').strip().upper()
                if sn:rows.append((sn,item.get('sourceStationCode') or item.get('stationCode'),
                                   item.get('batchId'),json.dumps(item,ensure_ascii=False),version,now))
            if rows:
                with self.connect() as db:
                    db.executemany('INSERT OR IGNORE INTO mes_confirmed_ng_cache VALUES(?,?,?,?,?,?)',rows[:limit])
                return len(rows)
        except Exception:return 0
        return 0

    def heartbeat(self):
        try:
            body=json.dumps({'type':'AGENT_HEARTBEAT','stationCode':STATION_CODE,
                'payload':{'agent':'pda_core','status':'running',
                           'sourceConnected':self.db_path.exists(),
                           'timestamp':int(time.time()*1000)}},ensure_ascii=False).encode('utf-8')
            req=urllib.request.Request(self.mes_api+'/pda/events',data=body,
                headers={'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req,timeout=3) as r:r.read()
            return True
        except Exception:return False

    def sync_outbox(self,limit=20):
        sent=0
        with self.connect() as db:
            rows=db.execute('SELECT * FROM pda_outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT ?',(limit,)).fetchall()
        for row in rows:
            try:
                req=urllib.request.Request(self.mes_api+'/pda/events',data=row['payload'].encode('utf-8'),
                    headers={'Content-Type':'application/json'},method='POST')
                urllib.request.urlopen(req,timeout=5).read()
                with self.connect() as db:
                    db.execute('UPDATE pda_outbox SET sent_at=?,attempts=attempts+1,last_error="" WHERE event_id=?',
                               (int(time.time()*1000),row['event_id']))
                sent+=1
            except Exception as ex:
                with self.connect() as db:
                    db.execute('UPDATE pda_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?',
                               (str(ex)[:300],row['event_id']))
                break
        return sent

    def record_scan(self,sn,destination_station,scan_type='SN_SCAN',source='pda'):
        with self.connect() as db:
            db.execute('INSERT INTO live_scans(time_ms,sn,destination_station,scan_type,source,received_at) VALUES(?,?,?,?,?,?)',
                       (int(time.time()*1000),str(sn).upper(),destination_station,scan_type,source,int(time.time()*1000)))

    def snapshot(self,limit=100):
        with self.connect() as db:
            active_ng=db.execute('SELECT COUNT(*) FROM mes_confirmed_ng_cache').fetchone()[0]
            bindings=[dict(r) for r in db.execute('SELECT * FROM binding_log ORDER BY bound_at DESC LIMIT ?',(limit,))]
            scans=[dict(r) for r in db.execute('SELECT * FROM live_scans ORDER BY received_at DESC LIMIT ?',(limit,))]
            outbox=[dict(r) for r in db.execute('SELECT * FROM pda_outbox ORDER BY created_at DESC LIMIT ?',(limit,))]
            changes=[dict(r) for r in db.execute('SELECT * FROM software_change_log ORDER BY id DESC')]
        return {'active_ng_count':active_ng,'bindings':bindings,'scans':scans,
                'outbox':outbox,'changes':changes,'station_code':STATION_CODE,
                'next_station':NEXT_STATION,'mes_api':self.mes_api,
                'db_path':str(self.db_path),'source_connected':self.db_path.exists()}
