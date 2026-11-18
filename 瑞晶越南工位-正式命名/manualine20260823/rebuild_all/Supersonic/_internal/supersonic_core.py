# -*- coding: utf-8 -*-
"""Authoritative SQL Server -> SQLite -> MES core for Supersonic station."""
from __future__ import annotations
import hashlib,json,os,re,sqlite3,sys,threading,time,urllib.error,urllib.request,uuid
from pathlib import Path
_IMPORT_STATION_DIR=Path(__file__).resolve().parent
_IMPORT_MANUAL_DIR=_IMPORT_STATION_DIR.parent
_IMPORT_FORMAL_DIR=_IMPORT_MANUAL_DIR.parent
for _p in (_IMPORT_STATION_DIR,_IMPORT_MANUAL_DIR,_IMPORT_FORMAL_DIR):
 if str(_p) not in sys.path:sys.path.insert(0,str(_p))
for _p in _IMPORT_FORMAL_DIR.glob('002-*'):
 if _p.is_dir() and str(_p) not in sys.path:sys.path.insert(0,str(_p));break
from station_retest import consume_retest_result
try:import pyodbc
except ImportError:pyodbc=None

BASE_DIR=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent;MANUAL=BASE_DIR.parent
if str(MANUAL) not in sys.path:sys.path.insert(0,str(MANUAL))
AUTO=MANUAL.parent/'002-自动线'
if AUTO.exists() and str(AUTO) not in sys.path:sys.path.insert(0,str(AUTO))
from station_arrival_core import ArrivalError, StationArrivalStore
from station_history_core import StationHistoryArchive

DB_PATH=BASE_DIR/'supersonic_local.db';STATION_CODE='manu_supersonic';NEXT_STATION='manu_agingcab'
MES_URL=os.environ.get('MES_API_URL','http://192.168.6.155:8080/api/pda/events')
SQL_HOST=os.environ.get('SUPERSONIC_SQL_HOST','192.168.6.96');SQL_PORT=int(os.environ.get('SUPERSONIC_SQL_PORT','1433'))
SQL_DATABASE=os.environ.get('SUPERSONIC_SQL_DATABASE','mesdb');SQL_USER=os.environ.get('SUPERSONIC_SQL_USER','sa');SQL_PASSWORD=os.environ.get('SUPERSONIC_SQL_PASSWORD','888888');SQL_TABLE=os.environ.get('SUPERSONIC_SQL_TABLE','')
SQL_EVENT_QUEUE=os.environ.get('SUPERSONIC_SQL_EVENT_QUEUE','dbo.SupersonicResultQueue')
SQL_EVENT_TIMEOUT_MS=int(os.environ.get('SUPERSONIC_SQL_EVENT_TIMEOUT_MS','1000'))
MEASUREMENTS=('frequency','amplitude','wavetime','energy','power','pcout','par1','par2')

class SupersonicError(RuntimeError):pass

class SupersonicCore:
 def __init__(self,db_path=DB_PATH):
  self.db_path=Path(db_path);self.lock=threading.RLock();self.sql_table='';self.sql_connected=False;self._manifest_refreshed_at=time.monotonic();self._arrival_refresh_started=False;self.init_db();self.arrivals=StationArrivalStore(self.db_path,STATION_CODE,MES_URL);self.history=StationHistoryArchive(self.db_path,STATION_CODE)
 def connect(self):db=sqlite3.connect(str(self.db_path),timeout=30);db.row_factory=sqlite3.Row;db.execute('PRAGMA journal_mode=WAL');return db
 def init_db(self):
  with self.connect() as db:
   db.executescript('''
   CREATE TABLE IF NOT EXISTS source_results(event_key TEXT PRIMARY KEY,sn TEXT NOT NULL,result TEXT NOT NULL,test_time TEXT NOT NULL,source_table TEXT NOT NULL,cached_at INTEGER NOT NULL,frequency TEXT,amplitude TEXT,wavetime TEXT,energy TEXT,power TEXT,pcout TEXT,par1 TEXT,par2 TEXT);
   CREATE INDEX IF NOT EXISTS idx_ultra_results_sn ON source_results(sn);
   CREATE TABLE IF NOT EXISTS all_sns(sn TEXT PRIMARY KEY,first_result TEXT NOT NULL,first_test_time TEXT NOT NULL,first_seen_at INTEGER NOT NULL);
   CREATE TABLE IF NOT EXISTS confirmed_ng(sn TEXT PRIMARY KEY,result TEXT NOT NULL,test_time TEXT NOT NULL,source_table TEXT NOT NULL,confirmed_at INTEGER NOT NULL);
   CREATE TABLE IF NOT EXISTS duplicate_events(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,result TEXT,test_time TEXT,detected_at INTEGER NOT NULL);
   CREATE TABLE IF NOT EXISTS scanner_checks(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,status TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '',created_at INTEGER NOT NULL);
   CREATE TABLE IF NOT EXISTS ingest_checkpoint(source_table TEXT PRIMARY KEY,last_test_time TEXT NOT NULL DEFAULT '',updated_at INTEGER NOT NULL);
   CREATE TABLE IF NOT EXISTS event_outbox(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',attempts INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL,synced_at INTEGER,last_error TEXT NOT NULL DEFAULT '');
   CREATE TABLE IF NOT EXISTS software_change_log(id INTEGER PRIMARY KEY AUTOINCREMENT,change_id TEXT UNIQUE NOT NULL,version TEXT NOT NULL,component TEXT NOT NULL,reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at INTEGER NOT NULL);
   CREATE TRIGGER IF NOT EXISTS ultra_change_no_update BEFORE UPDATE ON software_change_log BEGIN SELECT RAISE(ABORT,'software history is immutable');END;
   CREATE TRIGGER IF NOT EXISTS ultra_change_no_delete BEFORE DELETE ON software_change_log BEGIN SELECT RAISE(ABORT,'software history is immutable');END;
   ''')
   # Migrate the six-column database created by the 202607 build.  Keep its
   # historical rows, then add the measurement columns required by the SQL
   # importer so new 202608 results cannot fail on INSERT.
   cols={row[1] for row in db.execute('PRAGMA table_info(source_results)').fetchall()}
   required={'frequency','amplitude','wavetime','energy','power','pcout','par1','par2'}
   if cols and not required.issubset(cols):
    db.execute('DROP INDEX IF EXISTS idx_ultra_results_sn')
    db.execute('ALTER TABLE source_results RENAME TO source_results_legacy_202607')
    db.execute('CREATE TABLE source_results(event_key TEXT PRIMARY KEY,sn TEXT NOT NULL,result TEXT NOT NULL,test_time TEXT NOT NULL,source_table TEXT NOT NULL,cached_at INTEGER NOT NULL,frequency TEXT,amplitude TEXT,wavetime TEXT,energy TEXT,power TEXT,pcout TEXT,par1 TEXT,par2 TEXT)')
    db.execute('INSERT INTO source_results(event_key,sn,result,test_time,source_table,cached_at) SELECT event_key,sn,result,test_time,source_table,cached_at FROM source_results_legacy_202607')
    db.execute('CREATE INDEX idx_ultra_results_sn ON source_results(sn)')
   db.execute("INSERT OR IGNORE INTO software_change_log VALUES(NULL,?,?,?,?,?,?,?)",('ULTRA-001','4.0.0','Core','Remove 2D/3D coupling and preserve the one-SN SQL Server process','Independent SQL collector, local evidence, arrival, maintenance and archive lifecycle','source-row and duplicate/NG integration tests',int(time.time()*1000)))
 def _normalize_result(self,value):
  raw=str(value or '').strip().upper()
  if raw in {'OK','PASS','PASSED','GOOD','TRUE','1'}:return 'OK'
  if raw in {'NG','FAIL','FAILED','NOK','ERROR','FALSE','0'}:return 'NG'
  return ''
 def handle_source_row(self,sn,result,test_time,source_table,measurements=None):
  sn=str(sn or '').strip().upper();result=self._normalize_result(result);test_text=str(test_time or '').strip();source=str(source_table or '').strip();measurements={str(k).lower():v for k,v in dict(measurements or {}).items()}
  if not sn or not result or not test_text or not source:raise SupersonicError('SQL row requires PSN, Result, TestDatetime and source table')
  now=int(time.time()*1000);key=hashlib.sha256(f'{sn}|{result}|{test_text}|{source}'.encode()).hexdigest()
  arrival_blocked=''
  try:
   self.arrivals.record_arrival(sn,'SQL_SERVER',f'{source}|{test_text}',arrived_at=now)
  except ArrivalError as exc:
   # A previously confirmed NG may block attendance, but must not discard
   # this source result. Preserve the fact and continue the append-only ingest.
   arrival_blocked=str(exc)
  with self.lock,self.connect() as db:
   db.execute('BEGIN IMMEDIATE');duplicate=bool(db.execute('SELECT 1 FROM all_sns WHERE sn=?',(sn,)).fetchone())
   values=[measurements.get(x) for x in MEASUREMENTS]
   inserted=db.execute('INSERT OR IGNORE INTO source_results VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(key,sn,result,test_text,source,now,*values)).rowcount
   if not inserted:return {'inserted':False,'duplicateEvent':True,'sn':sn,'result':result}
   if duplicate:db.execute('INSERT INTO duplicate_events(sn,result,test_time,detected_at) VALUES(?,?,?,?)',(sn,result,test_text,now))
   else:db.execute('INSERT INTO all_sns VALUES(?,?,?,?)',(sn,result,test_text,now))
   if result=='NG':db.execute('INSERT INTO confirmed_ng VALUES(?,?,?,?,?) ON CONFLICT(sn) DO NOTHING',(sn,result,test_text,source,now))
   event_id=str(uuid.uuid4());event={'eventId':event_id,'type':'DUPLICATE_SN' if duplicate else ('SN_SCAN' if result=='OK' else 'NG_DEFECT'),'stationCode':STATION_CODE,'payload':{'sn':sn,'result':'PASS' if result=='OK' else 'FAIL','testTime':test_text,'sourceTable':source,'measurements':measurements,'duplicate':duplicate,'sourceStationCode':STATION_CODE,'destinationStationCode':NEXT_STATION,'returnRequired':result=='NG','returnStationCode':STATION_CODE if result=='NG' else None}}
   event['payload']['arrivalBlocked']=arrival_blocked or None
   db.execute("INSERT INTO event_outbox VALUES(?,?,?,'PENDING',0,?,NULL,'')",(event_id,event['type'],json.dumps(event,ensure_ascii=False),now))
  if result=='NG':
   with self.connect() as db:has_case=db.execute("SELECT 1 FROM maintenance_cases WHERE sn=? AND reason_code='NG_DEFECT'",(sn,)).fetchone()
   if not has_case:self.arrivals.maintenance.open_for_exception(sn,'NG_DEFECT',f'超声测试NG: {test_text} / {source}','SYSTEM')
  return {'inserted':True,'duplicateEvent':duplicate,'sn':sn,'result':result,'eventId':event_id}
 def archive_pending(self):
  with self.connect() as db:rows=[dict(r) for r in db.execute('SELECT * FROM source_results ORDER BY cached_at,event_key')]
  return self.history.seal_rows('source_results',rows,'event_key','超声SQL测试历史自动封存','SYSTEM') if rows else None
 def check_scan(self,raw):
  sn=str(raw or '').strip().upper()
  try:self.arrivals.assert_scan_allowed(sn)
  except ArrivalError as exc:
   detail=str(exc)
   with self.connect() as db:db.execute('INSERT INTO scanner_checks(sn,status,detail,created_at) VALUES(?,?,?,?)',(sn,'UPSTREAM_NG',detail,int(time.time()*1000)))
   return {'sn':sn,'status':'UPSTREAM_NG','detail':detail,'blocked':True,'voice':'上游工站不良，禁止测试'}
  if not sn:raise SupersonicError('SN不能为空')
  SIX_MONTHS_MS=181*24*3600*1000;now_ms=int(time.time()*1000)
  with self.connect() as db:
   ng=db.execute('SELECT test_time,source_table,confirmed_at FROM confirmed_ng WHERE sn=?',(sn,)).fetchone();old=db.execute('SELECT first_result,first_test_time FROM all_sns WHERE sn=?',(sn,)).fetchone();arrival_old=db.execute('SELECT arrived_at FROM sn_arrivals WHERE station_code=? AND sn=?',(STATION_CODE,sn)).fetchone()
   if ng:
    age_ms=now_ms-ng['confirmed_at'];too_old=age_ms>SIX_MONTHS_MS
    status='NG_TOO_OLD' if too_old else 'NG'
    detail=f'NG记录超过6个月({age_ms//86400000}天)，禁止回修' if too_old else ('确认NG '+ng['test_time'])
   else:
    status='DUPLICATE' if (old or arrival_old) else 'CLEAR'
    detail='已测试 '+old['first_test_time'] if old else ''
    if status=='DUPLICATE' and consume_retest_result(STATION_CODE,sn,'AUTHORIZED',detail):
     status='RETEST_AUTHORIZED';detail=f'Retest authorized: {detail}'
   db.execute('INSERT INTO scanner_checks(sn,status,detail,created_at) VALUES(?,?,?,?)',(sn,status,detail,int(time.time()*1000)))
  if status not in {'DUPLICATE','RETEST_AUTHORIZED'}:self.arrivals.record_arrival(sn,'SCANNER','manual-scanner')
  return {'sn':sn,'status':status,'detail':detail,'blocked':status in {'NG','NG_TOO_OLD','DUPLICATE'}}
 def discover_table(self,connection):
  if SQL_TABLE:return SQL_TABLE
  cur=connection.cursor();cur.execute("SELECT TOP 1 s.name,t.name FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.columns a ON a.object_id=t.object_id AND a.name='PSN' JOIN sys.columns b ON b.object_id=t.object_id AND b.name='Result' JOIN sys.columns c ON c.object_id=t.object_id AND c.name='TestDatetime' ORDER BY t.name");row=cur.fetchone()
  if not row:raise SupersonicError('No SQL table contains PSN, Result and TestDatetime')
  return f'{row[0]}.{row[1]}'
 def poll_sql_once(self):
  if pyodbc is None:raise SupersonicError('pyodbc is not installed')
  now=time.monotonic()
  if now-self._manifest_refreshed_at >= 30:
   self.arrivals.refresh_manifest();self._manifest_refreshed_at=now
  connection=pyodbc.connect('DRIVER={SQL Server};SERVER=%s,%s;DATABASE=%s;UID=%s;PWD=%s;TrustServerCertificate=yes;Encrypt=no;Connection Timeout=5'%(SQL_HOST,SQL_PORT,SQL_DATABASE,SQL_USER,SQL_PASSWORD),timeout=8)
  try:
   table_name=self.discover_table(connection);self.sql_table=table_name;schema,table=table_name.split('.',1) if '.' in table_name else ('dbo',table_name)
   with self.connect() as db:cp=db.execute('SELECT last_test_time FROM ingest_checkpoint WHERE source_table=?',(table_name,)).fetchone();watermark=cp[0] if cp else ''
   cur=connection.cursor()
   if not watermark:
    # First startup: import only the newest result so the operator sees the
    # current tester state immediately.  Do not replay the historical table.
    cur.execute(f'SELECT TOP 1 PSN,Result,TestDatetime,Frequency,Amplitude,Wavetime,Energy,Power,PCout,Par1,Par2 FROM [{schema}].[{table}] ORDER BY TestDatetime DESC')
    latest=cur.fetchone();rows=[latest] if latest else []
   else:
    cur.execute(f'SELECT TOP 500 PSN,Result,TestDatetime,Frequency,Amplitude,Wavetime,Energy,Power,PCout,Par1,Par2 FROM [{schema}].[{table}] WHERE TestDatetime > ? ORDER BY TestDatetime ASC',(watermark,));rows=cur.fetchall()
   added=0;maximum=watermark
   # Refresh the MES NG snapshot once per SQL batch; do not perform a network
   # refresh for every source row while importing a large result set.
   if not self._arrival_refresh_started:
    self._arrival_refresh_started=True
    threading.Thread(target=self.arrivals.refresh_active_ng,args=(2000,),daemon=True).start()
   arrival_store=self.arrivals
   skipped=0
   for row in rows:
    try:
     result=self.handle_source_row(row[0],row[1],row[2],table_name,dict(zip(MEASUREMENTS,row[3:11])));added+=int(result['inserted']);maximum=max(maximum,str(row[2]))
    except SupersonicError:
     skipped+=1
   arrival_store._last_ng_refresh=int(time.time()*1000)
   with self.connect() as db:db.execute('INSERT INTO ingest_checkpoint VALUES(?,?,?) ON CONFLICT(source_table) DO UPDATE SET last_test_time=excluded.last_test_time,updated_at=excluded.updated_at',(table_name,maximum,int(time.time()*1000)))
   self.sql_connected=True;return {'table':table_name,'read':len(rows),'added':added,'skipped':skipped}
  finally:connection.close()
 def wait_for_sql_event(self, timeout_ms=SQL_EVENT_TIMEOUT_MS):
  """Block on a SQL Server Service Broker queue until a source-row event arrives.

  The queue/trigger are installed separately by the DBA.  This method never
  falls back to polling; after an event, the caller may read the changed rows
  using the normal watermark query.
  """
  if pyodbc is None:raise SupersonicError('pyodbc is not installed')
  connection=pyodbc.connect('DRIVER={SQL Server};SERVER=%s,%s;DATABASE=%s;UID=%s;PWD=%s;TrustServerCertificate=yes;Encrypt=no;Connection Timeout=5'%(SQL_HOST,SQL_PORT,SQL_DATABASE,SQL_USER,SQL_PASSWORD),timeout=8,autocommit=True)
  try:
   timeout_ms=max(100,int(timeout_ms));queue_parts=SQL_EVENT_QUEUE.split('.',1)
   if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',part) for part in queue_parts):raise SupersonicError('Invalid SQL event queue identifier')
   queue_sql='].['.join(queue_parts);cur=connection.cursor();cur.execute('WAITFOR (RECEIVE TOP (1) conversation_handle,message_type_name,message_body FROM [%s]), TIMEOUT %d'%(queue_sql,timeout_ms));row=cur.fetchone()
   if not row:return {'received':False,'message_type':'','conversation_handle':None}
   handle=row[0]
   if handle:
    try:cur.execute('END CONVERSATION ?',handle)
    except Exception:pass
   self.sql_connected=True
   return {'received':True,'message_type':str(row[1] or ''),'conversation_handle':str(handle or '')}
  finally:connection.close()
 def snapshot(self,limit=300):
  with self.connect() as db:return {'results':[dict(r) for r in db.execute('SELECT * FROM source_results ORDER BY cached_at DESC LIMIT ?',(limit,))],'ng':[dict(r) for r in db.execute('SELECT * FROM confirmed_ng ORDER BY confirmed_at DESC LIMIT ?',(min(limit,10),))],'duplicates':[dict(r) for r in db.execute('SELECT * FROM duplicate_events ORDER BY id DESC LIMIT ?',(limit,))],'checks':[dict(r) for r in db.execute('SELECT * FROM scanner_checks ORDER BY id DESC LIMIT ?',(limit,))],'outbox':[dict(r) for r in db.execute('SELECT * FROM event_outbox ORDER BY created_at DESC LIMIT ?',(limit,))],'changes':[dict(r) for r in db.execute('SELECT * FROM software_change_log ORDER BY id DESC')],'arrival':self.arrivals.snapshot(limit),'maintenance':self.arrivals.maintenance.snapshot(limit),'history':self.history.snapshot(limit),'sql':{'host':SQL_HOST,'port':SQL_PORT,'database':SQL_DATABASE,'table':self.sql_table,'connected':self.sql_connected}}
 def sync_once(self,limit=50):
  sent=self.arrivals.sync_once(limit)+self.arrivals.maintenance.sync_once(MES_URL,limit)+self.history.sync_once(MES_URL,limit)
  with self.connect() as db:rows=db.execute("SELECT event_id,payload FROM event_outbox WHERE status='PENDING' ORDER BY created_at LIMIT ?",(limit,)).fetchall()
  for row in rows:
   try:
    req=urllib.request.Request(MES_URL,data=row['payload'].encode(),headers={'Content-Type':'application/json'},method='POST');urllib.request.urlopen(req,timeout=4).read()
    with self.connect() as db:db.execute("UPDATE event_outbox SET status='SYNCED',attempts=attempts+1,synced_at=?,last_error='' WHERE event_id=?",(int(time.time()*1000),row['event_id']));sent+=1
   except Exception as exc:
    with self.connect() as db:db.execute('UPDATE event_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?',(str(exc)[:300],row['event_id']))
  return sent
