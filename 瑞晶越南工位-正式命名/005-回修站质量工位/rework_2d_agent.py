# -*- coding: utf-8 -*-
"""Standalone Rework 2D; MES is the only authoritative source."""
import threading,time,json,shutil,tkinter as tk
from tkinter import messagebox,ttk
from rework_core import ReworkCore,ReworkError,now_text,STATION_CODE,REPAIR_STEPS,POST_REPAIR_TESTS
from station_components.local_resource_viewer import build_local_resource_view as _common_resource_view
from station_components.ng_query import query_ng_records

def build_local_resource_view(db_path, snapshot, resource_dirs=()):
    """Return read-only local resource facts for a station resource viewer."""
    return _common_resource_view(db_path, snapshot, resource_dirs)
    db_path = __import__('pathlib').Path(db_path)
    try:
        db_bytes = db_path.stat().st_size
    except OSError:
        db_bytes = 0
    root = db_path.parent
    directories = []
    for item in resource_dirs or ('attachments', 'evidence', 'exports'):
        path = root / item
        try:
            files = [p for p in path.rglob('*') if p.is_file()] if path.exists() else []
            size = sum(p.stat().st_size for p in files)
        except OSError:
            files, size = [], 0
        directories.append({'name': item, 'path': str(path), 'exists': path.exists(),
                            'files': len(files), 'bytes': size})
    try:
        usage = shutil.disk_usage(str(root))
        disk = {'total': usage.total, 'free': usage.free, 'used': usage.used}
    except OSError:
        disk = {'total': 0, 'free': 0, 'used': 0}
    return {'station_code': snapshot.get('station_code', ''),
            'database': {'path': str(db_path), 'exists': db_path.exists(), 'bytes': db_bytes},
            'outbox_pending': len(snapshot.get('outbox', [])),
            'directories': directories, 'disk': disk}

def build_wo_history_rows(snapshot, work_order_no='', query=''):
    """Return normalized, searchable timeline rows without changing any record."""
    wanted = str(work_order_no or '').strip()
    orders = [r for r in snapshot.get('work_orders', [])
              if not wanted or str(r.get('work_order_no', '')) == wanted]
    if not orders:
        return []
    no = orders[0].get('work_order_no', '')
    rows = []
    for row in snapshot.get('history', []):
        if row.get('work_order_no') not in (None, '', no) and row.get('wo_no') != no:
            continue
        rows.append({'time': row.get('recorded_at') or row.get('started_at') or row.get('created_at') or '',
                     'type': 'EVENT', 'code': row.get('action') or row.get('event_type') or '',
                     'result': row.get('result') or row.get('status') or '',
                     'detail': row.get('note') or '', 'operator': row.get('operator') or ''})
    for row in snapshot.get('step_progress', []):
        if row.get('work_order_no') == no:
            rows.append({'time': row.get('confirmed_at') or row.get('started_at') or '',
                         'type': 'STEP', 'code': row.get('step_code') or '',
                         'result': 'CONFIRMED', 'detail': row.get('note') or '',
                         'operator': row.get('confirmed_by') or ''})
    for row in snapshot.get('test_progress', []):
        if row.get('work_order_no') == no:
            rows.append({'time': row.get('tested_at') or '', 'type': 'RETEST',
                         'code': row.get('test_code') or '', 'result': row.get('result') or '',
                         'detail': row.get('measured_value') or '',
                         'operator': row.get('tested_by') or ''})
    for row in snapshot.get('materials', []):
        if row.get('work_order_no') == no:
            rows.append({'time': row.get('recorded_at') or '', 'type': 'MATERIAL',
                         'code': row.get('material_code') or '', 'result': 'USED',
                         'detail': 'qty={0} lot={1}'.format(row.get('quantity', ''), row.get('lot_no', '')),
                         'operator': row.get('operator') or ''})
    needle = str(query or '').strip().lower()
    if needle:
        rows = [r for r in rows if needle in ' '.join(str(v) for v in r.values()).lower()]
    return sorted(rows, key=lambda r: str(r.get('time') or ''))

def build_wo_history_text(snapshot, work_order_no=''):
    """Build a read-only, human-readable history view from a local MES snapshot."""
    wanted = str(work_order_no or '').strip()
    orders = [r for r in snapshot.get('work_orders', [])
              if not wanted or str(r.get('work_order_no', '')) == wanted]
    if not orders:
        return 'WO HISTORY / 工单历史\n\nNo local history for the selected work order.\n当前工单没有本地历史。'
    wo = orders[0]
    no = wo.get('work_order_no', '')
    lines = [
        'WO HISTORY / 工单历史',
        f"Station / 工站: {snapshot.get('station_code', '')}",
        f"WO: {no}    SN: {wo.get('ng_sn', '')}",
        f"Source / 来源: {wo.get('source_station', '')}    Status / 状态: {wo.get('status', '')}",
        f"Updated / 更新时间: {wo.get('updated_at', '')}",
        '',
        'EVENTS / 事件',
    ]
    for row in build_wo_history_rows(snapshot, no):
        lines.append('  {time}  [{type}]  {code}  {result}  {detail}  {operator}'.format(**row))
    lines.append('')
    lines.append('REPAIR STEPS / 维修步骤')
    for row in build_wo_history_rows(snapshot, no):
        if row['type'] == 'STEP':
            lines.append('  {code}  confirmed by {operator}  {time}'.format(**row))
    lines.append('')
    lines.append('RETEST / 复测')
    for row in build_wo_history_rows(snapshot, no):
        if row['type'] == 'RETEST':
            lines.append('  {code}  {result}  {detail}  {operator}  {time}'.format(**row))
    lines.append('')
    lines.append('MATERIALS / 物料')
    for row in build_wo_history_rows(snapshot, no):
        if row['type'] == 'MATERIAL':
            lines.append('  {code}  {detail}'.format(**row))
    return '\n'.join(lines)

def build_all_wo_history_rows(snapshot, query='', limit=None):
    """Return one searchable summary row per local repair work order."""
    needle = str(query or '').strip().lower()
    rows = []
    for order in snapshot.get('work_orders', []):
        wo = str(order.get('work_order_no') or '')
        timeline = build_wo_history_rows(snapshot, wo)
        row = {'work_order_no': wo, 'sn': str(order.get('ng_sn') or ''),
               'source_station': str(order.get('source_station') or ''),
               'batch_id': str(order.get('batch_id') or ''), 'status': str(order.get('status') or ''),
               'result': str(order.get('repair_result') or ''), 'updated_at': str(order.get('updated_at') or ''),
               'events': len(timeline), 'retests': sum(1 for item in timeline if item.get('type') == 'RETEST')}
        if not needle or needle in ' '.join(str(v) for v in row.values()).lower():
            rows.append(row)
    rows = sorted(rows, key=lambda row: row.get('updated_at', ''), reverse=True)
    return rows[:int(limit)] if limit else rows

class Rework2D:
    NB='notebook'
    def __init__(self,root):
        self.root=root;self.core=ReworkCore();self.running=True
        self.heartbeat_var=tk.StringVar(value='HEARTBEAT: STARTING')
        self.pickup_var=tk.StringVar(value='PICKUP: NONE / LINE LEADER or TEAM LEADER')
        self.scan=tk.StringVar();self.status=tk.StringVar(value='等待扫码 / Waiting for scan')
        self.selected_wo=tk.StringVar(value='')
        root.title(f'回修站质量工位 · 2D / Repair Quality · 2D');root.geometry('1500x960');root.configure(bg='#0f172a')
        self.materials=[];self.method=tk.StringVar();self.complete_var=tk.BooleanVar();self.no_material_var=tk.BooleanVar()
        self.mat_lot=tk.StringVar();self.mat_lot_records=[]
        self._build();self._refresh();self._refresh_lot_display()
        threading.Thread(target=self._worker,daemon=True).start()

    def _build(self):
        h=tk.Frame(self.root,bg='#0b1f35');h.pack(fill='x')
        self.heartbeat_label=tk.Label(h,textvariable=self.heartbeat_var,bg='#14532d',fg='#bbf7d0',font=('Consolas',10,'bold'),padx=8)
        self.heartbeat_label.pack(side='right',padx=8)
        tk.Label(h,text='回修站质量工位 / Repair Quality · 2D',bg='#0b1f35',fg='#67e8f9',font=('Microsoft YaHei',20,'bold')).pack(side='left',padx=16,pady=10)
        tk.Label(h,text=f'{STATION_CODE} · MES+Local SQLite',bg='#0b1f35',fg='#94a3b8',font=('Arial',11)).pack(side='left',padx=8)
        tk.Label(h,textvariable=self.status,bg='#0b1f35',fg='#fbbf24',font=('Arial',11,'bold')).pack(side='right',padx=16)
        bar=tk.Frame(self.root,bg='#083344');bar.pack(fill='x',padx=12,pady=6)
        tk.Label(bar,text='扫码',bg='#083344',fg='#67e8f9',font=('Microsoft YaHei',12,'bold')).pack(side='left',padx=8)
        e=tk.Entry(bar,textvariable=self.scan,font=('Consolas',16),bg='#10243b',fg='white',insertbackground='white')
        e.pack(side='left',fill='x',expand=True,padx=6,pady=6);e.bind('<Return>',lambda _e:self._receive())
        tk.Button(bar,text='扫码接收维修 / RECEIVE',command=self._receive,bg='#0891b2',fg='white').pack(side='left',padx=6)
        tk.Button(bar,text='刷新 / REFRESH',command=self._refresh,bg='#475569',fg='white').pack(side='right',padx=6)
        tk.Button(bar,text='物料质量报告 / IQC REPORT',command=self._show_iqc_report,bg='#7c3aed',fg='white').pack(side='right',padx=6)
        tk.Button(bar,text='本地资源 / LOCAL RESOURCES',command=self._show_local_resources,bg='#0f766e',fg='white').pack(side='right',padx=6)
        tk.Button(bar,text='NG查询 / NG QUERY',command=self._show_ng_query,bg='#be123c',fg='white').pack(side='right',padx=6)

        # Step control row — WO selector with dropdown of queued WOs from MES
        step_frame=tk.Frame(self.root,bg='#172033');step_frame.pack(fill='x',padx=12,pady=(4,2))
        tk.Label(step_frame,text='选择维修工单:',bg='#172033',fg='#94a3b8').pack(side='left',padx=(0,4))
        self.wo_combo=ttk.Combobox(step_frame,textvariable=self.selected_wo,width=32,
                                   font=('Consolas',12),state='readonly')
        self.wo_combo.pack(side='left',padx=4)
        tk.Button(step_frame,text='ALL WO HISTORY / 全部工单历史',command=self._show_all_history,bg='#5b21b6',fg='white').pack(side='left',padx=4)
        tk.Button(step_frame,text='确认步骤 / CONFIRM STEP',command=self._confirm_step_dlg,bg='#7c3aed',fg='white').pack(side='left',padx=4)
        tk.Button(step_frame,text='记录测试 / RECORD TEST',command=self._record_test_dlg,bg='#b45309',fg='white').pack(side='left',padx=4)
        tk.Button(step_frame,text='查看详情 / DETAIL',command=self._show_detail,bg='#0369a1',fg='white').pack(side='left',padx=4)
        tk.Button(step_frame,text='工单历史 / WO HISTORY',command=self._show_history,bg='#7c3aed',fg='white').pack(side='left',padx=4)
        tk.Button(step_frame,text='接收选中WO / RECEIVE',command=self._receive_selected,bg='#0891b2',fg='white').pack(side='left',padx=4)
        self.wo_count_lbl=tk.Label(step_frame,text='MES待接收: 0',bg='#172033',fg='#f59e0b',font=('Arial',10))
        self.wo_count_lbl.pack(side='left',padx=12)

        complete=tk.Frame(self.root,bg='#172033');complete.pack(fill='x',padx=12,pady=2)
        tk.Checkbutton(complete,text='确认维修完成 / REPAIR COMPLETED',variable=self.complete_var,bg='#172033',fg='#f8fafc',selectcolor='#0f172a',activebackground='#172033').pack(side='left',padx=8)
        tk.Label(complete,text='维修方法 / METHOD',bg='#172033',fg='#94a3b8').pack(side='left',padx=(12,4))
        tk.Entry(complete,textvariable=self.method,font=('Microsoft YaHei',11),width=32,bg='#10243b',fg='white',insertbackground='white').pack(side='left')
        mat_row=tk.Frame(self.root,bg='#172033');mat_row.pack(fill='x',padx=12,pady=(0,4))
        tk.Label(mat_row,text='物料批号',bg='#172033',fg='#cbd5e1').pack(side='left')
        self.mat_lot=tk.StringVar()
        tk.Entry(mat_row,textvariable=self.mat_lot,width=22,bg='#10243b',fg='#67e8f9',font=('Consolas',12),insertbackground='white').pack(side='left',padx=(3,8))
        tk.Button(mat_row,text='WMS查询 / WMS LOOKUP',command=self._wms_lookup,bg='#0369a1',fg='white').pack(side='left',padx=4)
        tk.Checkbutton(mat_row,text='无物料更换 / NO REPLACEMENT',variable=self.no_material_var,bg='#172033',fg='#f8fafc',selectcolor='#0f172a',activebackground='#172033').pack(side='left',padx=8)
        # WMS info display
        self.wms_info=tk.Label(self.root,text='扫码物料批号查WMS追溯 / Scan lot barcode to trace from WMS',bg='#0f172a',fg='#64748b')
        self.wms_info.pack(anchor='w',padx=18)
        # Scanned lots list
        self.mat_lots_frame=tk.Frame(self.root,bg='#0f172a')
        self.mat_lots_frame.pack(fill='x',padx=12,pady=(0,4))
        self.lot_labels=[]  # list of (lot_no, supplier, qty) labels
        self.mat_lot_records=[]  # list of {'lot_no':..., 'supplier_code':..., ...}
        self.material_label=tk.Label(self.root,text='尚未登记物料 / No material recorded',bg='#0f172a',fg='#fbbf24');self.material_label.pack(anchor='w',padx=18)
        tk.Button(self.root,text='完成维修工单 / COMPLETE WO',command=self._complete,bg='#16a34a',fg='white',font=('Microsoft YaHei',11,'bold')).pack(anchor='w',padx=18,pady=4)

        self.pickup_label=tk.Label(self.root,textvariable=self.pickup_var,bg='#422006',fg='#fde68a',font=('Microsoft YaHei',11,'bold'),anchor='w',padx=10)
        self.pickup_label.pack(fill='x',padx=18,pady=(0,4))
        tk.Button(self.root,text='CALL LINE LEADER / TEAM LEADER PICKUP',command=self._call_pickup,bg='#ea580c',fg='white',font=('Microsoft YaHei',10,'bold')).pack(anchor='w',padx=18,pady=(0,4))
        self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill='both',expand=True,padx=12,pady=8)
        self.trees={}
        for name,cols in (
            ('MES待接收',('RWO工单号','交接单','批次','来源','板数','送出时间','状态')),
            ('维修中',('RWO工单号','来源','批次','开始','已用','报警')),
            ('维修工单',('RWO工单号','NG SN','批次','来源','状态','完成时间','方法','结果','操作员')),
            ('物料记录',('工单号','SN','物料编码','名称','数量','单位','操作员','记录时间')),
            ('维修日志',('时间','SN','动作','结果','方法/原因','操作员','耗时')),
            ('QC控制',('RWO工单号','SN','来源','状态','完成时间','维修方法','维修结果','复测次数')),
            ('扫码记录',('时间','SN','结果','MES')),
            ('NG拦截',('时间','SN','来源','缺陷')),
            ('MES缓存',('SN','来源','批次','版本','同步时间')),
            ('MES通信',('事件','SN','结果','重试','创建时间')),
            ('物料追溯',('工单号','SN','物料编码','批号','供应商代码','供应商名称','仓位','收料时间','IQC状态','入库事务号','领料事务号','领料时间','使用工单','操作员','记录时间')),
            ('IQC报告',('工单号','SN','物料编码','批号','供应商','仓位','收料时间','IQC判定','来料检验','外观检验①过期','外观检验②受潮','外观检验③破损','外观检验④变形','操作员','记录时间')),
        ):
            p=tk.Frame(self.tabs);self.tabs.add(p,text=name);t=ttk.Treeview(p,columns=cols,show='headings')
            for c in cols:t.heading(c,text=c);t.column(c,width=145,anchor='center')
            t.pack(side='left',fill='both',expand=True);ttk.Scrollbar(p,command=t.yview).pack(side='right',fill='y');self.trees[name]=t
            if name in ('维修中','维修工单'):
                t.bind('<<TreeviewSelect>>',lambda e,name=name:self._on_wo_select(e,name))
        resource_page=tk.Frame(self.tabs,bg='#0b1f35')
        self.tabs.add(resource_page,text='本地资源 / LOCAL RESOURCES')
        self.resource_text=tk.Text(resource_page,wrap='none',bg='#0b1f35',fg='#dbeafe',font=('Consolas',10),state='disabled')
        self.resource_text.pack(side='left',fill='both',expand=True,padx=10,pady=10)
        tk.Button(resource_page,text='REFRESH RESOURCES / 刷新资源',command=self._refresh_resource_tab,bg='#0f766e',fg='white').pack(anchor='ne',padx=10,pady=10)

    def _fill(self,name,rows):
        t=self.trees.get(name)
        if t is None:return
        t.delete(*t.get_children());[t.insert('','end',values=r) for r in rows]

    def _refresh_resource_tab(self):
        view=build_local_resource_view(self.core.db_path,self.core.snapshot())
        disk=view['disk'];db=view['database']
        lines=['LOCAL RESOURCES / 本地资源',f"Station / 工站: {view['station_code']}",
               f"SQLite: {db['path']}",f"SQLite bytes: {db['bytes']}",
               f"Outbox pending / 待上传: {view['outbox_pending']}",
               f"Disk free: {disk['free']} / {disk['total']} bytes",'',
               'Directories / 目录:']
        lines += ['  {name}: {files} files, {bytes} bytes, exists={exists}'.format(**item) for item in view['directories']]
        lines += ['', 'SQLite TABLES / 数据表:']
        for item in view.get('tables', []):
            lines.append('  {name}: {rows} rows'.format(**item))
            lines.append('    columns: ' + ', '.join(item.get('columns', [])))
            for row in item.get('preview', []):
                lines.append('    ' + ' | '.join('{0}={1}'.format(k, v) for k, v in row.items()))
        lines += ['', 'OUTBOX EVENTS / 待上传事件:']
        lines += ['  {event_id} | {type} | SN={sn} | {result} | attempts={attempts} | {created_at}'.format(**item)
                  for item in view.get('outbox_events', [])]
        for item in view['directories']:
            if item.get('entries'):
                lines += ['', 'FILES / 文件 - {0}:'.format(item['name'])]
                lines += ['  ' + entry for entry in item['entries']]
        self.resource_text.configure(state='normal');self.resource_text.delete('1.0','end');self.resource_text.insert('1.0','\n'.join(lines));self.resource_text.configure(state='disabled')

    def _on_wo_select(self,event,name):
        sel=event.widget.selection()
        if not sel:return
        vals=event.widget.item(sel[0],'values')
        if vals:
            wo=vals[0]  # RWO is always col 0
            self.selected_wo.set(wo)
            try: self.wo_combo.set(wo)
            except Exception: pass

    def _receive_selected(self):
        """Manually receive the WO selected in the dropdown from MES queue."""
        wo=self.selected_wo.get().strip()
        if not wo:messagebox.showwarning('接收WO','请先从下拉列表选择待接收的维修工单');return
        try:
            # Find SN for this WO from the queued list
            pending=self.core.fetch_pending_handovers()
            sn=None
            for r in pending:
                if r.get('repairWorkOrderNo')==wo or r.get('requestId')==wo:
                    sn=r.get('batchId','');break
            if not sn:
                messagebox.showwarning('接收失败',f'工单 {wo} 不在MES待接收队列中');return
            r=self.core.receive_repair(sn)
            if not r.get('ok'):
                messagebox.showerror('接收失败',f'{wo}\n{r.get("error_code")}\n{r.get("detail","")}');return
            self.status.set(f'已接收 / RECEIVED: {r["batch_id"]} · {sn}')
        except ReworkError as ex:messagebox.showwarning('接收失败',str(ex));return
        self._refresh()

    def _receive(self):
        sn=self.scan.get().strip().upper();self.scan.set('')
        if not sn:return
        try:r=self.core.receive_repair(sn)
        except ReworkError as ex:messagebox.showwarning('扫码 / Scan',str(ex));return
        if not r.get('ok'):
            self.status.set(f'拦截 / BLOCKED: {sn} · {r.get("error_code")}')
            messagebox.showerror('拦截 / Blocked',f'{sn}\n{r.get("error_code")}\n{r.get("detail","")}');return
        self.status.set(f'已接收 / RECEIVED: {r["batch_id"]} · {sn}')
        self._refresh()

    def _wms_lookup(self):
        """Scan lot barcode → WMS lookup → IQC check → Visual QC → Record with full traceability."""
        lot=self.mat_lot.get().strip().upper()
        wo=self._selected_wo()
        if not lot:messagebox.showwarning('WMS查询','请输入物料批号');return
        self.wms_info.config(text=f'查询中 / Querying WMS... {lot}',fg='#fbbf24')
        self.root.update()
        try:
            info=self.core.wms_lookup_lot(lot)
        except Exception as ex:
            self.wms_info.config(text=f'WMS查询失败: {ex}',fg='#ef4444');return
        if not info:
            self.wms_info.config(text=f'WMS无此批号: {lot}  — 请手工输入',fg='#f59e0b')
            info={'lot_no':lot,'material_code':'','material_name':'','qty':1,
                  'iqc_status':'UNKNOWN','supplier_code':'','supplier_name':'','location_code':'','received_at':''}
        # Step 1: IQC status check
        iqc=info.get('iqc_status','').upper()
        iqc_color={'RELEASED':'#22c55e','HOLD':'#f59e0b','REJECTED':'#ef4444'}.get(iqc,'#94a3b8')
        self.wms_info.config(
            text=f"批号:{lot}  物料:{info.get('material_code','')}  "
                 f"供应商:{info.get('supplier_code','')}/{info.get('supplier_name','')}  "
                 f"仓位:{info.get('location_code','')}  库存:{info.get('qty',0)}  IQC:{iqc or '未查到'}",
            fg=iqc_color)
        if iqc=='REJECTED':
            messagebox.showerror('IQC不合格 / IQC Rejected',
                f'批号: {lot}\n物料: {info.get("material_code","")}\nIQC判定: 不合格，禁止使用！');return
        if iqc=='HOLD':
            if not messagebox.askyesno('IQC待判定 / IQC Pending',
                f'批号: {lot}\nIQC状态: HOLD(待判定)\n是否仍要使用？'):
                return
        # Step 2: Visual quality inspection dialog
        d=tk.Toplevel(self.root);d.title(f'物料质检 / Material QC: {lot}');d.configure(bg='#0f172a');d.geometry('600x420')
        tk.Label(d,text=f'批号: {lot}  物料: {info.get("material_code","")} {info.get("material_name","")}',
                 bg='#0f172a',fg='#67e8f9',font=('Microsoft YaHei',11,'bold')).pack(pady=8)
        tk.Label(d,text='═'*60,bg='#0f172a',fg='#334155').pack()
        tk.Label(d,text='外观检验 / Visual Inspection  (全部合格方可使用)',
                 bg='#0f172a',fg='#fbbf24',font=('Microsoft YaHei',11)).pack(pady=6)
        qc_vars={}
        for item,desc in [
            ('outdated',    '① 过期 / Outdated (超过保质期)'),
            ('moistured',   '② 受潮 / Moistured (包装潮湿)'),
            ('broken',      '③ 破损 / Visually Broken (外壳/引脚损坏)'),
            ('twisted',     '④ 变形 / Twisted (引脚弯曲/元件变形)'),
        ]:
            var=tk.BooleanVar(value=False)
            cb=tk.Checkbutton(d,text=desc,variable=var,
                              bg='#0f172a',fg='#f8fafc',selectcolor='#1e293b',
                              activebackground='#0f172a',font=('Microsoft YaHei',11))
            cb.pack(anchor='w',padx=40,pady=3)
            qc_vars[item]=var
        result_record={'ok':False}  # nonlocal slot

        def _confirm():
            failed=[k for k,v in qc_vars.items() if v.get()]
            if failed:
                names={'outdated':'过期','moistured':'受潮','broken':'破损','twisted':'变形'}
                messagebox.showerror('质检不合格 / QC Failed',
                    f"以下项目不合格，禁止使用：\n" + '\n'.join(f'  ✗ {names[k]}' for k in failed))
                return
            # All QC passed — record with WMS traceability
            record={
                'lot_no':        info.get('lot_no',lot),
                'material_code': info.get('material_code',''),
                'material_name': info.get('material_name',''),
                'qty':           info.get('qty',1),
                'supplier_code':info.get('supplier_code',''),
                'supplier_name':info.get('supplier_name',''),
                'location_code':info.get('location_code',''),
                'iqc_status':    iqc or 'UNKNOWN',
                'received_at':  info.get('received_at',''),
                'inbound_tx_no':'','pick_tx_no':'',
            }
            if wo:
                try:
                    res=self.core.record_material_with_lot(
                        wo, lot,
                        record['material_code'],record['material_name'],
                        record['qty'],'PCS',None)
                    record.update(res)
                except ReworkError as ex:
                    messagebox.showwarning('记录失败',str(ex));d.lift();return
            self.mat_lot_records.append(record)
            self.materials.append({
                'materialCode': record['material_code'],
                'materialName': record['material_name'],
                'quantity': record['qty'],
                'unit': 'PCS',
                'lotNo': record['lot_no'],
                'supplierCode': record['supplier_code'],
                'iqcStatus': record['iqc_status'],
            })
            self.mat_lot.set('')
            self._refresh_lot_display()
            self.status.set(f'物料已登记: {lot}  IQC:{iqc or "?"}')
            d.destroy()

        btn=tk.Frame(d,bg='#0f172a');btn.pack(pady=12)
        tk.Button(btn,text='合格 / PASS',command=_confirm,bg='#16a34a',fg='white',
                  font=('Microsoft YaHei',12,'bold')).pack(side='left',padx=12)
        tk.Button(btn,text='不合格 / FAIL',command=lambda:(
            messagebox.showerror('质检不合格','请将物料退回仓库'),
            d.destroy()),bg='#dc2626',fg='white',font=('Microsoft YaHei',12)).pack(side='left',padx=12)

    def _refresh_lot_display(self):
        """Re-render the scanned lots strip below the input row."""
        for w in self.mat_lots_frame.pack_slaves():
            w.destroy()
        self.lot_labels.clear()
        if not self.mat_lot_records:
            tk.Label(self.mat_lots_frame,text='无物料 / No materials',bg='#0f172a',fg='#475569',
                     font=('Arial',10)).pack(side='left')
            return
        for rec in self.mat_lot_records:
            iqc=rec.get('iqc_status','UNKNOWN')
            color={'RELEASED':'#22c55e','HOLD':'#f59e0b','REJECTED':'#ef4444'}.get(iqc,'#94a3b8')
            lbl=tk.Label(self.mat_lots_frame,
                         text=f"● {rec['lot_no']} 供应商:{rec['supplier_code']} IQC:{iqc} 数量:{rec['qty']}",
                         bg='#1e293b',fg=color,font=('Consolas',10))
            lbl.pack(side='left',padx=4,pady=2)
            self.lot_labels.append(lbl)
        self.material_label.config(
            text=' | '.join(f"{r['lot_no']}({r['iqc_status']})" for r in self.mat_lot_records),
            fg='#22c55e')

    def _show_ng_query(self):
        d=tk.Toplevel(self.root);d.title('NG QUERY / NG查询');d.configure(bg='#0f172a');d.geometry('1000x620')
        fields=[('SN','sn'),('Station / 工站','station'),('Status / 状态','status'),('WO','work_order'),('Box QR','box_qr'),('Shipment ID','shipment_id')]
        variables={}
        bar=tk.Frame(d,bg='#172033');bar.pack(fill='x',padx=10,pady=8)
        for label,key in fields:
            tk.Label(bar,text=label,bg='#172033',fg='#cbd5e1').pack(side='left',padx=(4,2))
            var=tk.StringVar();variables[key]=var
            tk.Entry(bar,textvariable=var,width=14,bg='#10243b',fg='white',insertbackground='white').pack(side='left',padx=(0,5))
        tree=ttk.Treeview(d,columns=('sn','station','status','wo','box','shipment','time'),show='headings')
        for col,title in zip(tree['columns'],('SN','Station','Status','WO','Box QR','Shipment','Time')):
            tree.heading(col,text=title);tree.column(col,width=130,anchor='center')
        tree.pack(fill='both',expand=True,padx=10,pady=8)
        def run_query():
            snap=self.core.snapshot()
            rows=query_ng_records(snap.get('ng_active',[]),**{key:var.get() for key,var in variables.items()})
            tree.delete(*tree.get_children())
            for row in rows:
                tree.insert('', 'end', values=(row.get('sn') or row.get('ng_sn',''),row.get('source') or row.get('source_station',''),row.get('status',''),row.get('repair_work_order_no',''),row.get('bucket_qr') or row.get('box_qr',''),row.get('shipmentId') or row.get('shipment_id',''),row.get('detected_at','')))
        tk.Button(bar,text='SEARCH / 查询',command=run_query,bg='#be123c',fg='white').pack(side='left',padx=6)
        run_query()

    def _show_local_resources(self):
        """Show shared local-resource facts read-only; no delete or write controls."""
        snap=self.core.snapshot()
        view=build_local_resource_view(self.core.db_path,snap)
        d=tk.Toplevel(self.root);d.title('LOCAL RESOURCES / 本地资源');d.configure(bg='#0f172a');d.geometry('760x520')
        text=tk.Text(d,wrap='none',bg='#0b1f35',fg='#dbeafe',font=('Consolas',10),state='normal')
        disk=view['disk'];db=view['database']
        lines=['LOCAL RESOURCES / 本地资源','',f"Station / 工站: {view['station_code']}",
               f"SQLite: {db['path']}",f"SQLite bytes / 数据库大小: {db['bytes']}",
               f"Outbox pending / 待上传: {view['outbox_pending']}",'',
               f"Disk free / 磁盘可用: {disk['free']} / {disk['total']} bytes",'',
               'RESOURCE DIRECTORIES / 资源目录']
        for item in view['directories']:
            lines.append('  {name}: exists={exists}, files={files}, bytes={bytes}, path={path}'.format(**item))
        lines += ['', 'Read-only view. MES remains authoritative.', '只读视图，MES 仍是唯一权威。']
        lines += ['', 'SQLite TABLES / 数据表:']
        for item in view.get('tables', []):
            lines.append('  {name}: {rows} rows'.format(**item))
            lines.append('    columns: ' + ', '.join(item.get('columns', [])))
            for row in item.get('preview', []):
                lines.append('    ' + ' | '.join('{0}={1}'.format(k, v) for k, v in row.items()))
        lines += ['', 'OUTBOX EVENTS / 待上传事件:']
        lines += ['  {event_id} | {type} | SN={sn} | {result} | attempts={attempts}'.format(**item)
                  for item in view.get('outbox_events', [])]
        for item in view['directories']:
            lines += ['', 'FILES / 文件 - {0}:'.format(item['name'])]
            lines += ['  ' + entry for entry in item.get('entries', [])]
        text.insert('1.0','\n'.join(lines));text.configure(state='disabled');text.pack(fill='both',expand=True,padx=10,pady=10)
        tk.Button(d,text='CLOSE / 关闭',command=d.destroy,bg='#475569',fg='white').pack(pady=(0,8))

    def _show_iqc_report(self):
        """Full IQC quality report dialog — view all material IQC history + submit to MES."""
        d=tk.Toplevel(self.root);d.title('物料质量报告 / Material IQC Quality Report');d.configure(bg='#0f172a');d.geometry('1300x750')
        # Header
        hdr=tk.Frame(d,bg='#0b1f35');hdr.pack(fill='x')
        tk.Label(hdr,text='物料质量报告 / Material IQC Quality Report',bg='#0b1f35',fg='#67e8f9',
                 font=('Microsoft YaHei',14,'bold')).pack(side='left',padx=12,pady=8)
        tk.Button(hdr,text='提交MES / SUBMIT TO MES',command=lambda:self._submit_iqc_to_mes(d),
                  bg='#7c3aed',fg='white',font=('Microsoft YaHei',10,'bold')).pack(side='right',padx=12)
        tk.Button(hdr,text='刷新 / REFRESH',command=lambda:self._reload_iqc_tree(iqc_tree),
                  bg='#475569',fg='white').pack(side='right',padx=4)

        # Filter bar
        filt=tk.Frame(d,bg='#172033');filt.pack(fill='x',padx=12,pady=4)
        tk.Label(filt,text='工单号:',bg='#172033',fg='#94a3b8').pack(side='left',padx=4)
        wo_var=tk.StringVar()
        tk.Entry(filt,textvariable=wo_var,width=22,bg='#10243b',fg='white',insertbackground='white').pack(side='left',padx=4)
        tk.Label(filt,text='SN:',bg='#172033',fg='#94a3b8').pack(side='left',padx=(12,4))
        sn_var=tk.StringVar()
        tk.Entry(filt,textvariable=sn_var,width=22,bg='#10243b',fg='white',insertbackground='white').pack(side='left',padx=4)
        tk.Label(filt,text='物料编码:',bg='#172033',fg='#94a3b8').pack(side='left',padx=(12,4))
        mc_var=tk.StringVar()
        tk.Entry(filt,textvariable=mc_var,width=18,bg='#10243b',fg='white',insertbackground='white').pack(side='left',padx=4)
        tk.Button(filt,text='过滤 / FILTER',command=lambda:self._reload_iqc_tree(iqc_tree,wo_var.get(),sn_var.get(),mc_var.get()),
                  bg='#0369a1',fg='white').pack(side='left',padx=8)
        tk.Button(filt,text='显示全部 / ALL',command=lambda:self._reload_iqc_tree(iqc_tree,'','',''),
                  bg='#475569',fg='white').pack(side='left',padx=4)

        # Summary strip
        summ=tk.Frame(d,bg='#083344');summ.pack(fill='x',padx=12,pady=(0,4))
        self._iqc_summary_labels={}
        for label,key in [('总计/Total','total'),('合格/PASS','pass'),('不合格/FAIL','fail'),
                           ('待判定/HOLD','hold'),('未知/UNKNOWN','unknown')]:
            fr=tk.Frame(summ,bg='#083344');fr.pack(side='left',padx=12,pady=4)
            tk.Label(fr,text=label,bg='#083344',fg='#94a3b8',font=('Arial',9)).pack()
            lbl=tk.Label(fr,text='0',bg='#083344',fg='#f8fafc',font=('Consolas',14,'bold'))
            lbl.pack();self._iqc_summary_labels[key]=lbl

        # Treeview with IQC status
        tree_fr=tk.Frame(d,bg='#0f172a');tree_fr.pack(fill='both',expand=True,padx=12,pady=4)
        cols=('工单号','SN','物料编码','批号','供应商','仓位','收料时间',
              'IQC判定','来料结果','外观检验①','外观检验②','外观检验③','外观检验④',
              '入库事务','领料时间','操作员','记录时间')
        iqc_tree=ttk.Treeview(tree_fr,columns=cols,show='headings',height=18)
        col_widths={'工单号':130,'SN':140,'物料编码':110,'批号':120,'供应商':90,
                    '仓位':80,'收料时间':110,'IQC判定':80,'来料结果':80,
                    '外观检验①':90,'外观检验②':90,'外观检验③':90,'外观检验④':90,
                    '入库事务':120,'领料时间':110,'操作员':90,'记录时间':130}
        for c in cols:
            iqc_tree.heading(c,text=c)
            iqc_tree.column(c,width=col_widths.get(c,100),anchor='center')
        iqc_tree.pack(side='left',fill='both',expand=True)
        sb=ttk.Scrollbar(tree_fr,command=iqc_tree.yview);sb.pack(side='right',fill='y')
        iqc_tree.configure(yscrollcommand=sb.set)

        # Tag colors for IQC status
        iqc_tree.tag_configure('PASS',background='#052e16',foreground='#22c55e')
        iqc_tree.tag_configure('FAIL',background='#2d0520',foreground='#ef4444')
        iqc_tree.tag_configure('HOLD',background='#2d1f00',foreground='#f59e0b')
        iqc_tree.tag_configure('UNKNOWN',background='#1e293b',foreground='#94a3b8')

        def _reload(wo='',sn='',mc=''):
            try:
                traces=self.core.fetch_material_trace(wo_no=wo.strip() or None,
                                                      sn=sn.strip() or None,
                                                      material_code=mc.strip() or None,
                                                      days=90,limit=500)
            except Exception as ex:
                messagebox.showwarning('查询失败',str(ex));return
            iqc_tree.delete(*iqc_tree.get_children())
            counts={'total':0,'pass':0,'fail':0,'hold':0,'unknown':0}
            for r in traces:
                iqc=r.get('iqc_status','') or ''
                iqc_upper=iqc.upper()
                tag='UNKNOWN'
                if iqc_upper=='RELEASED': tag='PASS';counts['pass']+=1
                elif iqc_upper=='REJECTED': tag='FAIL';counts['fail']+=1
                elif iqc_upper=='HOLD': tag='HOLD';counts['hold']+=1
                else: counts['unknown']+=1
                counts['total']+=1
                iqc_tree.insert('',0,values=(
                    r.get('wo_no',''),r.get('ng_sn',''),r.get('material_code',''),
                    r.get('lot_no',''),r.get('supplier_code',''),r.get('location_code',''),
                    r.get('received_at','')[:19] if r.get('received_at') else '',
                    iqc.upper(),
                    'PASS' if iqc_upper=='RELEASED' else ('FAIL' if iqc_upper in('REJECTED','HOLD') else 'N/A'),
                    '✓ 合格' if iqc_upper=='RELEASED' else '—',
                    '✓ 合格' if iqc_upper=='RELEASED' else '—',
                    '✓ 合格' if iqc_upper=='RELEASED' else '—',
                    '✓ 合格' if iqc_upper=='RELEASED' else '—',
                    r.get('inbound_tx_no',''),r.get('pick_issued_at','')[:19] if r.get('pick_issued_at') else '',
                    r.get('operator',''),r.get('replaced_at','')[:19] if r.get('replaced_at') else ''),
                    tags=(tag,))
            # Update summary counts
            for k,lbl in self._iqc_summary_labels.items():
                lbl.config(text=str(counts[k]))
            # Color summary labels
            self._iqc_summary_labels['pass'].config(fg='#22c55e')
            self._iqc_summary_labels['fail'].config(fg='#ef4444')
            self._iqc_summary_labels['hold'].config(fg='#f59e0b')
        iqc_tree._reload=_reload  # attach for refresh button
        _reload()
        tk.Button(d,text='关闭 / CLOSE',command=d.destroy,bg='#475569',fg='white').pack(pady=8)

    def _reload_iqc_tree(self,tree,wo='',sn='',mc=''):
        if hasattr(tree,'_reload'): tree._reload(wo,sn,mc)

    def _submit_iqc_to_mes(self,dlg):
        """Submit all material IQC quality report to MES."""
        try:
            result=self.core.submit_material_trace_report(days=90)
        except Exception as ex:
            messagebox.showerror('提交失败',f'MES提交失败:\n{ex}');return
        if result.get('ok'):
            messagebox.showinfo('提交成功',
                f"MES物料追溯报告已提交\n"
                f"报告ID: {result.get('report_id','')}\n"
                f"记录数: {result.get('total_records',0)}")
        else:
            messagebox.showerror('提交失败',f"MES返回: {result.get('response',{}).get('message','未知错误')}")

    def _selected_wo(self):
        wo=self.selected_wo.get().strip()
        if not wo:
            for name in ('维修中','维修工单'):
                sel=self.trees[name].selection()
                if sel:
                    vals=self.trees[name].item(sel[0],'values')
                    if vals:wo=vals[0];break
        return wo

    def _confirm_step_dlg(self):
        wo=self._selected_wo()
        if not wo:messagebox.showwarning('步骤 / Step','请先选择工单');return
        d=tk.Toplevel(self.root);d.title('确认维修步骤 / Confirm Repair Step');d.configure(bg='#0f172a');d.geometry('700x400')
        tk.Label(d,text=f'工单 / WO: {wo}',bg='#0f172a',fg='#67e8f9',font=('Microsoft YaHei',13,'bold')).pack(pady=6)
        info=self.core.repair_progress(wo)
        confirmed={}
        for code,name_zh,name_en,idx in REPAIR_STEPS:
            f=tk.Frame(d,bg='#1e293b');f.pack(fill='x',padx=16,pady=3)
            is_confirmed=code in info.get('steps_confirmed',[])
            tk.Label(f,text=f'{"[OK]" if is_confirmed else "[ ]"}',bg='#1e293b',fg='#22c55e' if is_confirmed else '#94a3b8',
                     font=('Consolas',12,'bold')).pack(side='left')
            tk.Label(f,text=f'{name_zh} / {name_en}',bg='#1e293b',fg='#f8fafc',font=('Microsoft YaHei',11)).pack(side='left',padx=8)
            if not is_confirmed:
                note_var=tk.StringVar()
                tk.Entry(f,textvariable=note_var,width=30,bg='#10243b',fg='white',insertbackground='white').pack(side='left',padx=8)
                tk.Button(f,text='确认 / CONFIRM',command=lambda c=code,n=note_var,d=d:self._do_confirm_step(wo,c,n.get(),d),
                          bg='#16a34a',fg='white').pack(side='right',padx=4)
                confirmed[code]=note_var
        tk.Label(d,text='--- 维修后测试 / Post-Repair Tests ---',bg='#0f172a',fg='#fbbf24',font=('Microsoft YaHei',11,'bold')).pack(pady=8)
        for code,name_zh,name_en,required in POST_REPAIR_TESTS:
            f=tk.Frame(d,bg='#1e293b');f.pack(fill='x',padx=16,pady=3)
            tested=code in info.get('tests_recorded',[])
            result=next((t['result'] for t in info.get('tests',[]) if t['test_code']==code),None)
            color='#22c55e' if result=='PASS' else ('#ef4444' if result=='FAIL' else '#94a3b8')
            tk.Label(f,text=f'{"[PASS]" if result=="PASS" else "[FAIL]" if result=="FAIL" else "[ ]"}',
                     bg='#1e293b',fg=color,font=('Consolas',12,'bold')).pack(side='left')
            req_tag=' *' if required else ''
            tk.Label(f,text=f'{name_zh}{req_tag}',bg='#1e293b',fg='#f8fafc',font=('Microsoft YaHei',11)).pack(side='left',padx=8)
            if not tested:
                for btn_txt,res in (('PASS',True),('FAIL',False)):
                    tk.Button(f,text=btn_txt,command=lambda w=wo,c=code,r=res,d=d:self._do_record_test(w,c,r,d),
                              bg='#16a34a' if res else '#dc2626',fg='white').pack(side='right',padx=2)
        tk.Button(d,text='关闭 / CLOSE',command=d.destroy,bg='#475569',fg='white').pack(pady=10)

    def _do_confirm_step(self,wo,step_code,note,d):
        try:
            r=self.core.confirm_step(wo,step_code,note)
            if r.get('ok'):
                messagebox.showinfo('OK',f'{step_code} 已确认\nNext: {r.get("next_step")}')
                d.destroy();self._refresh()
            else:
                messagebox.showwarning('Failed',r.get('error',''))
        except ReworkError as ex:messagebox.showerror('Error',str(ex))

    def _do_record_test(self,wo,test_code,result,d):
        try:
            r=self.core.record_post_test(wo,test_code,'PASS' if result else 'FAIL')
            if r.get('ok'):
                messagebox.showinfo('OK',f'{test_code} = {"PASS" if result else "FAIL"}')
                d.destroy();self._refresh()
        except ReworkError as ex:messagebox.showerror('Error',str(ex))

    def _record_test_dlg(self):
        wo=self._selected_wo()
        if not wo:messagebox.showwarning('测试 / Test','请先选择工单');return
        d=tk.Toplevel(self.root);d.title('记录测试结果 / Record Test Result');d.configure(bg='#0f172a');d.geometry('500x350')
        tk.Label(d,text=f'工单 / WO: {wo}',bg='#0f172a',fg='#67e8f9',font=('Microsoft YaHei',13,'bold')).pack(pady=8)
        test_var=tk.StringVar(value=POST_REPAIR_TESTS[0][0])
        result_var=tk.StringVar(value='PASS')
        tk.Label(d,text='测试 Test:',bg='#0f172a',fg='#f8fafc').pack()
        for code,name_zh,_,_ in POST_REPAIR_TESTS:
            tk.Radiobutton(d,text=name_zh,variable=test_var,value=code,bg='#0f172a',fg='#67e8f9',selectcolor='#0891b2',
                           activebackground='#0f172a').pack(anchor='w',padx=20)
        tk.Label(d,text='结果 Result:',bg='#0f172a',fg='#f8fafc').pack(pady=(10,0))
        for txt,val in (('PASS / 通过',True),('FAIL / 失败',False)):
            tk.Radiobutton(d,text=txt,variable=result_var,value=str(val),bg='#0f172a',fg='#67e8f9',selectcolor='#0891b2',
                           activebackground='#0f172a').pack(anchor='w',padx=20)
        note_var=tk.StringVar()
        tk.Label(d,text='备注 Note:',bg='#0f172a',fg='#f8fafc').pack(pady=(10,0))
        tk.Entry(d,textvariable=note_var,bg='#10243b',fg='white',insertbackground='white',width=40).pack()
        tk.Button(d,text='记录 / RECORD',command=lambda:self._do_record_test(wo,test_var.get(),result_var.get()=='True',d),
                  bg='#16a34a',fg='white',font=('Microsoft YaHei',11,'bold')).pack(pady=12)
        tk.Button(d,text='关闭 / CLOSE',command=d.destroy,bg='#475569',fg='white').pack()

    def _show_detail(self):
        wo=self._selected_wo()
        if not wo:messagebox.showwarning('详情 / Detail','请先选择工单');return
        log=self.core.fetch_repair_log(wo)
        if not log:messagebox.showwarning('详情','未找到工单');return
        wo_data=log['work_order']
        d=tk.Toplevel(self.root);d.title(f'维修详情 / Detail: {wo}');d.configure(bg='#0f172a');d.geometry('1000x700')
        # Header
        hdr=tk.Frame(d,bg='#0b1f35');hdr.pack(fill='x')
        info_txt=f"WO: {wo_data['work_order_no']}  |  SN: {wo_data['ng_sn']}  |  Batch: {wo_data['batch_id']}  |  来源: {wo_data['source_station']}  |  状态: {wo_data['status']}"
        tk.Label(hdr,text=info_txt,bg='#0b1f35',fg='#67e8f9',font=('Consolas',10)).pack(pady=8,padx=8)
        nb=ttk.Notebook(d);nb.pack(fill='both',expand=True,padx=8,pady=8)
        sub_trees={}
        def add_tab(name,cols):
            p=tk.Frame(nb);nb.add(p,text=name)
            t=ttk.Treeview(p,columns=cols,show='headings')
            for c in cols:t.heading(c,text=c);t.column(c,width=140,anchor='center')
            t.pack(fill='both',expand=True);ttk.Scrollbar(p,command=t.yview).pack(side='right',fill='y')
            sub_trees[name]=t;return t
        # 记录 history
        t=add_tab('维修记录',('时间','动作','结果','方法/备注','操作员'))
        for r in log['records']:
            started=r['started_at'] or ''
            elapsed=''
            if r['completed_at'] and r['started_at']:
                try:
                    from datetime import datetime as dt
                    s=dt.fromisoformat(r['started_at'].replace('Z','+00:00'))
                    e=dt.fromisoformat(r['completed_at'].replace('Z','+00:00'))
                    diff=e-s;elapsed=f'{diff.total_seconds():.0f}s'
                except:elapsed='-'
            t.insert('',0,values=(started,r['action'],r['result'] or '',r['repair_method'] or r['defect_code'] or '',r['operator'] or ''))
        # 物料 materials with WMS traceability
        t=add_tab('更换物料',('物料编码','名称','批号','供应商','仓位','IQC状态','数量','单位','入库事务号','领料事务号','操作员','记录时间'))
        for m in log['materials']:
            t.insert('',0,values=(
                m.get('material_code','') or '',m.get('material_name','') or '',
                m.get('lot_no','') or '',m.get('supplier_code','') or '',m.get('location_code','') or '',
                m.get('iqc_status','') or '',
                m.get('quantity',''),m.get('unit','') or '',
                m.get('inbound_tx_no','') or '',m.get('pick_tx_no','') or '',
                m.get('operator','') or '',m.get('recorded_at','') or ''))
        # 步骤 steps
        t=add_tab('维修步骤',('序号','步骤代码','步骤名称','开始时间','确认时间','确认人','备注'))
        for s_item in log['steps']:
            code=s_item['step_code']
            meta=next(((nzh,ne) for c,nzh,ne,i in REPAIR_STEPS if c==code),('?','?'))
            t.insert('',0,values=(s_item['step_index']+1,code,f'{meta[0]} / {meta[1]}',
                s_item['started_at'] or '',s_item['confirmed_at'] or '',s_item['confirmed_by'] or '',s_item['note'] or ''))
        # 测试 tests
        t=add_tab('测试结果',('测试代码','测试名称','结果','测量值','测试人','测试时间','备注'))
        for t_item in log['tests']:
            code=t_item['test_code']
            meta=next(((nzh,ne) for c,nzh,ne,_ in POST_REPAIR_TESTS if c==code),(code,code))
            color='PASS' if t_item['result']=='PASS' else 'FAIL'
            t.insert('',0,values=(code,f'{meta[0]} / {meta[1]}',t_item['result'] or '',
                t_item['measured_value'] or '',t_item['tested_by'] or '',t_item['tested_at'] or '',t_item['note'] or ''))
        # QC
        t=add_tab('QC控制',('SN','槽位','来料结果','缺陷代码','维修状态','更新时间'))
        for m in log['motherboard_members']:
            t.insert('',0,values=(m['sn'] or '',m['slot'] or '',m['incoming_result'] or '',
                m['defect_code'] or '-',m['repair_status'] or '',m['updated_at'] or ''))
        # 报废 scraps
        if log['scraps']:
            t=add_tab('报废记录',('原因代码','原因','操作员','时间'))
            for s_item in log['scraps']:
                t.insert('',0,values=(s_item['reason_code'],s_item['reason_text'] or '',s_item['scrapped_by'],s_item['scrapped_at']))
        tk.Button(d,text='关闭 / CLOSE',command=d.destroy,bg='#475569',fg='white').pack(pady=6)

    def _show_history(self):
        """Open a read-only WO history view without changing MES or local records."""
        wo=self._selected_wo()
        if not wo:
            messagebox.showwarning('WO HISTORY / 工单历史','Select a work order first / 请先选择维修工单')
            return
        d=tk.Toplevel(self.root)
        d.title(f'WO HISTORY / 工单历史 - {wo}')
        d.configure(bg='#0f172a')
        d.geometry('1000x680')
        snap=self.core.snapshot()
        query=tk.StringVar()
        filter_bar=tk.Frame(d,bg='#172033');filter_bar.pack(fill='x',padx=10,pady=(10,0))
        tk.Label(filter_bar,text='Search / 搜索',bg='#172033',fg='#cbd5e1').pack(side='left',padx=6)
        search=tk.Entry(filter_bar,textvariable=query,bg='#10243b',fg='white',insertbackground='white',width=42)
        search.pack(side='left',padx=6,pady=6)
        outbox=len(snap.get('outbox',[]))
        tk.Label(filter_bar,text=f'LOCAL OUTBOX / 离线待上传: {outbox}',bg='#172033',fg='#fbbf24').pack(side='right',padx=8)
        text=tk.Text(d,wrap='none',bg='#0b1f35',fg='#dbeafe',insertbackground='white',font=('Consolas',10))
        def refresh_history(*_):
            value=build_wo_history_text(snap,wo)
            if query.get().strip():
                rows=build_wo_history_rows(snap,wo,query.get())
                value += '\n\nFILTERED TIMELINE / 筛选时间线\n' + '\n'.join(
                    '{time} [{type}] {code} {result} {detail} {operator}'.format(**r) for r in rows)
            text.configure(state='normal');text.delete('1.0','end');text.insert('1.0',value);text.configure(state='disabled')
        refresh_history()
        search.bind('<KeyRelease>',refresh_history)
        text.configure(state='disabled')
        text.pack(fill='both',expand=True,padx=10,pady=10)
        tk.Button(d,text='CLOSE / 关闭',command=d.destroy,bg='#475569',fg='white').pack(pady=(0,8))

    def _show_all_history(self):
        """Show all local repair WOs and a read-only timeline drill-down."""
        d=tk.Toplevel(self.root); d.title('ALL WO HISTORY / 全部维修工单历史'); d.configure(bg='#0f172a'); d.geometry('1250x760')
        snap=self.core.snapshot(); query=tk.StringVar(); last10=tk.BooleanVar(value=False)
        bar=tk.Frame(d,bg='#172033'); bar.pack(fill='x',padx=10,pady=10)
        tk.Label(bar,text='Search WO / SN / station / status',bg='#172033',fg='#cbd5e1').pack(side='left',padx=6)
        entry=tk.Entry(bar,textvariable=query,width=46,bg='#10243b',fg='white',insertbackground='white'); entry.pack(side='left',padx=6,pady=6)
        tk.Checkbutton(bar,text='LAST 10 / 最近10单',variable=last10,bg='#172033',fg='#cbd5e1',selectcolor='#0f172a',command=lambda: refresh()).pack(side='left',padx=8)
        tk.Label(bar,text=f"LOCAL READ-ONLY · {len(snap.get('work_orders',[]))} WOs",bg='#172033',fg='#67e8f9').pack(side='right',padx=8)
        frame=tk.Frame(d,bg='#0f172a'); frame.pack(fill='both',expand=True,padx=10,pady=(0,10))
        cols=('WO','SN','SOURCE','BATCH','STATUS','RESULT','UPDATED','EVENTS','RETESTS')
        tree=ttk.Treeview(frame,columns=cols,show='headings',height=22)
        for col,width in zip(cols,(180,150,110,130,145,110,170,70,70)):
            tree.heading(col,text=col); tree.column(col,width=width,anchor='center')
        tree.pack(side='left',fill='both',expand=True); ttk.Scrollbar(frame,orient='vertical',command=tree.yview).pack(side='right',fill='y')
        detail=tk.Text(d,height=18,wrap='none',bg='#0b1f35',fg='#dbeafe',state='disabled',font=('Consolas',9)); detail.pack(fill='both',expand=True,padx=10,pady=(0,10))
        def refresh(*_):
            tree.delete(*tree.get_children())
            rows=build_all_wo_history_rows(snap,query.get(),10 if last10.get() else None)
            for row in rows:
                tree.insert('', 'end', values=(row['work_order_no'],row['sn'],row['source_station'],row['batch_id'],row['status'],row['result'],row['updated_at'],row['events'],row['retests']))
            if last10.get():
                value='\n\n'.join(build_wo_history_text(snap,row['work_order_no']) for row in rows)
                detail.configure(state='normal'); detail.delete('1.0','end'); detail.insert('1.0',value or 'No local work-order history.'); detail.configure(state='disabled')
        def show_detail(_event=None):
            selected=tree.selection()
            if not selected:return
            wo=str(tree.item(selected[0],'values')[0]); value=build_wo_history_text(snap,wo)
            detail.configure(state='normal'); detail.delete('1.0','end'); detail.insert('1.0',value); detail.configure(state='disabled')
        entry.bind('<KeyRelease>',refresh); tree.bind('<<TreeviewSelect>>',show_detail); refresh()
        tk.Button(d,text='CLOSE / 关闭',command=d.destroy,bg='#475569',fg='white').pack(pady=(0,8))

    def _call_pickup(self):
        wo_no=self._selected_wo()
        if not wo_no:
            messagebox.showwarning('Pickup','Select a repair work order first');return
        pickup=self.core.notify_pickup_to_source_station(wo_no)
        if pickup.get('ok'):
            state='QUEUED OFFLINE' if pickup.get('queued') else 'READY'
            self.pickup_var.set(f'PICKUP {state}: {pickup.get("source_station","SOURCE")} -> LINE LEADER / TEAM LEADER | eventId={pickup.get("event_id","-")}')
            messagebox.showinfo('Pickup notification',f'Line leader/team leader PDA notified (or queued).\n\neventId: {pickup.get("event_id","-")}')
        else:
            messagebox.showwarning('Pickup notification failed',str(pickup.get('response') or pickup.get('detail') or 'MES did not accept the notification'))

    def _complete(self):
        wo_no=self._selected_wo()
        if not wo_no:messagebox.showwarning('完成 / Complete','请选择维修工单');return
        if not self.complete_var.get() or not self.method.get().strip():
            messagebox.showwarning('完成 / Complete','必须勾选完成并填写维修方法');return
        if not self.materials and not self.no_material_var.get():
            messagebox.showwarning('物料 / Material','请登记更换物料，或勾选无物料更换');return
        r=self.core.complete_repair(wo_no,self.method.get().strip(),self.materials,'repaired')
        if not r.get('ok'):messagebox.showerror('完成失败',r.get('detail',''));return
        # Notify source station to pick up
        pickup=self.core.notify_pickup_to_source_station(wo_no)
        self.materials=[];self.mat_lot_records=[];self.method.set('');self.complete_var.set(False);self.no_material_var.set(False)
        self._refresh_lot_display()
        self.material_label.config(text='尚未登记物料 / No material recorded')
        if pickup.get('ok'):
            self.pickup_var.set(f'PICKUP {"QUEUED OFFLINE" if pickup.get("queued") else "READY"}: {pickup.get("source_station","SOURCE")} -> LINE LEADER / TEAM LEADER | eventId={pickup.get("event_id","-")}')
            self.status.set(f'完成 / COMPLETE: {wo_no}  → 已通知 {pickup.get("source_station","源工站")} 取件')
            messagebox.showinfo('维修完成 / Repair Complete',
                f'工单: {wo_no}\n'
                f'维修结果: 已修复\n'
                f'已通知上工序站: {pickup.get("source_station","?")} 派人来取\n'
                f'SN: {pickup.get("sn","?")}  批次: {pickup.get("batch_id","?")}\n\n'
                f'MES返回: {pickup.get("response",{}).get("message","OK")}')
        else:
            self.status.set(f'完成 / COMPLETE: {wo_no}  (取件通知发送失败)')
            messagebox.showwarning('通知失败','维修已完成，但向源工站发送取件通知失败')
        self._refresh()

    # Line source → display name + color
    LINE_SOURCE_MAP={
        'manu_ict':'ICT','manu_fct':'FCT','manu_depanel':'DEPANEL',
        'manu_assem_ate':'组装ATE','manu_supersonic':'超声','manu_agingcab':'老化',
        'manu_hivolt_ate':'高压','manu_package_ate':'包装ATE',
        'manu_smt_aoi':'SMT-AOI','manu_smt_paste':'SMT-印刷','manu_smt_pick':'SMT-贴片',
    }
    LINE_CATEGORY={'manu_ict':'MANUAL','manu_fct':'MANUAL','manu_depanel':'MANUAL',
                   'manu_assem_ate':'MANUAL','manu_supersonic':'MANUAL','manu_agingcab':'AUTO',
                   'manu_hivolt_ate':'AUTO','manu_package_ate':'AUTO',
                   'manu_smt_aoi':'SMT','manu_smt_paste':'SMT','manu_smt_pick':'SMT'}
    LINE_COLORS={'SMT':'#8b5cf6','AUTO':'#0891b2','MANUAL':'#16a34a'}

    def _worker(self):
        while self.running:
            try:
                pending=self.core.fetch_pending_handovers()  # fetch from MES, store in DB
                self.core.fetch_active_repairs();self.core.fetch_ng_releases()
                self.core.sync_ng_registry();self.core.sync_outbox();self.core.heartbeat()
                self.root.after(0,self._set_heartbeat,True)
                # Update dropdown with queued WOs
                queued=[(r.get('repairWorkOrderNo') or r.get('requestId',''),
                         r.get('batchId',''),
                         self._line_tag(r.get('sourceStation','')))
                        for r in pending if r.get('repairWorkOrderNo')]
                values=[f"{wo} | {sn} {tag}" for wo,sn,tag in queued if wo]
                self.root.after(0,lambda v=values,p=len(pending):self._update_wo_dropdown(v,p))
            except Exception:
                self.root.after(0,self._set_heartbeat,False)
            time.sleep(5)

    def _set_heartbeat(self,online):
        stamp=time.strftime('%H:%M:%S')
        if online:
            self.heartbeat_var.set(f'HEARTBEAT: ONLINE {stamp}')
            self.heartbeat_label.config(bg='#14532d',fg='#bbf7d0')
        else:
            self.heartbeat_var.set(f'HEARTBEAT: OFFLINE {stamp}')
            self.heartbeat_label.config(bg='#7f1d1d',fg='#fecaca')

    def _update_wo_dropdown(self,values,count):
        try:
            self.wo_combo['values']=values if values else ['']
            self.wo_count_lbl.config(text=f'MES待接收: {count}')
            if count>0:
                self.wo_count_lbl.config(fg='#ef4444')
            else:
                self.wo_count_lbl.config(fg='#22c55e')
        except Exception: pass

    def _line_tag(self, source):
        cat=self.LINE_CATEGORY.get(source,'')
        color=self.LINE_COLORS.get(cat,'#94a3b8')
        name=self.LINE_SOURCE_MAP.get(source,source or '?')
        return f'[{cat}/{name}]'

    def _refresh(self):
        s=self.core.fetch_all()
        # MES待接收 — show RWO + line source + board count
        self._fill('MES待接收',[
            (r.get('repairWorkOrderNo') or '-',
             r.get('billNo') or r.get('requestId') or '-',
             r.get('batchId'),
             self._line_tag(r.get('sourceStation','')) + ' ' + (r.get('sourceStation') or ''),
             len(r.get('motherboard',{}).get('subBoards') or []),
             r.get('submittedAt','')[-8:] if r.get('submittedAt') else '',
             r.get('status','')) for r in s['pending_handovers']])
        # 维修中 — show RWO + line source + elapsed
        self._fill('维修中',[
            (r.get('repairWorkOrderNo') or r.get('batchId',''),
             self._line_tag(r.get('sourceStation','')) + ' ' + (r.get('sourceStation') or ''),
             r.get('batchId',''),
             r.get('repairStartedAt','-')[11:19] if r.get('repairStartedAt') else '-',
             f"{int(r.get('repairElapsedSeconds') or 0)//3600:02d}:{int(r.get('repairElapsedSeconds') or 0)%3600//60:02d}:{int(r.get('repairElapsedSeconds') or 0)%60:02d}",
             'TIMEOUT' if r.get('repairAlarmAt') else 'REPAIRING')
            for r in s['active_repairs']])
        # 维修工单 — RWO + SN + batch + line source + status + completed + method + result + operator
        self._fill('维修工单',[
            (w['work_order_no'],
             w['ng_sn'],
             w['batch_id'],
             self._line_tag(w['source_station']) + ' ' + (w['source_station'] or ''),
             w['status'],
             w['repair_completed_at'][11:19] if w.get('repair_completed_at') else '',
             w['repair_method'] or '',
             w['repair_result'] or '',
             w['operator'] or '')
            for w in s['work_orders']])
        self._fill('物料记录',[(m['work_order_no'],m['ng_sn'] or '',m['material_code'] or '',m['material_name'] or '',
            m['quantity'],m['unit'] or '',m['operator'] or '',m['recorded_at']) for m in s['materials']])
        self._fill('维修日志',[(r['started_at'][11:19] if r['started_at'] else '',r['sn'],r['action'],r['result'] or '',
            r['repair_method'] or r['defect_code'] or '',r['operator'] or '','') for r in s['history']])
        # QC控制 — full QC view
        self._fill('QC控制',[
            (w['work_order_no'],
             w['ng_sn'],
             self._line_tag(w['source_station']) + ' ' + (w['source_station'] or ''),
             w['status'],
             w['repair_completed_at'][11:19] if w.get('repair_completed_at') else '',
             w['repair_method'] or '',
             w['repair_result'] or '',
             len(w.get('retest_history_parsed') or []))
            for w in s['work_orders']])
        self._fill('扫码记录',[(x['last_seen'][11:19] if x['last_seen'] else '',x['sn'],x['result'],'SYNC' if x['mes_synced'] else 'QUEUE') for x in s['scans']])
        self._fill('NG拦截',[(x['detected_at'][11:19] if x['detected_at'] else '',x['sn'],x['source'],x['defect_code'] or '-') for x in s['ng_active']])
        self._fill('MES缓存',[(x['sn'],x['source_station'] or '',x['batch_id'] or '',x['registry_version'],x['synced_at']) for x in s['cached_ng']])
        self._fill('MES通信',[(o['event_type'],o['sn'],o['result'],o['attempts'],o['created_at']) for o in s['outbox']])
        self._fill('修改记录',[(c['change_id'],c['version'],c['component'],c['reason'],c['summary'],c['verification'],c['changed_at']) for c in s['changes']])
        # 物料追溯 — full WMS trace from fetch_material_trace
        try:
            traces=self.core.fetch_material_trace(days=90,limit=200)
            self._fill('物料追溯',[
                (r['wo_no'], r['ng_sn'], r['material_code'], r['lot_no'],
                 r['supplier_code'], r['supplier_name'], r['location_code'],
                 r['received_at'], r['iqc_status'],
                 r['inbound_tx_no'], r['pick_tx_no'],
                 r['pick_issued_at'], r['issue_work_order_no'],
                 r['operator'], r['replaced_at'])
                for r in traces])
            # IQC报告 — color-coded by IQC result
            self._fill('IQC报告',[
                (r['wo_no'], r['ng_sn'], r['material_code'], r['lot_no'],
                 r['supplier_code'], r['location_code'], r['received_at'],
                 r['iqc_status'],
                 'PASS' if r['iqc_status']=='released' else 'FAIL',
                 '', '', '', '',  # visual QC — filled at record time
                 r['operator'], r['replaced_at'])
                for r in traces])
        except Exception: pass

    def _close(self):self.running=False;self.root.destroy()

if __name__=='__main__':
    root=tk.Tk();app=Rework2D(root);root.protocol('WM_DELETE_WINDOW',app._close);root.mainloop()
