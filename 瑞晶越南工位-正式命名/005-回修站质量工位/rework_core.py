# -*- coding: utf-8 -*-
"""Rework/Repair authority: MES-managed handovers, repair workflow, materials."""
from __future__ import annotations
import json,os,sqlite3,sys,threading,time,urllib.error,urllib.parse,urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE=Path(__file__).resolve().parent
DEFAULT_DB=BASE/'data'/'rework.db'
MES_API=os.environ.get('MES_API','http://192.168.6.155:8080/api').rstrip('/')
PDA_EVENT_URL=os.environ.get('PDA_EVENT_URL',f'{MES_API}/pda/events')
STATION_CODE=os.environ.get('MES_STATION_CODE','manu_rework')
STATION_IP=os.environ.get('MES_STATION_IP','192.168.6.160')
LINE_CODE=os.environ.get('MES_LINE_CODE','L004')
PROCESS_DOMAIN='MANUAL_LINE'
OPERATOR=os.environ.get('MES_OPERATOR','QC_VN_01')
PASSWORD=os.environ.get('MES_PASSWORD','Factory@123')
REPAIR_TIMEOUT_HOURS=2
ALLOWED_MANUAL_SOURCES={'manu_ict','manu_fct','manu_depanel'}

# ── Defect code dictionary (from MES source) ────────────────────────
DEFECT_CODES={
    'ATE':{
        'OC-001':'开路 / Open Circuit','SC-001':'短路 / Short Circuit',
        'HV-001':'高电压不良 / High Voltage','IR-001':'绝缘不良 / Insulation Resistance',
        'VR-001':'电压异常 / Voltage Range','FN-001':'功能不良 / Functional',
        'CM-001':'通信不良 / Communication',
    },
    'HIPOT':{f'HIPOT-0{i}':f'耐压测试不良 #{i}' for i in range(1,5)},
    'AGING':{f'AG-00{i}':f'老化测试不良 #{i}' for i in range(1,6)},
    'GENERAL':{f'GN-00{i}':f'通用不良 #{i}' for i in range(1,7)},
}
def get_defect_codes_for_source(source):
    source=str(source or '').upper().replace('MANU_','')
    return DEFECT_CODES.get(source,DEFECT_CODES['GENERAL'])

# ── 5-step repair workflow + post-repair tests ─────────────────────
REPAIR_STEPS=[
    ('DISASSEMBLY',  '① 拆壳检查',   'Disassembly',          0),
    ('PCB_LOCATE',   '② PCB故障定位','PCB Fault Location',   1),
    ('COMPONENT',    '③ 元件更换焊接','Component Replacement',2),
    ('CLEANING',     '④ 清洗烘干',   'Cleaning & Drying',    3),
    ('REASSEMBLY',   '⑤ 重装紧固',   'Reassembly',           4),
]
POST_REPAIR_TESTS=[
    ('ELECTRICAL', '基本电性测试',  'Electrical Test',   True),
    ('AGING',      '老化联测',      'Aging Test',        False),
    ('HIPOT',      '耐压安全测试',  'Hipot Safety Test', False),
]
STEP_REPAIR=0   # index in REPAIR_STEPS for the repair phase
STEP_TEST=5     # 5th step is post-repair tests (index after REPAIR_STEPS)

class ReworkError(RuntimeError):pass

def now_text():return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def http(method,url,body=None,timeout=8,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']=f'Bearer {token}'
    data=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:return e.code,json.loads(e.read().decode('utf-8'))
        except Exception:return e.code,{'code':f'HTTP_{e.code}'}
    except Exception as e:return 0,{'code':'MES_OFFLINE','message':str(e)}

class ReworkCore:
    def __init__(self,db_path=DEFAULT_DB,mes_api=MES_API,station_code=STATION_CODE,
                 line_code=LINE_CODE,operator=OPERATOR,password=PASSWORD):
        self.db_path=Path(db_path);self.db_path.parent.mkdir(parents=True,exist_ok=True)
        self.mes_api=mes_api;self.station_code=station_code;self.line_code=line_code
        self.operator=operator;self.password=password
        self.lock=threading.RLock()
        self._token=None;self._token_expires_at=0
        self.init_db()

    def connect(self):
        db=sqlite3.connect(str(self.db_path),timeout=30);db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL');return db

    @staticmethod
    def _add_col_safe(db, table, col_def):
        """Add column if not exists — safe for older SQLite without ADD COLUMN IF NOT EXISTS."""
        cur = db.execute('PRAGMA table_info(%s)' % table)
        existing = set(row[1] for row in cur.fetchall())
        col_name = col_def.strip().split()[0]
        if col_name not in existing:
            db.execute('ALTER TABLE %s ADD COLUMN %s' % (table, col_def))

    def init_db(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS motherboards(batch_id TEXT PRIMARY KEY,source_station TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'waiting_repair',received_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS motherboard_members(id INTEGER PRIMARY KEY AUTOINCREMENT,batch_id TEXT NOT NULL,sn TEXT NOT NULL,slot INTEGER,incoming_result TEXT NOT NULL DEFAULT 'NG',defect_code TEXT,repair_status TEXT NOT NULL DEFAULT 'waiting',updated_at TEXT NOT NULL,UNIQUE(batch_id,sn));
            CREATE INDEX IF NOT EXISTS idx_rework_member_sn ON motherboard_members(sn);
            CREATE TABLE IF NOT EXISTS repair_work_orders(work_order_no TEXT PRIMARY KEY,handover_bill_no TEXT,batch_id TEXT NOT NULL,ng_sn TEXT NOT NULL,source_station TEXT NOT NULL,submitted_at TEXT,received_at TEXT,repair_started_at TEXT,repair_completed_at TEXT,repair_method TEXT,repair_result TEXT,operator TEXT,retest_history TEXT NOT NULL DEFAULT '[]',status TEXT NOT NULL DEFAULT 'WAITING_RECEIPT',mes_synced INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_local_repair_wo_batch ON repair_work_orders(batch_id);
            CREATE TABLE IF NOT EXISTS repair_records(id INTEGER PRIMARY KEY AUTOINCREMENT,batch_id TEXT,sn TEXT NOT NULL,action TEXT NOT NULL,result TEXT,defect_code TEXT,repair_method TEXT,operator TEXT,started_at TEXT NOT NULL,completed_at TEXT,mes_synced INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS idx_repair_records_sn ON repair_records(sn);
            CREATE TABLE IF NOT EXISTS repair_material_usage(id INTEGER PRIMARY KEY AUTOINCREMENT,work_order_no TEXT NOT NULL,ng_sn TEXT,material_code TEXT,material_name TEXT,quantity REAL NOT NULL,unit TEXT,operator TEXT,recorded_at TEXT NOT NULL,mes_synced INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ng_records(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,source TEXT NOT NULL,defect_code TEXT,status TEXT NOT NULL DEFAULT 'pending',detected_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_rework_ng_sn ON ng_records(sn);
            CREATE TABLE IF NOT EXISTS duplicate_events(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL,source TEXT NOT NULL,decision TEXT NOT NULL DEFAULT 'blocked',detected_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sn_records(id INTEGER PRIMARY KEY AUTOINCREMENT,sn TEXT NOT NULL UNIQUE,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,station_code TEXT NOT NULL,result TEXT NOT NULL,mes_synced INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS mes_sync_queue(id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,sn TEXT NOT NULL,result TEXT NOT NULL,payload TEXT,created_at TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS mes_confirmed_ng_cache(sn TEXT PRIMARY KEY,source_station TEXT,batch_id TEXT,payload TEXT NOT NULL,registry_version INTEGER NOT NULL DEFAULT 0,synced_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS ng_migrations(id INTEGER PRIMARY KEY AUTOINCREMENT,migration_key TEXT NOT NULL UNIQUE,batch_id TEXT,sn TEXT NOT NULL,slot INTEGER,source_station TEXT NOT NULL,destination_station TEXT NOT NULL,defect_code TEXT,status TEXT NOT NULL DEFAULT 'received',migrated_at TEXT NOT NULL,completed_at TEXT,mes_synced INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS idx_ng_migrations_batch ON ng_migrations(batch_id);
            CREATE INDEX IF NOT EXISTS idx_ng_migrations_sn ON ng_migrations(sn);
            CREATE TABLE IF NOT EXISTS motherboard_migration_state(batch_id TEXT PRIMARY KEY,source_station TEXT NOT NULL,destination_station TEXT NOT NULL,member_count INTEGER NOT NULL DEFAULT 0,ng_count INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'received',migrated_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS software_change_log(id INTEGER PRIMARY KEY AUTOINCREMENT,change_id TEXT UNIQUE NOT NULL,version TEXT NOT NULL,component TEXT NOT NULL,reason TEXT NOT NULL,summary TEXT NOT NULL,verification TEXT NOT NULL,changed_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS repair_process(id INTEGER PRIMARY KEY AUTOINCREMENT,work_order_no TEXT NOT NULL,step_code TEXT NOT NULL,step_index INTEGER NOT NULL,started_at INTEGER NOT NULL,confirmed_at INTEGER,confirmed_by TEXT,note TEXT,mes_synced INTEGER NOT NULL DEFAULT 1,UNIQUE(work_order_no,step_code));
            CREATE TABLE IF NOT EXISTS repair_test(id INTEGER PRIMARY KEY AUTOINCREMENT,work_order_no TEXT NOT NULL,test_code TEXT NOT NULL,test_name TEXT NOT NULL,result TEXT NOT NULL,measured_value TEXT,tested_at INTEGER NOT NULL,tested_by TEXT,note TEXT,mes_synced INTEGER NOT NULL DEFAULT 1,UNIQUE(work_order_no,test_code));
            CREATE TABLE IF NOT EXISTS scrap_reasons(id INTEGER PRIMARY KEY AUTOINCREMENT,work_order_no TEXT NOT NULL,reason_code TEXT NOT NULL,reason_text TEXT,scrapped_by TEXT,scrapped_at INTEGER NOT NULL,mes_synced INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS repair_pickup_notifications(
                event_id TEXT PRIMARY KEY,work_order_no TEXT NOT NULL,sn TEXT,batch_id TEXT,
                source_station TEXT NOT NULL,notify_role TEXT NOT NULL DEFAULT 'LINE_LEADER',
                status TEXT NOT NULL,created_at INTEGER NOT NULL,sent_at INTEGER,last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_pickup_notifications_status ON repair_pickup_notifications(status);
            """)
            for col in ('process_domain TEXT','event_id TEXT','route_version TEXT','policy_version TEXT','destination_station TEXT'):
                self._add_col_safe(db,'repair_work_orders',col)
            self._add_col_safe(db,'mes_sync_queue','event_id TEXT')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_mes_sync_queue_event_id ON mes_sync_queue(event_id) WHERE event_id IS NOT NULL')
            # WMS columns — add safely (older SQLite lacks ADD COLUMN IF NOT EXISTS)
            wms_cols = [
                'lot_no TEXT','supplier_code TEXT','supplier_name TEXT','location_code TEXT',
                'wms_material_id INTEGER','received_at TEXT','iqc_status TEXT','wms_lot_status TEXT',
                'inbound_tx_no TEXT','inbound_supplier_tx_no TEXT','inbound_received_at TEXT','inbound_po_no TEXT',
                'pick_tx_no TEXT','pick_issued_at TEXT','pick_issued_by TEXT','issue_work_order_no TEXT',
                'wms_synced INTEGER NOT NULL DEFAULT 0',
            ]
            for col in wms_cols:
                self._add_col_safe(db, 'repair_material_usage', col)
            # Triggers (separate executescript to avoid single-quote/Python triple-quote issues)
            db.executescript("""
            CREATE TRIGGER IF NOT EXISTS rework_wo_no_delete BEFORE DELETE ON repair_work_orders BEGIN SELECT RAISE(ABORT,"repair work orders cannot be deleted");END;
            CREATE TRIGGER IF NOT EXISTS rework_process_no_delete BEFORE DELETE ON repair_process BEGIN SELECT RAISE(ABORT,"repair process is immutable");END;
            CREATE TRIGGER IF NOT EXISTS rework_test_no_delete BEFORE DELETE ON repair_test BEGIN SELECT RAISE(ABORT,"repair test results are immutable");END;
            CREATE TRIGGER IF NOT EXISTS rework_change_no_update BEFORE UPDATE ON software_change_log BEGIN SELECT RAISE(ABORT,"software history is immutable");END;
            CREATE TRIGGER IF NOT EXISTS rework_change_no_delete BEFORE DELETE ON software_change_log BEGIN SELECT RAISE(ABORT,"software history is immutable");END;
            """)
            db.execute("INSERT OR IGNORE INTO software_change_log VALUES(NULL,?,?,?,?,?,?,?)",
                       ('REWORK-CORE-001','1.0.0','Core','Migrate to Core/2D/3D unified architecture',
                        'MES handovers repair workflow materials MES completion; 2D/3D only consume snapshot',
                        'receive, complete, materials, heartbeat, NG registry sync',int(time.time()*1000)))
            db.execute("INSERT OR IGNORE INTO software_change_log VALUES(NULL,?,?,?,?,?,?,?)",
                       ('REWORK-CORE-002','1.1.0','Core','Add 5-step workflow + defect codes + post-repair tests',
                        'DISASSEMBLY->PCB_LOCATE->COMPONENT->CLEANING->REASSEMBLY->3 tests (ELECTRICAL/AGING/HIPOT)',
                        'step confirm, test record, defect dict, scrap reason',int(time.time()*1000)))

    def check_scan(self,sn):
        code=str(sn or '').strip().upper()
        if not code:raise ReworkError('SN 不能为空')
        with self.connect() as db:
            ng_count=db.execute('SELECT COUNT(*) FROM ng_records WHERE UPPER(sn)=?',(code,)).fetchone()[0]
            dup_count=db.execute('SELECT COUNT(*) FROM duplicate_events WHERE UPPER(sn)=?',(code,)).fetchone()[0]
            cached_ng=db.execute('SELECT 1 FROM mes_confirmed_ng_cache WHERE UPPER(sn)=? LIMIT 1',(code,)).fetchone()
        blocked=bool(ng_count or cached_ng)
        if cached_ng:status='CONFIRMED_NG';detail='MES 缓存中存在该 NG'
        elif ng_count:status='NG_MARKED';detail=f'本站已标记 {ng_count} 条 NG'
        elif dup_count:status='DUPLICATE_MARKED';detail=f'本站已记录 {dup_count} 次重复扫码'
        else:status='CLEAR';detail='未发现 NG 或重复记录'
        with self.connect() as db:
            db.execute('INSERT INTO sn_records(sn,first_seen,last_seen,station_code,result,mes_synced) VALUES(?,?,?,?,?,0) ON CONFLICT(sn) DO UPDATE SET last_seen=excluded.last_seen,result=excluded.result',
                       (code,now_text(),now_text(),self.station_code,status))
        return {'sn':code,'status':status,'detail':detail,'blocked':blocked}

    def _ensure_token(self):
        if self._token and time.time()<self._token_expires_at-60:return self._token
        try:
            code,data=http('POST',f'{self.mes_api}/auth/login',{'username':self.operator,'password':self.password})
            if code in (200,201):
                payload=data.get('data') or data
                self._token=payload.get('token','')
                expires=payload.get('expiresAt','')
                if expires:
                    try:self._token_expires_at=datetime.fromisoformat(expires.replace('Z','+00:00')).timestamp()
                    except Exception:self._token_expires_at=time.time()+3600
                else:self._token_expires_at=time.time()+3600
            else:self._token=None
        except Exception:self._token=None
        return self._token

    def receive_repair(self,sn):
        code=str(sn or '').strip().upper()
        if not code:raise ReworkError('SN 不能为空')
        with self.connect() as db:
            db.execute('INSERT INTO repair_records(batch_id,sn,action,result,operator,started_at) VALUES(?,?,?,?,?,?)',
                       ('',code,'RECEIVE_ATTEMPT','PENDING',self.operator,now_text()))
        receive_event=f'{self.station_code}:REPAIR_RECEIVE:{code}'
        status,result=http('POST',f'{self.mes_api}/station/maintenance-handovers/receive',
                           {'stationCode':self.station_code,'sn':code,
                            'processDomain':PROCESS_DOMAIN,'lineCode':self.line_code,
                            'eventId':receive_event})
        if status!=200:
            error=(result or {}).get('error') or result
            error_code=error.get('code') or 'NO_REPAIR_HANDOVER'
            return {'ok':False,'sn':code,'error_code':error_code,'detail':json.dumps(result,ensure_ascii=False)}
        batch_id=str(result.get('batchId') or code)
        wo_no=result.get('repairWorkOrderNo') or f'WO-{batch_id}'
        source=str(result.get('sourceStationCode') or '').strip().lower()
        domain=str(result.get('processDomain') or result.get('domain') or '').strip().upper()
        if domain != PROCESS_DOMAIN:
            return {'ok':False,'sn':code,'error_code':'DOMAIN_MISMATCH',
                    'detail':f'Expected {PROCESS_DOMAIN}, received {domain or "missing"}'}
        if source not in ALLOWED_MANUAL_SOURCES:
            return {'ok':False,'sn':code,'error_code':'SOURCE_STATION_NOT_ALLOWED',
                    'detail':f'Manual repair source must be ICT/FCT/Depanel, received {source or "missing"}'}
        ts=now_text()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO motherboards(batch_id,source_station,status,received_at,updated_at) VALUES(?,?,?,?,?)',
                       (batch_id,source,'received',ts,ts))
            db.execute('INSERT OR IGNORE INTO ng_migrations(migration_key,batch_id,sn,source_station,destination_station,status,migrated_at) VALUES(?,?,?,?,?,?,?)',
                       (f'{batch_id}:{code}:receipt',batch_id,code,source,self.station_code,'received',ts))
            db.execute("""INSERT INTO repair_work_orders(work_order_no,batch_id,ng_sn,source_station,received_at,repair_started_at,retest_history,status,operator,updated_at)
                VALUES(?,?,?,?,?,?,?,'REPAIR_IN_PROGRESS',?,?) ON CONFLICT(work_order_no) DO UPDATE SET
                received_at=excluded.received_at,repair_started_at=excluded.repair_started_at,
                retest_history=excluded.retest_history,status='REPAIR_IN_PROGRESS',updated_at=excluded.updated_at""",
                (wo_no,batch_id,code,source,result.get('receivedAt') or ts,
                 result.get('repairStartedAt') or ts,
                json.dumps(result.get('retestHistory') or [],ensure_ascii=False),self.operator,ts))
            db.execute('''UPDATE repair_work_orders SET process_domain=?,event_id=?,route_version=?,policy_version=?,destination_station=? WHERE work_order_no=?''',
                       (PROCESS_DOMAIN,receive_event,str(result.get('routeVersion') or ''),
                        str(result.get('policyVersion') or ''),self.station_code,wo_no))
            db.execute('INSERT INTO repair_records(batch_id,sn,action,result,repair_method,operator,started_at,completed_at,mes_synced) VALUES(?,?,?,?,?,?,?,?,1)',
                       (batch_id,code,'REPAIR_RECEIVED','RECEIVED','MES_HANDOVER',self.operator,ts,ts))
        return {'ok':True,'sn':code,'batch_id':batch_id,'work_order_no':wo_no,'source':source,'handover':result}

    def add_material(self,work_order_no,code,name,qty,unit='PCS'):
        work_order_no=str(work_order_no or '').strip()
        code=str(code or '').strip();name=str(name or '').strip()
        try:qty=float(qty)
        except (TypeError,ValueError):raise ReworkError('数量必须为数字')
        if not work_order_no or not code or not name or qty<=0:
            raise ReworkError('工单号、物料编码、名称、数量必须填写')
        with self.connect() as db:
            wo=db.execute('SELECT ng_sn FROM repair_work_orders WHERE work_order_no=?',(work_order_no,)).fetchone()
            if not wo:raise ReworkError(f'工单 {work_order_no} 不存在')
            db.execute("""INSERT INTO repair_material_usage(work_order_no,ng_sn,material_code,material_name,quantity,unit,operator,recorded_at,mes_synced)
                VALUES(?,?,?,?,?,?,?,?,0)""",(work_order_no,wo['ng_sn'],code,name,qty,unit,self.operator,now_text()))
        return {'ok':True,'work_order_no':work_order_no,'material':{'materialCode':code,'materialName':name,'quantity':qty,'unit':unit}}

    def start_step(self,work_order_no,step_code,operator=None):
        """Start a repair step (records started_at, idempotent)."""
        work_order_no=str(work_order_no or '').strip()
        step_code=str(step_code or '').strip().upper()
        operator=operator or self.operator
        if not work_order_no or not step_code:raise ReworkError('工单号和步骤必填')
        step_index=next((idx for code,_,_,idx in REPAIR_STEPS if code==step_code),-1)
        if step_index<0:raise ReworkError(f'未知步骤: {step_code}')
        with self.connect() as db:
            wo=db.execute('SELECT work_order_no FROM repair_work_orders WHERE work_order_no=?',(work_order_no,)).fetchone()
            if not wo:raise ReworkError(f'工单 {work_order_no} 不存在')
            db.execute('INSERT INTO repair_process(work_order_no,step_code,step_index,started_at,mes_synced) VALUES(?,?,?,?,1) ON CONFLICT(work_order_no,step_code) DO UPDATE SET started_at=MIN(repair_process.started_at,?)',
                       (work_order_no,step_code,step_index,now_text(),now_text()))
        return {'ok':True,'work_order_no':work_order_no,'step_code':step_code,'step_index':step_index}

    def _emit(self,event_type,payload,idempotent_id=None):
        """Send an event to MES; persist it in the local Outbox when MES is unavailable."""
        now_ms=int(time.time()*1000)
        event_id=idempotent_id or f'{self.station_code}-{event_type}-{now_ms}'
        body={'from':self.station_code,'to':'mes_server','type':event_type,
              'stationCode':self.station_code,'eventId':event_id,
              'payload':payload,'priority':'normal','createdAt':now_ms}
        status,response=http('POST',PDA_EVENT_URL,body,timeout=5,token=self._ensure_token())
        if 200 <= int(status or 0) < 300:
            return {'status':'SENT','event_id':event_id,'mes_status':status}
        sn=str(payload.get('sn') or payload.get('SN') or payload.get('ngSn') or '')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO mes_sync_queue(event_id,event_type,sn,result,payload,created_at) VALUES(?,?,?,?,?,?)',
                       (event_id,event_type,sn,'PENDING',json.dumps(body,ensure_ascii=False),now_text()))
        return {'status':'QUEUED_OFFLINE','event_id':event_id,'error':(response or {}).get('code','MES_OFFLINE')}

    def confirm_step(self,work_order_no,step_code,note=None,operator=None):
        """Confirm a repair step is done. Returns next required step or 'TESTS'."""
        work_order_no=str(work_order_no or '').strip()
        step_code=str(step_code or '').strip().upper()
        operator=operator or self.operator
        if not work_order_no or not step_code:raise ReworkError('工单号和步骤必填')
        step_index=next((idx for code,_,_,idx in REPAIR_STEPS if code==step_code),-1)
        if step_index<0:raise ReworkError(f'未知步骤: {step_code}')
        now=now_text();now_ms=int(time.time()*1000)
        with self.connect() as db:
            wo=db.execute('SELECT work_order_no FROM repair_work_orders WHERE work_order_no=?',(work_order_no,)).fetchone()
            if not wo:raise ReworkError(f'工单 {work_order_no} 不存在')
            # Check previous steps confirmed
            for code,_,_,idx in REPAIR_STEPS:
                if idx<step_index:
                    prev=db.execute('SELECT confirmed_at FROM repair_process WHERE work_order_no=? AND step_code=?',
                                    (work_order_no,code)).fetchone()
                    if not prev or not prev['confirmed_at']:
                        return {'ok':False,'error':f'前置步骤 {code} 未完成','next_step':code}
            db.execute('INSERT INTO repair_process(work_order_no,step_code,step_index,started_at,confirmed_at,confirmed_by,note,mes_synced) '
                       'VALUES(?,?,?,?,?,?,?,1) '
                       'ON CONFLICT(work_order_no,step_code) DO UPDATE SET confirmed_at=?,confirmed_by=?,note=?',
                       (work_order_no,step_code,step_index,now,now,operator,note,now,operator,note))
            db.execute('INSERT INTO repair_records(batch_id,sn,action,result,repair_method,operator,started_at,completed_at,mes_synced) '
                       'VALUES((SELECT batch_id FROM repair_work_orders WHERE work_order_no=?),'
                       '(SELECT ng_sn FROM repair_work_orders WHERE work_order_no=?),?,?,?,?,?,?,1)',
                       (work_order_no,work_order_no,f'STEP_{step_code}','CONFIRMED',note or '',operator,now,now))
            next_step=next(((c,n,_,idx) for c,n,_,idx in REPAIR_STEPS if idx==step_index+1),None)
        self._emit('REPAIR_STEP_CONFIRMED',{'workOrderNo':work_order_no,'stepCode':step_code,
              'stepIndex':step_index,'stepNameZh':next((n for c,n,_,i in REPAIR_STEPS if c==step_code),step_code),
              'confirmedBy':operator,'confirmedAt':now_ms,'note':note},
              idempotent_id=f'{work_order_no}-{step_code}-{now_ms}')
        return {'ok':True,'work_order_no':work_order_no,'step_code':step_code,'confirmed_at':now,
                'next_step':next_step[0] if next_step else 'TESTS'}

    def record_post_test(self,work_order_no,test_code,result,measured_value=None,note=None,operator=None):
        """Record a post-repair test result."""
        work_order_no=str(work_order_no or '').strip()
        test_code=str(test_code or '').strip().upper()
        result=str(result or '').strip().upper()
        operator=operator or self.operator
        if not work_order_no or not test_code or not result:
            raise ReworkError('工单号、测试名、结果必填')
        if result not in ('PASS','FAIL'):raise ReworkError('测试结果必须是 PASS 或 FAIL')
        test_meta=next(((n,full) for c,n,full,_ in POST_REPAIR_TESTS if c==test_code), None)
        if not test_meta:raise ReworkError(f'未知测试: {test_code}')
        with self.connect() as db:
            wo=db.execute('SELECT work_order_no FROM repair_work_orders WHERE work_order_no=?',(work_order_no,)).fetchone()
            if not wo:raise ReworkError(f'工单 {work_order_no} 不存在')
            db.execute('INSERT INTO repair_test(work_order_no,test_code,test_name,result,measured_value,tested_at,tested_by,note,mes_synced) '
                       'VALUES(?,?,?,?,?,?,?,?,1) '
                       'ON CONFLICT(work_order_no,test_code) DO UPDATE SET result=?,measured_value=?,tested_at=?,tested_by=?,note=?',
                       (work_order_no,test_code,test_meta[0],result,measured_value,now_text(),operator,note,
                        result,measured_value,now_text(),operator,note))
        now_ms=int(time.time()*1000)
        self._emit('REPAIR_TEST_COMPLETED',{'workOrderNo':work_order_no,'testCode':test_code,
              'testNameZh':test_meta[0],'result':result,'measuredValue':measured_value,
              'testedBy':operator,'testedAt':now_ms,'note':note},
              idempotent_id=f'{work_order_no}-{test_code}-{now_ms}')
        return {'ok':True,'work_order_no':work_order_no,'test_code':test_code,'result':result}

    def repair_progress(self,work_order_no):
        """Return current step status + post-repair test results for a work order."""
        work_order_no=str(work_order_no or '').strip()
        with self.connect() as db:
            steps=[dict(r) for r in db.execute('SELECT * FROM repair_process WHERE work_order_no=? ORDER BY step_index',(work_order_no,))]
            tests=[dict(r) for r in db.execute('SELECT * FROM repair_test WHERE work_order_no=? ORDER BY tested_at',(work_order_no,))]
            wo=db.execute('SELECT batch_id,ng_sn,source_station,status,repair_method,received_at,repair_started_at FROM repair_work_orders WHERE work_order_no=?',(work_order_no,)).fetchone()
        step_codes=[s['step_code'] for s in steps if s['confirmed_at']]
        next_step=next(((c,n,full,idx) for c,n,full,idx in REPAIR_STEPS if c not in step_codes),None)
        test_codes={t['test_code'] for t in tests}
        all_steps_done=len(step_codes)==len(REPAIR_STEPS)
        if all_steps_done:
            tests_required=set(c for c,_,_,r in POST_REPAIR_TESTS if r)
            tests_pass=all(t['result']=='PASS' for t in tests if t['test_code'] in tests_required)
            next_step_status='ALL_TESTS_REQUIRED' if not tests_required.issubset(test_codes) else ('TESTS_PASS' if tests_pass else 'TESTS_FAIL')
        else:
            next_step_status=next_step[0] if next_step else 'COMPLETE'
        return {'work_order_no':work_order_no,'work_order':dict(wo) if wo else None,
                'steps':steps,'tests':tests,
                'steps_confirmed':step_codes,'tests_recorded':list(test_codes),
                'next_step':next_step[0] if next_step and not all_steps_done else None,
                'next_step_name':next_step[1] if next_step and not all_steps_done else None,
                'all_steps_done':all_steps_done,
                'all_required_tests_pass':all_steps_done and all(
                    t['result']=='PASS' for t in tests
                    if t['test_code'] in (set(c for c,_,_,r in POST_REPAIR_TESTS if r))),
                'status':next_step_status}

    def scrap_ng(self,work_order_no,reason_code,reason_text=None,operator=None):
        """Record a scrap decision for a work order (when unrepairable)."""
        work_order_no=str(work_order_no or '').strip()
        reason_code=str(reason_code or '').strip()
        operator=operator or self.operator
        if not work_order_no or not reason_code:raise ReworkError('工单号和报废原因必填')
        with self.connect() as db:
            wo=db.execute('SELECT work_order_no,ng_sn FROM repair_work_orders WHERE work_order_no=?',(work_order_no,)).fetchone()
            if not wo:raise ReworkError(f'工单 {work_order_no} 不存在')
            db.execute('INSERT INTO scrap_reasons(work_order_no,reason_code,reason_text,scrapped_by,scrapped_at) VALUES(?,?,?,?,?)',
                       (work_order_no,reason_code,reason_text or '',operator,now_text()))
        now_ms=int(time.time()*1000)
        self._emit('REPAIR_SCRAPPED',{'workOrderNo':work_order_no,'reasonCode':reason_code,
              'reasonText':reason_text,'scrappedBy':operator,'scrappedAt':now_ms},
              idempotent_id=f'{work_order_no}-SCRAP-{now_ms}')
        return {'ok':True,'work_order_no':work_order_no,'reason_code':reason_code}

    def notify_pickup_to_source_station(self, work_order_no):
        """After repair complete, notify source station to pick up the repaired board.

        Posts to MES endpoint which:
        1. Creates a PENDING_PICKUP record at the source station
        2. Broadcasts a MAINTENANCE_PICKUP_READY notification
        3. Source station operator sees a pickup task and goes to collect the board
        """
        work_order_no = str(work_order_no or '').strip()
        if not work_order_no:
            return {'ok': False, 'detail': '工单号为空'}
        # Fetch WO info to get source station
        with self.connect() as db:
            wo = db.execute('SELECT * FROM repair_work_orders WHERE work_order_no=?',
                            (work_order_no,)).fetchone()
        if not wo:
            return {'ok': False, 'detail': f'工单 {work_order_no} 不存在'}
        sn = wo['ng_sn']
        batch_id = wo['batch_id']
        source_station = wo['source_station']
        repair_result = wo['repair_result']
        if repair_result == 'scrapped':
            return {'ok': True, 'action': 'scrapped', 'detail': '已报废，不产生取件通知'}
        # One stable event per completed work order: retries must not create duplicate calls.
        event_id = f'REPAIR-PICKUP-READY-{work_order_no}'
        payload = {
            'type': 'MAINTENANCE_PICKUP_READY',
            'processDomain': PROCESS_DOMAIN,
            'lineCode': self.line_code,
            'eventId': event_id,
            'workOrderNo': work_order_no,
            'sn': sn,
            'batchId': batch_id,
            'sourceStation': source_station,
            'repairStation': self.station_code,
            'status': 'PENDING_PICKUP',
            'pickupStatus': 'WAITING_LINE_LEADER',
            'notifyRole': 'LINE_LEADER',
            'alternateNotifyRole': 'TEAM_LEADER',
            'recipientRoles': ['LINE_LEADER', 'TEAM_LEADER'],
            'pdaChannel': 'LINE_MANAGER_PDA',
            'priority': 'normal',
            'createdAt': int(time.time() * 1000),
        }
        envelope = {
            'from': self.station_code,
            'to': source_station,
            'type': 'MAINTENANCE_PICKUP_READY',
            'stationCode': self.station_code,
            'eventId': event_id,
            'recipientRoles': ['LINE_LEADER', 'TEAM_LEADER'],
            'pdaChannel': 'LINE_MANAGER_PDA',
            'payload': payload,
            'priority': 'high',
            'createdAt': int(time.time() * 1000),
        }
        with self.connect() as db:
            existing = db.execute('SELECT status FROM repair_pickup_notifications WHERE event_id=?',(event_id,)).fetchone()
            if existing and existing['status'] == 'SENT':
                return {'ok':True,'already_sent':True,'event_id':event_id,'source_station':source_station,'sn':sn,'batch_id':batch_id}
            db.execute('INSERT OR IGNORE INTO repair_pickup_notifications(event_id,work_order_no,sn,batch_id,source_station,notify_role,status,created_at) VALUES(?,?,?,?,?,?,?,?)',
                       (event_id,work_order_no,sn,batch_id,source_station,'LINE_LEADER','PENDING',int(time.time()*1000)))
        status, result = http('POST', PDA_EVENT_URL, envelope, token=self._ensure_token())
        if status in (200,201,202):
            with self.connect() as db:
                db.execute('UPDATE repair_pickup_notifications SET status=?,sent_at=?,last_error=NULL WHERE event_id=?',('SENT',int(time.time()*1000),event_id))
            return {'ok':True,'event_id':event_id,'source_station':source_station,'sn':sn,'batch_id':batch_id,'response':result}
        # MES down: retain an append-only outbox entry for replay by eventId.
        with self.connect() as db:
            duplicate=db.execute("SELECT 1 FROM mes_sync_queue WHERE event_type=? AND payload LIKE ? LIMIT 1",
                                 ('MAINTENANCE_PICKUP_READY',f'%{event_id}%')).fetchone()
            if not duplicate:
                db.execute('INSERT INTO mes_sync_queue(event_type,sn,result,payload,created_at) VALUES(?,?,?,?,?)',
                           ('MAINTENANCE_PICKUP_READY',sn,'PENDING_OUTBOX',json.dumps(envelope,ensure_ascii=False),now_text()))
            db.execute('UPDATE repair_pickup_notifications SET status=?,last_error=? WHERE event_id=?',('OUTBOX',str(result.get('message') or result.get('code') or 'MES unavailable'),event_id))
        return {
            'ok': True,
            'queued': True,
            'event_id': event_id,
            'source_station': source_station,
            'sn': sn,
            'batch_id': batch_id,
            'response': result,
        }

    def complete_repair(self,work_order_no,method,materials,repair_result='repaired'):
        work_order_no=str(work_order_no or '').strip()
        method=str(method or '').strip()
        if not work_order_no:raise ReworkError('工单号必填')
        if not method:raise ReworkError('维修方法必填')
        with self.connect() as db:
            wo=db.execute('SELECT * FROM repair_work_orders WHERE work_order_no=?',(work_order_no,)).fetchone()
            if not wo:raise ReworkError(f'工单 {work_order_no} 不存在')
            if wo['status']!='REPAIR_IN_PROGRESS':raise ReworkError(f'工单 {work_order_no} 状态不是维修中 ({wo["status"]})')
        payload={'completed':True,'repairMethod':method,'repairResult':repair_result,
                 'operator':self.operator,'materialsConfirmed':True,'materials':materials or []}
        status,result=http('POST',f'{self.mes_api}/station/maintenance-work-orders/{urllib.parse.quote(work_order_no)}/complete',payload)
        if status!=200:
            return {'ok':False,'work_order_no':work_order_no,'detail':json.dumps(result,ensure_ascii=False)}
        ts=now_text()
        with self.connect() as db:
            db.execute("UPDATE repair_work_orders SET status='PENDING_QUALITY',repair_method=?,repair_result=?,repair_completed_at=?,updated_at=? WHERE work_order_no=?",
                       (method,repair_result,ts,ts,work_order_no))
            db.execute("INSERT INTO repair_records(batch_id,sn,action,result,repair_method,operator,started_at,completed_at,mes_synced) VALUES(?,?,?,?,?,?,?,?,1)",
                       (wo['batch_id'],wo['ng_sn'],'REPAIR_COMPLETE',repair_result,method,self.operator,wo['repair_started_at'] or ts,ts))
            for item in (materials or []):
                db.execute("""INSERT INTO repair_material_usage(work_order_no,ng_sn,material_code,material_name,quantity,unit,operator,recorded_at,mes_synced)
                    VALUES(?,?,?,?,?,?,?,?,1)""",(work_order_no,wo['ng_sn'],item.get('materialCode'),
                                                  item.get('materialName'),item.get('quantity',0),
                                                  item.get('unit','PCS'),self.operator,ts))
        return {'ok':True,'work_order_no':work_order_no,'batch_id':wo['batch_id'],'result':result}

    def fetch_pending_handovers(self):
        url=f'{self.mes_api}/station/route-requests?destinationStation={urllib.parse.quote(self.station_code)}&status=WAITING_RECEIPT'
        status,result=http('GET',url,timeout=4)
        if status!=200:return []
        items=result.get('items',result if isinstance(result,list) else [])
        with self.connect() as db:
            ts=now_text()
            for row in items:
                if not row.get('repairWorkOrderNo'):continue
                board=row.get('motherboard') or {}
                ng_sn=board.get('mainSn') or row.get('batchId')
                db.execute("""INSERT INTO repair_work_orders(work_order_no,handover_bill_no,batch_id,ng_sn,source_station,submitted_at,received_at,status,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(work_order_no) DO UPDATE SET
                    status=excluded.status,updated_at=excluded.updated_at""",
                    (row['repairWorkOrderNo'],row.get('billNo'),row.get('batchId'),ng_sn,
                     row.get('sourceStation'),row.get('submittedAt'),row.get('processedAt'),
                     row.get('status') or 'WAITING_RECEIPT',ts))
        return items

    def fetch_active_repairs(self):
        url=f'{self.mes_api}/station/route-requests?destinationStation={urllib.parse.quote(self.station_code)}&status=REPAIR_IN_PROGRESS'
        status,result=http('GET',url,timeout=4)
        if status!=200:return []
        items=result.get('items',result if isinstance(result,list) else [])
        with self.connect() as db:
            ts=now_text()
            for row in items:
                if not row.get('repairWorkOrderNo'):continue
                board=row.get('motherboard') or {}
                ng_sn=board.get('mainSn') or row.get('batchId')
                db.execute("""INSERT INTO repair_work_orders(work_order_no,handover_bill_no,batch_id,ng_sn,source_station,submitted_at,received_at,repair_started_at,status,updated_at)
                    VALUES(?,?,?,?,?,?,?,?, 'REPAIR_IN_PROGRESS',?) ON CONFLICT(work_order_no) DO UPDATE SET
                    status='REPAIR_IN_PROGRESS',repair_started_at=excluded.repair_started_at,updated_at=excluded.updated_at""",
                    (row['repairWorkOrderNo'],row.get('billNo'),row.get('batchId'),ng_sn,
                     row.get('sourceStation'),row.get('submittedAt'),row.get('processedAt'),
                     row.get('repairStartedAt'),ts))
        return items

    def fetch_ng_releases(self):
        url=f'{self.mes_api}/station/ng-releases?stationCode={urllib.parse.quote(self.station_code)}'
        status,result=http('GET',url,timeout=4)
        if status!=200:return []
        releases=result.get('items',[])
        for release in releases:
            sn=str(release.get('sn') or '').strip().upper()
            batch_id=str(release.get('batchId') or '')
            if not sn:continue
            with self.connect() as db:
                removed=db.execute('DELETE FROM ng_records WHERE UPPER(sn)=?',(sn,)).rowcount
                db.execute("UPDATE motherboard_members SET repair_status='revived',updated_at=? WHERE UPPER(sn)=? OR batch_id=?",
                           (now_text(),sn,batch_id))
                db.execute("UPDATE ng_migrations SET status='completed',completed_at=? WHERE UPPER(sn)=? OR batch_id=?",
                           (now_text(),sn,batch_id))
                db.execute("UPDATE motherboards SET status='returned_to_origin',updated_at=? WHERE batch_id=?",
                           (now_text(),batch_id))
                if release.get('releaseId'):
                    status,resp=http('POST',f"{self.mes_api}/station/ng-releases/{release['releaseId']}/ack",
                         {'stationCode':self.station_code,'localRowsRemoved':removed},timeout=4)
                    if status==200:
                        self._emit('NG_REVIVED_RECEIVED',{'sn':sn,'batchId':batch_id,
                              'releaseId':release.get('releaseId'),'originStationCode':release.get('originStationCode'),
                              'revivedAt':int(time.time()*1000),'repairWorkOrderNo':work_order_no},
                              idempotent_id=f'REVIVE-{sn}-{release.get("releaseId")}')
        return releases

    def heartbeat(self):
        try:
            now=int(time.time()*1000)
            body=json.dumps({'type':'AGENT_HEARTBEAT','stationCode':self.station_code,
                             'eventId':f'heartbeat-{self.station_code}-{now}',
                             'payload':{'agent':'rework_core','agentVersion':'3.1-heartbeat','status':'running',
                                        'sourceType':'SCANNER','sourceConnected':True,
                                        'stationIp':self.station_ip if hasattr(self,'station_ip') else STATION_IP,
                                        'timestamp':now}},ensure_ascii=False)
            req=urllib.request.Request(f'{PDA_EVENT_URL}',data=body.encode('utf-8'),
                                       headers={'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req,timeout=3) as r:r.read()
            return True
        except Exception:return False

    def sync_ng_registry(self):
        url=f'{self.mes_api}/station/ng-guard'
        status,result=http('GET',url,timeout=8)
        if status!=200:return 0
        now=int(time.time()*1000);version=int(result.get('version') or 0)
        rows=[]
        for item in result.get('items') or []:
            sn=str(item.get('sn') or '').strip().upper()
            if sn:rows.append((sn,item.get('sourceStationCode') or item.get('stationCode'),
                               item.get('batchId'),json.dumps(item,ensure_ascii=False),version,now))
        if rows:
            with self.connect() as db:
                db.executemany('INSERT OR IGNORE INTO mes_confirmed_ng_cache VALUES(?,?,?,?,?,?)',rows)
        return len(rows)

    def sync_outbox(self,limit=20):
        sent=0
        with self.connect() as db:
            rows=db.execute('SELECT * FROM mes_sync_queue ORDER BY id LIMIT ?',(limit,)).fetchall()
        for row in rows:
            try:
                payload=json.loads(row['payload'] or '{}')
                req=urllib.request.Request(PDA_EVENT_URL,data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
                                           headers={'Content-Type':'application/json'},method='POST')
                with urllib.request.urlopen(req,timeout=5) as r:r.read()
                with self.connect() as db:
                    db.execute('DELETE FROM mes_sync_queue WHERE id=?',(row['id'],))
                sent+=1
            except Exception:
                with self.connect() as db:
                    db.execute('UPDATE mes_sync_queue SET attempts=attempts+1 WHERE id=?',(row['id'],))
                break
        return sent

    def snapshot(self,limit=200):
        with self.connect() as db:
            work_orders=[dict(r) for r in db.execute('SELECT * FROM repair_work_orders ORDER BY updated_at DESC LIMIT ?',(limit,))]
            history=[dict(r) for r in db.execute('SELECT * FROM repair_records ORDER BY id DESC LIMIT ?',(limit,))]
            materials=[dict(r) for r in db.execute('SELECT * FROM repair_material_usage ORDER BY id DESC LIMIT ?',(limit,))]
            ng_active=[dict(r) for r in db.execute('SELECT * FROM ng_records ORDER BY id DESC LIMIT ?',(limit,))]
            dups=[dict(r) for r in db.execute('SELECT * FROM duplicate_events ORDER BY id DESC LIMIT ?',(limit,))]
            scans=[dict(r) for r in db.execute('SELECT * FROM sn_records ORDER BY id DESC LIMIT ?',(limit,))]
            outbox=[dict(r) for r in db.execute('SELECT * FROM mes_sync_queue ORDER BY id DESC LIMIT ?',(limit,))]
            cached_ng=[dict(r) for r in db.execute('SELECT * FROM mes_confirmed_ng_cache ORDER BY synced_at DESC LIMIT ?',(limit,))]
            changes=[dict(r) for r in db.execute('SELECT * FROM software_change_log ORDER BY id DESC')]
            motherboards=[dict(r) for r in db.execute('SELECT * FROM motherboards ORDER BY updated_at DESC LIMIT ?',(limit,))]
            step_progress=[dict(r) for r in db.execute('SELECT work_order_no,step_code,confirmed_at,confirmed_by,note FROM repair_process ORDER BY work_order_no,step_index LIMIT ?',(limit,))]
            test_progress=[dict(r) for r in db.execute('SELECT work_order_no,test_code,test_name,result,measured_value,tested_by,tested_at FROM repair_test ORDER BY work_order_no,tested_at LIMIT ?',(limit,))]
            scraps=[dict(r) for r in db.execute('SELECT * FROM scrap_reasons ORDER BY scrapped_at DESC LIMIT ?',(limit,))]
        for wo in work_orders:
            try:wo['retest_history_parsed']=json.loads(wo.get('retest_history') or '[]')
            except Exception:wo['retest_history_parsed']=[]
        return {'work_orders':work_orders,'history':history,'materials':materials,
                'ng_active':ng_active,'duplicates':dups,'scans':scans,'outbox':outbox,
                'cached_ng':cached_ng,'changes':changes,'motherboards':motherboards,
                'step_progress':step_progress,'test_progress':test_progress,
                'scraps':scraps,
                'repair_steps':[{'code':c,'name_zh':n,'name_en':e,'index':i} for c,n,e,i in REPAIR_STEPS],
                'post_repair_tests':[{'code':c,'name_zh':n,'name_en':e,'required':r} for c,n,e,r in POST_REPAIR_TESTS],
                'defect_codes':DEFECT_CODES,
                'station_code':self.station_code,'line_code':self.line_code,
                'mes_api':self.mes_api,'repair_timeout_hours':REPAIR_TIMEOUT_HOURS,
                'pending_handovers':[],'active_repairs':[]}

    def fetch_repair_log(self, work_order_no):
        """Full repair history for one work order: records, materials, steps, tests, QC info."""
        work_order_no=str(work_order_no or '').strip()
        with self.connect() as db:
            wo=db.execute('SELECT * FROM repair_work_orders WHERE work_order_no=?',(work_order_no,)).fetchone()
            if not wo: return None
            records=[dict(r) for r in db.execute(
                'SELECT * FROM repair_records WHERE batch_id=? OR sn=? ORDER BY started_at',
                (wo['batch_id'], wo['ng_sn']))]
            materials=[dict(r) for r in db.execute(
                'SELECT * FROM repair_material_usage WHERE work_order_no=? ORDER BY recorded_at',
                (work_order_no,))]
            steps=[dict(r) for r in db.execute(
                'SELECT * FROM repair_process WHERE work_order_no=? ORDER BY step_index',
                (work_order_no,))]
            tests=[dict(r) for r in db.execute(
                'SELECT * FROM repair_test WHERE work_order_no=? ORDER BY tested_at',
                (work_order_no,))]
            scraps=[dict(r) for r in db.execute(
                'SELECT * FROM scrap_reasons WHERE work_order_no=? ORDER BY scrapped_at',
                (work_order_no,))]
            members=[dict(r) for r in db.execute(
                'SELECT * FROM motherboard_members WHERE batch_id=? ORDER BY slot',
                (wo['batch_id'],))]
        return {
            'work_order': dict(wo),
            'records': records,
            'materials': materials,
            'steps': steps,
            'tests': tests,
            'scraps': scraps,
            'motherboard_members': members,
            'defect_codes': DEFECT_CODES,
        }

    def fetch_statistics(self, days=30):
        """Aggregate statistics from local DB: defect distribution, top materials, by-station counts, completion metrics."""
        import collections
        with self.connect() as db:
            cutoff_ms = int((time.time() - days * 86400) * 1000)
            # WO status breakdown
            status_rows = db.execute(
                'SELECT status, COUNT(*) as cnt FROM repair_work_orders GROUP BY status').fetchall()
            # By-station (source) counts
            station_rows = db.execute(
                'SELECT source_station, COUNT(*) as cnt FROM repair_work_orders GROUP BY source_station ORDER BY cnt DESC').fetchall()
            # Defect codes from repair_records
            defect_rows = db.execute(
                "SELECT defect_code, COUNT(*) as cnt FROM repair_records "
                "WHERE defect_code IS NOT NULL AND defect_code != '' AND defect_code != 'NG' "
                "GROUP BY defect_code ORDER BY cnt DESC LIMIT 20").fetchall()
            # Top replaced materials
            mat_rows = db.execute(
                'SELECT material_code, material_name, SUM(quantity) as total_qty, COUNT(*) as usage_count '
                'FROM repair_material_usage WHERE material_code IS NOT NULL AND material_code != "" '
                'GROUP BY material_code, material_name ORDER BY total_qty DESC LIMIT 15').fetchall()
            # Repair result distribution
            result_rows = db.execute(
                "SELECT repair_result, COUNT(*) as cnt FROM repair_work_orders "
                "WHERE repair_result IS NOT NULL GROUP BY repair_result").fetchall()
            # Daily WO volume (last N days)
            daily_rows = db.execute(
                "SELECT DATE(received_at) as day, COUNT(*) as cnt "
                "FROM repair_work_orders WHERE received_at IS NOT NULL "
                "GROUP BY day ORDER BY day DESC LIMIT ?", (days,)).fetchall()
            # Avg repair time (for completed WOs)
            time_rows = db.execute(
                "SELECT repair_completed_at, repair_started_at FROM repair_work_orders "
                "WHERE repair_completed_at IS NOT NULL AND repair_started_at IS NOT NULL "
                "AND repair_completed_at != '' AND repair_started_at != ''").fetchall()
            # Method frequency
            method_rows = db.execute(
                "SELECT repair_method, COUNT(*) as cnt FROM repair_work_orders "
                "WHERE repair_method IS NOT NULL AND repair_method != '' "
                "GROUP BY repair_method ORDER BY cnt DESC LIMIT 10").fetchall()
            # Scrap rate
            scrap_rows = db.execute(
                "SELECT COUNT(*) FROM repair_work_orders WHERE repair_result IN ('scrapped','SCRAPPED')").fetchone()
            total_rows = db.execute("SELECT COUNT(*) FROM repair_work_orders").fetchone()

        # Compute repair time averages
        repair_times = []
        for completed, started in time_rows:
            try:
                if completed and started:
                    c = datetime.fromisoformat(str(completed).replace('Z','+00:00'))
                    s = datetime.fromisoformat(str(started).replace('Z','+00:00'))
                    repair_times.append((c - s).total_seconds() / 60)
            except: pass

        avg_repair_min = sum(repair_times)/len(repair_times) if repair_times else 0
        median_repair_min = sorted(repair_times)[len(repair_times)//2] if repair_times else 0

        total = total_rows[0] if total_rows else 0
        scrapped = scrap_rows[0] if scrap_rows else 0

        LINE_MAP = {
            'manu_ict':'ICT','manu_fct':'FCT','manu_depanel':'DEPANEL',
            'manu_assem_ate':'组装ATE','manu_supersonic':'超声','manu_agingcab':'老化',
            'manu_hivolt_ate':'高压','manu_package_ate':'包装ATE',
            'manu_smt_aoi':'SMT-AOI','manu_smt_paste':'SMT-印刷','manu_smt_pick':'SMT-贴片',
        }
        LINE_CAT = {'manu_ict':'MANUAL','manu_fct':'MANUAL','manu_depanel':'MANUAL',
                    'manu_assem_ate':'MANUAL','manu_supersonic':'MANUAL','manu_agingcab':'AUTO',
                    'manu_hivolt_ate':'AUTO','manu_package_ate':'AUTO',
                    'manu_smt_aoi':'SMT','manu_smt_paste':'SMT','manu_smt_pick':'SMT'}

        # Aggregate by line category
        cat_counts = collections.defaultdict(int)
        for station, cnt in station_rows:
            cat = LINE_CAT.get(station, 'OTHER')
            cat_counts[cat] += cnt

        DEFECT_NAMES = {}
        for source, codes in DEFECT_CODES.items():
            DEFECT_NAMES.update(codes)

        defect_distribution = [{'code': code, 'name': DEFECT_NAMES.get(code, code or 'Unknown'), 'count': cnt}
                              for code, cnt in defect_rows]

        top_materials = [{'code': m[0], 'name': m[1], 'total_qty': m[2], 'usage_count': m[3]}
                         for m in mat_rows]

        daily_trend = [{'day': str(d[0]), 'count': d[1]} for d in reversed(daily_rows)]

        completed_count = sum(cnt for s, cnt in status_rows
                               if 'COMPLETE' in s or 'QUALITY' in s or s in ('PENDING_QUALITY','PENDING_RETEST','CLOSED_RETEST_PASS'))
        in_progress = sum(cnt for s, cnt in status_rows
                          if s in ('REPAIR_IN_PROGRESS','WAITING_RECEIPT','RECEIVED'))

        # ── Station × Material cross-tabulation ─────────────────────────────────
        with self.connect() as db:
            xmat_rows = db.execute("""
                SELECT w.source_station, m.material_code, m.material_name,
                       COUNT(*) as usage_count, SUM(m.quantity) as total_qty
                FROM repair_material_usage m
                JOIN repair_work_orders w ON w.work_order_no = m.work_order_no
                WHERE m.material_code IS NOT NULL AND m.material_code != ''
                GROUP BY w.source_station, m.material_code, m.material_name
                ORDER BY w.source_station, usage_count DESC
            """).fetchall()

        station_materials = collections.defaultdict(list)
        for station, code, name, uc, qty in xmat_rows:
            station_materials[station].append({
                'code': code, 'name': name or code,
                'usage_count': uc, 'total_qty': qty,
                'category': LINE_CAT.get(station, 'OTHER'),
            })

        cat_top_materials = {}
        for cat in set(LINE_CAT.values()):
            cat_stations = [s for s, c in LINE_CAT.items() if c == cat]
            cat_mats = collections.defaultdict(lambda: {'code':'','name':'','usage_count':0,'total_qty':0})
            for st in cat_stations:
                for m in station_materials.get(st, []):
                    cat_mats[m['code']]['code'] = m['code']
                    cat_mats[m['code']]['name'] = m['name']
                    cat_mats[m['code']]['usage_count'] += m['usage_count']
                    cat_mats[m['code']]['total_qty'] += m['total_qty']
            cat_top_materials[cat] = sorted(cat_mats.values(), key=lambda x: -x['usage_count'])[:8]

        # Defect codes per station
        with self.connect() as db:
            xdefect_rows = db.execute("""
                SELECT w.source_station, r.defect_code, COUNT(*) as cnt
                FROM repair_records r
                JOIN repair_work_orders w ON (w.batch_id = r.batch_id OR w.ng_sn = r.sn)
                WHERE r.defect_code IS NOT NULL AND r.defect_code != '' AND r.defect_code != 'NG'
                GROUP BY w.source_station, r.defect_code
                ORDER BY w.source_station, cnt DESC
            """).fetchall()

        station_defects = collections.defaultdict(list)
        for station, code, cnt in xdefect_rows:
            station_defects[station].append({'code': code, 'name': DEFECT_NAMES.get(code, code or 'Unknown'), 'count': cnt})

        return {
            'total_wos': total, 'scrapped': scrapped,
            'scrapped_pct': round(scrapped/total*100, 1) if total else 0,
            'completed': completed_count, 'in_progress': in_progress,
            'completion_rate': round(completed_count/total*100, 1) if total else 0,
            'avg_repair_min': round(avg_repair_min, 1), 'median_repair_min': round(median_repair_min, 1),
            'status_breakdown': [{'status': s, 'count': c} for s, c in status_rows],
            'station_breakdown': [{'station': LINE_MAP.get(s,s), 'code': s, 'count': c} for s, c in station_rows],
            'line_category_breakdown': [{'category': cat, 'count': cnt} for cat, cnt in sorted(cat_counts.items(), key=lambda x:-x[1])],
            'defect_distribution': defect_distribution, 'top_materials': top_materials,
            'result_distribution': [{'result': r or 'Unknown', 'count': c} for r, c in result_rows],
            'daily_trend': daily_trend,
            'method_distribution': [{'method': m or 'Unknown', 'count': c} for m, c in method_rows],
            'station_materials': dict(station_materials),
            'cat_top_materials': cat_top_materials,
            'station_defects': dict(station_defects),
        }

    def submit_statistics_report(self, days=30, period_label=None):
        """Generate and POST a statistics report to MES for a time period."""
        stats = self.fetch_statistics(days)
        period = period_label or f'last_{days}_days'
        report_id = f'REPORT-{self.station_code.upper()}-{period}-{int(time.time()*1000)}'
        payload = {
            'type': 'REPAIR_STATISTICS_REPORT',
            'reportId': report_id,
            'stationCode': self.station_code,
            'periodDays': days,
            'periodLabel': period,
            'generatedAt': int(time.time() * 1000),
            'generatedBy': self.operator,
            'summary': {
                'totalWorkOrders': stats['total_wos'],
                'completed': stats['completed'],
                'inProgress': stats['in_progress'],
                'scrapped': stats['scrapped'],
                'scrappedPct': stats['scrapped_pct'],
                'completionRate': stats['completion_rate'],
                'avgRepairMinutes': stats['avg_repair_min'],
                'medianRepairMinutes': stats['median_repair_min'],
            },
            'lineCategoryBreakdown': stats['line_category_breakdown'],
            'stationBreakdown': stats['station_breakdown'],
            'defectDistribution': stats['defect_distribution'][:20],
            'topMaterials': stats['top_materials'][:15],
            'resultDistribution': stats['result_distribution'],
            'methodDistribution': stats['method_distribution'],
            'dailyTrend': stats['daily_trend'],
            'stationMaterials': {
                s: [{'code': m['code'], 'name': m['name'], 'usageCount': m['usage_count'], 'totalQty': m['total_qty']}
                    for m in items[:10]]
                for s, items in stats['station_materials'].items()
            },
            'stationDefects': {
                s: [{'code': d['code'], 'name': d['name'], 'count': d['count']}
                    for d in items[:10]]
                for s, items in stats['station_defects'].items()
            },
        }
        status, result = http('POST', f'{self.mes_api}/pda/events', {
            'from': self.station_code, 'to': 'mes_server',
            'type': 'REPAIR_STATISTICS_REPORT',
            'stationCode': self.station_code,
            'eventId': report_id,
            'payload': payload,
            'priority': 'normal',
            'createdAt': int(time.time() * 1000),
        }, token=self._ensure_token())
        return {'ok': status == 200, 'report_id': report_id, 'response': result, 'stats': stats}

    # ── Material Traceability ───────────────────────────────────────────────────

    def fetch_material_trace(self, wo_no=None, sn=None, material_code=None, days=0, limit=200):
        """Fetch full material replacement history with full traceability chain.

        Args:
            wo_no:       Filter by repair work order number
            sn:          Filter by product SN
            material_code: Filter by material code
            days:        Only last N days (0 = all time)
            limit:       Max rows to return

        Returns:
            List of material trace records with WO, SN, batch, station, operator, timestamp
        """
        conditions = ['m.material_code IS NOT NULL', "m.material_code != ''"]
        params = []
        if wo_no:
            conditions.append('m.work_order_no = ?')
            params.append(wo_no)
        if sn:
            conditions.append('(w.ng_sn = ? OR m.ng_sn = ?)')
            params.extend([sn, sn])
        if material_code:
            conditions.append('m.material_code = ?')
            params.append(material_code)
        if days > 0:
            cutoff = datetime.now() - timedelta(days=days)
            conditions.append("m.recorded_at >= ?")
            params.append(cutoff.strftime('%Y-%m-%d %H:%M:%S'))
        where = ' AND '.join(conditions) if conditions else '1=1'
        query = f"""
            SELECT
                m.id             as trace_id,
                m.work_order_no  as wo_no,
                w.ng_sn          as ng_sn,
                w.batch_id       as batch_id,
                w.source_station as source_station,
                w.repair_method  as repair_method,
                w.repair_result  as repair_result,
                m.material_code  as material_code,
                m.material_name  as material_name,
                m.quantity        as quantity,
                m.unit           as unit,
                m.operator       as operator,
                m.recorded_at    as replaced_at,
                w.status         as wo_status,
                w.repair_completed_at as wo_completed_at,
                m.lot_no         as lot_no,
                m.supplier_code  as supplier_code,
                m.supplier_name  as supplier_name,
                m.location_code  as location_code,
                m.received_at    as received_at,
                m.iqc_status    as iqc_status,
                m.wms_lot_status as wms_lot_status,
                m.inbound_tx_no  as inbound_tx_no,
                m.inbound_received_at as inbound_received_at,
                m.inbound_po_no  as inbound_po_no,
                m.pick_tx_no     as pick_tx_no,
                m.pick_issued_at as pick_issued_at,
                m.issue_work_order_no as issue_work_order_no
            FROM repair_material_usage m
            JOIN repair_work_orders w ON w.work_order_no = m.work_order_no
            WHERE {where}
            ORDER BY m.recorded_at DESC
            LIMIT ?
        """
        params.append(limit)
        with self.connect() as db:
            rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def submit_material_trace_report(self, wo_no=None, days=30):
        """Generate and POST a material traceability report to MES.

        Args:
            wo_no:  Single WO to report (None = all WOs in period)
            days:   Lookback window for report

        Returns:
            {'ok': bool, 'report_id': str, 'total_records': int, 'response': ...}
        """
        records = self.fetch_material_trace(wo_no=wo_no, days=days, limit=5000)
        if not records:
            return {'ok': True, 'report_id': None, 'total_records': 0, 'records': []}
        report_id = f'MAT_TRACE-{self.station_code.upper()}-{int(time.time()*1000)}'
        payload = {
            'type': 'MATERIAL_REPLACEMENT_TRACE',
            'reportId': report_id,
            'stationCode': self.station_code,
            'generatedAt': int(time.time() * 1000),
            'generatedBy': self.operator,
            'periodDays': days,
            'woNo': wo_no,
            'totalRecords': len(records),
            'records': [
                {
                    'woNo':              r['wo_no'],
                    'ngSn':              r['ng_sn'],
                    'batchId':           r['batch_id'],
                    'sourceStation':     r['source_station'],
                    'repairMethod':      r['repair_method'] or '',
                    'repairResult':      r['repair_result'] or '',
                    'materialCode':      r['material_code'],
                    'materialName':      r['material_name'] or r['material_code'],
                    'quantity':          r['quantity'],
                    'unit':              r['unit'] or 'PCS',
                    'operator':          r['operator'] or '',
                    'replacedAt':        r['replaced_at'],
                    'woStatus':          r['wo_status'] or '',
                    'woCompletedAt':     r['wo_completed_at'] or '',
                    # ── WMS traceability chain ────────────────────────────
                    'lotNo':             r['lot_no'] or '',
                    'supplierCode':      r['supplier_code'] or '',
                    'supplierName':      r['supplier_name'] or '',
                    'locationCode':      r['location_code'] or '',
                    'receivedAt':        r['received_at'] or '',
                    'iqcStatus':        r['iqc_status'] or '',
                    'wmsLotStatus':     r['wms_lot_status'] or '',
                    'inboundTxNo':      r['inbound_tx_no'] or '',
                    'inboundReceivedAt': r['inbound_received_at'] or '',
                    'inboundPoNo':      r['inbound_po_no'] or '',
                    'pickTxNo':         r['pick_tx_no'] or '',
                    'pickIssuedAt':     r['pick_issued_at'] or '',
                    'issueWorkOrderNo': r['issue_work_order_no'] or '',
                }
                for r in records
            ],
        }
        status, result = http('POST', f'{self.mes_api}/pda/events', {
            'from': self.station_code,
            'to': 'mes_server',
            'type': 'MATERIAL_REPLACEMENT_TRACE',
            'stationCode': self.station_code,
            'eventId': report_id,
            'payload': payload,
            'priority': 'normal',
            'createdAt': int(time.time() * 1000),
        }, token=self._ensure_token())
        return {
            'ok': status == 200,
            'report_id': report_id,
            'total_records': len(records),
            'response': result,
            'records': records,
        }

    # ── WMS Material Lot Lookup ───────────────────────────────────────────────

    def wms_lookup_lot(self, lot_no_or_label):
        """Query MES WMS for a material lot by lot_no or label_id (smart shelf barcode).

        Returns full lot record: {lotNo, materialCode, materialName, qty, iqcStatus,
        supplierCode, supplierName, locationCode, receivedAt, lotStatus}
        """
        if not lot_no_or_label:
            return None
        # Try by lot_no first, then by label_id
        for key in ('lotNo', 'labelId'):
            url = f'{self.mes_api}/wms/material-lots?{key}={urllib.parse.quote(lot_no_or_label)}&limit=1'
            status, data = http('GET', url, timeout=6)
            if status == 200:
                items = data.get('data', [])
                if items:
                    row = items[0]
                    return {
                        'lot_no':         row.get('lotNo', lot_no_or_label),
                        'label_id':       row.get('labelId', ''),
                        'material_code':  row.get('materialCode', ''),
                        'material_name':  row.get('name_zh', row.get('materialCode', '')),
                        'qty':            row.get('qty', 0),
                        'iqc_status':     row.get('iqcStatus', ''),
                        'supplier_code':  row.get('supplierCode', ''),
                        'supplier_name':  row.get('supplierName', ''),
                        'location_code':  row.get('locationCode', ''),
                        'received_at':    row.get('receivedAt', ''),
                        'lot_status':     row.get('lotStatus', 'open'),
                    }
        return None

    def wms_lot_transaction_chain(self, lot_no):
        """Fetch the full inventory transaction chain for a lot_no.

        Returns ordered list of transactions from RECEIVE → IQC → STORAGE → PICK → ISSUE_TO_LINE.
        Each entry: {txNo, action, qty, referenceType, referenceNo, occurredAt}
        """
        if not lot_no:
            return []
        url = f'{self.mes_api}/wms/inventory-transactions?limit=100'
        status, data = http('GET', url, timeout=6)
        if status != 200:
            return []
        all_tx = data.get('data', [])
        # Filter to transactions involving this lot
        chain = []
        for tx in all_tx:
            lots = tx.get('lots', [])
            if any(str(lot_no) in str(l.get('lotNo', '')) for l in lots):
                chain.append({
                    'tx_no':         tx.get('txNo', ''),
                    'action':        tx.get('action', ''),
                    'qty':           tx.get('qty', 0),
                    'reference_type':tx.get('referenceType', ''),
                    'reference_no':  tx.get('referenceNo', ''),
                    'occurred_at':   tx.get('occurredAt', ''),
                })
        # Sort chronologically
        chain.sort(key=lambda x: x.get('occurred_at', ''))
        return chain

    def record_material_with_lot(self, work_order_no, lot_no_or_label, material_code,
                                 material_name, quantity, unit, operator):
        """Record a material replacement with WMS lot traceability.

        1. Look up lot from WMS (supplier, location, received date, IQC status)
        2. Fetch transaction chain (RECEIVE → PICK → ISSUE)
        3. Store everything in local DB
        """
        work_order_no = str(work_order_no or '').strip()
        lot_no_or_label = str(lot_no_or_label or '').strip()
        if not work_order_no:
            raise ReworkError('工单号必填')
        if not lot_no_or_label:
            raise ReworkError('物料批号/标签必填')

        # WMS lookup
        lot_info = self.wms_lookup_lot(lot_no_or_label)
        wms_data = lot_info or {}
        inbound_tx = None
        pick_tx = None
        if lot_no_or_label:
            chain = self.wms_lot_transaction_chain(lot_no_or_label)
            for tx in chain:
                if tx['action'].upper() in ('RECEIVE', 'RECEIVING', 'INBOUND'):
                    inbound_tx = tx
                elif tx['action'].upper() in ('ISSUE', 'ISSUE_TO_LINE', 'PICK', 'PICKING'):
                    pick_tx = tx

        ts = now_text()
        with self.connect() as db:
            # Get ng_sn for this WO
            wo = db.execute('SELECT ng_sn FROM repair_work_orders WHERE work_order_no=?',
                            (work_order_no,)).fetchone()
            ng_sn = wo['ng_sn'] if wo else ''
            db.execute("""
                INSERT INTO repair_material_usage(
                    work_order_no, ng_sn, material_code, material_name, quantity, unit,
                    operator, recorded_at, lot_no, supplier_code, supplier_name,
                    location_code, wms_material_id, received_at, iqc_status, wms_lot_status,
                    inbound_tx_no, inbound_received_at, inbound_po_no,
                    pick_tx_no, pick_issued_at, pick_issued_by, issue_work_order_no, wms_synced
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            """, (
                work_order_no, ng_sn,
                material_code or wms_data.get('material_code', ''),
                material_name or wms_data.get('material_name', ''),
                quantity, unit or 'PCS',
                operator or self.operator, ts,
                wms_data.get('lot_no', lot_no_or_label),
                wms_data.get('supplier_code', ''),
                wms_data.get('supplier_name', ''),
                wms_data.get('location_code', ''),
                None,  # wms_material_id
                wms_data.get('received_at', ''),
                wms_data.get('iqc_status', ''),
                wms_data.get('lot_status', ''),
                inbound_tx['tx_no'] if inbound_tx else None,
                inbound_tx['occurred_at'] if inbound_tx else None,
                inbound_tx['reference_no'] if inbound_tx else None,
                pick_tx['tx_no'] if pick_tx else None,
                pick_tx['occurred_at'] if pick_tx else None,
                pick_tx['reference_no'] if pick_tx else None,   # pick_issued_by (actor)
                pick_tx['reference_no'] if pick_tx else None,   # issue_work_order_no
            ))
        self._emit('MATERIAL_RECORDED_WITH_LOT', {
            'workOrderNo': work_order_no,
            'ngSn': ng_sn,
            'materialCode': material_code,
            'lotNo': wms_data.get('lot_no', lot_no_or_label),
            'supplierCode': wms_data.get('supplier_code', ''),
            'operator': operator or self.operator,
            'recordedAt': ts,
        }, idempotent_id=f'{work_order_no}-{lot_no_or_label}-{ts}')
        return {
            'ok': True,
            'work_order_no': work_order_no,
            'lot_no': wms_data.get('lot_no', lot_no_or_label),
            'supplier_code': wms_data.get('supplier_code', ''),
            'supplier_name': wms_data.get('supplier_name', ''),
            'location_code': wms_data.get('location_code', ''),
            'iqc_status': wms_data.get('iqc_status', ''),
            'received_at': wms_data.get('received_at', ''),
            'inbound_tx': inbound_tx,
            'pick_tx': pick_tx,
        }

    def fetch_all(self):
        snap=self.snapshot()
        snap['pending_handovers']=self.fetch_pending_handovers()
        snap['active_repairs']=self.fetch_active_repairs()
        return snap
