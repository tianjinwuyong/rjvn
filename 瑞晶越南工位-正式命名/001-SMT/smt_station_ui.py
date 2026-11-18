# -*- coding: utf-8 -*-
"""Small tri-lingual operator UI backed by the canonical SMT runtime."""
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk

TEXT = {
    "zh": {"scan": "扫码检查", "status": "运行状态", "source": "数据源", "sync": "待同步",
           "raw": "原始记录", "checks": "扫码检查", "submit": "检查", "pending": "待配置",
           "online": "MES在线", "offline": "MES离线/排队", "title": "SMT 工位 Agent"},
    "en": {"scan": "Scan check", "status": "Status", "source": "Data source", "sync": "Pending sync",
           "raw": "Raw records", "checks": "Scan checks", "submit": "Check", "pending": "Pending config",
           "online": "MES online", "offline": "MES offline / queued", "title": "SMT Station Agent"},
    "vi": {"scan": "Kiểm tra quét", "status": "Trạng thái", "source": "Nguồn dữ liệu", "sync": "Chờ đồng bộ",
           "raw": "Dữ liệu gốc", "checks": "Lần quét", "submit": "Kiểm tra", "pending": "Chờ cấu hình",
           "online": "MES trực tuyến", "offline": "MES ngoại tuyến / xếp hàng", "title": "Agent trạm SMT"},
}


class SmtStationWindow:
    def __init__(self, agent):
        self.agent = agent
        self.lang = "zh"
        self.events = queue.Queue()
        self.root = tk.Tk()
        self.root.geometry("980x680")
        self.root.minsize(820, 600)
        self.instance_lock = None
        self.root.configure(bg="#eef3f8")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._build()
        self.change_language("zh")
        threading.Thread(target=self._worker, daemon=True).start()
        self.refresh()

    def _build(self):
        top = tk.Frame(self.root, bg="#12324a", height=76)
        top.pack(fill="x")
        self.heading = tk.Label(top, fg="white", bg="#12324a", font=("Microsoft YaHei UI", 17, "bold"))
        self.heading.pack(side="left", padx=22, pady=18)
        for lang, label in (("zh", "中文"), ("en", "EN"), ("vi", "VI")):
            tk.Button(top, text=label, command=lambda x=lang: self.change_language(x),
                      bg="#1d526f", fg="white", relief="flat", width=7).pack(side="right", padx=3, pady=20)
        body = tk.Frame(self.root, bg="#eef3f8")
        body.pack(fill="both", expand=True, padx=22, pady=18)
        self.cards = tk.Frame(body, bg="#eef3f8")
        self.cards.pack(fill="x")
        self.values = {}
        self.labels = {}
        for key in ("status", "source", "sync", "raw", "checks"):
            card = tk.Frame(self.cards, bg="white", highlightbackground="#d9e2ea", highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=4)
            self.labels[key] = tk.Label(card, bg="white", fg="#627386", font=("Microsoft YaHei UI", 9))
            self.labels[key].pack(pady=(12, 3))
            self.values[key] = tk.Label(card, bg="white", fg="#16394f", font=("Microsoft YaHei UI", 14, "bold"))
            self.values[key].pack(pady=(0, 13))
        self.visual = tk.Canvas(body, height=120, bg="#102b3c", highlightthickness=0)
        self.visual.pack(fill="x", pady=(14, 0))
        self.visual.bind("<Configure>", lambda _event: self.draw_station_visual())
        scan_box = tk.LabelFrame(body, bg="white", padx=15, pady=15)
        scan_box.pack(fill="x", pady=18)
        self.scan_box = scan_box
        self.scan_value = tk.StringVar()
        self.scan_entry = ttk.Entry(scan_box, textvariable=self.scan_value, font=("Consolas", 15))
        self.scan_entry.pack(side="left", fill="x", expand=True, ipady=7)
        self.scan_entry.bind("<Return>", lambda _e: self.submit_scan())
        self.scan_button = tk.Button(scan_box, command=self.submit_scan, bg="#1687a7", fg="white",
                                     relief="flat", font=("Microsoft YaHei UI", 11, "bold"), width=12)
        self.scan_button.pack(side="left", padx=(12, 0), ipady=6)
        self.log = tk.Text(body, height=9, bg="#0e2535", fg="#bfe9ff", insertbackground="white",
                           font=("Consolas", 10), relief="flat", state="disabled")
        self.log.pack(fill="both", expand=True)
        actions = tk.Frame(body, bg="#eef3f8")
        actions.pack(fill="x", pady=(12, 0))
        for event_type, label in (
            ("UNIT_ARRIVED", "到达 / Arrived"),
            ("WORK_STARTED", "开始 / Start"),
            ("WORK_COMPLETED", "完成 / Complete"),
            ("UNIT_DEPARTED", "离站 / Depart"),
        ):
            tk.Button(
                actions, text=label, command=lambda value=event_type: self.submit_activity(value),
                bg="#235a75", fg="white", relief="flat", padx=8,
            ).pack(side="left", padx=3)
        tk.Button(actions, text="职责 / Responsibilities", command=self.show_responsibilities,
                  bg="#5a3f82", fg="white", relief="flat", padx=8).pack(side="right", padx=3)
        tk.Button(actions, text="本地数据 / Local data", command=self.show_resources,
                  bg="#5a3f82", fg="white", relief="flat", padx=8).pack(side="right", padx=3)
        tk.Button(actions, text="确认送维修 / Send to repair", command=self.send_to_repair,
                  bg="#b45309", fg="white", relief="flat", padx=8).pack(side="right", padx=3)
        fault = tk.Frame(body, bg="#eef3f8")
        fault.pack(fill="x", pady=(8, 0))
        self.fault_code = ttk.Entry(fault, width=18)
        self.fault_code.insert(0, "FAULT_CODE")
        self.fault_code.pack(side="left", padx=3)
        self.fault_message = ttk.Entry(fault)
        self.fault_message.insert(0, "Fault detail")
        self.fault_message.pack(side="left", fill="x", expand=True, padx=3)
        tk.Button(fault, text="故障 / Fault", command=self.raise_fault,
                  bg="#b53a3a", fg="white", relief="flat").pack(side="left", padx=3)
        tk.Button(fault, text="确认 / Ack", command=self.ack_fault,
                  bg="#b77b18", fg="white", relief="flat").pack(side="left", padx=3)
        tk.Button(fault, text="清除 / Clear", command=self.clear_fault,
                  bg="#27845a", fg="white", relief="flat").pack(side="left", padx=3)
        self.scan_entry.focus_set()

    def draw_station_visual(self):
        canvas = self.visual
        canvas.delete("all")
        width = max(canvas.winfo_width(), 600)
        canvas.create_rectangle(20, 82, width - 20, 96, fill="#61788a", outline="")
        for x in range(35, width - 25, 42):
            canvas.create_oval(x, 83, x + 11, 94, fill="#b7c7d3", outline="")
        center = width // 2
        accent = "#16a6c9" if self.agent.online else "#d28a2c"
        shapes = {
            "smt_pda_loading": (150, 62),
            "smt_laser_marking": (180, 70),
            "smt_auto_insertion": (250, 74),
            "smt_printer": (230, 70),
            "smt_spi": (210, 68),
            "smt_placement": (300, 78),
            "smt_aoi": (230, 72),
        }
        machine_w, machine_h = shapes.get(self.agent.code, (220, 70))
        left, top = center - machine_w // 2, 78 - machine_h
        canvas.create_rectangle(left, top, left + machine_w, 82, fill="#234c63", outline=accent, width=3)
        canvas.create_rectangle(center - 45, top + 14, center + 45, top + 48, fill="#071823", outline=accent)
        if self.agent.code == "smt_laser_marking":
            canvas.create_line(center, top + 4, center, 80, fill="#ff5252", width=3)
        elif self.agent.code in {"smt_auto_insertion", "smt_placement"}:
            for offset in (-80, -40, 0, 40, 80):
                canvas.create_line(center + offset, top + 8, center + offset, 76, fill="#7dd3fc", width=3)
        elif self.agent.code in {"smt_spi", "smt_aoi"}:
            canvas.create_oval(center - 24, top + 10, center + 24, top + 58, outline="#9cf6ff", width=3)
        canvas.create_rectangle(40, 66, 128, 82, fill="#167b52", outline="#86efac")
        canvas.create_text(84, 58, text="PCB →", fill="white", font=("Microsoft YaHei UI", 10, "bold"))
        canvas.create_text(center, 108, text="  ·  ".join(self.agent.responsibilities()[-4:]),
                           fill="#bcecff", font=("Consolas", 9))

    def change_language(self, lang):
        self.lang = lang
        t = TEXT[lang]
        self.root.title(f"{self.agent.cfg['nameZh']} · {t['title']}")
        self.heading.config(text=f"{self.agent.cfg['nameZh']}  /  {self.agent.cfg['nameEn']}")
        for key in self.labels:
            self.labels[key].config(text=t[key])
        self.scan_box.config(text=t["scan"])
        self.scan_button.config(text=t["submit"])

    def submit_scan(self):
        sn = self.scan_value.get().strip()
        if not sn:
            return
        result = self.agent.scan(sn)
        self.write_log(json.dumps(result, ensure_ascii=False))
        self.scan_value.set("")

    def current_sn(self):
        return self.scan_value.get().strip().upper()

    def submit_activity(self, event_type):
        try:
            if event_type == "WORK_COMPLETED":
                event_id = self.agent.complete_process(
                    self.current_sn(), {"operatorSource": "STATION_UI"}
                )
            else:
                event_id = self.agent.activity(
                    event_type, self.current_sn(), {"operatorSource": "STATION_UI"}
                )
            self.write_log(f"{event_type} · {event_id}")
        except Exception as exc:
            self.write_log(f"ERROR · {exc}")

    def raise_fault(self):
        try:
            event_id = self.agent.fault(self.fault_code.get(), self.fault_message.get(), "ERROR")
            self.write_log(f"FAULT_OCCURRED · {event_id}")
        except Exception as exc:
            self.write_log(f"ERROR · {exc}")

    def ack_fault(self):
        try:
            event_id = self.agent.acknowledge_fault(self.fault_code.get(), "STATION_OPERATOR")
            self.write_log(f"FAULT_ACKNOWLEDGED · {event_id}")
        except Exception as exc:
            self.write_log(f"ERROR · {exc}")

    def clear_fault(self):
        try:
            event_id = self.agent.clear_fault(
                self.fault_code.get(), "STATION_OPERATOR", self.fault_message.get()
            )
            self.write_log(f"FAULT_CLEARED · {event_id}")
        except Exception as exc:
            self.write_log(f"ERROR · {exc}")

    def send_to_repair(self):
        try:
            sn = self.current_sn()
            event_id = self.agent.send_ng_to_repair(sn, "STATION_OPERATOR")
            self.write_log(f"REPAIR_HANDOVER_REQUESTED · {sn} · {event_id}")
            self.scan_value.set("")
        except Exception as exc:
            self.write_log(f"ERROR · {exc}")

    def show_responsibilities(self):
        window = tk.Toplevel(self.root)
        window.title("Station responsibilities")
        window.geometry("620x460")
        box = tk.Text(window, font=("Consolas", 11), padx=14, pady=14)
        box.pack(fill="both", expand=True)
        box.insert("end", "\n".join(f"• {item}" for item in self.agent.responsibilities()))
        box.config(state="disabled")

    def show_resources(self):
        window = tk.Toplevel(self.root)
        window.title("Local station resources")
        window.geometry("860x560")
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True)
        resources = self.agent.recent_resources()
        for key in ("raw", "activities", "faults", "outbox"):
            box = tk.Text(notebook, font=("Consolas", 9), padx=8, pady=8, wrap="none")
            box.insert("end", json.dumps(resources[key], ensure_ascii=False, indent=2))
            box.config(state="disabled")
            notebook.add(box, text=key.upper())

    def write_log(self, message):
        self.log.config(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _worker(self):
        import time
        next_heartbeat = 0.0
        while not self.agent.stop_event.wait(1):
            try:
                self.agent.watch_once()
                self.agent.flush()
                stamp = time.monotonic()
                if stamp >= next_heartbeat:
                    self.agent.heartbeat()
                    next_heartbeat = stamp + int(self.agent.cfg.get("heartbeatSeconds", 10))
            except Exception as exc:
                self.events.put(str(exc))

    def refresh(self):
        while not self.events.empty():
            self.write_log(self.events.get_nowait())
        counts = self.agent.counts()
        source = self.agent.cfg.get("source", {})
        t = TEXT[self.lang]
        self.values["status"].config(text=t["online"] if self.agent.online else t["offline"],
                                     fg="#14995b" if self.agent.online else "#d78418")
        self.values["source"].config(text=source.get("status", "pending") if source.get("path") else t["pending"])
        self.values["sync"].config(text=str(counts["pendingSync"]))
        self.values["raw"].config(text=str(counts["rawRecords"]))
        self.values["checks"].config(text=str(counts["scanChecks"]))
        self.draw_station_visual()
        self.root.after(1000, self.refresh)

    def close(self):
        self.agent.stop_event.set()
        if self.instance_lock:
            self.instance_lock.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def run_ui(agent):
    from smt_station_agent import SingleInstance
    window = SmtStationWindow(agent)
    window.instance_lock = SingleInstance(agent.code, agent.station_dir).acquire()
    window.run()
