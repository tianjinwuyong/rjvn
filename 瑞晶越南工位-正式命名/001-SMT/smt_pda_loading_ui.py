# -*- coding: utf-8 -*-
"""Tri-lingual SMT PDA material-loading UI."""
import json
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

LANG = {
    "zh": {
        "pcb": "PCB SN（SPI）", "bypass": "绕过 PCB SN 绑定",
        "bypass_reason": "绕过原因（必填）",
        "bypass_authorizer": "线长工号（必填）",
        "bypass_confirm_title": "确认绕过 PCB SN",
        "bypass_confirm": "确认不绑定 SPI PCB SN 并继续？\n\n原因：{reason}\n授权人：{leader}\n\nMES 将永久记录本次操作。",
        "title": "PDA 扫码上料", "wo": "工单", "machine": "机台", "operator": "操作员工号",
        "start": "开始上料", "scan": "扫码输入", "confirm": "确认绑定", "leader": "线长工号",
        "release": "线长确认放行", "slots": "已绑定槽位", "step": "当前步骤", "roll": "换料卷",
        "steps": {"MACHINE":"请扫机位码（两个机位均以扫码为准）", "SLOT":"请扫槽号", "FEEDER":"请扫飞达号", "REEL":"请扫物料盘码", "OPERATOR":"请扫操作员工号", "CONFIRM":"请核对并确认绑定", "RELEASED":"工单已放行"},
    },
    "en": {
        "title": "PDA Material Loading", "wo": "Work order", "machine": "Machine", "operator": "Operator badge",
        "start": "Start loading", "scan": "Scanner input", "confirm": "Confirm binding", "leader": "Line-leader badge",
        "release": "Release line", "slots": "Bound slots", "step": "Current step", "roll": "Change reel",
        "pcb": "PCB SN (SPI)", "bypass": "Bypass PCB SN binding",
        "bypass_reason": "Reason (required)",
        "bypass_authorizer": "Line-leader badge (required)",
        "bypass_confirm_title": "Confirm PCB SN bypass",
        "bypass_confirm": "Continue without binding a SPI PCB SN?\n\nReason: {reason}\nAuthorized by: {leader}\n\nThis action is permanently recorded in MES.",
        "steps": {"MACHINE":"Scan machine position (both positions are scan identified)", "SLOT":"Scan slot", "FEEDER":"Scan feeder", "REEL":"Scan reel label", "OPERATOR":"Scan operator badge", "CONFIRM":"Verify and confirm binding", "RELEASED":"Work order released"},
    },
    "vi": {
        "pcb": "PCB SN (SPI)", "bypass": "Bỏ qua liên kết PCB SN",
        "bypass_reason": "Lý do (bắt buộc)",
        "bypass_authorizer": "Mã trưởng chuyền (bắt buộc)",
        "bypass_confirm_title": "Xác nhận bỏ qua PCB SN",
        "bypass_confirm": "Tiếp tục mà không liên kết PCB SN từ SPI?\n\nLý do: {reason}\nNgười duyệt: {leader}\n\nThao tác này sẽ được lưu vĩnh viễn trong MES.",
        "title": "PDA cấp liệu", "wo": "Lệnh sản xuất", "machine": "Máy", "operator": "Mã nhân viên",
        "start": "Bắt đầu cấp liệu", "scan": "Dữ liệu quét", "confirm": "Xác nhận liên kết", "leader": "Mã trưởng chuyền",
        "release": "Cho phép chạy chuyền", "slots": "Khe đã liên kết", "step": "Bước hiện tại", "roll": "Đổi cuộn",
        "steps": {"MACHINE":"Quét vị trí máy (cả hai vị trí đều xác định bằng quét)", "SLOT":"Quét vị trí", "FEEDER":"Quét feeder", "REEL":"Quét cuộn vật liệu", "OPERATOR":"Quét mã nhân viên", "CONFIRM":"Kiểm tra và xác nhận", "RELEASED":"Đã cho phép sản xuất"},
    },
}


class PdaLoadingWindow:
    def __init__(self, agent):
        self.agent = agent
        self.lang = "zh"
        self.root = tk.Tk()
        self.root.geometry("1120x720")
        self.root.minsize(940, 620)
        self.root.configure(bg="#eaf0f5")
        self.vars = {k: tk.StringVar() for k in ("wo", "machine", "operator", "pcb", "scan", "leader")}
        self._build()
        self.set_language("zh")
        self.refresh()

    def _build(self):
        top = tk.Frame(self.root, bg="#12324a", height=70)
        top.pack(fill="x")
        self.heading = tk.Label(top, bg="#12324a", fg="white", font=("Microsoft YaHei UI", 18, "bold"))
        self.heading.pack(side="left", padx=22, pady=18)
        for code, label in (("vi","VI"),("en","EN"),("zh","中文")):
            tk.Button(top, text=label, command=lambda c=code:self.set_language(c),
                      bg="#1d526f", fg="white", relief="flat", width=7).pack(side="right", padx=3, pady=19)
        content = tk.Frame(self.root, bg="#eaf0f5")
        content.pack(fill="both", expand=True, padx=20, pady=18)
        left = tk.Frame(content, bg="white", highlightbackground="#d4dee7", highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0,10))
        right = tk.Frame(content, bg="white", width=390, highlightbackground="#d4dee7", highlightthickness=1)
        right.pack(side="right", fill="both", padx=(10,0))
        form = tk.Frame(left, bg="white")
        form.pack(fill="x", padx=20, pady=18)
        self.field_labels = {}
        for row, key in enumerate(("wo","machine","operator","pcb")):
            self.field_labels[key] = tk.Label(form, bg="white", fg="#405466", anchor="w")
            self.field_labels[key].grid(row=row, column=0, sticky="w", pady=6)
            entry = ttk.Entry(form, textvariable=self.vars[key], width=34)
            if key == "machine":
                entry.configure(state="readonly")
            entry.grid(row=row, column=1, sticky="ew", padx=10, pady=6)
        form.columnconfigure(1, weight=1)
        self.start_btn = tk.Button(form, command=self.start, bg="#087f5b", fg="white",
                                   relief="flat", font=("Microsoft YaHei UI", 11, "bold"))
        self.start_btn.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(8,0), pady=6)
        self.bypass_btn = tk.Button(form, command=self.start_bypass, bg="#b42318", fg="white",
                                    relief="flat", font=("Microsoft YaHei UI", 10, "bold"))
        self.bypass_btn.grid(row=2, column=2, rowspan=2, sticky="nsew", padx=(8,0), pady=6)
        self.step_caption = tk.Label(left, bg="white", fg="#617386")
        self.step_caption.pack(anchor="w", padx=20, pady=(10,2))
        self.step_value = tk.Label(left, bg="#102b3c", fg="#8cf1d2", font=("Microsoft YaHei UI", 18, "bold"),
                                   anchor="w", padx=18, pady=16)
        self.step_value.pack(fill="x", padx=20)
        scan_row = tk.Frame(left, bg="white")
        scan_row.pack(fill="x", padx=20, pady=16)
        self.scan_label = tk.Label(scan_row, bg="white", fg="#405466")
        self.scan_label.pack(anchor="w")
        self.scan_entry = ttk.Entry(scan_row, textvariable=self.vars["scan"], font=("Consolas", 15))
        self.scan_entry.pack(fill="x", pady=(5,0), ipady=8)
        self.scan_entry.bind("<Return>", lambda _e:self.scan())
        self.draft = tk.Text(left, height=8, bg="#f5f8fa", fg="#18384b", relief="flat", font=("Consolas", 11))
        self.draft.pack(fill="both", expand=True, padx=20, pady=(0,12))
        self.confirm_btn = tk.Button(left, command=self.confirm, bg="#1971c2", fg="white",
                                     relief="flat", font=("Microsoft YaHei UI", 11, "bold"))
        self.confirm_btn.pack(fill="x", padx=20, pady=(0,18), ipady=8)
        self.slots_label = tk.Label(right, bg="white", fg="#243b4a", font=("Microsoft YaHei UI", 12, "bold"))
        self.slots_label.pack(anchor="w", padx=16, pady=(16,8))
        self.table = ttk.Treeview(right, columns=("slot","feeder","material","lot"), show="headings", height=16)
        for key, width in (("slot",65),("feeder",85),("material",105),("lot",105)):
            self.table.heading(key, text=key.upper()); self.table.column(key, width=width, anchor="center")
        self.table.pack(fill="both", expand=True, padx=16)
        self.roll_btn = tk.Button(right, command=self.change_roll, bg="#6f42c1", fg="white",
                                  relief="flat", font=("Microsoft YaHei UI", 10, "bold"))
        self.roll_btn.pack(fill="x", padx=16, pady=(10,0), ipady=5)
        release = tk.Frame(right, bg="white")
        release.pack(fill="x", padx=16, pady=16)
        self.leader_label = tk.Label(release, bg="white", fg="#405466")
        self.leader_label.pack(anchor="w")
        ttk.Entry(release, textvariable=self.vars["leader"]).pack(fill="x", pady=5, ipady=5)
        self.release_btn = tk.Button(release, command=self.release, bg="#b45309", fg="white",
                                     relief="flat", font=("Microsoft YaHei UI", 11, "bold"))
        self.release_btn.pack(fill="x", ipady=7)
        self.status = tk.Label(self.root, bg="#18384b", fg="white", anchor="w", padx=18, pady=7)
        self.status.pack(fill="x")

    def text(self): return LANG[self.lang]

    def set_language(self, code):
        self.lang = code; t = self.text()
        self.root.title(t["title"]); self.heading.config(text=f"{t['title']}  /  SMT L001")
        for key in ("wo","machine","operator","pcb"):
            self.field_labels[key].config(text=t.get(key, "PCB SN (SPI)" if key == "pcb" else key))
        self.start_btn.config(text=t["start"]); self.scan_label.config(text=t["scan"])
        self.bypass_btn.config(text=t.get("bypass", "Bypass PCB SN binding"))
        self.confirm_btn.config(text=t["confirm"]); self.leader_label.config(text=t["leader"])
        self.release_btn.config(text=t["release"]); self.slots_label.config(text=t["slots"])
        self.roll_btn.config(text=t["roll"])
        self.step_caption.config(text=t["step"]); self.refresh()

    def start(self):
        try:
            self.agent.start_loading(
                self.vars["wo"].get(), self.vars["operator"].get(), self.vars["pcb"].get()
            )
            self.status.config(text="MES: OK", bg="#087f5b"); self.refresh()
        except Exception as exc: self.error(exc)

    def start_bypass(self):
        try:
            t = self.text()
            reason = simpledialog.askstring(
                t["bypass_confirm_title"], t["bypass_reason"], parent=self.root
            )
            if not reason or not reason.strip():
                return
            leader = simpledialog.askstring(
                t["bypass_confirm_title"], t["bypass_authorizer"], parent=self.root
            )
            if not leader or not leader.strip():
                return
            reason = reason.strip()
            leader = leader.strip().upper()
            if not messagebox.askyesno(
                t["bypass_confirm_title"],
                t["bypass_confirm"].format(reason=reason, leader=leader),
                parent=self.root,
            ):
                return
            self.agent.start_loading(
                self.vars["wo"].get(), self.vars["operator"].get(), "",
                bypass_pcb_sn_binding=True, bypass_reason=reason,
                bypass_authorized_by=leader,
            )
            self.status.config(
                text=f"PCB SN BYPASS AUTHORIZED: {leader.upper()}", bg="#b45309"
            )
            self.refresh()
        except Exception as exc:
            self.error(exc)

    def scan(self):
        try:
            self.agent.loading_scan(self.vars["scan"].get()); self.vars["scan"].set("")
            self.status.config(text="SCAN: OK", bg="#087f5b"); self.refresh()
        except Exception as exc: self.error(exc)

    def confirm(self):
        try:
            self.agent.confirm_loading_binding(); self.status.config(text="BINDING: OK", bg="#087f5b"); self.refresh()
        except Exception as exc: self.error(exc)

    def release(self):
        try:
            self.agent.release_loading(self.vars["leader"].get()); self.status.config(text="RELEASED", bg="#087f5b"); self.refresh()
        except Exception as exc: self.error(exc)

    def change_roll(self):
        try:
            selected = self.table.selection()
            if not selected:
                raise ValueError("Select a bound slot first.")
            slot = self.table.item(selected[0], "values")[0]
            reel = simpledialog.askstring("New reel", "MATERIAL_CODE,LOT_NO", parent=self.root)
            remaining = simpledialog.askfloat("Remaining", "Old remaining quantity", parent=self.root, minvalue=0)
            operator = self.vars["operator"].get()
            if not reel or remaining is None or not operator:
                return
            self.agent.change_loading_roll(slot, reel, operator, remaining)
            self.status.config(text="ROLL CHANGE: OK", bg="#087f5b"); self.refresh()
        except Exception as exc: self.error(exc)

    def error(self, exc):
        self.status.config(text=f"ALARM: {exc}", bg="#b42318")
        self.root.bell()

    def refresh(self):
        state = self.agent.loading_state(); step = state.get("step","SLOT")
        self.step_value.config(text=self.text()["steps"].get(step, step))
        self.draft.config(state="normal"); self.draft.delete("1.0","end")
        self.draft.insert("end", json.dumps(state.get("draft",{}), ensure_ascii=False, indent=2))
        self.draft.config(state="disabled")
        for item in self.table.get_children(): self.table.delete(item)
        for row in state.get("bindings",[]):
            self.table.insert("", "end", values=(row.get("slot_no"),row.get("feeder_code"),row.get("material_code"),row.get("lot_no")))
        session = state.get("session") or {}
        if session:
            self.vars["wo"].set(session.get("work_order_code","")); self.vars["machine"].set(session.get("machine_code",""))
        self.scan_entry.focus_set()

    def run(self): self.root.mainloop()


def run_ui(agent):
    PdaLoadingWindow(agent).run()
