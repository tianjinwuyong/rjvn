# -*- coding: utf-8 -*-
"""2D production UI for outer-case binding."""
import subprocess
import threading
import tkinter as tk
import datetime
import os
import queue
import re
import sys
import json
import time
import urllib.request
import winsound
from tkinter import filedialog, messagebox, simpledialog, ttk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(APP_DIR))
MANUAL_LINE_DIR = os.path.join(os.path.dirname(os.path.dirname(APP_DIR)), "002-自动线")
if str(MANUAL_LINE_DIR) not in sys.path and os.path.isdir(MANUAL_LINE_DIR):
    sys.path.insert(1, str(MANUAL_LINE_DIR))
MANUAL_BINDING_DIR = os.path.join(MANUAL_LINE_DIR, "(12)外箱绑码")
if str(MANUAL_BINDING_DIR) not in sys.path and os.path.isdir(MANUAL_BINDING_DIR):
    sys.path.insert(2, str(MANUAL_BINDING_DIR))
from station_resource_startup import start_first_install_resource_read
start_first_install_resource_read(APP_DIR)
from auto_case_binding_core import (
    BindingError,
    CaseBindingStore,
    MES_BASE,
    STATION_CODE,
)
from station_retest import install_station_retest_panel
from station_i18n import TrilingualController, translated
from station_ui_primitives import install_station_tabs


_voice_queue = queue.Queue(maxsize=8)


def outerbox_heartbeat_worker():
    """Publish an auto-line outer-box binding heartbeat every 10 seconds."""
    while True:
        event = {
            "type": "AGENT_HEARTBEAT",
            "stationCode": STATION_CODE,
            "payload": {
                "agent": "outer_box_binding_agent",
                "lineDomain": "AUTO",
                "status": "running",
                "timestamp": int(time.time() * 1000),
            },
        }
        try:
            request = urllib.request.Request(
                MES_BASE.rstrip("/") + "/events",
                data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                response.read()
        except Exception:
            # Heartbeat failure must not block scanning; the next tick retries.
            pass
        time.sleep(10)


def _voice_worker():
    voice = None
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        voice = win32com.client.Dispatch("SAPI.SpVoice")
    except Exception:
        voice = None
    while True:
        text = _voice_queue.get()
        try:
            if voice is not None:
                # Async + purge: a newer scan count immediately replaces any
                # stale count still being spoken.
                voice.Speak(text, 3)
            else:
                script = "Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;$s.Speak('%s')" % text.replace("'", "''")
                subprocess.run(["powershell", "-NoProfile", "-Command", script], creationflags=0x08000000, check=False)
        finally:
            _voice_queue.task_done()


threading.Thread(target=_voice_worker, daemon=True, name="voice-worker").start()


class LocalizedStringVar(tk.StringVar):
    def __init__(self, language_getter, value=""):
        self._language_getter = language_getter
        self._original_value = value
        super().__init__(value=translated(value, language_getter()))

    def set(self, value):
        self._original_value = str(value)
        super().set(translated(self._original_value, self._language_getter()))

    def refresh_language(self):
        super().set(translated(self._original_value, self._language_getter()))


def speak(text):
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    voice_dir = os.path.join(base, "voice_prompts")
    fixed = {"外箱已满，封箱完成":"full.wav","发现不良品":"ng.wav","发现重复条码":"duplicate.wav","绑码失败":"binding_failed.wav"}
    filename = fixed.get(text)
    match = re.fullmatch(r"还差 (\d+) 个", text)
    if match: filename = "remaining_%s.wav" % match.group(1)
    match = re.fullmatch(r"不良品已替换，剩余不良 (\d+) 个", text)
    if match: filename = "ng_replaced_%s.wav" % match.group(1)
    wav = os.path.join(voice_dir, filename) if filename else ""
    if wav and os.path.isfile(wav):
        winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return
    try:
        while True:
            _voice_queue.get_nowait()
            _voice_queue.task_done()
    except queue.Empty:
        pass
    try:
        _voice_queue.put_nowait(text)
    except queue.Full:
        # Never delay scanning because an older announcement is still playing.
        pass


class CaseBinding2D:
    def __init__(self, root):
        self.root, self.store, self.mode = root, CaseBindingStore(), "product"
        root.title("外箱绑码 / CASE BINDING 2D")
        root.geometry("1280x780")
        root.state("zoomed")
        root.configure(bg="#07111f")
        self.ui_language = "zh"
        self.status = LocalizedStringVar(lambda:self.ui_language, value="等待 MES 下发 WO，然后扫描产品 SN")
        self.wo = LocalizedStringVar(lambda:self.ui_language, value="MES WO: --")
        self.wo_choice = tk.StringVar(value=self.store.active_work_order())
        self.scan = tk.StringVar()
        self.count = tk.StringVar(value="0")
        self.ng_count = LocalizedStringVar(lambda:self.ui_language, value="NG拦截 0")
        self.dup_count = LocalizedStringVar(lambda:self.ui_language, value="重复拦截 0")
        self.cached_ng = LocalizedStringVar(lambda:self.ui_language, value="MES NG缓存 0")
        self.capacity = tk.StringVar(value="48")
        self.print_template = tk.StringVar(value=self.store.selected_print_template())
        self.last_blocked_ng_sn = ""
        self.alarm_overlay = None
        self.alarm_active = False
        self.alarm_phase = False
        self.alarm_kind = ""
        self.alarm_message = ""
        self._build()
        self.language = TrilingualController(root, self.header, use_place=False, on_change=self._language_changed)
        self.refresh()
        self.scan_entry.focus_set()
        root.after(1000, self.tick)

    def _language_changed(self, language):
        self.ui_language = language
        self.root.title(translated("外箱绑码 / CASE BINDING 2D", language))
        for variable in (self.status, self.wo, self.ng_count, self.dup_count, self.cached_ng):
            variable.refresh_language()

    def speak_loaded_count(self, count):
        count = int(count)
        if self.ui_language == "vi":
            speak("Đã đóng %d sản phẩm" % count)
        elif self.ui_language == "en":
            speak("%d items loaded" % count)
        else:
            speak("已装 %d 个" % count)

    def speak_full_box(self):
        if self.ui_language == "vi":
            speak("Đã đủ 48 sản phẩm, hoàn tất đóng thùng")
        elif self.ui_language == "en":
            speak("Box full, 48 items, sealing complete")
        else:
            speak("外箱已满，48个，封箱完成")

    def _build(self):
        style = ttk.Style(); style.theme_use("clam")
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 11))
        top = tk.Frame(self.root, bg="#10243b", padx=18, pady=14); top.pack(fill="x"); self.header=top
        tk.Label(top, text="外箱绑码  CASE BINDING", bg="#10243b", fg="white", font=("Microsoft YaHei UI", 22, "bold")).pack(side="left")
        tk.Button(top,text="资源查看 / RESOURCES",command=self.open_resources,bg="#475569",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=14)
        tk.Label(top, textvariable=self.status, bg="#10243b", fg="#38bdf8", font=("Microsoft YaHei UI", 14, "bold")).pack(side="right")
        for var,color in ((self.ng_count,"#ef4444"),(self.dup_count,"#f59e0b"),(self.cached_ng,"#a78bfa")):
            tk.Label(top,textvariable=var,bg="#10243b",fg=color,font=("Microsoft YaHei UI",12,"bold"),padx=10).pack(side="right")
        scanbar = tk.Frame(self.root, bg="#07111f", padx=18, pady=14); scanbar.pack(fill="x")
        tk.Label(scanbar, text="工单 WO", bg="#07111f", fg="white", font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=(0, 5))
        self.wo_box=ttk.Combobox(scanbar,textvariable=self.wo_choice,values=self.store.work_order_codes(),state="readonly",width=20,font=("Consolas",13))
        self.wo_box.pack(side="left",padx=(0,10))
        self.wo_box.bind("<<ComboboxSelected>>",self._wo_selected)
        self.wo_bypass_btn=tk.Button(scanbar,text="MES WO 必须绑定",command=self.toggle_wo_bypass,width=15,bg="#334155",fg="white",font=("Microsoft YaHei UI",11,"bold"),state="disabled")
        self.wo_bypass_btn.pack(side="left",padx=(0,10))
        tk.Label(scanbar,text="容量",bg="#07111f",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=(0,4))
        ttk.Combobox(scanbar,textvariable=self.capacity,values=(48,),state="readonly",width=5,font=("Consolas",15)).pack(side="left",padx=(0,8))
        tk.Label(scanbar,text="打印模板",bg="#07111f",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=(0,4))
        self.template_box=ttk.Combobox(scanbar,textvariable=self.print_template,values=[p.name for p in self.store.available_print_templates()],state="readonly",width=21,font=("Segoe UI",10))
        self.template_box.pack(side="left",padx=(0,8))
        self.template_box.bind("<<ComboboxSelected>>",self._template_changed)
        tk.Button(scanbar,text="添加模板",command=self.add_print_template,bg="#0369a1",fg="white",font=("Microsoft YaHei UI",10,"bold")).pack(side="left",padx=(0,8))
        self.product_btn = tk.Button(scanbar, text="扫描产品 SN", command=lambda:self.set_mode("product"), width=16, bg="#0ea5e9", fg="white", font=("Microsoft YaHei UI", 13, "bold")); self.product_btn.pack(side="left", padx=8)
        self.scan_entry = tk.Entry(scanbar, textvariable=self.scan, font=("Consolas", 18), bg="#e2e8f0"); self.scan_entry.pack(side="left", fill="x", expand=True, padx=10); self.scan_entry.bind("<Return>", self.submit)
        self.notebook=ttk.Notebook(self.root);self.notebook.pack(fill="both",expand=True,padx=10,pady=(2,8));self.live_tab=tk.Frame(self.notebook,bg="#07111f");self.notebook.add(self.live_tab,text="实时监控 / LIVE")
        self.live_canvas=tk.Canvas(self.live_tab,bg="#07111f",highlightthickness=0)
        live_scroll=ttk.Scrollbar(self.live_tab,orient="vertical",command=self.live_canvas.yview)
        self.live_canvas.configure(yscrollcommand=live_scroll.set)
        live_scroll.pack(side="right",fill="y")
        self.live_canvas.pack(side="left",fill="both",expand=True)
        live_content=tk.Frame(self.live_canvas,bg="#07111f")
        live_window=self.live_canvas.create_window((0,0),window=live_content,anchor="nw")
        live_content.bind("<Configure>",lambda _e:self.live_canvas.configure(scrollregion=self.live_canvas.bbox("all")))
        self.live_canvas.bind("<Configure>",lambda e:self.live_canvas.itemconfigure(live_window,width=e.width))
        self.live_canvas.bind("<Enter>",lambda _e:self.live_canvas.bind_all("<MouseWheel>",self._scroll_live))
        self.live_canvas.bind("<Leave>",lambda _e:self.live_canvas.unbind_all("<MouseWheel>"))
        body=tk.Frame(live_content,bg="#07111f",padx=18);body.pack(fill="both",expand=True)
        left=tk.LabelFrame(body,text=" 当前外箱产品 / CURRENT CASE ",bg="#0f1e31",fg="white",font=("Microsoft YaHei UI",13,"bold"));left.pack(side="left",fill="both",expand=True,padx=(0,8))
        tk.Label(left,textvariable=self.count,bg="#0f1e31",fg="#38bdf8",font=("Segoe UI",38,"bold")).pack(anchor="ne",padx=16)
        self.slot_panel=tk.Frame(left,bg="#0f1e31");self.slot_panel.pack(fill="x",padx=12,pady=6);self.slot_labels=[]
        self.draft=ttk.Treeview(left,columns=("pos","sn","release"),show="headings");self.draft.heading("pos",text="#");self.draft.heading("sn",text="产品 SN");self.draft.heading("release",text="质量状态");self.draft.column("pos",width=60,anchor="center");self.draft.column("release",width=150,anchor="center");self.draft.pack(fill="both",expand=True,padx=12,pady=10)
        self.sn_menu=tk.Menu(self.root,tearoff=0)
        self.sn_menu.add_command(label="删除此 SN",command=self.remove_selected_sn)
        self.draft.bind("<Button-3>",self.show_sn_actions)
        self.draft.bind("<Double-1>",self.show_sn_actions)
        right=tk.LabelFrame(body,text=" 绑定历史 / BINDING RESULT ",bg="#0f1e31",fg="white",font=("Microsoft YaHei UI",13,"bold"));right.pack(side="left",fill="both",expand=True,padx=(8,0))
        self.history=ttk.Treeview(right,columns=("case","qty","time","sync"),show="headings");
        for key,title,width in (("case","外箱码",210),("qty","数量",60),("time","时间",150),("sync","MES",65)):self.history.heading(key,text=title);self.history.column(key,width=width,anchor="center")
        self.history.pack(fill="both",expand=True,padx=12,pady=10)
        guard_row=tk.Frame(live_content,bg="#07111f",padx=18);guard_row.pack(fill="x",pady=8)
        ng_box=tk.LabelFrame(guard_row,text=" NG BOX / 不良品箱 ",bg="#3f1018",fg="#fecaca",font=("Microsoft YaHei UI",11,"bold"),highlightbackground="#ef4444",highlightthickness=2);ng_box.pack(side="left",fill="both",expand=True,padx=(0,6))
        self.ng_box=ttk.Treeview(ng_box,columns=("sn","source","reason"),show="headings",height=4);self.ng_box.heading("sn",text="NG SN");self.ng_box.heading("source",text="来源工位");self.ng_box.heading("reason",text="原因");self.ng_box.column("source",width=140,anchor="center");self.ng_box.pack(fill="x",padx=8,pady=6)
        incidents=tk.LabelFrame(guard_row,text=" NG / DUP 检测记录 ",bg="#0f1e31",fg="white",font=("Microsoft YaHei UI",11,"bold"));incidents.pack(side="left",fill="both",expand=True,padx=(6,0))
        self.incidents=ttk.Treeview(incidents,columns=("type","code","time"),show="headings",height=4);self.incidents.heading("type",text="类型");self.incidents.heading("code",text="条码");self.incidents.heading("time",text="时间");self.incidents.column("type",width=180,anchor="center");self.incidents.column("time",width=180,anchor="center");self.incidents.pack(fill="x",padx=8,pady=6)
        footer=tk.Frame(live_content,bg="#10243b",padx=18,pady=10);footer.pack(fill="x")
        self.root._retest_host=footer
        self.ng_approver_choice=tk.StringVar(value="蒙营 — 工厂长")
        self.ng_approver_box=ttk.Combobox(
            footer,textvariable=self.ng_approver_choice,
            values=("蒙营 — 工厂长","黄文钢 — 线长"),
            state="readonly",width=18,font=("Microsoft YaHei UI",11),
        )
        self.ng_approver_box.pack(side="left",padx=(0,8));self.ng_approver_box.current(0)
        tk.Button(footer,text="删除所选 SN",command=self.remove_selected_sn,bg="#dc2626",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=(0,8))
        tk.Button(footer,text="线长/厂长特许 NG",command=self.approve_ng_exemption,bg="#be123c",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=(0,8))
        tk.Button(footer,text="尾数封箱",command=self.seal_partial,bg="#7c3aed",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=(0,8))
        tk.Button(footer,text="补打标签",command=self.open_reprint_tab,bg="#d97706",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=(0,8))
        tk.Button(footer,text="清空未绑定扫描",command=self.clear,bg="#f59e0b",font=("Microsoft YaHei UI",11)).pack(side="left")
        tk.Label(footer,text="重复 SN / NG / 已使用外箱码：阻止绑定；MES 离线：本地保存并自动补传",bg="#10243b",fg="#cbd5e1",font=("Microsoft YaHei UI",11)).pack(side="right")
        self.resource_trees={}
        reprint=tk.Frame(self.notebook,bg="#07111f");self.reprint_tab=reprint;self.notebook.add(reprint,text="补打标签 / REPRINT")
        reprint_bar=tk.Frame(reprint,bg="#07111f",padx=14,pady=12);reprint_bar.pack(fill="x")
        tk.Label(reprint_bar,text="产品SN / 外箱SN",bg="#07111f",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left")
        self.reprint_search=tk.StringVar();entry=tk.Entry(reprint_bar,textvariable=self.reprint_search,width=30,font=("Consolas",15));entry.pack(side="left",padx=8)
        entry.bind("<Return>",lambda _e:self.refresh_reprint())
        tk.Button(reprint_bar,text="查找",command=self.refresh_reprint,bg="#2563eb",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=4)
        tk.Button(reprint_bar,text="补打所选标签",command=self.reprint_selected,bg="#d97706",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=4)
        self.reprint_tree=ttk.Treeview(reprint,columns=("case","wo","qty","time"),show="headings",selectmode="extended")
        for key,title in (("case","外箱 SN"),("wo","工单 WO"),("qty","数量"),("time","绑定时间")):self.reprint_tree.heading(key,text=title)
        self.reprint_tree.pack(fill="both",expand=True,padx=14,pady=(0,14))
        for tab_name,source_name in (("外箱记录 / CASES","外箱绑定 / CASES"),("SN记录 / SN","产品关系 / PRODUCTS"),("绑定映射 / MAPPING","绑定映射 / MAPPING"),("NG记录 / NG","NG缓存 / NG CACHE"),("原始数据 / RAW DATA","NG-DUP事件 / GUARD"),("MES通信 / COMMS","MES Outbox"),("工位配置 / SETTINGS","工位配置 / SETTINGS"),("变更记录 / CHANGE LOG","变更记录 / CHANGE LOG")):
            page=tk.Frame(self.notebook,bg="#07111f");self.notebook.add(page,text=tab_name);self.resource_trees[source_name]=self._resource_tree(page)

    def _resource_tree(self,parent):
        tree=ttk.Treeview(parent,show="headings");sy=ttk.Scrollbar(parent,orient="vertical",command=tree.yview);sx=ttk.Scrollbar(parent,orient="horizontal",command=tree.xview);tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set);tree.grid(row=0,column=0,sticky="nsew",padx=(8,0),pady=(8,0));sy.grid(row=0,column=1,sticky="ns",pady=(8,0));sx.grid(row=1,column=0,sticky="ew",padx=(8,0));parent.grid_rowconfigure(0,weight=1);parent.grid_columnconfigure(0,weight=1);return tree

    def _scroll_live(self, event):
        self.live_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def set_mode(self, mode):
        self.mode="product";self.product_btn.configure(bg="#0ea5e9")
        self.status.set("连续扫描产品 SN；满箱后自动生成外箱二维码并绑定");self.scan_entry.focus_set()

    def _confirm_print_label(self, result, label_type="CARTON SERIES"):
        """Print automatically after a full carton is bound."""
        try:
            outcome=self.store._print_case_label(result,self.print_template.get())
            if outcome.get("method")=="failed":
                self.status.set("外箱已绑定，但标签打印失败，请检查打印机")
        except Exception:
            self.status.set("外箱已绑定，但标签打印失败，请检查打印机")

    def _template_changed(self, _event=None):
        try:
            self.store.set_print_template(self.print_template.get())
            self.status.set("打印模板已选择: "+self.print_template.get())
        except BindingError as exc:
            messagebox.showerror("模板错误",str(exc))

    def add_print_template(self):
        source=filedialog.askopenfilename(
            title="添加 BarTender 打印模板",
            filetypes=(("BarTender 模板","*.btw"),("所有文件","*.*")),
        )
        if not source:
            return
        try:
            name=self.store.import_print_template(source)
            self.template_box.configure(values=[p.name for p in self.store.available_print_templates()])
            self.print_template.set(name)
            self.status.set("打印模板已添加并选择: "+name)
        except Exception as exc:
            messagebox.showerror("添加模板失败",str(exc))

    def _wo_selected(self, _event=None):
        try:
            selected=self.store.select_work_order(self.wo_choice.get())
            self.wo.set("MES WO: "+selected+" [LOCKED]")
            self.status.set("工单已锁定: "+selected)
        except BindingError as exc:
            self.wo_choice.set(self.store.active_work_order())
            messagebox.showerror("工单锁定",str(exc))

    def toggle_wo_bypass(self):
        self.store.set_work_order_bypass(False)
        self.status.set("自动线正式模式：必须绑定 MES 工单")
        self.refresh()

    def submit(self, _event=None):
        code=self.scan.get().strip();self.scan.set("")
        try:
            if self.mode=="product":
                result=self.store.scan_product(code,self.capacity.get())
                # Auto-seal triggers when case is full → scan_product returns payload dict
                if isinstance(result,dict) and result.get("containerId"):
                    self.status.set("外箱已满，二维码已生成: "+result.get("cartonSn",code)+" / "+str(len(result.get("items",[])))+" 产品");self.speak_full_box();self.set_mode("product")
                    self._confirm_print_label(result)
                elif isinstance(result,dict) and result.get("replacedNg"):
                    snap=self.store.snapshot();remaining_ng=sum(int(row.get("is_ng",0)) for row in snap["draft"])
                    self.status.set("已替换 NG %s → %s；剩余 NG %d"%(result["replacedNg"],result["replacementSn"],remaining_ng));speak("不良品已替换，剩余不良 %d 个"%remaining_ng)
                else:
                    snap=self.store.snapshot();loaded_count=len(snap["draft"]);remaining=max(0,int(snap["activeCapacity"])-loaded_count)
                    self.status.set("产品已加入当前外箱: %s，当前第 %d 个，还差 %d 个"%(code,loaded_count,remaining));self.speak_loaded_count(loaded_count)
            self.refresh()
        except BindingError as exc:
            message = str(exc)
            if "NG" in message:
                self.last_blocked_ng_sn = code
            self.status.set(message)
            if "NG" in message:
                self.start_blocking_alarm("NG", message)
            elif "重复" in message or "已使用" in message:
                self.start_blocking_alarm("DUP", message)
            else:
                speak("绑码失败")
                messagebox.showerror("禁止操作", message)
            self.refresh()

    def start_blocking_alarm(self, kind, message):
        self.alarm_kind = kind
        self.alarm_message = message
        self.alarm_active = True
        self.scan_entry.configure(state="disabled")
        if self.alarm_overlay is None or not self.alarm_overlay.winfo_exists():
            self.alarm_overlay = tk.Frame(self.root, bg="#dc2626", bd=8, relief="ridge")
            self.alarm_title = tk.Label(
                self.alarm_overlay, text="", bg="#dc2626", fg="white",
                font=("Microsoft YaHei UI", 38, "bold"),
            )
            self.alarm_title.pack(pady=(90, 24))
            self.alarm_detail = tk.Label(
                self.alarm_overlay, text="", bg="#dc2626", fg="white",
                font=("Microsoft YaHei UI", 20, "bold"), wraplength=1000,
            )
            self.alarm_detail.pack(padx=40, pady=20)
            tk.Button(
                self.alarm_overlay, text="解除报警 / ACKNOWLEDGE / XÁC NHẬN",
                command=self.stop_blocking_alarm, bg="#ffffff", fg="#991b1b",
                font=("Microsoft YaHei UI", 22, "bold"), padx=30, pady=14,
            ).pack(pady=42)
        self.alarm_title.configure(text="NG 报警 / NG ALARM" if kind == "NG" else "重复编码报警 / DUPLICATE ALARM")
        self.alarm_detail.configure(text=message)
        self.alarm_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.alarm_overlay.lift()
        self.language.set(self.ui_language)
        self._alarm_pulse()
        self._alarm_voice()

    def _alarm_pulse(self):
        if not self.alarm_active or not self.alarm_overlay:
            return
        self.alarm_phase = not self.alarm_phase
        color = "#ff0000" if self.alarm_phase else "#7f1d1d"
        self.alarm_overlay.configure(bg=color)
        self.alarm_title.configure(bg=color)
        self.alarm_detail.configure(bg=color)
        self.root.after(350, self._alarm_pulse)

    def _alarm_voice(self):
        if not self.alarm_active:
            return
        speak("发现不良品" if self.alarm_kind == "NG" else "发现重复条码")
        self.root.bell()
        self.root.after(2500, self._alarm_voice)

    def stop_blocking_alarm(self):
        self.alarm_active = False
        if self.alarm_overlay:
            self.alarm_overlay.place_forget()
        self.scan_entry.configure(state="normal")
        self.scan_entry.focus_set()
        self.status.set("报警已解除，请处理拦截品后继续扫描")

    def approve_ng_exemption(self):
        sn = self.last_blocked_ng_sn.strip()
        if not sn:
            messagebox.showwarning("没有待特批 NG", "请先扫描并触发一个 NG 拦截")
            return
        people = {
            "蒙营 — 工厂长": ("蒙营", "FACTORY_DIRECTOR"),
            "黄文钢 — 线长": ("黄文钢", "LINE_LEADER"),
        }
        leader_id, approver_role = people.get(
            self.ng_approver_choice.get(), ("蒙营", "FACTORY_DIRECTOR")
        )
        auth = self.store.active_line_leader_auth()
        if (not auth or str(auth.get("leaderId") or "") != leader_id
                or str(auth.get("approverRole") or "") != approver_role):
            try:
                auth = self.store.authenticate_line_leader(leader_id, approver_role)
            except BindingError as exc:
                messagebox.showerror("认证失败", str(exc))
                return
        leader_id = str(auth.get("leaderId") or "")
        role_name = "工厂长" if auth.get("approverRole") == "FACTORY_DIRECTOR" else "线长"
        remaining_seconds = max(0, int(auth.get("expiresAt") or 0) - int(datetime.datetime.now().timestamp()))
        reason = self.select_exemption_reason()
        if reason is None:
            return
        if not messagebox.askyesno(
            "确认特批放行",
            "仅允许此 SN 在当前外箱使用一次。\n\nSN: %s\n审批角色: %s\n工号: %s\n授权剩余: %d小时%d分钟\n原因: %s\n\n确认放行？" %
            (sn, role_name, leader_id.strip().upper(), remaining_seconds // 3600,
             (remaining_seconds % 3600) // 60, reason.strip()),
        ):
            return
        try:
            self.store.approve_ng_exemption(sn, leader_id, reason)
            self.status.set("线长特批已登记，请重新扫描: %s" % sn)
            self.last_blocked_ng_sn = ""
            self.refresh()
        except BindingError as exc:
            messagebox.showerror("特批失败", str(exc))
        finally:
            self.scan_entry.focus_set()

    def select_exemption_reason(self):
        """Select a controlled exemption reason without free-text entry."""
        dialog = tk.Toplevel(self.root)
        dialog.title("选择特许类型")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg="#0f1e31", padx=24, pady=20)
        tk.Label(
            dialog, text="特许类型 / EXEMPTION TYPE / LOẠI ĐẶC CÁCH",
            bg="#0f1e31", fg="white", font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(anchor="w", pady=(0, 10))
        choice = tk.StringVar(value="临时放行")
        combo = ttk.Combobox(
            dialog, textvariable=choice,
            values=("临时放行", "测试", "其他"), state="readonly",
            width=28, font=("Microsoft YaHei UI", 13),
        )
        combo.pack(fill="x", pady=(0, 16)); combo.current(0)
        result = {"value": None}
        buttons = tk.Frame(dialog, bg="#0f1e31"); buttons.pack(fill="x")
        def confirm():
            result["value"] = choice.get()
            dialog.destroy()
        tk.Button(
            buttons, text="确认 / CONFIRM / XÁC NHẬN", command=confirm,
            bg="#16a34a", fg="white", font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons, text="取消 / CANCEL / HỦY", command=dialog.destroy,
            bg="#475569", fg="white", font=("Microsoft YaHei UI", 12),
        ).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry("+%d+%d" % (max(0, x), max(0, y)))
        combo.focus_set()
        self.root.wait_window(dialog)
        return result["value"]

    def select_ng_approver(self, sn):
        """Select the approved person from a controlled factory list."""
        people = {
            "蒙营 — 工厂长": ("蒙营", "FACTORY_DIRECTOR"),
            "黄文钢 — 线长": ("黄文钢", "LINE_LEADER"),
        }
        dialog = tk.Toplevel(self.root)
        dialog.title("选择特许审批人")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg="#0f1e31", padx=24, pady=20)
        choice = tk.StringVar(value=next(iter(people)))
        tk.Label(
            dialog, text="超声波 NG 特许审批 / 8小时授权",
            bg="#0f1e31", fg="white", font=("Microsoft YaHei UI", 15, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        tk.Label(
            dialog, text="SN: %s" % sn, bg="#0f1e31", fg="#fca5a5",
            font=("Consolas", 13, "bold"),
        ).pack(anchor="w", pady=(0, 12))
        combo = ttk.Combobox(
            dialog, textvariable=choice, values=list(people), state="readonly",
            width=30, font=("Microsoft YaHei UI", 13),
        )
        combo.pack(fill="x", pady=(0, 16)); combo.current(0)
        result = {"value": None}
        buttons = tk.Frame(dialog, bg="#0f1e31"); buttons.pack(fill="x")
        def confirm():
            result["value"] = people.get(choice.get())
            dialog.destroy()
        tk.Button(
            buttons, text="确认 / CONFIRM / XÁC NHẬN", command=confirm,
            bg="#16a34a", fg="white", font=("Microsoft YaHei UI", 11, "bold"),
            padx=18, pady=7,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons, text="取消 / CANCEL / HỦY", command=dialog.destroy,
            bg="#475569", fg="white", font=("Microsoft YaHei UI", 11),
            padx=18, pady=7,
        ).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry("+%d+%d" % (max(0, x), max(0, y)))
        combo.focus_set()
        self.root.wait_window(dialog)
        return result["value"]

    def seal(self):
        try:
            result=self.store.seal_active_case()
            self.status.set("外箱已满，封箱完成: "+result.get("cartonSn","?")+" / "+str(len(result.get("items",[])))+" 产品");self.speak_full_box();self.set_mode("case");self.refresh()
            self._confirm_print_label(result)
        except BindingError as exc:
            self.status.set(str(exc));speak("绑码失败");messagebox.showerror("禁止操作",str(exc))

    def seal_partial(self):
        snap=self.store.snapshot();count=len(snap["draft"]);target=int(snap["activeCapacity"] or self.capacity.get())
        if count<1:
            messagebox.showwarning("没有产品","当前外箱没有已扫描产品")
            return
        if not messagebox.askyesno("确认尾数封箱","当前 %d / %d 件。\n确认作为工单尾数封箱？"%(count,target)):
            return
        try:
            result=self.store.seal_active_case(True,"WORK_ORDER_TAIL")
            self.status.set("尾数外箱已封箱：%s / %d 件"%(result.get("cartonSn",""),count))
            speak("尾数封箱完成");self.refresh();self._confirm_print_label(result)
        except BindingError as exc:
            messagebox.showerror("尾数封箱失败",str(exc))

    def clear(self):
        if messagebox.askyesno("确认","清空当前尚未绑定的产品扫描？"):self.store.clear_draft();self.refresh()

    def remove_selected_sn(self):
        selected=self.draft.selection()
        if not selected:
            messagebox.showwarning("请选择 SN","请先在当前外箱产品列表中选择一个 SN")
            return
        values=self.draft.item(selected[0],"values")
        sn=str(values[1] if len(values)>1 else "").strip()
        if not messagebox.askyesno("确认删除","从当前未封箱外箱中删除 SN：\n%s？"%sn):
            return
        reason=simpledialog.askstring("删除原因","请输入删除 %s 的原因："%sn,parent=self.root)
        if reason is None:
            return
        reason=reason.strip()
        if not reason:
            messagebox.showwarning("必须填写原因","删除 SN 必须填写原因")
            return
        try:
            result=self.store.remove_draft_product(sn,reason,"OPERATOR")
            self.status.set("已删除 SN %s；当前 %d/48，还需补 %d 件"%(result["sn"],result["afterCount"],result["remainingToFill"]))
            self.speak_loaded_count(result["afterCount"])
            self.refresh()
        except BindingError as exc:
            messagebox.showerror("删除失败",str(exc))

    def show_sn_actions(self, event):
        row_id=self.draft.identify_row(event.y)
        if not row_id:
            return
        self.draft.selection_set(row_id)
        self.draft.focus(row_id)
        self.sn_menu.tk_popup(event.x_root,event.y_root)

    def refresh_reprint(self):
        term=self.reprint_search.get().strip().upper()
        self.reprint_tree.delete(*self.reprint_tree.get_children())
        for row in self.store.snapshot(500)["history"]:
            products=[str(sn).upper() for sn in row.get("products",[])]
            if term and term not in row["carton_sn"].upper() and not any(term in sn for sn in products):
                continue
            bound=datetime.datetime.fromtimestamp(row["bound_at"]).strftime("%Y-%m-%d %H:%M:%S")
            self.reprint_tree.insert("","end",values=(row["carton_sn"],row["work_order_code"],row["item_count"],bound))

    def open_reprint_tab(self):
        self.refresh_reprint()
        self.notebook.select(self.reprint_tab)

    def reprint_selected(self):
        selected=self.reprint_tree.selection()
        if not selected:
            messagebox.showwarning("请选择外箱","请先选择需要补打的外箱标签")
            return
        if not messagebox.askyesno("确认补打","确认补打所选 %d 个外箱标签？"%len(selected)):
            return
        try:
            for item in selected:
                self.store.reprint_case_label(self.reprint_tree.item(item,"values")[0],"OPERATOR")
            self.status.set("已补打 %d 个外箱标签"%len(selected))
            speak("外箱标签补打完成")
        except BindingError as exc:
            messagebox.showerror("补打失败",str(exc))

    def select_draft_position(self, position):
        rows=self.draft.get_children()
        if position < 0 or position >= len(rows):
            return
        row_id=rows[position]
        self.draft.selection_set(row_id)
        self.draft.focus(row_id)
        self.draft.see(row_id)

    def refresh(self):
        snap=self.store.snapshot()
        self.draft.delete(*self.draft.get_children());self.history.delete(*self.history.get_children())
        for i,row in enumerate(snap["draft"],1):
            quality = "特殊放行" if row.get("special_release") else ("NG" if row.get("is_ng") else "PASS")
            tags = ("special_release",) if row.get("special_release") else ()
            self.draft.insert("","end",values=(i,row["sn"],quality),tags=tags)
        self.draft.tag_configure("special_release",background="#7f1d1d",foreground="#ffffff")
        self.count.set((snap["activeCase"] or "NO CASE")+" · "+str(len(snap["draft"]))+" / "+str(snap["activeCapacity"] or self.capacity.get()))
        self.render_slots(int(snap["activeCapacity"] or self.capacity.get()),snap["draft"])
        import datetime
        for row in snap["history"]:self.history.insert("","end",values=(row["carton_sn"]+" / "+row["work_order_code"],row["item_count"],datetime.datetime.fromtimestamp(row["bound_at"]).strftime("%Y-%m-%d %H:%M:%S"),"已同步" if row["mes_synced"] else "待同步"))
        guard=self.store.guard_status();self.ng_count.set("NG拦截 %d"%guard["ngBlocked"]);self.dup_count.set("重复拦截 %d"%guard["duplicateBlocked"]);self.cached_ng.set("MES NG缓存 %d"%guard["cachedNg"]);self.incidents.delete(*self.incidents.get_children())
        bypass=self.store.work_order_bypass()
        self.wo_bypass_btn.configure(text="MES WO 必须绑定",bg="#334155",state="disabled")
        for row in guard["incidents"]:self.incidents.insert("","end",values=(row["event_type"],row["code"],datetime.datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d %H:%M:%S")))
        self.ng_box.delete(*self.ng_box.get_children())
        for row in guard["ngItems"]:self.ng_box.insert("","end",values=(row["sn"],row["source_station"],row["reason"]))
        self.refresh_resource_tabs()

    def refresh_resource_tabs(self):
        for name,rows in self.store.resource_tables(300).items():
            tree=self.resource_trees.get(name)
            if tree is None:continue
            columns=list(rows[0].keys()) if rows else list(tree["columns"] or ("状态",));tree.configure(columns=columns)
            for column in columns:tree.heading(column,text=column);tree.column(column,width=180 if column not in ("payload","detail") else 520,anchor="w")
            tree.delete(*tree.get_children())
            for row in rows:tree.insert("","end",values=[str(row.get(column,""))[:2000] for column in columns])

    def render_slots(self,capacity,rows):
        if len(self.slot_labels)!=capacity:
            for widget in self.slot_panel.winfo_children():widget.destroy()
            self.slot_labels=[]
            columns=12
            for i in range(capacity):
                label=tk.Label(self.slot_panel,text=str(i+1),width=8,height=2,bg="#1e293b",fg="#94a3b8",font=("Consolas",10,"bold"),relief="ridge",bd=2)
                label.grid(row=i//columns,column=i%columns,padx=3,pady=3,sticky="nsew");self.slot_labels.append(label)
            for col in range(columns):self.slot_panel.grid_columnconfigure(col,weight=1)
        for i,label in enumerate(self.slot_labels):
            if i<len(rows):
                is_ng=bool(rows[i].get("is_ng"))
                is_released=bool(rows[i].get("special_release"))
                quality_text="\n特许 NG" if is_released else ("\nNG" if is_ng else "")
                label.configure(text=str(i+1)+"\n"+rows[i]["sn"][-8:]+quality_text,bg="#b91c1c" if is_ng else "#166534",fg="white")
                label.bind("<Button-1>",lambda _e,pos=i:self.select_draft_position(pos))
            else:
                label.configure(text=str(i+1),bg="#1e293b",fg="#64748b")
                label.unbind("<Button-1>")

    def open_resources(self):
        self.refresh_resource_tabs();self.notebook.select(1)

    def tick(self):
        def network(): self.store.refresh_mes_work_order();self.store.sync_once()
        threading.Thread(target=network,daemon=True).start()
        codes=self.store.work_order_codes();self.wo_box.configure(values=codes)
        active=self.store.active_work_order();self.wo_choice.set(active)
        self.wo.set("MES WO: "+(active or "--")+(" [LOCKED]" if self.store.work_order_locked() else ""))
        self.refresh();self.root.after(3000,self.tick)


if __name__ == "__main__":
    threading.Thread(target=outerbox_heartbeat_worker, daemon=True, name="outerbox-heartbeat").start()
    root=tk.Tk()
    install_station_tabs(root)
    CaseBinding2D(root)
    install_station_retest_panel(
        root, STATION_CODE, MES_BASE, test_station=False, announcer=speak
    )
    from station_repair_workflow import install_repair_workflow
    install_repair_workflow(root, STATION_CODE, MES_BASE, "外箱绑码")
    root.mainloop()
