
# -*- coding: utf-8 -*-
import socket,subprocess,threading,time,tkinter as tk,sys
from pathlib import Path
from tkinter import messagebox,ttk
from supersonic_core import SupersonicCore,SupersonicError,MES_URL,STATION_CODE
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from station_common_bootstrap import attach_common_agent
COMMON_AGENT = attach_common_agent(STATION_CODE, __file__, "supersonic")
from station_heartbeat import StationHeartbeat
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from station_language import install_language_menu
from station_ui_primitives import UI_PREVIEW, add_preview_watermark, configure_tk_station, restore_scanner_focus
from station_arrival_ui import ProductGateComponent
from station_scan_alarm import show_blocking_alarm

def speak_alert(text):
 safe=str(text).replace("'","''")
 try:
  subprocess.Popen(["powershell","-NoProfile","-WindowStyle","Hidden","-Command",f"Add-Type -AssemblyName System.Speech;$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;$v.Speak('{safe}')"],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
 except Exception:
  pass

class _SupersonicPreviewCore:
 sql_connected=True
 def snapshot(self):
  row={'test_time':'2026-08-04 10:08:00','sn':'RJ-US-PREVIEW-0008','result':'OK','frequency':'20.1 kHz','amplitude':'42 um','wavetime':'1.8 s','energy':'880 J','power':'520 W','source_table':'PREVIEW_ONLY'}
  return {'results':[row],'ng':[],'arrival':{'route':{'identity_type':'PCBA','identity':'RJ-US-PREVIEW-0008','gate_state':'ALLOW','reason':'Expected process','next_action':'Continue to Assembly ATE'}},'maintenance':{'cases':[]},'history':{'batches':[]},'outbox':[{'event_id':'PREVIEW-EVT-US-001','event_type':'TEST_RESULT','status':'BLOCKED','last_error':'UI_PREVIEW'}],'sql':{'host':'NO CONNECTION','port':'--','database':'PREVIEW','table':'PREVIEW_ONLY','connected':False},'changes':[]}
 def check_scan(self,value):return {'status':'PREVIEW','sn':value or 'RJ-US-PREVIEW-0008','blocked':False,'detail':'No production lookup performed'}
 def poll_sql_once(self):return {'table':'PREVIEW_ONLY','added':0}
 def sync_once(self):return None

class Supersonic2D:
 def __init__(self,root):
        self._rendered_result_keys=set()
        self._spoken_result_keys=set()
        self._alarm_result_keys=set()
        self.root=root;self.core=_SupersonicPreviewCore() if UI_PREVIEW else SupersonicCore();self.running=True;self.heartbeat=None if UI_PREVIEW else StationHeartbeat(STATION_CODE,MES_URL,'supersonic_agent');self.scan=tk.StringVar();self.status=tk.StringVar(value='PREVIEW · deterministic sample · all writes blocked' if UI_PREVIEW else 'SQL Server连接中');root.title('超声工站 / SUPERSONIC · 2D');configure_tk_station(root);install_language_menu(root);add_preview_watermark(root);self.build();self.refresh()
        if not UI_PREVIEW:
            threading.Thread(target=self.event_worker,daemon=True).start()
            threading.Thread(target=self.sync_worker,daemon=True).start()
            threading.Thread(target=self.scanner,daemon=True).start()
 def build(self):
  h=tk.Frame(self.root,bg='#10243b');h.pack(fill='x');tk.Label(h,text='超声工站 · 单SN测试',bg='#10243b',fg='white',font=('Microsoft YaHei',22,'bold')).pack(side='left',padx=16,pady=10);tk.Label(h,textvariable=self.status,bg='#10243b',fg='#38bdf8',font=('Microsoft YaHei',12,'bold')).pack(side='right',padx=16)
  bar=tk.Frame(self.root,bg='#422006');bar.pack(fill='x',padx=12,pady=6);tk.Label(bar,text='扫码只检查NG/重复',bg='#422006',fg='#fde047').pack(side='left',padx=8);e=tk.Entry(bar,textvariable=self.scan,width=35);self.scan_entry=e;e.pack(side='left',pady=8,ipady=7);e.bind('<Return>',lambda _e:self.check());COMMON_AGENT.bind_ui_root(self.root,self._common_scan);tk.Button(bar,text='检查',command=self.check).pack(side='left',padx=6)
  self.product_gate=ProductGateComponent(self.root)
  self.card=tk.Label(self.root,text='等待 SQL Server 新记录\nWAITING',bg='#334155',fg='white',font=('Consolas',30,'bold'),height=4,relief='ridge');self.card.pack(fill='x',padx=12,pady=6)
  self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill='both',expand=True,padx=12,pady=6);self.trees={}
  specs={'测试结果':['时间','SN','结果','频率','振幅','波时','能量','功率','来源'],'SQLite记录':['时间','SN','结果','来源','缓存时间'],'SQL TABLE':['TABLE','TIME','SN','RESULT','SOURCE'],'NG':['时间','SN','来源'],'维修工单':['本地工单','MES工单','SN','部门','状态'],'历史封存':['批次','记录数','哈希','时间'],'MES通信':['事件','类型','状态','错误'],'设置':['项目','值'],'修改记录':['编号','版本','原因','内容']}
  for name,cols in specs.items():
   f=tk.Frame(self.tabs);self.tabs.add(f,text=name);t=ttk.Treeview(f,columns=cols,show='headings');self.trees[name]=t
   for c in cols:t.heading(c,text=c);t.column(c,width=145,anchor='center')
   t.pack(side='left',fill='both',expand=True);ttk.Scrollbar(f,command=t.yview).pack(side='right',fill='y')
 def fill(self,name,rows):
  t=self.trees[name];t.delete(*t.get_children())
  for row in rows:t.insert('','end',values=row)
 def _voice_new_ng(self,rows):
  for row in rows:
   result=str(row.get('result','')).upper()
   key=f"{row.get('sn','')}|{row.get('test_time','')}|{row.get('source_table','')}"
   if key in self._spoken_result_keys:continue
   if result in {'NG','FAIL','NOK'}:
    self._spoken_result_keys.add(key);speak_alert(f"Supersonic NG. Check serial number {row.get('sn','')}")
 def _alarm_new_ng(self,rows):
  """Block the station when a newly imported tester result is NG.

  Scanner blocking only protects a later scan.  An NG arriving directly from
  SQL Server must also stop the operator immediately; otherwise the current
  unit can continue through the station before anyone scans it again.
  """
  for row in rows:
   result=str(row.get('result','')).strip().upper()
   key=f"{row.get('sn','')}|{row.get('test_time','')}|{row.get('source_table','')}"
   if result in {'NG','FAIL','NOK'} and key not in self._alarm_result_keys:
    self._alarm_result_keys.add(key)
    show_blocking_alarm(self.root,'NG',row.get('sn',''),
                        f"Supersonic tester NG: {row.get('test_time','')}",
                        STATION_CODE,MES_URL)
 def _prime_voice_keys(self,rows):
  """Seed history without speaking old NG records during startup."""
  for row in rows:
   self._spoken_result_keys.add(f"{row.get('sn','')}|{row.get('test_time','')}|{row.get('source_table','')}")
 def append_results(self,rows):
  # Recover keys from the initial full render so SQL events append only new rows.
  result_tree=self.trees.get('测试结果') or next(iter(self.trees.values()))
  for item_id in result_tree.get_children():
   values=result_tree.item(item_id,'values')
   if len(values) >= 9:
    self._rendered_result_keys.add(f"{values[1]}|{values[0]}|{values[8]}")
  """Append only unseen SQL rows; avoid repainting existing result tables."""
  result_tree=self.trees['测试结果'];sql_tree=self.trees['SQL TABLE']
  for x in rows:
   key=str(x.get('event_key') or f"{x.get('sn','')}|{x.get('test_time','')}|{x.get('source_table','')}")
   if key in self._rendered_result_keys:continue
   self._rendered_result_keys.add(key)
   values=(x.get('test_time',''),x.get('sn',''),x.get('result',''),x.get('frequency',''),x.get('amplitude',''),x.get('wavetime',''),x.get('energy',''),x.get('power',''),x.get('source_table',''))
   result_tree.insert('','end',values=values)
   sql_tree.insert('','end',values=(x.get('source_table',''),x.get('test_time',''),x.get('sn',''),x.get('result',''),x.get('source_table','')))
 def check(self, clear_input=True):
  try:
   raw=self.scan.get();code=str(raw or '').strip().upper()
   r=({'status':'NG','sn':code,'blocked':True,'detail':'MES confirmed NG (LOCAL SQLITE)'}
      if code and COMMON_AGENT.local_confirmed_ng(code) else self.core.check_scan(raw))
   if clear_input:self.scan.set('')
   self.status.set(f'{r["status"]}: {r["sn"]}')
   if r.get('status') in {'NG','NG_TOO_OLD'}:speak_alert('NG')
   elif r.get('status')=='DUPLICATE':speak_alert(f"Duplicate serial number {r['sn']}. Confirm retest if required")
   if r.get('blocked'):
    show_blocking_alarm(self.root,r.get('status','BLOCKED'),r.get('sn',''),r.get('detail',''),STATION_CODE,MES_URL)
  except SupersonicError as e:messagebox.showwarning('扫码',str(e))

 def _common_scan(self,value,scanner_id=''):
  """Route keyboard-wedge/COM scans into the visible Supersonic check."""
  self._accept_scanned_value(value)
 def _accept_scanned_value(self,value):
  """Accept a scanner burst without requiring a physical keyboard."""
  value=str(value or '').strip().upper()
  if not value:return
  self.scan.set(value)
  self.check(clear_input=False)
  self.refresh()
  restore_scanner_focus(self.root,self.scan_entry)
 def event_worker(self):
  initialized=False
  while self.running:
   try:
    if self.heartbeat:
     try:self.heartbeat.tick(sourceConnected=self.core.sql_connected,sourceType='SQL_SERVER')
     except Exception:pass
    if not initialized:
     result=self.core.poll_sql_once()
     initialized=True
     self.root.after(0,lambda x=result:self.status.set(f'SQL初始同步 · {x["table"]} · 读取{x["read"]}条'))
     self.root.after(0,lambda:self.refresh())
     continue
    # Active polling is authoritative. Do not wait for a Service Broker
    # trigger; read SQL Server on a one-second cadence.
    time.sleep(1)
    event={'received':False}
    result=self.core.poll_sql_once()
    if event.get('received') or result.get('added'):
     mode='SQL事件在线' if event.get('received') else 'SQL轮询在线'
     self.root.after(0,lambda x=result,m=mode:self.status.set(f'{m} · {x["table"]} · 新增{x["added"]}'))
     self.root.after(0,lambda:self.refresh_incremental())
   except Exception as e:
    self.core.sql_connected=False
    try:
     fallback=self.core.poll_sql_once()
     self.root.after(0,lambda x=fallback:self.status.set(f'SQL触发器不可用 · 水位降级读取 {x["added"]} 条'))
     self.root.after(0,lambda:self.refresh_incremental())
    except Exception as poll_error:
     self.root.after(0,lambda x=str(poll_error):self.status.set('SQL事件/降级读取失败: '+x[:100]))
    time.sleep(1)
 def sync_worker(self):
  while self.running:
   try:self.core.sync_once()
   except Exception as e:self.root.after(0,lambda x=str(e):self.status.set('MES sync delayed: '+x[:100]))
   time.sleep(5)
 def scanner(self):
  s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
  try:
   s.bind(('0.0.0.0',1008));s.listen(5);s.settimeout(1)
   while self.running:
    try:
     c,_=s.accept();v=c.recv(4096).decode(errors='ignore').strip();c.close()
     if v:self.root.after(0,lambda x=v:self._accept_scanned_value(x))
    except socket.timeout:pass
  except OSError as e:self.root.after(0,lambda:self.status.set(f'扫码端口错误: {e}'))
  finally:s.close()
 def refresh_incremental(self):
  """Update the live card and append new SQL rows without repainting result tables."""
  s=self.core.snapshot();self.product_gate.update(s.get('arrival',{}));r=s.get('results',[]);latest=r[0] if r else None
  self._voice_new_ng(r);self.card.config(text=f'{latest["sn"]}\n{latest["result"]}' if latest else 'WAITING SQL Server',bg='#166534' if latest and latest['result']=='OK' else '#991b1b' if latest else '#334155')
  self.append_results(r)
  self.fill('SQLite记录',[(x.get('test_time',''),x.get('sn',''),x.get('result',''),x.get('source_table',''),x.get('cached_at','')) for x in r])
  self.fill('NG',[(x.get('test_time',''),x.get('sn',''),x.get('source_table','')) for x in s.get('ng',[])[:1]])
 def refresh(self):
  s=self.core.snapshot();self.product_gate.update(s.get('arrival',{}));r=s['results'];latest=r[0] if r else None;self._prime_voice_keys(r)
  self.card.config(text=f'{latest["sn"]}\n{latest["result"]}' if latest else '等待 SQL Server 新记录\nWAITING',bg='#166534' if latest and latest['result']=='OK' else '#991b1b' if latest else '#334155')
  self.fill('测试结果',[(x.get('test_time',''),x.get('sn',''),x.get('result',''),x.get('frequency',''),x.get('amplitude',''),x.get('wavetime',''),x.get('energy',''),x.get('power',''),x.get('source_table','')) for x in r]);self.fill('SQLite记录',[(x.get('test_time',''),x.get('sn',''),x.get('result',''),x.get('source_table',''),x.get('cached_at','')) for x in r]);self.fill('SQL TABLE',[(x.get('source_table',''),x.get('test_time',''),x.get('sn',''),x.get('result',''),x.get('source_table','')) for x in r]);self.fill('NG',[(x.get('test_time',''),x.get('sn',''),x.get('source_table','')) for x in s['ng'][:1]]);self.fill('维修工单',[(x['local_case_id'],x['mes_work_order_id'] or '',x['sn'],x['department'],x['status']) for x in s['maintenance']['cases']]);self.fill('历史封存',[(x['archive_batch_id'],x['record_count'],x['content_hash'],x['sealed_at']) for x in s['history']['batches']]);self.fill('MES通信',[(x['event_id'],x['event_type'],x['status'],x['last_error']) for x in s['outbox']]);q=s['sql'];self.fill('设置',[('SQL Server',f'{q["host"]}:{q["port"]}'),('Database',q['database']),('Table',q['table']),('Connected',q['connected']),('数据流向','SQL Server → 本地SQLite → MES'),('NG策略','记录/标记；不语音报警')]);self.fill('修改记录',[(x['change_id'],x['version'],x['reason'],x['summary']) for x in s['changes']])
 def close(self):self.running=False;self.root.destroy()
if __name__=='__main__':
 root=tk.Tk();app=Supersonic2D(root)
 if not UI_PREVIEW:
  from station_retest import install_station_retest_panel
  from station_repair_workflow import install_repair_workflow
  install_station_retest_panel(root,STATION_CODE,MES_URL.replace('/api/pda/events',''))
  install_repair_workflow(root,STATION_CODE,MES_URL,'超声')
 root.protocol('WM_DELETE_WINDOW',app.close);root.mainloop()
