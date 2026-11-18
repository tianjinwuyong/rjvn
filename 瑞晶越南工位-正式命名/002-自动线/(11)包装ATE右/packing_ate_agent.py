# -*- coding: utf-8 -*-
"""Packaging ATE 2D UI. Business/data authority lives in packing_ate_core."""
import socket
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR.parent))
MANUAL_LINE_DIR = APP_DIR.parent.parent / "002-自动线"
if str(MANUAL_LINE_DIR) not in sys.path and MANUAL_LINE_DIR.exists():
    sys.path.insert(1, str(MANUAL_LINE_DIR))
from packing_ate_core import PackingAteCore, PackingAteError, MES_URL, STATION_CODE
from station_heartbeat import StationHeartbeat
from station_scan_alarm import show_blocking_alarm
from station_language import install_language_menu
from station_excel_events import ExcelEventWatcher
from station_ui_primitives import install_station_tabs


class PackingAte2D:
    def __init__(self, root):
        self.root=root; self.core=PackingAteCore(); self.running=True
        self.heartbeat=StationHeartbeat(STATION_CODE, MES_URL, "packing_ate_agent")
        self.excel_watcher=ExcelEventWatcher(self.core.watch_dir,self._excel_event)
        root.title("包装 ATE / Packaging ATE · 2D"); root.geometry("1500x900"); root.configure(bg="#0f172a")
        self.status=tk.StringVar(value="启动中"); self.scan=tk.StringVar(); self.cards={}
        install_station_tabs(root); install_language_menu(root); self._build(); self.refresh()
        threading.Thread(target=self._worker,daemon=True).start()
        threading.Thread(target=self._scanner,daemon=True).start()
        self.excel_watcher.start()

    def _build(self):
        head=tk.Frame(self.root,bg="#111827");head.pack(fill="x")
        tk.Label(head,text="包装 ATE · 2D",font=("Microsoft YaHei",20,"bold"),fg="white",bg="#111827").pack(side="left",padx=16,pady=10)
        tk.Label(head,textvariable=self.status,font=("Microsoft YaHei",11,"bold"),fg="#67e8f9",bg="#111827").pack(side="right",padx=16)
        scan=tk.Frame(self.root,bg="#422006");scan.pack(fill="x",padx=12,pady=6)
        tk.Label(scan,text="扫码检查（只检查 NG / 重复，不生成测试结果）",bg="#422006",fg="#fde047",font=("Microsoft YaHei",11,"bold")).pack(side="left",padx=8)
        ent=tk.Entry(scan,textvariable=self.scan,font=("Consolas",14),width=32);ent.pack(side="left",padx=8,pady=8);ent.bind("<Return>",lambda _e:self.check_scan())
        tk.Button(scan,text="检查",command=self.check_scan).pack(side="left")
        tk.Button(scan,text="选择数据目录",command=self.choose_dir).pack(side="right",padx=8)
        tk.Button(scan,text="部分测试（<8条）",command=self.partial_test,bg="#7c3aed",fg="white",
                  font=("Microsoft YaHei",10,"bold")).pack(side="right",padx=8)
        banks=tk.Frame(self.root,bg="#0f172a");banks.pack(fill="x",padx=12)
        for side in ("L","R"):
            box=tk.LabelFrame(banks,text=f"{side} · 8 个独立 SN",fg="white",bg="#111827",font=("Microsoft YaHei",11,"bold"));box.pack(side="left",fill="x",expand=True,padx=4)
            for i in range(1,9):
                c=tk.Label(box,text=f"{side}{i}\n--",width=17,height=3,bg="#334155",fg="white",font=("Consolas",10,"bold"),relief="ridge")
                c.grid(row=(i-1)//4,column=(i-1)%4,padx=4,pady=4,sticky="nsew");self.cards[f"{side}{i}"]=c
        self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill="both",expand=True,padx=12,pady=8)
        specs=[("实时结果",("时间","通道","SN","结果","错误","重复","MES")),("预发SN",("预发时间","SN","来源","状态","到站时间")),("报到记录",("到站时间","SN","预发","状态","MES确认时间","来源")),("未报到原因",("时间","SN","原因代码","原因说明","操作员","主管")),("维修工单",("本地工单","MES工单","SN","原因","部门","状态","创建时间")),("历史封存",("封存批次","原因","记录数","总哈希","封存时间","人员")),("NG",("时间","通道","SN","错误")),("扫码检查",("时间","SN","状态","说明")),("原始数据",("源文件","行","周期","通道","SN","结果")),("MES通信",("事件ID","状态","重试","错误")),("设置",("项目","值")),("修改记录",("编号","版本","组件","原因","内容","验证","时间"))]
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
        except PackingAteError as exc:messagebox.showwarning("扫码",str(exc))
        self.refresh()

    def choose_dir(self):
        value=filedialog.askdirectory(initialdir=str(self.core.watch_dir))
        if value:
            self.core.set_watch_dir(value)
            self.excel_watcher.directory=self.core.watch_dir
            self.excel_watcher.start()
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

    def _worker(self):
        while self.running:
            self.heartbeat.tick(sourceConnected=self.core.watch_dir.exists(), sourceType="XLSX")
            self.core.sync_once()
            time.sleep(5)

    def _excel_event(self):
        if not self.running:return
        report=self.core.ingest_once()
        if report["added"]:
            self.core.sync_once()
            self.root.after(0,lambda r=report:self._after_poll(r))

    def _after_poll(self,report):
        if report["added"]:self.status.set(f'新增 {len(report["added"])} 条 Excel 测试记录')
        elif report["errors"]:self.status.set("有 Excel 文件暂时无法读取")
        self.refresh()

    def _scanner(self):
        server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:
            server.bind(("0.0.0.0",int(__import__("os").environ.get("STATION_SCANNER_PORT","1003"))));server.listen(5);server.settimeout(1)
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
        arrival=snap["arrival"]
        self._fill(self.trees["预发SN"],[(r["expected_at"],r["sn"],r["source_station"],r["arrival_status"],r["arrived_at"] or "") for r in arrival["expected"]])
        self._fill(self.trees["报到记录"],[(r["arrived_at"],r["sn"],"YES" if r["expected"] else "NO",r["arrival_status"],r["mes_reported_at"] or "",r["source_type"]) for r in arrival["arrivals"]])
        self._fill(self.trees["未报到原因"],[(r["created_at"],r["sn"],r["reason_code"],r["reason_detail"],r["operator_id"],r["supervisor_id"]) for r in arrival["exceptions"]])
        self._fill(self.trees["维修工单"],[(r["local_case_id"],r["mes_work_order_id"] or "",r["sn"],r["reason_code"],r["department"],r["status"],r["created_at"]) for r in snap["maintenance"]["cases"]])
        self._fill(self.trees["历史封存"],[(r["archive_batch_id"],r["reason"],r["record_count"],r["content_hash"],r["sealed_at"],r["created_by"]) for r in snap["history"]["batches"]])
        self._fill(self.trees["NG"],[(r["test_time"],r["channel"],r["sn"],r["error_code"]) for r in results if r["result"]=="FAIL"])
        self._fill(self.trees["扫码检查"],[(r["created_at"],r["sn"],r["status"],r["detail"]) for r in snap["checks"]])
        self._fill(self.trees["原始数据"],[(r["source_file"],r["source_row"],r["test_cycle_id"],r["channel"],r["sn"],r["result"]) for r in results])
        self._fill(self.trees["MES通信"],[(r["event_id"],"SENT" if r["sent_at"] else "QUEUED",r["retry_count"],r["last_error"]) for r in snap["outbox"]])
        self._fill(self.trees["设置"],[("Excel 数据目录",snap["watch_dir"]),("数据源状态","ONLINE" if snap["source_connected"] else "MISSING"),("数据流向","本地 SQLite → MES"),("扫码规则","仅 NG / 重复检查")])
        self._fill(self.trees["修改记录"],[(r["change_id"],r["version"],r["component"],r["reason"],r["summary"],r["verification"],r["changed_at"]) for r in snap["changes"]])

    def close(self):self.running=False;self.excel_watcher.stop();self.root.destroy()


if __name__=="__main__":
    root=tk.Tk();app=PackingAte2D(root)
    from station_retest import install_station_retest_panel
    install_station_retest_panel(root,STATION_CODE,MES_URL.replace("/api/pda/events",""))
    from station_repair_workflow import install_repair_workflow
    install_repair_workflow(root, STATION_CODE, MES_URL, "包装 ATE 右")
    root.protocol("WM_DELETE_WINDOW",app.close);root.mainloop()
