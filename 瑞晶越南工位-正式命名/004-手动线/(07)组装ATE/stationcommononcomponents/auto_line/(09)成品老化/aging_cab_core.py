# -*- coding: utf-8 -*-
"""Authoritative SQL Server -> SQLite -> MES core for AgingCab station."""
from __future__ import annotations
import hashlib,json,os,re,sqlite3,sys,threading,time,urllib.error,urllib.request,uuid
from pathlib import Path
try:import pyodbc
except ImportError:pyodbc=None
try:import pymysql
except ImportError:pymysql=None

BASE_DIR=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent;MANUAL=BASE_DIR.parent
if str(MANUAL) not in sys.path:sys.path.insert(0,str(MANUAL))
MANUAL_LINE=BASE_DIR.parent.parent/'002-自动线'
if not getattr(sys,'frozen',False) and str(MANUAL_LINE) not in sys.path and MANUAL_LINE.exists():sys.path.insert(1,str(MANUAL_LINE))
from station_arrival_core import ArrivalError, StationArrivalStore
from station_history_core import StationHistoryArchive
from station_retest import claim_duplicate_retest, consume_retest_result

DB_PATH=BASE_DIR/'aging_cab_local.db';STATION_CODE='auto_agingcab';NEXT_STATION='auto_hivolt_ate'
MES_URL=os.environ.get('MES_API_URL','http://192.168.6.155:8080/api/pda/events')
SQL_HOST=os.environ.get('AGING_SQL_HOST','192.168.6.57');SQL_PORT=int(os.environ.get('AGING_SQL_PORT','1433'));SQL_USER=os.environ.get('AGING_SQL_USER','sa');SQL_PASSWORD=os.environ.get('AGING_SQL_PASSWORD','tryhow123456');SQL_DATABASE=os.environ.get('AGING_SQL_DATABASE','AgingCabinet');SQL_TABLE=os.environ.get('AGING_SQL_TABLE','dbo.BI_Test_Result')
MYSQL_HOST=SQL_HOST;MYSQL_PORT=3306;MYSQL_USER='';MYSQL_PASSWORD='';MYSQL_DATABASE=SQL_DATABASE;MYSQL_TABLE=SQL_TABLE;SN_COLUMN='ProductBarcode';RESULT_COLUMN='TestResult';TIME_COLUMN='EndTime'
for _identifier in (SQL_TABLE,SN_COLUMN,RESULT_COLUMN,TIME_COLUMN):
 if not re.fullmatch(r'[A-Za-z0-9_.]+',_identifier):raise ValueError('Unsafe SQL Server identifier')
MEASUREMENTS=('frequency','amplitude','wavetime','energy','power','pcout','par1','par2')
EXPECTED_AGING_MS=int(os.environ.get('AGING_EXPECTED_SECONDS','7200'))*1000

class AgingCabError(RuntimeError):pass

class AgingCabCore:
 def __init__(self,db_path=DB_PATH):
  self.db_path=Path(db_path);self.lock=threading.RLock();self.sql_table=SQL_TABLE;self.sql_connected=False;self.mysql_blocked_until=0;self.warehouse_state=[];self.area_state=[];self.stand_slots=[];self.init_db();self.arrivals=StationArrivalStore(self.db_path,STATION_CODE,MES_URL);self.history=StationHistoryArchive(self.db_path,STATION_CODE)
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
   CREATE TABLE IF NOT EXISTS aging_mysql_cursor(cursor_name TEXT PRIMARY KEY,last_id INTEGER NOT NULL DEFAULT 0,updated_at TEXT);
   CREATE TABLE IF NOT EXISTS aging_native_sessions(cabinet INTEGER NOT NULL,addr INTEGER NOT NULL,sn TEXT NOT NULL,started_at INTEGER,expected_end_at INTEGER,elapsed TEXT,record_time TEXT,current TEXT,voltage TEXT,reason TEXT,state TEXT NOT NULL,updated_at INTEGER NOT NULL,PRIMARY KEY(cabinet,addr));
   CREATE TABLE IF NOT EXISTS aging_batches(batch_id TEXT PRIMARY KEY,started_at INTEGER NOT NULL,expected_end_at INTEGER NOT NULL,completed_at INTEGER,status TEXT NOT NULL,timeout_alarmed_at INTEGER,updated_at INTEGER NOT NULL);
   CREATE TABLE IF NOT EXISTS aging_batch_members(batch_id TEXT NOT NULL,slot INTEGER NOT NULL,sn TEXT NOT NULL,result TEXT,completed_at INTEGER,PRIMARY KEY(batch_id,slot),UNIQUE(batch_id,sn));
   CREATE TABLE IF NOT EXISTS event_outbox(event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',attempts INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL,synced_at INTEGER,last_error TEXT NOT NULL DEFAULT '');
   CREATE TABLE IF NOT EXISTS software_change_log(id INTEGER PRIMARY KEY AUTOINCREMENT,change_id TEXT UNIQUE NOT NULL,version TEXT NOT NULL,component TEXT NOT NULL,reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at INTEGER NOT NULL);
   CREATE TRIGGER IF NOT EXISTS ultra_change_no_update BEFORE UPDATE ON software_change_log BEGIN SELECT RAISE(ABORT,'software history is immutable');END;
   CREATE TRIGGER IF NOT EXISTS ultra_change_no_delete BEFORE DELETE ON software_change_log BEGIN SELECT RAISE(ABORT,'software history is immutable');END;
   ''')
   db.execute("INSERT OR IGNORE INTO software_change_log VALUES(NULL,?,?,?,?,?,?,?)",('ULTRA-001','4.0.0','Core','Remove 2D/3D coupling and preserve the one-SN SQL Server process','Independent SQL collector, local evidence, arrival, maintenance and archive lifecycle','source-row and duplicate/NG integration tests',int(time.time()*1000)))
 def _normalize_result(self,value):
  raw=str(value or '').strip().upper()
  if raw in {'OK','PASS','PASSED','GOOD','TRUE','1'}:return 'OK'
  if raw in {'NG','FAIL','FAILED','NOK','ERROR','FALSE','0'}:return 'NG'
  return ''
 def handle_source_row(self,sn,result,test_time,source_table,measurements=None,simulation=False,source_record_id=None):
  sn=str(sn or '').strip().upper();result=self._normalize_result(result);test_text=str(test_time or '').strip();source=str(source_table or '').strip();measurements={str(k).lower():v for k,v in dict(measurements or {}).items()}
  if not sn or not result or not test_text or not source:raise AgingCabError('SQL row requires PSN, Result, TestDatetime and source table')
  now=int(time.time()*1000);key=hashlib.sha256(f'{sn}|{result}|{test_text}|{source}'.encode()).hexdigest()
  with self.lock,self.connect() as db:
   db.execute('BEGIN IMMEDIATE');duplicate=bool(db.execute('SELECT 1 FROM all_sns WHERE sn=?',(sn,)).fetchone());retest_authorized=bool(duplicate and consume_retest_result(STATION_CODE,sn,'PASS' if result=='OK' else 'FAIL',{'sourceTable':source}))
   values=[measurements.get(x) for x in MEASUREMENTS]
   inserted=db.execute('INSERT OR IGNORE INTO source_results VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(key,sn,result,test_text,source,now,*values)).rowcount
   if not inserted:return {'inserted':False,'duplicateEvent':True,'sn':sn,'result':result}
   if duplicate:db.execute('INSERT INTO duplicate_events(sn,result,test_time,detected_at) VALUES(?,?,?,?)',(sn,result,test_text,now))
   else:db.execute('INSERT INTO all_sns VALUES(?,?,?,?)',(sn,result,test_text,now))
   if result=='NG':db.execute('INSERT INTO confirmed_ng VALUES(?,?,?,?,?) ON CONFLICT(sn) DO NOTHING',(sn,result,test_text,source,now))
   event_id=None
   # Station 57 publishes only genuine, newly-ingested final NG results.
   # PASS remains local for the cursor/duplicate history; simulation never leaves the PC.
   if result=='NG' and not simulation:
    event_id=str(uuid.uuid4());event={'eventId':event_id,'type':'NG_DEFECT','stationCode':STATION_CODE,'payload':{'sn':sn,'result':'FAIL','testTime':test_text,'sourceTable':source,'sourceRecordId':source_record_id,'fixtureNumber':measurements.get('fixture_number'),'fixturePosition':measurements.get('fixture_position'),'simulation':False,'sourceLine':'AUTO_LINE','sourceProcessDomain':'AUTO_LINE','sourceLineCode':'L002','sourceAuto':True}}
    db.execute("INSERT INTO event_outbox VALUES(?,?,?,'PENDING',0,?,NULL,'')",(event_id,event['type'],json.dumps(event,ensure_ascii=False),now))
  return {'inserted':True,'duplicateEvent':duplicate,'sn':sn,'result':result,'eventId':event_id,'queued':bool(event_id)}
 def archive_pending(self):
  with self.connect() as db:rows=[dict(r) for r in db.execute('SELECT * FROM source_results ORDER BY cached_at,event_key')]
  return self.history.seal_rows('source_results',rows,'event_key','老化SQL测试历史自动封存','SYSTEM') if rows else None
 def start_batch(self,sns=None,operator_id='OPERATOR'):
  now=int(time.time()*1000);batch=f'AGING-{time.strftime("%Y%m%d-%H%M%S")}-{now%1000:03d}'
  with self.connect() as db:
   if db.execute("SELECT 1 FROM aging_batches WHERE status IN('AGING','TIMEOUT')").fetchone():raise AgingCabError('已有正在老化的批次')
   db.execute("INSERT INTO aging_batches VALUES(?,?,?,?,?,?,?)",(batch,now,now+EXPECTED_AGING_MS,None,'AGING',None,now))
   for slot,sn in enumerate(list(sns or []),1):db.execute('INSERT INTO aging_batch_members(batch_id,slot,sn) VALUES(?,?,?)',(batch,slot,str(sn).strip().upper()))
  return {'batchId':batch,'startedAt':now,'expectedEndAt':now+EXPECTED_AGING_MS}
 def end_batch(self,batch_id=None,operator_id='OPERATOR'):
  now=int(time.time()*1000)
  with self.connect() as db:
   row=db.execute("SELECT batch_id FROM aging_batches WHERE status IN('AGING','TIMEOUT') AND (? IS NULL OR batch_id=?) ORDER BY started_at DESC LIMIT 1",(batch_id,batch_id)).fetchone()
   if not row:raise AgingCabError('没有正在老化的批次')
   db.execute("UPDATE aging_batches SET status='COMPLETE',completed_at=?,updated_at=? WHERE batch_id=?",(now,now,row[0]));return row[0]
 def check_timeouts(self):
  now=int(time.time()*1000);timed=[]
  with self.connect() as db:
   rows=db.execute("SELECT batch_id FROM aging_batches WHERE status='AGING' AND expected_end_at<=?",(now,)).fetchall()
   for row in rows:db.execute("UPDATE aging_batches SET status='TIMEOUT',timeout_alarmed_at=?,updated_at=? WHERE batch_id=?",(now,now,row[0]));timed.append(row[0])
  return timed
 def check_scan(self,raw):
  sn=str(raw or '').strip().upper()
  try:self.arrivals.assert_scan_allowed(sn)
  except ArrivalError as exc:
   detail=str(exc)
   return {'sn':sn,'status':'UPSTREAM_NG','detail':detail,'blocked':True,'voice':'上游工站不良，禁止老化'}
  if not sn:raise AgingCabError('SN不能为空')
  SIX_MONTHS_MS=181*24*3600*1000;now_ms=int(time.time()*1000)
  with self.connect() as db:
   ng=db.execute('SELECT test_time,source_table,confirmed_at FROM confirmed_ng WHERE sn=?',(sn,)).fetchone();old=db.execute('SELECT first_result,first_test_time FROM all_sns WHERE sn=?',(sn,)).fetchone()
   if ng:
    age_ms=now_ms-ng['confirmed_at'];too_old=age_ms>SIX_MONTHS_MS
    status='NG_TOO_OLD' if too_old else 'NG'
    detail=f'NG记录超过6个月({age_ms//86400000}天)，禁止回修' if too_old else ('确认NG '+ng['test_time'])
   else:
    status='DUPLICATE' if old else 'CLEAR'
    detail='已测试 '+old['first_test_time'] if old else ''
    if old and claim_duplicate_retest(STATION_CODE,sn):status='RETEST_AUTHORIZED';detail='操作员已确认复检；保留原历史'
  return {'sn':sn,'status':status,'detail':detail,'blocked':status in {'NG','NG_TOO_OLD','DUPLICATE'}}
 def discover_table(self,connection):
  if SQL_TABLE:return SQL_TABLE
  cur=connection.cursor();cur.execute("SELECT TOP 1 s.name,t.name FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.columns a ON a.object_id=t.object_id AND a.name='PSN' JOIN sys.columns b ON b.object_id=t.object_id AND b.name='Result' JOIN sys.columns c ON c.object_id=t.object_id AND c.name='TestDatetime' ORDER BY t.name");row=cur.fetchone()
  if not row:raise AgingCabError('No SQL table contains PSN, Result and TestDatetime')
  return f'{row[0]}.{row[1]}'
 def poll_sql_once(self):
  if pyodbc is None:raise AgingCabError('pyodbc is not installed')
  self.arrivals.refresh_manifest();connection=pyodbc.connect('DRIVER={SQL Server};SERVER=%s,%s;DATABASE=%s;UID=%s;PWD=%s;TrustServerCertificate=yes;Encrypt=no;Connection Timeout=5'%(SQL_HOST,SQL_PORT,SQL_DATABASE,SQL_USER,SQL_PASSWORD),timeout=8)
  try:
   table_name=SQL_TABLE;self.sql_table=table_name;schema,table=table_name.split('.',1) if '.' in table_name else ('dbo',table_name)
   with self.connect() as db:row=db.execute("SELECT last_id FROM aging_mysql_cursor WHERE cursor_name='aging_sql_server'").fetchone();last_id=int(row[0]) if row else 0
   if not row:
    # Startup watermark: never replay history on first run.  Persist MAX(ID)
    # as the baseline; only rows inserted after the baseline can be ingested.
    cur=connection.cursor();cur.execute(f'SELECT ISNULL(MAX(ID),0) FROM [{schema}].[{table}]');last_id=max(0,int(cur.fetchone()[0]) or 0)
   cur=connection.cursor();cur.execute('SELECT WarehouseNumber,WarehouseUseNum,WarehouseUseState,InIndex,FileName FROM dbo.WarehouseState ORDER BY WarehouseNumber');warehouse_rows=cur.fetchall()
   self.warehouse_state=[{'warehouseNumber':int(x[0]),'useNumber':int(x[1] or 0),'state':str(x[2] or ''),'inIndex':int(x[3] or 0),'fileName':str(x[4] or '')} for x in warehouse_rows]
   cur=connection.cursor();cur.execute('SELECT StaNumber,leftStaNumber,rightStaNumber,AreaState FROM dbo.A_rergion ORDER BY StaNumber');area_rows=cur.fetchall()
   self.area_state=[{'position':int(x[0]),'leftStand':str(x[1] or '0').strip(),'rightStand':str(x[2] or '0').strip(),'state':str(x[3] or '')} for x in area_rows]
   cur=connection.cursor();cur.execute('SELECT VehicleNumber,Barcodes,Result,VehicleStatus,CreateTime FROM dbo.RuiJjing_FixInfos ORDER BY TRY_CONVERT(int,VehicleNumber)');fix_rows=cur.fetchall()
   cur=connection.cursor();cur.execute('SELECT CardNumber,BarcodeL1,BarcodeL2,BarcodeL3,BarcodeL4,BarcodeL5,BarcodeL6,BarcodeL7,BarcodeL8,BarcodeR1,BarcodeR2,BarcodeR3,BarcodeR4,BarcodeR5,BarcodeR6,BarcodeR7,BarcodeR8,State FROM dbo.BarcodeNumber');barcode_rows=cur.fetchall();barcode_map={str(x[0]):x for x in barcode_rows}
   self.stand_slots=[]
   for x in fix_rows:
    stand=str(x[0] or '').strip();results=(str(x[2] or '').split(';')+['']*20)[:20];barcodes=(str(x[1] or '').split(';')+['']*20)[:20];live=barcode_map.get(stand)
    if live:
     live_codes=[str(v or '').strip() for v in live[1:17]]
     for i,value in enumerate(live_codes):
      if value.upper() not in {'','NULL'}:barcodes[i]=value
    for slot in range(20):self.stand_slots.append({'stand':stand,'slot':slot+1,'sn':barcodes[slot],'result':results[slot],'standState':str(x[3] or ''),'updatedAt':str(x[4] or '')})
   cur=connection.cursor();cur.execute(f'SELECT TOP 500 ID,ProductBarcode,TestResult,EndTime,ModelName,FixturePosition,FixtureNumber FROM [{schema}].[{table}] WHERE ID>? ORDER BY ID ASC',last_id);rows=cur.fetchall();added=0
   for row in rows:
    source=f'{table_name}::{row[4] or ""}'
    result=self.handle_source_row(row[1],row[2],row[3],source,{'fixture_number':row[6],'fixture_position':row[5]},source_record_id=int(row[0]));added+=int(result['inserted']);last_id=int(row[0])
   with self.connect() as db:db.execute("INSERT INTO aging_mysql_cursor VALUES('aging_sql_server',?,?) ON CONFLICT(cursor_name) DO UPDATE SET last_id=excluded.last_id,updated_at=excluded.updated_at",(last_id,time.strftime('%Y-%m-%d %H:%M:%S')))
   self.sql_connected=True;return {'table':table_name,'read':len(rows),'added':added,'warehouseRows':len(self.warehouse_state),'conveyorPositions':len(self.area_state),'standSlots':len(self.stand_slots)}
  finally:connection.close()
 def _mysql_connect(self):
  if pymysql is None:raise AgingCabError('pymysql is not installed')
  remaining=int(self.mysql_blocked_until-time.time())
  if remaining>0:raise AgingCabError(f'MYSQL CIRCUIT OPEN - retry suppressed for {remaining}s; FLUSH HOSTS required')
  try:return pymysql.connect(host=MYSQL_HOST,port=MYSQL_PORT,user=MYSQL_USER,password=MYSQL_PASSWORD,database=MYSQL_DATABASE,connect_timeout=5,read_timeout=8,write_timeout=8,autocommit=True)
  except Exception as exc:
   if getattr(exc,'args',()) and exc.args[0]==1129:self.mysql_blocked_until=time.time()+600
   raise
 def poll_mysql_once(self):
  self.arrivals.refresh_manifest();connection=self._mysql_connect();added=0;native=[]
  try:
   with self.connect() as db:row=db.execute("SELECT last_id FROM aging_mysql_cursor WHERE cursor_name='ps_station_log'").fetchone();last_id=int(row[0]) if row else 0
   with connection.cursor() as cursor:
    if not row:
     # Startup watermark: never replay history on first run.
     cursor.execute(f"SELECT COALESCE(MAX(`id`),0) FROM `{MYSQL_TABLE}`")
     last_id=int(cursor.fetchone()[0] or 0)
    cursor.execute(f"SELECT `id`,`{SN_COLUMN}`,`{RESULT_COLUMN}`,`{TIME_COLUMN}`,`station`,`operator` FROM `{MYSQL_TABLE}` WHERE `id`>%s ORDER BY `id` ASC LIMIT 500",(last_id,));rows=cursor.fetchall()
    for row in rows:
     label=f'{MYSQL_TABLE}::{row[4]}';result=self.handle_source_row(row[1],row[2],row[3],label);added+=int(result['inserted']);last_id=int(row[0])
    cursor.execute('SELECT number,start_time,end_time FROM ps_info ORDER BY id DESC');infos=cursor.fetchall();cursor.execute('SHOW TABLES');tables={str(x[0]) for x in cursor.fetchall()};seen=set()
    for number,start_at,end_at in infos:
     cabinet=int(number)
     if cabinet in seen or cabinet != 1:continue
     seen.add(cabinet);bt=f'ps_barcode_{cabinet}';dt=f'ps_{cabinet}'
     if bt not in tables:continue
     cursor.execute(f"SELECT addr,barcode FROM `{bt}` WHERE COALESCE(barcode,'')<>''")
     for addr,barcode in cursor.fetchall():
      measurement=None
      if dt in tables:cursor.execute(f'SELECT elapsed,record_time,current,voltage,reason FROM `{dt}` WHERE addr=%s ORDER BY id DESC LIMIT 1',(addr,));measurement=cursor.fetchone()
      elapsed,record_time,current,voltage,reason=measurement or (None,None,None,None,None);now=int(time.time()*1000);start=int(start_at.timestamp()*1000) if start_at else None;end=int(end_at.timestamp()*1000) if end_at else None;state='COMPLETE' if end and now>=end else 'AGING';sn=str(barcode).strip().upper();native.append((cabinet,int(addr),sn,start,end,str(elapsed or ''),str(record_time or ''),str(current or ''),str(voltage or ''),str(reason or ''),state,now))
   with self.connect() as db:
    db.execute("INSERT INTO aging_mysql_cursor VALUES('ps_station_log',?,?) ON CONFLICT(cursor_name) DO UPDATE SET last_id=excluded.last_id,updated_at=excluded.updated_at",(last_id,time.strftime('%Y-%m-%d %H:%M:%S')))
    db.executemany('INSERT INTO aging_native_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(cabinet,addr) DO UPDATE SET sn=excluded.sn,started_at=excluded.started_at,expected_end_at=excluded.expected_end_at,elapsed=excluded.elapsed,record_time=excluded.record_time,current=excluded.current,voltage=excluded.voltage,reason=excluded.reason,state=excluded.state,updated_at=excluded.updated_at',native)
   for row in native:
    sn=row[2]
    with self.connect() as db:exists=db.execute('SELECT 1 FROM sn_arrivals WHERE station_code=? AND sn=?',(STATION_CODE,sn)).fetchone()
    if not exists:self.arrivals.record_arrival(sn,'MYSQL_SLOT',f'cabinet={row[0]},slot={row[1]}',arrived_at=row[3] or int(time.time()*1000))
   self.sql_connected=True;return {'table':MYSQL_TABLE,'read':len(rows),'added':added,'native':len(native)}
  finally:connection.close()
 def snapshot(self,limit=1000):
  self.check_timeouts()
  with self.connect() as db:return {'results':[dict(r) for r in db.execute('SELECT * FROM source_results ORDER BY cached_at DESC LIMIT ?',(limit,))],'native':[dict(r) for r in db.execute('SELECT * FROM aging_native_sessions ORDER BY cabinet,addr')],'batches':[dict(r) for r in db.execute('SELECT * FROM aging_batches ORDER BY started_at DESC LIMIT ?',(limit,))],'batch_members':[dict(r) for r in db.execute('SELECT * FROM aging_batch_members ORDER BY batch_id DESC,slot')],'ng':[dict(r) for r in db.execute('SELECT * FROM confirmed_ng ORDER BY confirmed_at DESC LIMIT ?',(limit,))],'duplicates':[dict(r) for r in db.execute('SELECT * FROM duplicate_events ORDER BY id DESC LIMIT ?',(limit,))],'checks':[dict(r) for r in db.execute('SELECT * FROM scanner_checks ORDER BY id DESC LIMIT ?',(limit,))],'outbox':[dict(r) for r in db.execute('SELECT * FROM event_outbox ORDER BY created_at DESC LIMIT ?',(limit,))],'changes':[dict(r) for r in db.execute('SELECT * FROM software_change_log ORDER BY id DESC')],'arrival':self.arrivals.snapshot(limit),'maintenance':self.arrivals.maintenance.snapshot(limit),'history':self.history.snapshot(limit),'sql':{'host':SQL_HOST,'port':SQL_PORT,'database':SQL_DATABASE,'table':self.sql_table,'connected':self.sql_connected,'blockedUntil':0}}
 def sync_once(self,limit=50):
  sent=0
  with self.connect() as db:rows=db.execute("SELECT event_id,event_type,payload FROM event_outbox WHERE status='PENDING' ORDER BY created_at LIMIT ?",(limit,)).fetchall()
  for row in rows:
   try:
    event=json.loads(row['payload'])
    payload=event.get('payload') or {}
    if row['event_type']!='NG_DEFECT' or bool(payload.get('simulation')):
     with self.connect() as db:db.execute("UPDATE event_outbox SET status='SKIPPED',last_error='NOT_ELIGIBLE_FOR_SYNC' WHERE event_id=?",(row['event_id'],))
     continue
    req=urllib.request.Request(MES_URL,data=row['payload'].encode(),headers={'Content-Type':'application/json'},method='POST');urllib.request.urlopen(req,timeout=4).read()
    with self.connect() as db:db.execute("UPDATE event_outbox SET status='SYNCED',attempts=attempts+1,synced_at=?,last_error='' WHERE event_id=?",(int(time.time()*1000),row['event_id']));sent+=1
   except Exception as exc:
    with self.connect() as db:db.execute('UPDATE event_outbox SET attempts=attempts+1,last_error=? WHERE event_id=?',(str(exc)[:300],row['event_id']))
  return sent
