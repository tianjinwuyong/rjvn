# -*- coding: utf-8 -*-
"""Authoritative SQL Server -> SQLite -> MES core for AgingCab station."""
from __future__ import annotations
import hashlib,json,os,re,sqlite3,sys,threading,time,urllib.error,urllib.request,uuid
from station_retest import consume_retest_result
from pathlib import Path
try:import pyodbc
except ImportError:pyodbc=None
try:import pymysql
except ImportError:pymysql=None
try:
 from openpyxl import load_workbook
except ImportError:
 load_workbook=None

BASE_DIR=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent;MANUAL=BASE_DIR.parent
if str(MANUAL) not in sys.path:sys.path.insert(0,str(MANUAL))
from station_arrival_core import ArrivalError, StationArrivalStore
from station_history_core import StationHistoryArchive

DB_PATH=BASE_DIR/'aging_cab_local.db';STATION_CODE='manu_agingcab';NEXT_STATION='manu_hivolt_ate'
def _default_aging_record_dir():
 for candidate in (BASE_DIR/'record',BASE_DIR.parent/'record',Path(r'D:\PowerSupply\record')):
  if candidate.exists():return candidate
 return BASE_DIR/'record'
AGING_RECORD_DIR=Path(os.environ.get('AGING_RECORD_DIR',str(_default_aging_record_dir())))
MES_URL=os.environ.get('MES_API_URL','http://192.168.6.155:8080/api/pda/events')
MYSQL_HOST=os.environ.get('AGING_MYSQL_HOST','192.168.6.97');MYSQL_PORT=int(os.environ.get('AGING_MYSQL_PORT','3306'));MYSQL_USER=os.environ.get('AGING_MYSQL_USER','root');MYSQL_PASSWORD=os.environ.get('AGING_MYSQL_PASSWORD','8712234');MYSQL_DATABASE=os.environ.get('AGING_MYSQL_DATABASE','ps');MYSQL_TABLE=os.environ.get('AGING_MYSQL_TABLE','ps_station_log');SN_COLUMN=os.environ.get('AGING_SN_COLUMN','sn');RESULT_COLUMN=os.environ.get('AGING_RESULT_COLUMN','result');TIME_COLUMN=os.environ.get('AGING_TIME_COLUMN','tested_at')
for _identifier in (MYSQL_TABLE,SN_COLUMN,RESULT_COLUMN,TIME_COLUMN):
 if not re.fullmatch(r'[A-Za-z0-9_]+',_identifier):raise ValueError('Unsafe MySQL identifier')
SQL_HOST=os.environ.get('AGING_SQL_HOST','192.168.6.56');SQL_PORT=int(os.environ.get('AGING_SQL_PORT','1433'));SQL_DATABASE=os.environ.get('AGING_SQL_DATABASE','mesdb');SQL_USER=os.environ.get('AGING_SQL_USER','sa');SQL_PASSWORD=os.environ.get('AGING_SQL_PASSWORD','888888');SQL_TABLE=os.environ.get('AGING_SQL_TABLE','')
MEASUREMENTS=('frequency','amplitude','wavetime','energy','power','pcout','par1','par2')
EXPECTED_AGING_MS=int(os.environ.get('AGING_EXPECTED_SECONDS','7200'))*1000

class AgingCabError(RuntimeError):pass

class AgingCabCore:
 def __init__(self,db_path=DB_PATH):
  self.db_path=Path(db_path);self.lock=threading.RLock();self.sql_table=MYSQL_TABLE;self.sql_connected=False;self.mysql_blocked_until=0;self.warehouse_state=[];self.area_state=[];self.stand_slots=[];self.init_db();self.arrivals=StationArrivalStore(self.db_path,STATION_CODE,MES_URL);self.history=StationHistoryArchive(self.db_path,STATION_CODE)
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
   CREATE TABLE IF NOT EXISTS aging_excel_cursor(source_path TEXT PRIMARY KEY,file_size INTEGER NOT NULL DEFAULT 0,modified_ns INTEGER NOT NULL DEFAULT 0,last_imported_at INTEGER NOT NULL DEFAULT 0,rows_imported INTEGER NOT NULL DEFAULT 0);
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
 def handle_source_row(self,sn,result,test_time,source_table,measurements=None,emit_event=True):
  sn=str(sn or '').strip().upper();result=self._normalize_result(result);test_text=str(test_time or '').strip();source=str(source_table or '').strip();measurements={str(k).lower():v for k,v in dict(measurements or {}).items()}
  if not sn or not result or not test_text or not source:raise AgingCabError('SQL row requires PSN, Result, TestDatetime and source table')
  now=int(time.time()*1000);key=hashlib.sha256(f'{sn}|{result}|{test_text}|{source}'.encode()).hexdigest()
  with self.connect() as arrival_db:arrival_exists=arrival_db.execute('SELECT 1 FROM sn_arrivals WHERE station_code=? AND sn=?',(STATION_CODE,sn)).fetchone()
  if not arrival_exists:
   try:self.arrivals.record_arrival(sn,'MYSQL',f'{source}|{test_text}',arrived_at=now)
   except ArrivalError:pass
  with self.lock,self.connect() as db:
   db.execute('BEGIN IMMEDIATE');duplicate=bool(db.execute('SELECT 1 FROM all_sns WHERE sn=?',(sn,)).fetchone())
   values=[measurements.get(x) for x in MEASUREMENTS]
   inserted=db.execute('INSERT OR IGNORE INTO source_results VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(key,sn,result,test_text,source,now,*values)).rowcount
   if not inserted:return {'inserted':False,'duplicateEvent':True,'sn':sn,'result':result}
   if duplicate:db.execute('INSERT INTO duplicate_events(sn,result,test_time,detected_at) VALUES(?,?,?,?)',(sn,result,test_text,now))
   else:db.execute('INSERT INTO all_sns VALUES(?,?,?,?)',(sn,result,test_text,now))
   if result=='NG':db.execute('INSERT INTO confirmed_ng VALUES(?,?,?,?,?) ON CONFLICT(sn) DO NOTHING',(sn,result,test_text,source,now))
   event_id=str(uuid.uuid4());event={'eventId':event_id,'type':'DUPLICATE_SN' if duplicate else ('SN_SCAN' if result=='OK' else 'NG_DEFECT'),'stationCode':STATION_CODE,'payload':{'sn':sn,'result':'PASS' if result=='OK' else 'FAIL','testTime':test_text,'sourceTable':source,'measurements':measurements,'duplicate':duplicate,'sourceStationCode':STATION_CODE,'destinationStationCode':NEXT_STATION,'returnRequired':result=='NG','returnStationCode':STATION_CODE if result=='NG' else None}}
   if emit_event:db.execute("INSERT INTO event_outbox VALUES(?,?,?,'PENDING',0,?,NULL,'')",(event_id,event['type'],json.dumps(event,ensure_ascii=False),now))
  if result=='NG' and emit_event:
   with self.connect() as db:has_case=db.execute("SELECT 1 FROM maintenance_cases WHERE sn=? AND reason_code='NG_DEFECT'",(sn,)).fetchone()
   if not has_case:self.arrivals.maintenance.open_for_exception(sn,'NG_DEFECT',f'老化测试NG: {test_text} / {source}','SYSTEM')
  return {'inserted':True,'duplicateEvent':duplicate,'sn':sn,'result':result,'eventId':event_id}
 def _excel_value(self,value):
  if value is None:return ''
  if hasattr(value,'isoformat'):return value.isoformat(sep=' ')
  return str(value).strip()
 def _excel_file_rows(self,path):
  if load_workbook is None:raise AgingCabError('openpyxl is not installed; Excel import is disabled')
  workbook=load_workbook(path,read_only=True,data_only=True)
  try:
   if 'General Info' not in workbook.sheetnames:return []
   ws=workbook['General Info'];completed=self._excel_value(ws['D5'].value) or self._excel_value(ws['D4'].value) or path.stem
   rows=[]
   for row in range(12,ws.max_row+1):
    slot=ws.cell(row,1).value;sn=self._excel_value(ws.cell(row,2).value).upper();result=self._normalize_result(ws.cell(row,3).value)
    # Excel is the aging-cab NG evidence source only.  PASS rows are already
    # represented by the controller/MySQL stream and must not be replayed as
    # new station arrivals.
    if result!='NG' or not sn:continue
    abnormal=self._excel_value(ws.cell(row,4).value);reason=self._excel_value(ws.cell(row,5).value)
    if abnormal in {'','--','-'}:abnormal=''
    if reason in {'','--','-'}:reason=''
    measurements={'reason':reason or abnormal,'slot':slot,'product':self._excel_value(ws['B3'].value),'cabinet':self._excel_value(ws['D3'].value)}
    rows.append((sn,result,completed,f'EXCEL::{path}::General Info::{row}',measurements))
   return rows
  finally:workbook.close()
 def poll_excel_once(self,root=None,limit=100000):
  root=Path(root or AGING_RECORD_DIR);report={'root':str(root),'files':0,'read':0,'added':0,'silent':False}
  if load_workbook is None:return dict(report,error='openpyxl is not installed')
  if not root.exists():return dict(report,error='record directory not found')
  files=sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in {'.xlsx','.xlsm'})
  with self.connect() as db:
   known={str(r['source_path']):dict(r) for r in db.execute('SELECT * FROM aging_excel_cursor')}
  first_import=not known
  report['silent']=first_import
  for path in files:
   if report['read']>=limit:break
   try:stat=path.stat();key=str(path.resolve());old=known.get(key)
   except OSError:continue
   if old and int(old['file_size'])==stat.st_size and int(old['modified_ns'])==stat.st_mtime_ns:continue
   try:rows=self._excel_file_rows(path)
   except Exception as exc:
    report['files']+=1;continue
   imported=0
   for sn,result,test_time,source,measurements in rows:
    if report['read']>=limit:break
    outcome=self.handle_source_row(sn,result,test_time,source,measurements,emit_event=not first_import)
    report['read']+=1;imported+=1;report['added']+=int(outcome['inserted'])
   with self.connect() as db:db.execute('INSERT INTO aging_excel_cursor(source_path,file_size,modified_ns,last_imported_at,rows_imported) VALUES(?,?,?,?,?) ON CONFLICT(source_path) DO UPDATE SET file_size=excluded.file_size,modified_ns=excluded.modified_ns,last_imported_at=excluded.last_imported_at,rows_imported=excluded.rows_imported',(key,stat.st_size,stat.st_mtime_ns,int(time.time()*1000),imported))
   report['files']+=1
  return report
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
   with self.connect() as db:db.execute('INSERT INTO scanner_checks(sn,status,detail,created_at) VALUES(?,?,?,?)',(sn,'UPSTREAM_NG',detail,int(time.time()*1000)))
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
    if status=='DUPLICATE' and consume_retest_result(STATION_CODE,sn,'AUTHORIZED',detail):
     status='RETEST_AUTHORIZED';detail=f'Retest authorized: {detail}'
   db.execute('INSERT INTO scanner_checks(sn,status,detail,created_at) VALUES(?,?,?,?)',(sn,status,detail,int(time.time()*1000)))
  return {'sn':sn,'status':status,'detail':detail,'blocked':status in {'NG','NG_TOO_OLD','DUPLICATE'}}
 def discover_table(self,connection):
  if SQL_TABLE:return SQL_TABLE
  cur=connection.cursor();cur.execute("SELECT TOP 1 s.name,t.name FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.columns a ON a.object_id=t.object_id AND a.name='PSN' JOIN sys.columns b ON b.object_id=t.object_id AND b.name='Result' JOIN sys.columns c ON c.object_id=t.object_id AND c.name='TestDatetime' ORDER BY t.name");row=cur.fetchone()
  if not row:raise AgingCabError('No SQL table contains PSN, Result and TestDatetime')
  return f'{row[0]}.{row[1]}'
 def poll_sql_once(self):
  if pyodbc is None:raise AgingCabError('pyodbc is not installed')
  try:self.arrivals.refresh_manifest()
  except Exception:pass
  connection=pyodbc.connect('DRIVER={SQL Server};SERVER=%s,%s;DATABASE=%s;UID=%s;PWD=%s;TrustServerCertificate=yes;Encrypt=no;Connection Timeout=5'%(SQL_HOST,SQL_PORT,SQL_DATABASE,SQL_USER,SQL_PASSWORD),timeout=8)
  try:
   table_name=self.discover_table(connection);self.sql_table=table_name;schema,table=table_name.split('.',1) if '.' in table_name else ('dbo',table_name)
   with self.connect() as db:cp=db.execute('SELECT last_test_time FROM ingest_checkpoint WHERE source_table=?',(table_name,)).fetchone();watermark=cp[0] if cp else ''
   cur=connection.cursor()
   if not watermark:
    # Startup watermark: never replay history on first run.  Persist the
    # latest TestDatetime as the baseline and stay silent.
    cur.execute(f'SELECT TOP 1 TestDatetime FROM [{schema}].[{table}] ORDER BY TestDatetime DESC')
    top=cur.fetchone();watermark=str(top[0]) if top and top[0] is not None else '';rows=[]
   else:
    cur.execute(f'SELECT TOP 500 PSN,Result,TestDatetime,Frequency,Amplitude,Wavetime,Energy,Power,PCout,Par1,Par2 FROM [{schema}].[{table}] WHERE TestDatetime > ? ORDER BY TestDatetime ASC',(watermark,));rows=cur.fetchall()
   added=0;maximum=watermark
   for row in rows:
    result=self.handle_source_row(row[0],row[1],row[2],table_name,dict(zip(MEASUREMENTS,row[3:11])));added+=int(result['inserted']);maximum=max(maximum,str(row[2]))
   with self.connect() as db:db.execute('INSERT INTO ingest_checkpoint VALUES(?,?,?) ON CONFLICT(source_table) DO UPDATE SET last_test_time=excluded.last_test_time,updated_at=excluded.updated_at',(table_name,maximum,int(time.time()*1000)))
   self.sql_connected=True;return {'table':table_name,'read':len(rows),'added':added}
  finally:connection.close()
 def _mysql_connect(self):
  if pymysql is None:raise AgingCabError('pymysql is not installed')
  remaining=int(self.mysql_blocked_until-time.time())
  if remaining>0:raise AgingCabError(f'MYSQL CIRCUIT OPEN - retry suppressed for {remaining}s; FLUSH HOSTS required')
  # The factory aging controller runs an older MySQL build that does not
  # advertise utf8mb4.  PyMySQL now defaults to utf8mb4, so request the
  # controller-compatible utf8 charset explicitly.
  try:return pymysql.connect(host=MYSQL_HOST,port=MYSQL_PORT,user=MYSQL_USER,password=MYSQL_PASSWORD,database=MYSQL_DATABASE,charset='utf8',connect_timeout=5,read_timeout=8,write_timeout=8,autocommit=True)
  except Exception as exc:
   if getattr(exc,'args',()) and exc.args[0]==1129:self.mysql_blocked_until=time.time()+600
   raise
 def poll_mysql_once(self):
  try:self.arrivals.refresh_manifest()
  except Exception:pass
  connection=self._mysql_connect();added=0;native=[]
  try:
   with self.connect() as db:row=db.execute("SELECT last_id FROM aging_mysql_cursor WHERE cursor_name='ps_station_log'").fetchone();last_id=int(row[0]) if row else None
   with connection.cursor() as cursor:
    if last_id is None:
     # Startup watermark: never replay history on first run.  Persist MAX(id)
     # as the baseline and stay silent; only newly inserted rows can alarm.
     cursor.execute(f"SELECT COALESCE(MAX(`id`),0) FROM `{MYSQL_TABLE}`")
     last_id=int(cursor.fetchone()[0] or 0);rows=[]
    else:
     cursor.execute(f"SELECT `id`,`{SN_COLUMN}`,`{RESULT_COLUMN}`,`{TIME_COLUMN}`,`station`,`operator` FROM `{MYSQL_TABLE}` WHERE `id`>%s ORDER BY `id` ASC LIMIT 500",(last_id,));rows=cursor.fetchall()
    skipped=0
    for row in rows:
     try:
      label=f'{MYSQL_TABLE}::{row[4]}';result=self.handle_source_row(row[1],row[2],row[3],label);added+=int(result['inserted']);last_id=max(last_id,int(row[0]))
     except AgingCabError:
      skipped+=1;last_id=max(last_id,int(row[0]))
    cursor.execute('SELECT number,start_time,end_time FROM ps_info ORDER BY id DESC');infos=cursor.fetchall();cursor.execute('SHOW TABLES');tables={str(x[0]) for x in cursor.fetchall()};seen=set()
    for number,start_at,end_at in infos:
     cabinet=int(number)
     if cabinet in seen or cabinet not in range(1,8):continue
     seen.add(cabinet);bt=f'ps_barcode_{cabinet}';dt=f'ps_{cabinet}'
     if bt not in tables:continue
     # A controller may publish measurements before the barcode binding is
     # written.  Build the cabinet view from both sources so the UI still
     # shows real slots/measurements, while leaving SN blank instead of
     # inventing product identity.
     cursor.execute(f"SELECT addr,barcode FROM `{bt}`")
     barcodes={int(addr):str(barcode or '').strip().upper() for addr,barcode in cursor.fetchall()}
     measurements={}
     if dt in tables:
      cursor.execute(f'SELECT addr,elapsed,record_time,current,voltage,reason FROM `{dt}` ORDER BY id DESC')
      for addr,elapsed,record_time,current,voltage,reason in cursor.fetchall():
       measurements.setdefault(int(addr),(elapsed,record_time,current,voltage,reason))
     slot_addrs=sorted(set(barcodes)|set(measurements))
     for addr in slot_addrs:
      barcode=barcodes.get(addr,'');measurement=measurements.get(addr)
      elapsed,record_time,current,voltage,reason=measurement or (None,None,None,None,None);now=int(time.time()*1000);start=int(start_at.timestamp()*1000) if start_at else None;end=int(end_at.timestamp()*1000) if end_at else None;state='COMPLETE' if end and now>=end else 'AGING';sn=str(barcode).strip().upper();native.append((cabinet,int(addr),sn,start,end,str(elapsed or ''),str(record_time or ''),str(current or ''),str(voltage or ''),str(reason or ''),state,now))
   with self.connect() as db:
    db.execute("INSERT INTO aging_mysql_cursor VALUES('ps_station_log',?,?) ON CONFLICT(cursor_name) DO UPDATE SET last_id=excluded.last_id,updated_at=excluded.updated_at",(last_id,time.strftime('%Y-%m-%d %H:%M:%S')))
    db.executemany('INSERT INTO aging_native_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(cabinet,addr) DO UPDATE SET sn=excluded.sn,started_at=excluded.started_at,expected_end_at=excluded.expected_end_at,elapsed=excluded.elapsed,record_time=excluded.record_time,current=excluded.current,voltage=excluded.voltage,reason=excluded.reason,state=excluded.state,updated_at=excluded.updated_at',native)
   for row in native:
    sn=row[2]
    with self.connect() as db:exists=db.execute('SELECT 1 FROM sn_arrivals WHERE station_code=? AND sn=?',(STATION_CODE,sn)).fetchone()
    if sn and not exists:self.arrivals.record_arrival(sn,'MYSQL_SLOT',f'cabinet={row[0]},slot={row[1]}',arrived_at=row[3] or int(time.time()*1000))
   with self.connect() as db:db.execute("INSERT INTO aging_mysql_cursor VALUES('ps_station_log',?,?) ON CONFLICT(cursor_name) DO UPDATE SET last_id=excluded.last_id,updated_at=excluded.updated_at",(last_id,time.strftime('%Y-%m-%d %H:%M:%S')))
   self.sql_connected=True;return {'table':MYSQL_TABLE,'read':len(rows),'added':added,'skipped':skipped,'native':len(native)}
  finally:connection.close()
 def snapshot(self,limit=1000):
  self.check_timeouts()
  with self.connect() as db:return {'results':[dict(r) for r in db.execute('SELECT * FROM source_results ORDER BY cached_at DESC LIMIT ?',(limit,))],'native':[dict(r) for r in db.execute('SELECT * FROM aging_native_sessions ORDER BY cabinet,addr')],'batches':[dict(r) for r in db.execute('SELECT * FROM aging_batches ORDER BY started_at DESC LIMIT ?',(limit,))],'batch_members':[dict(r) for r in db.execute('SELECT * FROM aging_batch_members ORDER BY batch_id DESC,slot')],'ng':[dict(r) for r in db.execute('SELECT * FROM confirmed_ng ORDER BY confirmed_at DESC LIMIT ?',(limit,))],'duplicates':[dict(r) for r in db.execute('SELECT * FROM duplicate_events ORDER BY id DESC LIMIT ?',(limit,))],'checks':[dict(r) for r in db.execute('SELECT * FROM scanner_checks ORDER BY id DESC LIMIT ?',(limit,))],'outbox':[dict(r) for r in db.execute('SELECT * FROM event_outbox ORDER BY created_at DESC LIMIT ?',(limit,))],'changes':[dict(r) for r in db.execute('SELECT * FROM software_change_log ORDER BY id DESC')],'arrival':self.arrivals.snapshot(limit),'maintenance':self.arrivals.maintenance.snapshot(limit),'history':self.history.snapshot(limit),'sql':{'host':MYSQL_HOST,'port':MYSQL_PORT,'database':MYSQL_DATABASE,'table':self.sql_table,'connected':self.sql_connected,'blockedUntil':self.mysql_blocked_until}}
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
