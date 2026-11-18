# -*- coding: utf-8 -*-
"""Assembly ATE 2D UI. Business/data authority lives in assembly_ate_core."""
import os
import socket
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

SHARED_DIR=Path(__file__).resolve().parents[2] / "002-自动线"
if str(SHARED_DIR) not in sys.path: sys.path.insert(0,str(SHARED_DIR))

from assembly_ate_core import AssemblyAteCore, AssemblyAteError, MES_URL, STATION_CODE
from assembly_ate_preview import AutoAssemblyAtePreviewCore
from station_heartbeat import StationHeartbeat
from station_scan_alarm import show_blocking_alarm
from station_language import install_language_menu
from station_ui_primitives import UI_PREVIEW, add_preview_watermark, configure_tk_station, register_scanner_entry, restore_scanner_focus
from station_arrival_ui import ProductGateComponent


class ExcelChangeHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_created(self, event):
        self.app.excel_changed(event.src_path, event.is_directory)

    def on_modified(self, event):
        self.app.excel_changed(event.src_path, event.is_directory)

    def on_moved(self, event):
        self.app.excel_changed(event.dest_path, event.is_directory)


class AssemblyAte2D:
    def __init__(self, root):
        self.root=root; self.core=AutoAssemblyAtePreviewCore() if UI_PREVIEW else AssemblyAteCore(); self.running=True
        self.heartbeat=None if UI_PREVIEW else StationHeartbeat(STATION_CODE, MES_URL, "assembly_ate_agent")
        self.observer=None;self.event_lock=threading.Lock();self.event_timer=None
        root.title("自动线组装 ATE / Auto-line Assembly ATE · 2D"); configure_tk_station(root)
        self.status=tk.StringVar(value="启动中"); self.scan=tk.StringVar(); self.cards={}
        install_language_menu(root); add_preview_watermark(root); self._build(); self.refresh()
        if UI_PREVIEW: self.status.set("PREVIEW · all production writes blocked")
        else:
            threading.Thread(target=self._worker,daemon=True).start()
            threading.Thread(target=self._scanner,daemon=True).start()
            self.start_excel_watcher()

    def _build(self):
        head=tk.Frame(self.root,bg="#111827");head.pack(fill="x")
        tk.Label(head,text="自动线组装 ATE · 2D",font=("Microsoft YaHei",20,"bold"),fg="white",bg="#111827").pack(side="left",padx=16,pady=10)
        tk.Label(head,textvariable=self.status,font=("Microsoft YaHei",11,"bold"),fg="#67e8f9",bg="#111827").pack(side="right",padx=16)
        scan=tk.Frame(self.root,bg="#422006");scan.pack(fill="x",padx=12,pady=6)
        tk.Label(scan,text="扫码检查（产品路线 / NG / 重复 / 返修复测权限）",bg="#422006",fg="#fde047",font=("Microsoft YaHei",11,"bold")).pack(side="left",padx=8)
        ent=tk.Entry(scan,textvariable=self.scan,font=("Consolas",14),width=32);register_scanner_entry(self.root,ent);self.scan_entry=ent;ent.pack(side="left",padx=8,pady=8);ent.bind("<Return>",lambda _e:self.check_scan())
        tk.Button(scan,text="检查",command=self.check_scan).pack(side="left")
        tk.Button(scan,text="选择数据目录",command=self.choose_dir).pack(side="right",padx=8)
        tk.Button(scan,text="部分测试（<8条）",command=self.partial_test,bg="#7c3aed",fg="white",
                  font=("Microsoft YaHei",10,"bold")).pack(side="right",padx=8)
        self.arrival_route=ProductGateComponent(self.root)
        banks=tk.Frame(self.root,bg="#0f172a");banks.pack(fill="x",padx=12)
        for side in ("L","R"):
            box=tk.LabelFrame(banks,text=f"{side} · 8 个独立 SN",fg="white",bg="#111827",font=("Microsoft YaHei",11,"bold"));box.pack(side="left",fill="x",expand=True,padx=4)
            for i in range(1,9):
                c=tk.Label(box,text=f"{side}{i}\n--",width=17,height=3,bg="#334155",fg="white",font=("Consolas",10,"bold"),relief="ridge")
                c.grid(row=(i-1)//4,column=(i-1)%4,padx=4,pady=4,sticky="nsew");self.cards[f"{side}{i}"]=c
        self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill="both",expand=True,padx=12,pady=8)
        specs=[("实时结果",("时间","通道","SN","结果","错误","重复","MES")),("产品路线",("产品SN","门禁","决定","原因","当前工站","下一动作","路线版本")),("确认NG历史",("SN","原因","来源工站","首次确认时间")),("维修工单",("本地工单","MES工单","SN","原因","部门","状态","创建时间")),("历史封存",("封存批次","原因","记录数","总哈希","封存时间","人员")),("NG测试结果",("时间","通道","SN","错误")),("扫码审计",("时间","SN","状态","说明")),("原始设备数据",("源文件","行","周期","通道","SN","结果")),("MES通信",("事件ID","状态","重试","错误")),("运行诊断",("项目","状态","说明")),("设置与版本",("项目","值")),("修改记录",("编号","版本","组件","原因","内容","验证","时间"))]
        self.trees={}
        for name,cols in specs:
            frame=tk.Frame(self.tabs);self.tabs.add(frame,text=name);tree=ttk.Treeview(frame,columns=cols,show="headings")
            for col in cols:tree.heading(col,text=col);tree.column(col,width=150,anchor="center")
            tree.pack(side="left",fill="both",expand=True);ttk.Scrollbar(frame,command=tree.yview).pack(side="right",fill="y");self.trees[name]=tree

    def check_scan(self):
        try:
            result=self.core.check_scan(self.scan.get()); self.scan.set("")
            message=f'{result["status"]}: {result["sn"]} {result["detail"]}'
            self.status.set(message)
            if result["blocked"]: show_blocking_alarm(self.root,result["status"],result["sn"],result["detail"],STATION_CODE,MES_URL)
        except AssemblyAteError as exc:messagebox.showwarning("扫码",str(exc))
        self.refresh(); restore_scanner_focus(self.root,self.scan_entry)

    def choose_dir(self):
        value=filedialog.askdirectory(initialdir=str(self.core.watch_dir))
        if value:self.core.set_watch_dir(value);self.start_excel_watcher();self.refresh()

    def _worker(self):
        while self.running:
            self.heartbeat.tick(sourceConnected=self.core.watch_dir.exists(), sourceType="XLSX")
            self.core.sync_once()
            time.sleep(5)

    def start_excel_watcher(self):
        if self.observer:
            self.observer.stop();self.observer.join(timeout=2)
        self.observer=Observer()
        if self.core.watch_dir.exists():
            self.observer.schedule(ExcelChangeHandler(self),str(self.core.watch_dir),recursive=True)
            self.observer.start()
            self.status.set("等待 Excel 新记录触发")

    def excel_changed(self,path,is_directory=False):
        name=str(path).replace("/","\\").split("\\")[-1]
        if is_directory or not name.lower().endswith(".xlsx") or name.startswith("~$"):
            return
        with self.event_lock:
            if self.event_timer:self.event_timer.cancel()
            self.event_timer=threading.Timer(2.0,self.process_excel_event)
            self.event_timer.daemon=True;self.event_timer.start()

    def process_excel_event(self):
        if not self.running:return
        report=self.core.ingest_once()
        if report["added"]:
            self.core.sync_once()
            self.root.after(0,lambda r=report:self._after_poll(r))

    def _after_poll(self,report):
        if report["added"]:self.status.set(f'新增 {len(report["added"])} 条 Excel 测试记录')
        elif report["errors"]:self.status.set("有 Excel 文件暂时无法读取")
        self.refresh()

    def partial_test(self):
        self.status.set("正在读取部分 ATE 测试记录…")
        threading.Thread(target=self._partial_test_worker, daemon=True).start()

    def _partial_test_worker(self):
        report = self.core.ingest_partial_once()
        if report["added"]:
            self.core.sync_once()
        self.root.after(0, lambda r=report: self._after_partial_test(r))

    def _after_partial_test(self, report):
        if report["added"]:
            self.status.set(f'部分测试已读取 {len(report["added"])} 条记录')
        elif report["errors"]:
            self.status.set("部分测试文件暂时无法读取")
            messagebox.showwarning("部分测试", report["errors"][0]["error"])
        else:
            self.status.set("没有待处理的 1–7 条新记录")
        self.refresh()

    def _scanner(self):
        server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:
            server.bind(("0.0.0.0",1007));server.listen(5);server.settimeout(1)
            while self.running:
                try:
                    conn,_=server.accept();data=conn.recv(4096).decode(errors="ignore").strip();conn.close()
                    if data:self.root.after(0,lambda x=data:(self.scan.set(x),self.check_scan()))
                except socket.timeout:pass
        except OSError as exc:self.root.after(0,lambda:self.status.set(f"扫码端口不可用: {exc}"))
        finally:server.close()

    def _fill(self,tree,rows):
        tree.delete(*tree.get_children())
        for row in rows:tree.insert("","end",values=row)

    def refresh(self):
        snap=self.core.snapshot();results=snap["results"]
        latest={}
        for r in results:
            if r["channel"] in self.cards and r["channel"] not in latest:latest[r["channel"]]=r
        for channel,card in self.cards.items():
            r=latest.get(channel);card.config(text=f'{channel}\n{r["sn"] if r else "--"}',bg="#166534" if r and r["result"]=="PASS" else "#991b1b" if r else "#334155")
        self._fill(self.trees["实时结果"],[(r["test_time"],r["channel"],r["sn"],r["result"],r["error_code"],"YES" if r["duplicate"] else "", "SYNC" if r["mes_synced"] else "QUEUED") for r in results[:500]])
        arrival=snap["arrival"]; self.arrival_route.update(arrival)
        route=arrival.get("route") or {}
        self._fill(self.trees["产品路线"],[(route.get("sn",""),route.get("gate_state",""),route.get("decision",""),route.get("reason",""),route.get("current_station",""),route.get("next_action",""),route.get("route_revision",""))] if route else [])
        self._fill(self.trees["确认NG历史"],[(r.get("sn",""),r.get("reason",""),r.get("source_station",""),r.get("received_at","")) for r in snap.get("ng",[])])
        self._fill(self.trees["维修工单"],[(r["local_case_id"],r["mes_work_order_id"] or "",r["sn"],r["reason_code"],r["department"],r["status"],r["created_at"]) for r in snap["maintenance"]["cases"]])
        self._fill(self.trees["历史封存"],[(r["archive_batch_id"],r["reason"],r["record_count"],r["content_hash"],r["sealed_at"],r["created_by"]) for r in snap["history"]["batches"]])
        self._fill(self.trees["NG测试结果"],[(r["test_time"],r["channel"],r["sn"],r["error_code"]) for r in results if r["result"]=="FAIL"])
        self._fill(self.trees["扫码审计"],[(r["created_at"],r["sn"],r["status"],r["detail"]) for r in snap["checks"]])
        self._fill(self.trees["原始设备数据"],[(r["source_file"],r["source_row"],r["test_cycle_id"],r["channel"],r["sn"],r["result"]) for r in results])
        self._fill(self.trees["MES通信"],[(r["event_id"],"SENT" if r["sent_at"] else "QUEUED",r["retry_count"],r["last_error"]) for r in snap["outbox"]])
        pending=sum(1 for r in snap["outbox"] if not r["sent_at"])
        self._fill(self.trees["运行诊断"],[("设备数据源","ONLINE" if snap["source_connected"] else "MISSING",snap["watch_dir"]),("扫码网关","PREVIEW" if UI_PREVIEW else "LISTENING","TCP 1007 + keyboard wedge"),("MES队列","OK" if pending==0 else "PENDING",f"{pending} events awaiting acknowledgement"),("历史完整性","SEALED",f"{len(snap['history']['batches'])} immutable batches"),("生产写入","BLOCKED" if UI_PREVIEW else "ENABLED","Preview never writes production truth")])
        self._fill(self.trees["设置与版本"],[("工站代码",STATION_CODE),("线体域","AUTO_LINE"),("Excel 数据目录",snap["watch_dir"]),("数据源状态","ONLINE" if snap["source_connected"] else "MISSING"),("数据流向","本地 SQLite → MES（确认回执）"),("扫码规则","产品路线 / NG / 重复 / 返修复测权限"),("Agent版本","5.0-station-standard")])
        self._fill(self.trees["修改记录"],[(r["change_id"],r["version"],r["component"],r["reason"],r["summary"],r["verification"],r["changed_at"]) for r in snap["changes"]])

    def close(self):
        self.running=False
        with self.event_lock:
            if self.event_timer:self.event_timer.cancel()
        if self.observer:self.observer.stop();self.observer.join(timeout=2)
        self.root.destroy()


if __name__=="__main__":
    root=tk.Tk();app=AssemblyAte2D(root)
    from station_retest import install_station_retest_panel
    install_station_retest_panel(root,STATION_CODE,MES_URL.replace("/api/pda/events",""))
    from station_repair_workflow import install_repair_workflow
    install_repair_workflow(root, STATION_CODE, MES_URL, "组装 ATE")
    root.protocol("WM_DELETE_WINDOW",app.close);root.mainloop()
