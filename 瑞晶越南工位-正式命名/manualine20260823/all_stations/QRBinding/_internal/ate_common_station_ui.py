"""Standalone ATE UI backed only by atecommonagent."""
from __future__ import annotations

import os
import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from atecommonagent import AteCommonAgent, flexible_parse_file
from station_ui_primitives import register_scanner_entry


def standard_time(value):
    try:
        return datetime.fromtimestamp(float(value) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(value or "")


class AteCommonStationUI:
    def __init__(self, root):
        self.root = root
        self.colors = {
            "navy": "#0b1220", "panel": "#111c2e", "panel2": "#17263d",
            "cyan": "#22d3ee", "blue": "#38bdf8", "green": "#22c55e",
            "red": "#ef4444", "amber": "#f59e0b", "text": "#e5f3ff",
            "muted": "#94a3b8", "white": "#ffffff",
        }
        self.station = os.getenv("ATE_STATION_CODE", "ATE_COMMON")
        self.title = os.getenv("ATE_DISPLAY_NAME", self.station)
        self.ui_language = tk.StringVar(value=os.getenv("ATE_LANGUAGE", "中文"))
        self.root.title(f"{self.title} · 2D")
        self.root.geometry("1280x780")
        self.root.minsize(1000, 650)
        self.agent = AteCommonAgent(
            db_path=Path(os.getenv("ATE_DB_PATH", f"{self.station}.db")),
            watch_dir=os.getenv("ATE_WATCH_DIR", r"D:\ATS\测试报表"),
            parser=flexible_parse_file,
            station_code=self.station,
        )
        self.agent.add_listener(self._on_rows)
        self._scan_after_id = None
        self.cards = {}
        self._build()
        register_scanner_entry(self.root, self.scan_entry)
        self.agent.start_watching(interval=1.0, include_existing=True)
        self._refresh_ng()
        self.scan_entry.focus_set()

    def _build(self):
        c = self.colors
        self.root.configure(bg=c["navy"])
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=c["navy"], borderwidth=0)
        style.configure("TNotebook.Tab", background=c["panel2"], foreground=c["muted"], padding=(16, 8), font=("Microsoft YaHei", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", c["cyan"])], foreground=[("selected", c["navy"])])
        style.configure("Treeview", background="#f8fafc", fieldbackground="#f8fafc", foreground="#0f172a", rowheight=30, font=("Consolas", 10))
        style.configure("Treeview.Heading", background=c["panel2"], foreground=c["text"], font=("Microsoft YaHei", 10, "bold"), padding=6)
        header = tk.Frame(self.root, bg=c["navy"])
        header.pack(fill="x", padx=18, pady=(14, 8))
        tk.Label(header, text="◆", fg=c["cyan"], bg=c["navy"], font=("Consolas", 24, "bold")).pack(side="left", padx=(0, 10))
        tk.Label(header, text=self.title, fg=c["white"], bg=c["navy"],
                 font=("Microsoft YaHei", 22, "bold")).pack(side="left")
        tk.Label(header, text="● ONLINE   |   COMMON ATE · LOCAL-FIRST", fg=c["green"], bg=c["navy"],
                 font=("Consolas", 11)).pack(side="right", pady=8)

        language_bar = tk.Frame(self.root, bg=c["navy"])
        language_bar.pack(fill="x", padx=18, pady=(0, 3))
        tk.Label(language_bar, text="语言 / Language / Ngôn ngữ", bg=c["navy"], fg=c["muted"]).pack(side="right", padx=6)
        self.language_box = ttk.Combobox(language_bar, textvariable=self.ui_language,
                                         values=("中文", "English", "Tiếng Việt"), state="readonly", width=13)
        self.language_box.pack(side="right")
        self.language_box.bind("<<ComboboxSelected>>", self._set_language)
        scan = tk.Frame(self.root, bg=c["panel"], highlightbackground=c["cyan"], highlightthickness=1)
        scan.pack(fill="x", padx=18, pady=4)
        tk.Label(scan, text="⌕  SN / 扫码", fg=c["text"], bg=c["panel"], font=("Microsoft YaHei", 12, "bold")).pack(side="left", padx=12)
        self.scan_entry = tk.Entry(scan, bg="#f8fafc", fg="#0f172a", insertbackground=c["navy"], relief="flat", font=("Consolas", 18), width=42)
        self.scan_entry.pack(side="left", padx=8, pady=8)
        # Scanner guns commonly finish with Enter or Tab. Handle the field
        # directly as a fallback when the global keyboard-wedge listener is
        # unavailable or the scanner is focused in this entry.
        self.scan_entry.bind("<Return>", lambda event: self._scan(event) or "break")
        self.scan_entry.bind("<KP_Enter>", lambda event: self._scan(event) or "break")
        self.scan_entry.bind("<Tab>", lambda event: self._scan(event) or "break")
        self.scan_entry.bind("<KeyRelease>", self._schedule_scan)
        # The common global keyboard-wedge listener owns Enter/Tab completion.
        tk.Button(scan, text="▶  检查 / CHECK", command=self._scan, width=16, bg=c["cyan"], fg=c["navy"], activebackground=c["blue"], relief="flat", font=("Microsoft YaHei", 10, "bold")).pack(side="left", padx=5, ipady=5)
        self.status = tk.StringVar(value="READY  ·  等待扫码")
        self.status_label = tk.Label(scan, textvariable=self.status, bg=c["panel"], fg=c["green"],
                 font=("Microsoft YaHei", 11, "bold"))
        self.status_label.pack(side="right", padx=12)

        cards_frame = tk.LabelFrame(self.root, text="  ◈ 实时通道 / LIVE CHANNELS  ", fg=c["cyan"], bg=c["panel"], padx=8, pady=6, font=("Microsoft YaHei", 10, "bold"))
        cards_frame.pack(fill="x", padx=18, pady=8)
        for i in range(16):
            channel = f"L{i + 1}" if i < 8 else f"R{i - 7}"
            card = tk.Label(cards_frame, text=f"{channel}\n—  READY", width=14, height=3,
                            bg=c["panel2"], fg=c["muted"], font=("Consolas", 10, "bold"), relief="flat", bd=0)
            card.grid(row=i // 8, column=i % 8, padx=3, pady=3, sticky="nsew")
            self.cards[channel] = card

        tabs = ttk.Notebook(self.root)
        self.tabs = tabs
        tabs.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        live = tk.Frame(tabs)
        ng = tk.Frame(tabs)
        tabs.add(live, text="实时结果 / LIVE RESULTS")
        tabs.add(ng, text="MES NG缓存 / MES NG CACHE")
        self.results = ttk.Treeview(live, columns=("file", "sn", "result", "time", "channel"), show="headings")
        for key, label, width in (("file", "文件 / FILE", 320), ("sn", "SN", 260), ("result", "结果", 100), ("time", "时间", 180), ("channel", "通道", 80)):
            self.results.heading(key, text=label)
            self.results.column(key, width=width, anchor="center")
        self.results.pack(fill="both", expand=True, padx=5, pady=5)
        self.results.tag_configure("scan_ng", background="#7f1d1d", foreground="#fee2e2")
        self.results.tag_configure("scan_dup", background="#92400e", foreground="#fef3c7")
        self.results.tag_configure("scan_ok", background="#14532d", foreground="#dcfce7")
        self.results.tag_configure("flash_ng", background="#ef4444", foreground="#ffffff")
        self.results.tag_configure("flash_dup", background="#fbbf24", foreground="#111827")
        self.ng = ttk.Treeview(ng, columns=("sn", "source", "reason", "time"), show="headings")
        for key, label, width in (("sn", "SN", 300), ("source", "来源", 180), ("reason", "原因", 420), ("time", "时间", 190)):
            self.ng.heading(key, text=label)
            self.ng.column(key, width=width, anchor="center")
        self.ng.pack(fill="both", expand=True, padx=5, pady=5)
        parsed_frame = tk.Frame(tabs, bg=self.colors["navy"])
        tabs.add(parsed_frame, text="本地解析NG / PARSED NG")
        self.parsed_ng = ttk.Treeview(parsed_frame, columns=("sn", "file", "result", "reason", "time"), show="headings")
        for key, label, width in (("sn", "SN", 280), ("file", "来源文件", 360), ("result", "读取结果", 120), ("reason", "原因", 320), ("time", "解析时间", 190)):
            self.parsed_ng.heading(key, text=label)
            self.parsed_ng.column(key, width=width, anchor="center")
        self.parsed_ng.pack(fill="both", expand=True, padx=5, pady=5)
        sn_frame = tk.Frame(tabs, bg=self.colors["navy"])
        tabs.add(sn_frame, text="本地SN SQLite / LOCAL SN")
        self.local_sn = ttk.Treeview(sn_frame, columns=("sn", "file", "result", "time"), show="headings")
        for key, label, width in (("sn", "SN", 320), ("file", "来源文件", 420), ("result", "结果", 120), ("time", "记录时间", 220)):
            self.local_sn.heading(key, text=label)
            self.local_sn.column(key, width=width, anchor="center")
        self.local_sn.pack(fill="both", expand=True, padx=5, pady=5)
        self._build_resource_view(tabs)

    def _build_resource_view(self, tabs):
        frame = tk.Frame(tabs, bg=self.colors["navy"])
        tabs.add(frame, text="资源查看 / RESOURCES")
        toolbar = tk.Frame(frame, bg="#0b1f35", padx=8, pady=6)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="Excel/CSV 文件查看 · READ ONLY", bg="#0b1f35", fg="#bae6fd",
                 font=("Microsoft YaHei", 11, "bold")).pack(side="left")
        self.resource_status = tk.StringVar(value="递归资源读取中")
        tk.Label(toolbar, textvariable=self.resource_status, bg="#0b1f35", fg="#fef08a").pack(side="right", padx=12)
        tk.Button(toolbar, text="刷新文件", command=self._refresh_resource_files, bg="#0e7490", fg="white").pack(side="right")
        body = tk.PanedWindow(frame, orient="horizontal", sashrelief="raised", bg=self.colors["navy"])
        body.pack(fill="both", expand=True, padx=8, pady=8)
        left = tk.Frame(body, bg="#111827")
        right = tk.Frame(body, bg="#111827")
        body.add(left, minsize=320)
        body.add(right, minsize=650)
        tk.Label(left, text="可用文件 / AVAILABLE FILES", bg="#111827", fg="#e2e8f0",
                 font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", padx=8, pady=6)
        self.resource_files_tree = ttk.Treeview(left, columns=("file", "type", "size", "modified", "rows", "ng"), show="headings")
        for key, label, width in (("file", "文件", 230), ("type", "类型", 70), ("size", "大小", 85), ("modified", "修改时间", 145), ("rows", "记录数", 75), ("ng", "NG数", 65)):
            self.resource_files_tree.heading(key, text=label)
            self.resource_files_tree.column(key, width=width, anchor="w")
        self.resource_files_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.resource_files_tree.bind("<<TreeviewSelect>>", self._show_resource_file)
        tk.Label(right, text="表格预览 / TABLE PREVIEW", bg="#111827", fg="#e2e8f0",
                 font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", padx=8, pady=6)
        self.resource_preview = ttk.Treeview(right, show="headings")
        self.resource_preview.pack(fill="both", expand=True, padx=6, pady=6)
        self._refresh_resource_files()

    def _refresh_resource_files(self):
        if not hasattr(self, "resource_files_tree"):
            return
        self.resource_files_tree.delete(*self.resource_files_tree.get_children())
        paths = self.agent.resource_files()
        for path in paths[:200]:
            try:
                stat = path.stat()
                parsed = flexible_parse_file(path) or []
                ng_count = sum(1 for row in parsed if str(row.get("result", "")).upper() in {"NG", "FAIL", "FAILED"})
                self.resource_files_tree.insert("", "end", iid=str(path), values=(path.name, path.suffix.upper().lstrip("."), f"{stat.st_size:,} B", datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"), len(parsed), ng_count))
            except Exception:
                continue
        self.resource_status.set(f"{len(paths)} 个文件 · 递归读取 / READ ONLY")

    def _show_resource_file(self, _event=None):
        selected = self.resource_files_tree.selection()
        if not selected:
            return
        path = Path(selected[0])
        rows = flexible_parse_file(path) or []
        columns = sorted({key for row in rows[:100] for key in row.keys()})
        self.resource_preview.delete(*self.resource_preview.get_children())
        self.resource_preview.configure(columns=columns)
        for column in columns:
            self.resource_preview.heading(column, text=column)
            self.resource_preview.column(column, width=150, anchor="w")
        for row in rows[:500]:
            self.resource_preview.insert("", "end", values=[str(row.get(column, ""))[:300] for column in columns])

    def _set_language(self, _event=None):
        labels = {
            "中文": ("语言已切换：中文", "等待扫码"),
            "English": ("Language changed: English", "Waiting for scan"),
            "Tiếng Việt": ("Đã đổi ngôn ngữ: Tiếng Việt", "Chờ quét mã"),
        }
        message, waiting = labels.get(self.ui_language.get(), labels["中文"])
        self.status.set(f"{message} · {waiting}")

    def _scan(self, _event=None):
        sn = self.scan_entry.get().strip()
        if not sn:
            return
        result = self.agent.check_scan(sn)
        self._show_scan_result(result, "manual")
        self.scan_entry.delete(0, "end")

    def _schedule_scan(self, event=None):
        """Fallback for scanners that type a fast SN without a usable Enter."""
        if event and getattr(event, "keysym", "") in {"Return", "KP_Enter", "Tab"}:
            return
        if len(self.scan_entry.get().strip()) < 8:
            return
        if self._scan_after_id:
            self.root.after_cancel(self._scan_after_id)
        self._scan_after_id = self.root.after(150, self._auto_scan)

    def _auto_scan(self):
        self._scan_after_id = None
        if self.scan_entry.get().strip():
            self._scan()

    def _on_scanner_input(self, sn, source):
        self.root.after(0, lambda: self._apply_scanner_input(sn, source))

    def _apply_scanner_input(self, sn, source):
        self.scan_entry.delete(0, "end")
        self.scan_entry.insert(0, sn)
        result = self.agent.check_scan(sn)
        self._show_scan_result(result, source)
        self.scan_entry.delete(0, "end")

    def _show_scan_result(self, result, source):
        """Keep every scan decision visible and highlight blocked scans."""
        self.agent.start_mes_background_refresh()
        status = str(result.get("status", ""))
        detail = str(result.get("detail", ""))
        tag = "scan_ng" if status == "NG" else "scan_dup" if "DUPLICATE" in status else "scan_ok"
        item_id = self.results.insert("", 0, values=(f"SCANNER / {source}", result.get("sn", ""), status,
                          detail, "SCAN"), tags=(tag,))
        self.results.selection_set(item_id)
        self.results.focus(item_id)
        self.results.see(item_id)
        self.tabs.select(0)
        if tag in {"scan_ng", "scan_dup"}:
            self._flash_alert(item_id, tag, 0)
            self._alarm_scan(status, result.get("sn", ""), detail)
        if status == "NG":
            self.status.set(f"⛔ NG · 禁止通过 · {detail}")
            self.status_label.configure(fg=self.colors["red"])
            self.tabs.tab(0, text="实时结果 / LIVE RESULTS · NG")
        elif "DUPLICATE" in status:
            self.status.set(f"⚠ DUPLICATE · 禁止通过 · {detail}")
            self.status_label.configure(fg=self.colors["amber"])
            self.tabs.tab(0, text="实时结果 / LIVE RESULTS · DUP")
        else:
            self.status.set(f"✓ CLEAR · {source}")
            self.status_label.configure(fg=self.colors["green"])
            self.tabs.tab(0, text="实时结果 / LIVE RESULTS")

    def _flash_alert(self, item_id, tag, count):
        if not self.results.exists(item_id) or count >= 10:
            if self.results.exists(item_id):
                self.results.item(item_id, tags=(tag,))
            return
        flash_tag = "flash_ng" if tag == "scan_ng" else "flash_dup"
        self.results.item(item_id, tags=(flash_tag if count % 2 == 0 else tag,))
        self.root.after(450, lambda: self._flash_alert(item_id, tag, count + 1))

    def _alarm_scan(self, status, sn="", detail=""):
        """Use the ICT-style blocking alarm: full-screen, flashing, and voice."""
        try:
            from station_scan_alarm import show_blocking_alarm
            show_blocking_alarm(self.root, status, sn, detail, voice_enabled=True)
            return
        except Exception:
            pass
        message = "发现不良品，禁止离开本站。" if status == "NG" else "发现重复编码，禁止离开本站。"
        def alarm():
            try:
                import winsound
                winsound.Beep(1100, 180)
                winsound.Beep(800, 220)
            except Exception:
                pass
            try:
                import win32com.client
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Volume = 100
                voice.Speak(message, 0)
            except Exception:
                pass
        import threading
        threading.Thread(target=alarm, name="ate-scan-alarm", daemon=True).start()

    def _on_rows(self, rows):
        self.root.after(0, lambda: self._apply_rows(rows))

    def _apply_rows(self, rows):
        for row in rows:
            sn = str(row.get("sn", ""))
            channel = str(row.get("channel", "")).upper()
            if channel in self.cards:
                fail = str(row.get("result", "")).upper() in {"NG", "FAIL", "FAILED"}
                self.cards[channel].configure(text=f"{channel}\n{sn or '--'}", bg="#991b1b" if fail else "#166534")
            live_result = str(row.get("result", "")).upper()
            live_tag = "scan_ng" if live_result in {"NG", "FAIL", "FAILED"} else "scan_ok"
            self.results.insert("", "end", values=(Path(str(row.get("source_file", ""))).name,
                              sn, row.get("result", ""), row.get("test_time", ""), channel), tags=(live_tag,))
        self.status.set(f"● 文件更新，{len(rows)}条数据  /  {self.station}")

    def _refresh_ng(self):
        try:
            self.ng.delete(*self.ng.get_children())
            with sqlite3.connect(str(self.agent.db_path)) as db:
                rows = db.execute("SELECT sn,source_station,reason,received_at FROM atecommon_mes_ng_cache ORDER BY received_at DESC LIMIT 200").fetchall()
                parsed_rows = db.execute("SELECT sn,source_file,result,reason,parsed_at FROM atecommon_parsed_ng ORDER BY parsed_at DESC LIMIT 200").fetchall()
                local_rows = db.execute("SELECT sn,source_file,result,test_time FROM atecommon_local_records ORDER BY recorded_at DESC LIMIT 500").fetchall()
            for row in rows:
                self.ng.insert("", "end", values=(row[0], row[1], row[2], standard_time(row[3])))
            self.parsed_ng.delete(*self.parsed_ng.get_children())
            for row in parsed_rows:
                self.parsed_ng.insert("", "end", values=(row[0], row[1], row[2], row[3], standard_time(row[4])))
            self.local_sn.delete(*self.local_sn.get_children())
            for row in local_rows:
                self.local_sn.insert("", "end", values=(row[0], Path(row[1]).name, row[2], row[3]))
        except Exception:
            pass
        self.root.after(1000, self._refresh_ng)

    def close(self):
        self.agent.stop_watching()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = AteCommonStationUI(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()


if __name__ == "__main__":
    main()
