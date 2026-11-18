# -*- coding: utf-8 -*-
import re,socket,subprocess,threading,time,tkinter as tk,sys
from pathlib import Path
from tkinter import messagebox,ttk
APP_DIR=Path(__file__).resolve().parent
sys.path.insert(0,str(APP_DIR.parent))
MANUAL_LINE=APP_DIR.parent.parent/'002-自动线'
if not getattr(sys,'frozen',False) and str(MANUAL_LINE) not in sys.path and MANUAL_LINE.exists():sys.path.insert(1,str(MANUAL_LINE))
from aging_cab_core import AgingCabCore,AgingCabError,EXPECTED_AGING_MS,MES_URL,STATION_CODE
from station_heartbeat import StationHeartbeat
from station_runtime_safety import acquire_single_instance
from station_scan_alarm import show_blocking_alarm
from station_language import install_language_menu
from station_ui_primitives import install_station_tabs

def speak(text):
 safe=str(text).replace("'","''");subprocess.Popen(['powershell','-NoProfile','-WindowStyle','Hidden','-Command',f"Add-Type -AssemblyName System.Speech;$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;$v.Speak('{safe}')"],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
def fmt(ms):
 if not ms:return '--'
 return time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(int(ms)/1000))
def duration(ms):
 sec=max(0,int(ms)//1000);return f'{sec//3600:02d}:{sec%3600//60:02d}:{sec%60:02d}'

class AgingCab2D:
 def __init__(self,root):
        install_station_tabs(root)
        self.root=root;self.core=AgingCabCore();self.running=True;self.heartbeat=StationHeartbeat(STATION_CODE,MES_URL,'aging_cab_agent');self.scan=tk.StringVar();self.status=tk.StringVar(value='SQL Server连接中');self.summary=tk.StringVar(value='等待老化结果');root.title('成品老化 / AGING CAB · 2D');root.geometry('1600x920');root.configure(bg='#07111f');install_language_menu(root);self.build();self.refresh();threading.Thread(target=self.worker,daemon=True).start();threading.Thread(target=self.scanner,daemon=True).start()
 def build(self):
  self.simulated_slots={}
  self.simulated_batches=[]
  self.simulated_batch_states=[]
  self.simulated_batch_rows=[]
  h=tk.Frame(self.root,bg='#10243b');h.pack(fill='x');tk.Label(h,text='成品老化 · 1个老化柜',bg='#10243b',fg='white',font=('Microsoft YaHei',22,'bold')).pack(side='left',padx=16,pady=10);tk.Label(h,textvariable=self.status,bg='#10243b',fg='#38bdf8',font=('Microsoft YaHei',12,'bold')).pack(side='right',padx=16)
  bar=tk.Frame(self.root,bg='#172033');bar.pack(fill='x',padx=12,pady=6);tk.Label(bar,text='扫码只检查、不生成SN记录',bg='#172033',fg='#fde047').pack(side='left',padx=(8,5),pady=7);e=tk.Entry(bar,textvariable=self.scan,font=('Consolas',14),width=28);e.pack(side='left');e.bind('<Return>',lambda _e:self.check());tk.Button(bar,text='检查',command=self.check).pack(side='left',padx=5)
  tk.Button(bar,text='模拟20槽位',command=self.simulate_20,bg='#7c3aed',fg='white',font=('Microsoft YaHei',12,'bold')).pack(side='left',padx=8)
  tk.Button(bar,text='清除模拟',command=self.clear_simulation,bg='#475569',fg='white',font=('Microsoft YaHei',11)).pack(side='left',padx=3)
  tk.Label(self.root,textvariable=self.summary,bg='#0f172a',fg='#67e8f9',font=('Consolas',13,'bold')).pack(fill='x',padx=12);self.progress=ttk.Progressbar(self.root,maximum=100);self.progress.pack(fill='x',padx=12,pady=5)
  self.line_box=tk.LabelFrame(self.root,text='入口 → 约20米老化输送线（位置001–151，左右架号）→ 出口；每个移动架20槽（每2秒刷新）',bg='#07111f',fg='white',font=('Microsoft YaHei',11,'bold'));self.line_box.pack(fill='x',padx=12)
  self.line_count=tk.StringVar(value='当前移动架：等待SQL');tk.Label(self.line_box,textvariable=self.line_count,bg='#07111f',fg='#67e8f9',font=('Microsoft YaHei',10,'bold')).pack(anchor='w',padx=8)
  self.line_canvas=tk.Canvas(self.line_box,bg='#07111f',height=78,highlightthickness=0);line_scroll=ttk.Scrollbar(self.line_box,orient='horizontal',command=self.line_canvas.xview);self.line_canvas.configure(xscrollcommand=line_scroll.set);self.line_canvas.pack(fill='x',expand=True);line_scroll.pack(fill='x')
  self.line_frame=tk.Frame(self.line_canvas,bg='#07111f');self.line_window=self.line_canvas.create_window((0,0),window=self.line_frame,anchor='nw');self.line_frame.bind('<Configure>',lambda _e:self.line_canvas.configure(scrollregion=self.line_canvas.bbox('all')))
  self.cabs=tk.LabelFrame(self.root,text='移动架20槽最终结果 / 20-SLOT CARRIER RESULT HISTORY',bg='#07111f',fg='white',font=('Microsoft YaHei',11,'bold'));self.cabs.pack(fill='x',padx=12)
  self.cab_canvas=tk.Canvas(self.cabs,bg='#07111f',height=245,highlightthickness=0);scroll=ttk.Scrollbar(self.cabs,orient='vertical',command=self.cab_canvas.yview);self.cab_canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.cab_canvas.pack(side='left',fill='both',expand=True)
  self.cab_history=tk.Frame(self.cab_canvas,bg='#07111f');self.cab_window=self.cab_canvas.create_window((0,0),window=self.cab_history,anchor='nw');self.cab_history.bind('<Configure>',lambda _e:self.cab_canvas.configure(scrollregion=self.cab_canvas.bbox('all')));self.cab_canvas.bind('<Configure>',lambda e:self.cab_canvas.itemconfigure(self.cab_window,width=e.width));self.cab_frames=[self.cab_history]
  self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill='both',expand=True,padx=12,pady=7);self.trees={};specs={'输送线架位':['位置','左架号','右架号','区域状态'],'移动架20槽':['架号','槽位','SN','槽位结果','架状态','更新时间'],'SQL仓位状态':['编号','使用值','状态','InIndex','测试文件'],'老化时间':['柜','槽位','SN','状态','开始','预计结束','当前时长','要求时长'],'测试结果':['时间','SN','结果','来源'],'NG':['时间','SN','来源'],'报到记录':['到站','SN','预发','状态','MES确认'],'报到异常':['时间','SN','原因','说明','维修工单'],'维修工单':['本地工单','MES工单','SN','部门','状态'],'历史封存':['批次','记录数','哈希','时间'],'MES通信':['事件','类型','状态','错误'],'设置':['项目','值'],'修改记录':['编号','版本','原因','内容']}
  for n,cols in specs.items():f=tk.Frame(self.tabs);self.tabs.add(f,text=n);t=ttk.Treeview(f,columns=cols,show='headings');self.trees[n]=t
  for n,t in self.trees.items():
   for c in t['columns']:t.heading(c,text=c);t.column(c,width=145,anchor='center')
   t.pack(fill='both',expand=True)
 def fill(self,n,rows):t=self.trees[n];t.delete(*t.get_children());[t.insert('','end',values=x) for x in rows]
 def simulate_20(self):
  stamp=time.strftime('%H%M%S')
  test_time=time.strftime('%Y-%m-%d %H:%M:%S')
  batch={position:{
   'sn':f'SIM57{stamp}{position:02d}',
   'result':'NG' if position in {6,14} else 'OK',
   'test_time':test_time,
   'source_table':f'dbo.BI_Test_Result::EPS48WR1-36::fixture=60::position={position}'
  } for position in range(1,21)}
  self.simulated_batches.append(batch);self.simulated_slots=batch
  batch_index=len(self.simulated_batches)-1;self.simulated_batch_states.append('ROLLING_IN');self.simulated_batch_rows.append(1)
  self.status.set('模拟批次进入：20槽位，18 PASS / 2 NG；完成后同步MES')
  self.refresh()
  for row_number in range(2,152):self.root.after((row_number-1)*65,lambda index=batch_index,row=row_number:self._move_simulation(index,row))
  self.root.after(10000,lambda index=batch_index:self._set_simulation_state(index,'ROLLING_OUT'))
  self.root.after(11200,lambda index=batch_index:self._finish_simulation(index))
 def _move_simulation(self,index,row):
  if index>=len(self.simulated_batch_rows):return
  self.simulated_batch_rows[index]=row;self.simulated_batch_states[index]='AGING' if row<151 else 'ROLLING_OUT';self.status.set(f'模拟移动架 {index+1}: 输送线位置 {row:03d}/151（架内20槽）');self.refresh()
 def _set_simulation_state(self,index,state):
  if index>=len(self.simulated_batch_states):return
  self.simulated_batch_states[index]=state;self.status.set(f'模拟批次 {index+1}: {state}');self.refresh()
 def _finish_simulation(self,index):
  if index>=len(self.simulated_batches):return
  self.simulated_batch_states[index]='COMPLETE'
  for position,row in sorted(self.simulated_batches[index].items()):
   self.core.handle_source_row(row['sn'],row['result'],row['test_time'],row['source_table'],simulation=True)
  self.core.sync_once(limit=100)
  self.status.set(f'模拟批次 {index+1}: COMPLETE，20条最终结果已进入MES同步队列')
  self.refresh()
 def clear_simulation(self):
  self.simulated_slots={}
  self.simulated_batches=[]
  self.simulated_batch_states=[]
  self.simulated_batch_rows=[]
  self.status.set('模拟数据已清除')
  self.refresh()
 def start(self):
  try:r=self.core.start_batch([x['sn'] for x in self.core.snapshot()['native'] if x['sn']]);self.status.set('开始老化 '+r['batchId']);speak('开始老化计时');self.refresh()
  except AgingCabError as e:messagebox.showwarning('开始老化',str(e))
 def end(self):
  try:b=self.core.end_batch();self.status.set('结束老化 '+b);speak('结束老化计时');self.refresh()
  except AgingCabError as e:messagebox.showwarning('结束老化',str(e))
 def check(self):
  try:r=self.core.check_scan(self.scan.get());self.scan.set('');self.status.set(f'{r["status"]}: {r["sn"]}');show_blocking_alarm(self.root,r['status'],r['sn'],r['detail'],STATION_CODE,MES_URL) if r['blocked'] else None
  except AgingCabError as e:messagebox.showwarning('扫码',str(e))
 def worker(self):
  while self.running:
   self.heartbeat.tick(sourceConnected=self.core.sql_connected,sourceType='SQL_SERVER',sourceTable=self.core.sql_table)
   try:r=self.core.poll_sql_once();self.root.after(0,lambda x=r:self.status.set(f'SQL Server在线 · 读取{x["read"]} · 新增{x["added"]}'))
   except Exception as e:self.core.sql_connected=False;self.root.after(0,lambda x=str(e):self.status.set('SQL Server离线: '+x[:100]))
   self.core.sync_once();self.root.after(0,self.refresh);time.sleep(2)
 def scanner(self):
  s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
  try:
   s.bind(('0.0.0.0',1009));s.listen(5);s.settimeout(1)
   while self.running:
    try:c,_=s.accept();v=c.recv(4096).decode(errors='ignore').strip();c.close();self.root.after(0,lambda x=v:(self.scan.set(x),self.check())) if v else None
    except socket.timeout:pass
  except OSError as e:self.root.after(0,lambda:self.status.set(f'扫码端口错误: {e}'))
  finally:s.close()
 def refresh(self):
  timed=self.core.check_timeouts();speak('老化时间已到') if timed else None;s=self.core.snapshot();now=int(time.time()*1000)
  ui_signature=(tuple((x['position'],x['leftStand'],x['rightStand'],x['state']) for x in self.core.area_state),tuple((x['stand'],x['slot'],x['sn'],x['result'],x['standState'],x['updatedAt']) for x in self.core.stand_slots),tuple((x.get('event_key'),x.get('result')) for x in s['results'][:200]))
  if ui_signature==getattr(self,'_last_ui_signature',None) and not self.simulated_batches:return
  self._last_ui_signature=ui_signature
  for child in self.line_frame.winfo_children():child.destroy()
  real_rows={int(x['position']):x for x in self.core.area_state}
  real_stands={v for x in self.core.area_state for v in (x['leftStand'],x['rightStand']) if v not in {'','0','NULL'} and v.isdigit()};self.line_count.set(f'当前移动架：{len(real_stands)} 个（去重） · 非零占位：{sum((x["leftStand"] not in {"","0","NULL"})+(x["rightStand"] not in {"","0","NULL"}) for x in self.core.area_state)}')
  simulated_at={self.simulated_batch_rows[index]:index for index in range(len(self.simulated_batch_rows)) if self.simulated_batch_states[index]!='COMPLETE'}
  tk.Label(self.line_frame,text='入口 →',bg='#07111f',fg='#fde047',font=('Microsoft YaHei',10,'bold')).pack(side='left',padx=4)
  for row_number in range(1,152):
   row=real_rows.get(row_number,{});sim_index=simulated_at.get(row_number);left=row.get('leftStand','0');right=row.get('rightStand','0');occupied=left not in {'','0','NULL'} or right not in {'','0','NULL'}
   state='SIM '+str(sim_index+1) if sim_index is not None else str(row.get('state') or '等待');color='#2563eb' if sim_index is not None else '#166534' if occupied else '#334155'
   tk.Label(self.line_frame,text=f'{row_number:03d}\nL:{left} R:{right}\n{state}',bg=color,fg='white',font=('Consolas',7,'bold'),width=12,height=3,relief='ridge').pack(side='left',padx=1,pady=2)
  tk.Label(self.line_frame,text='→ 出口',bg='#07111f',fg='#fde047',font=('Microsoft YaHei',10,'bold')).pack(side='left',padx=4)
  if self.simulated_batches:
   simulated_rows=[batch[position] for batch in self.simulated_batches for position in sorted(batch)]
   s=dict(s)
   s['results']=simulated_rows
   s['ng']=[row for row in simulated_rows if row['result']=='NG']
  for f in self.cab_frames:
   for c in f.winfo_children():c.destroy()
  # One completed SQL batch is one horizontal 20-slot row. New batches are
  # appended below and remain available through the vertical scrollbar.
  display_batches=[]
  if self.simulated_batches:
   display_batches=[(f'SIM BATCH {index+1}',self.simulated_batch_states[index],batch)
    for index,batch in enumerate(self.simulated_batches)]
  else:
   grouped={}
   for item in reversed(s['results']):
    source=str(item.get('source_table') or '');match=re.search(r'fixture=([^:]+)::position=([^:]+)',source)
    if not match:continue
    try:position=int(str(match.group(2)).strip())
    except ValueError:continue
    second=str(item.get('test_time') or '')[:19];key=(str(match.group(1)).strip(),second)
    grouped.setdefault(key,{})[position]=item
   display_batches=[(f'FIXTURE {fixture} · {second}','COMPLETE',batch)
    for (fixture,second),batch in list(grouped.items())[-50:]]
  cabinet=self.cab_frames[0]
  for batch_number,(batch_label,batch_state,positions) in enumerate(display_batches):
   batch_frame=tk.Frame(cabinet,bg='#0f172a',highlightbackground='#334155',highlightthickness=1);batch_frame.pack(fill='x',padx=3,pady=3)
   # Keep fixture/completion time in its own fixed-width column so the
   # 20 slot cells can never cover or clip it.
   tk.Label(batch_frame,text=f'{batch_label}\n{batch_state}',bg='#172033',fg='#67e8f9',font=('Consolas',8,'bold'),width=28,anchor='center',justify='center').grid(row=0,column=0,sticky='nsew',padx=(0,4))
   batch_frame.grid_columnconfigure(0,weight=0,minsize=220)
   for position in range(1,21):
    item=positions.get(position);final_visible=batch_state in {'ROLLING_OUT','COMPLETE'}
    result=str(item.get('result') or '') if item and final_visible else ''
    color='#166534' if result=='OK' else '#b91c1c' if result=='NG' else '#92400e' if batch_state=='AGING' else '#334155';sn=str(item.get('sn') or '--') if item else '--'
    phase=result or ('AGING' if batch_state=='AGING' else 'MOVING')
    tk.Label(batch_frame,text=f'{position:02d}\n{sn}\n{phase}',bg=color,fg='white',font=('Consolas',7,'bold'),relief='ridge',bd=1).grid(row=0,column=position,sticky='nsew',padx=1)
    batch_frame.grid_columnconfigure(position,weight=1,uniform=f'batch-{batch_number}')
  self.cab_canvas.update_idletasks();self.cab_canvas.yview_moveto(1.0)
  for x in []:
   cab=1;color='#166534' if x['state']=='COMPLETE' else '#92400e';tk.Label(self.cab_frames[cab-1],text=f"槽位 {x['addr']} · {x['sn']}\n{x['state']} · {x['elapsed']}",bg=color,fg='white',font=('Consolas',10,'bold'),anchor='w').pack(fill='x',padx=4,pady=2)
  b=s['batches'][0] if s['batches'] else None
  if b:
   end=b['completed_at'] or min(now,b['expected_end_at']);pct=max(0,min(100,(end-b['started_at'])*100/max(1,b['expected_end_at']-b['started_at'])));self.progress['value']=pct;self.summary.set(f"BATCH {b['batch_id']} | START {fmt(b['started_at'])} | EXPECTED {fmt(b['expected_end_at'])} | END {fmt(b['completed_at'])} | CURRENT {duration(end-b['started_at'])} | REQUIRED {duration(EXPECTED_AGING_MS)} | {pct:.1f}% | {b['status']}")
  else:self.summary.set('等待老化批次');self.progress['value']=0
  self.fill('SQL仓位状态',[(x['warehouseNumber'],x['useNumber'],x['state'],x['inIndex'],x['fileName']) for x in self.core.warehouse_state])
  self.fill('输送线架位',[(x['position'],x['leftStand'],x['rightStand'],x['state']) for x in self.core.area_state])
  self.fill('移动架20槽',[(x['stand'],x['slot'],x['sn'],x['result'],x['standState'],x['updatedAt']) for x in self.core.stand_slots if x['stand'] in real_stands])
  self.fill('老化时间',[(x['cabinet'],x['addr'],x['sn'],x['state'],fmt(x['started_at']),fmt(x['expected_end_at']),x['elapsed'] or duration(now-(x['started_at'] or now)),duration((x['expected_end_at'] or 0)-(x['started_at'] or 0))) for x in s['native']]);self.fill('测试结果',[(x['test_time'],x['sn'],x['result'],x['source_table']) for x in s['results']]);self.fill('NG',[(x['test_time'],x['sn'],x['source_table']) for x in s['ng']]);a=s['arrival'];self.fill('报到记录',[(x['arrived_at'],x['sn'],'YES' if x['expected'] else 'NO',x['arrival_status'],x['mes_reported_at'] or '') for x in a['arrivals']]);self.fill('报到异常',[(x['created_at'],x['sn'],x['reason_code'],x['reason_detail'],x['maintenance_case_id']) for x in a['exceptions']]);self.fill('维修工单',[(x['local_case_id'],x['mes_work_order_id'] or '',x['sn'],x['department'],x['status']) for x in s['maintenance']['cases']]);self.fill('历史封存',[(x['archive_batch_id'],x['record_count'],x['content_hash'],x['sealed_at']) for x in s['history']['batches']]);self.fill('MES通信',[(x['event_id'],x['event_type'],x['status'],x['last_error']) for x in s['outbox']]);q=s['sql'];self.fill('设置',[('SQL Server',f'{q["host"]}:{q["port"]}'),('Database',q['database']),('Table',q['table']),('Connected',q['connected']),('要求老化',duration(EXPECTED_AGING_MS)),('扫码','只检查，不记录SN')]);self.fill('修改记录',[(x['change_id'],x['version'],x['reason'],x['summary']) for x in s['changes']])
 def close(self):self.running=False;self.root.destroy()
if __name__=='__main__':
 _instance_mutex=acquire_single_instance('AUTO_AGING_CAB_AGENT')
 if _instance_mutex is None:raise SystemExit('Aging Cab Agent is already running')
 root=tk.Tk();app=AgingCab2D(root)
 from station_retest import install_station_retest_panel
 install_station_retest_panel(root,STATION_CODE,MES_URL.replace('/api/pda/events',''))
 from station_repair_workflow import install_repair_workflow
 install_repair_workflow(root,STATION_CODE,MES_URL,'成品老化')
 root.protocol('WM_DELETE_WINDOW',app.close);root.mainloop()
