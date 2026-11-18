# -*- coding: utf-8 -*-
"""Manual-line aging UI: seven independent cabinets backed by station 97 MySQL."""
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

_MANUAL_ROOT = Path(__file__).resolve().parent.parent
_AUTO_ROOT = next(
    (path for path in _MANUAL_ROOT.parent.iterdir()
     if path.is_dir() and path.name.startswith("002-")),
    None,
)
sys.path.insert(0, str(_MANUAL_ROOT))
if _AUTO_ROOT is not None:
    sys.path.insert(0, str(_AUTO_ROOT))
from aging_cab_core import AgingCabCore, AgingCabError, EXPECTED_AGING_MS, MES_URL, STATION_CODE
from station_common_bootstrap import attach_common_agent
COMMON_AGENT = attach_common_agent(STATION_CODE, __file__, "aging-cabinet")
from station_heartbeat import StationHeartbeat
from station_runtime_safety import acquire_single_instance

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from station_language import install_language_menu
from station_scan_alarm import show_blocking_alarm
from station_i18n import translated
from station_ui_primitives import UI_PREVIEW, add_preview_watermark, configure_tk_station, register_scanner_entry, restore_scanner_focus
from station_arrival_ui import ProductGateComponent


class _AgingPreviewCore:
    sql_connected = True
    sql_table = "PREVIEW_ONLY"
    def snapshot(self):
        native=[]
        for cab in range(1,8):
            for addr in range(1,5):
                active=addr <= 2
                native.append({"cabinet":cab,"addr":addr,"sn":f"RJ-AGE-C{cab}-{addr:02d}" if active else "","state":"NG" if cab==4 and addr==2 else "AGING" if active else "EMPTY","updated_at":1722740400000,"started_at":1722736800000 if active else 0,"elapsed":"01:00:00" if active else ""})
        return {"native":native,"results":[],"ng":[],"arrival":{"route":{"identity_type":"SHELL","identity":"RJ-AGE-C4-02","gate_state":"HOLD","reason":"Aging cycle active","next_action":"Wait for final cycle result"}},"outbox":[{"event_id":"PREVIEW-AGE-001","event_type":"AGING_STATE","status":"BLOCKED","last_error":"UI_PREVIEW"}],"sql":{"host":"NO CONNECTION","port":"--","database":"PREVIEW","table":"PREVIEW_ONLY","connected":False}}
    def check_scan(self,value):return {"status":"PREVIEW","sn":value or "RJ-AGE-DEMO-0001","blocked":False,"detail":"No production lookup performed"}


def fmt(ms):
    if not ms:
        return "--"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ms) / 1000))


def duration(ms):
    seconds = max(0, int(ms or 0) // 1000)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


class AgingCab2D:
    CABINET_COUNT = 7

    def __init__(self, root):
        self.root = root
        self.core = _AgingPreviewCore() if UI_PREVIEW else AgingCabCore()
        # Aging results come from the recursive local record resource. This
        # agent must not poll the legacy MySQL source during normal operation.
        self._last_mysql_poll = float("inf")
        self.running = True
        self.heartbeat = None if UI_PREVIEW else StationHeartbeat(STATION_CODE, MES_URL, "aging_cab_agent")
        self.scan = tk.StringVar()
        self.status = tk.StringVar(value="MySQL连接中")
        self.summary = tk.StringVar(value="7个老化柜 · 等待97 MySQL数据")
        self.cabinet_summary = {number: tk.StringVar(value="等待数据") for number in range(1, 8)}
        self.cabinet_frames = {}
        self._alarm_keys = set()
        self._alarm_flash_on = False
        self._alarm_flash_timer = None
        root.title("手动线成品老化 / MANUAL AGING CAB · 7 CABINETS")
        configure_tk_station(root)
        self.locale = install_language_menu(root)
        add_preview_watermark(root)
        self.build()
        self.locale.trace_add("write", self._language_changed)
        self.refresh()
        if UI_PREVIEW:
            self.status.set("PREVIEW · deterministic sample · all writes blocked")
        else:
            threading.Thread(target=self.worker, daemon=True).start()
            threading.Thread(target=self.scanner, daemon=True).start()

    def build(self):
        header = tk.Frame(self.root, bg="#0b1f35")
        header.pack(fill="x")
        tk.Label(header, text="手动线成品老化 · 7个独立柜体", bg="#0b1f35", fg="#e0f2fe",
                 font=("Segoe UI", 20, "bold")).pack(side="left", padx=20, pady=12)
        tk.Label(header, text="97 MySQL · 柜号/槽位/SN/最终结果", bg="#0b1f35", fg="#7dd3fc",
                 font=("Microsoft YaHei UI", 11)).pack(side="left", padx=16)
        tk.Label(header, textvariable=self.status, bg="#0b1f35", fg="#fbbf24",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(side="right", padx=16)
        self.sql_source_var = tk.StringVar(value="MYSQL SOURCE: --")
        tk.Label(self.root, textvariable=self.sql_source_var, bg="#10243b", fg="#a7f3d0",
                 font=("Consolas", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(2, 4))

        scanbar = tk.Frame(self.root, bg="#083344")
        scanbar.pack(fill="x", padx=10, pady=8)
        tk.Label(scanbar, text="扫码检查 / SCANNER", bg="#083344", fg="#67e8f9",
                 font=("Microsoft YaHei UI", 12, "bold")).pack(side="left", padx=8)
        entry = tk.Entry(scanbar, textvariable=self.scan, justify="center")
        register_scanner_entry(self.root, entry)
        self.scan_entry = entry
        entry.pack(side="left", fill="x", expand=True, padx=8, ipady=7)
        entry.bind("<Return>", lambda _event: self.check())
        tk.Button(scanbar, text="检查 / CHECK", command=self.check, bg="#0369a1", fg="white",
                  font=("Microsoft YaHei UI", 10, "bold"), padx=16).pack(side="left", padx=5)
        self.product_gate = ProductGateComponent(self.root)
        self.summary_label = tk.Label(self.root, textvariable=self.summary, bg="#07111f", fg="#67e8f9",
                 font=("Consolas", 12, "bold"))
        self.summary_label.pack(fill="x", padx=12, pady=(0, 5))

        self.cabinet_book = ttk.Notebook(self.root)
        self.cabinet_book.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        for cabinet in range(1, self.CABINET_COUNT + 1):
            tab = tk.Frame(self.cabinet_book, bg="#07111f")
            self.cabinet_book.add(tab, text=f"柜体 {cabinet}")
            tk.Label(tab, textvariable=self.cabinet_summary[cabinet], bg="#07111f", fg="#7dd3fc",
                     font=("Microsoft YaHei UI", 12, "bold")).pack(fill="x", padx=10, pady=6)
            canvas = tk.Canvas(tab, bg="#07111f", highlightthickness=0)
            scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            content = tk.Frame(canvas, bg="#07111f")
            window = canvas.create_window((0, 0), window=content, anchor="nw")
            content.bind("<Configure>", lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.bind("<Configure>", lambda e, c=canvas, w=window: c.itemconfigure(w, width=e.width))
            self.cabinet_frames[cabinet] = content

        details = ttk.Notebook(self.root)
        details.pack(fill="x", padx=10, pady=(0, 8))
        self.trees = {}
        specs = {
            "测试结果": ("时间", "SN", "结果", "来源"),
            "SQL TABLE": ("TABLE", "TIME", "SN", "RESULT", "SOURCE"),
            "SQLite": ("TABLE", "ROWS", "LATEST", "DATABASE"),
            "MySQL SOURCE": ("TABLE", "TIME", "SN", "RESULT"),
            "NG": ("时间", "SN", "来源"),
            "MES通信": ("事件", "类型", "状态", "错误"),
            "设置": ("项目", "值"),
        }
        for name, columns in specs.items():
            frame = tk.Frame(details)
            details.add(frame, text=name)
            tree = ttk.Treeview(frame, columns=columns, show="headings", height=5)
            for column in columns:
                tree.heading(column, text=column)
                tree.column(column, width=180, anchor="center")
            tree.pack(fill="both", expand=True)
            self.trees[name] = tree
        self.analytics_tab = tk.Frame(details, bg="#0f172a")
        details.add(self.analytics_tab, text="分析 / ANALYTICS")
        self.analytics_kpis = {}
        kpi_row = tk.Frame(self.analytics_tab, bg="#0f172a")
        kpi_row.pack(fill="x", padx=8, pady=8)
        for key, label, color in (
            ("slots", "SLOTS", "#38bdf8"), ("active", "ACTIVE", "#22c55e"),
            ("ng", "NG", "#ef4444"), ("rate", "NG RATE", "#f59e0b"),
        ):
            card = tk.Frame(kpi_row, bg="#10243b", highlightbackground=color, highlightthickness=2, padx=12, pady=8)
            card.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(card, text=label, bg="#10243b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(anchor="w")
            var = tk.StringVar(value="0")
            self.analytics_kpis[key] = var
            tk.Label(card, textvariable=var, bg="#10243b", fg=color, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        period_row = tk.Frame(self.analytics_tab, bg="#0f172a")
        period_row.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(period_row, text="PERIOD / 统计周期", bg="#0f172a", fg="#cbd5e1",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        self.analytics_period = tk.StringVar(value="daily")
        for value, label in (("daily", "DAILY / 日"), ("weekly", "WEEKLY / 周"), ("monthly", "MONTHLY / 月")):
            tk.Radiobutton(period_row, text=label, value=value, variable=self.analytics_period,
                           command=self.refresh, indicatoron=False, padx=10, pady=3,
                           bg="#1e3a5f", fg="#e0f2fe", selectcolor="#0369a1",
                           activebackground="#075985", activeforeground="white",
                           font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
        self.analytics_period_summary = tk.StringVar(value="No history in selected period")
        tk.Label(period_row, textvariable=self.analytics_period_summary, bg="#0f172a", fg="#a7f3d0",
                 font=("Consolas", 9, "bold")).pack(side="right", padx=4)
        self.analytics_canvas = tk.Canvas(self.analytics_tab, height=260, bg="#0b1728", highlightthickness=0)
        self.analytics_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _refresh_analytics(self, snapshot):
        native = list(snapshot.get("native") or [])
        results = list(snapshot.get("results") or [])
        total = len(native)
        active = sum(1 for row in native if row.get("sn"))
        ng = sum(1 for row in native if str(row.get("state") or "").upper() in ("NG", "FAIL"))
        self.analytics_kpis["slots"].set(str(total))
        self.analytics_kpis["active"].set(str(active))
        self.analytics_kpis["ng"].set(str(ng))
        self.analytics_kpis["rate"].set(f"{(ng / active * 100) if active else 0:.1f}%")
        canvas = self.analytics_canvas
        canvas.delete("all")
        width = max(700, canvas.winfo_width())
        chart_top, chart_bottom = 34, 220
        canvas.create_text(18, 14, text="CABINET UTILIZATION / 柜体利用率", anchor="w", fill="#7dd3fc", font=("Segoe UI", 10, "bold"))
        by_cabinet = {}
        for row in native:
            cab = int(row.get("cabinet") or 0)
            item = by_cabinet.setdefault(cab, {"total": 0, "active": 0, "ng": 0})
            item["total"] += 1
            item["active"] += bool(row.get("sn"))
            item["ng"] += str(row.get("state") or "").upper() in ("NG", "FAIL")
        count = max(1, len(by_cabinet))
        bar_w = max(24, int((width - 80) / count) - 12)
        for index, cab in enumerate(sorted(by_cabinet)):
            item = by_cabinet[cab]
            x = 45 + index * (bar_w + 12)
            total_h = chart_bottom - chart_top
            active_h = int(total_h * (item["active"] / max(1, item["total"])))
            ng_h = int(total_h * (item["ng"] / max(1, item["total"])))
            canvas.create_rectangle(x, chart_bottom - active_h, x + bar_w, chart_bottom, fill="#166534", outline="#22c55e")
            if ng_h:
                canvas.create_rectangle(x, chart_bottom - ng_h, x + bar_w, chart_bottom, fill="#991b1b", outline="#ef4444")
            canvas.create_text(x + bar_w / 2, chart_bottom + 14, text=f"C{cab}", fill="#cbd5e1", font=("Segoe UI", 9, "bold"))
            canvas.create_text(x + bar_w / 2, chart_bottom - active_h - 10, text=f"{item['active']}/{item['total']}", fill="#e2e8f0", font=("Consolas", 8))
        pass_count = sum(1 for row in results if str(row.get("result") or "").upper() in ("OK", "PASS"))
        fail_count = sum(1 for row in results if str(row.get("result") or "").upper() in ("NG", "FAIL"))
        canvas.create_text(width - 250, 14, text=f"SOURCE RESULTS  PASS {pass_count}  ·  NG {fail_count}", anchor="w", fill="#a7f3d0", font=("Segoe UI", 10, "bold"))

        now = time.time()
        period = self.analytics_period.get()
        window = {"daily": 86400, "weekly": 7 * 86400, "monthly": 30 * 86400}.get(period, 86400)
        def row_time(row):
            value = row.get("test_time") or row.get("updated_at") or row.get("created_at")
            if isinstance(value, (int, float)):
                return float(value) / 1000 if value > 10_000_000_000 else float(value)
            text = str(value or "").strip()
            if not text:
                return 0.0
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError, OverflowError):
                return 0.0
        period_results = [row for row in results if row_time(row) >= now - window]
        period_pass = sum(1 for row in period_results if str(row.get("result") or "").upper() in ("OK", "PASS"))
        period_ng = sum(1 for row in period_results if str(row.get("result") or "").upper() in ("NG", "FAIL"))
        period_total = period_pass + period_ng
        yield_rate = period_pass / period_total * 100 if period_total else 0
        self.analytics_period_summary.set(f"{period.upper()}  RESULTS {period_total}  PASS {period_pass}  NG {period_ng}  YIELD {yield_rate:.1f}%")

    def fill(self, name, rows):
        tree = self.trees[name]
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=row)

    def tr(self, text):
        return translated(text, self.locale.get())

    def _flash_ng_banner(self):
        if not self.running or not self.summary_label.winfo_exists():
            return
        self._alarm_flash_on = not self._alarm_flash_on
        self.summary_label.configure(
            bg="#facc15" if self._alarm_flash_on else "#991b1b",
            fg="#111827" if self._alarm_flash_on else "white")
        self._alarm_flash_timer = self.summary_label.after(400, self._flash_ng_banner)

    def _alarm_ng_results(self, rows):
        ng_rows = [row for row in rows if str(row.get("result", "")).upper() in ("NG", "FAIL")]
        if not ng_rows:
            if self._alarm_flash_timer:
                try: self.summary_label.after_cancel(self._alarm_flash_timer)
                except tk.TclError: pass
                self._alarm_flash_timer = None
            self.summary_label.configure(bg="#07111f", fg="#67e8f9")
            return
        if not self._alarm_flash_timer:
            self._flash_ng_banner()
        for row in ng_rows:
            key=f"{row.get('sn','')}|{row.get('test_time','')}|{row.get('source_table','')}"
            if key in self._alarm_keys:
                continue
            self._alarm_keys.add(key)
            show_blocking_alarm(self.root, "NG", row.get("sn", ""),
                                row.get("source_table", "Aging NG"), STATION_CODE, MES_URL)

    def _language_changed(self, *_args):
        self._last_signature = None
        self.refresh()

    def check(self):
        try:
            raw = self.scan.get(); code = str(raw or "").strip().upper()
            result = ({"status":"NG","sn":code,"blocked":True,"detail":"MES confirmed NG (LOCAL SQLITE)"}
                      if code and COMMON_AGENT.local_confirmed_ng(code) else self.core.check_scan(raw))
            self.scan.set("")
            self.status.set(f'{result["status"]}: {result["sn"]}')
            if result["blocked"]:
                show_blocking_alarm(self.root, result["status"], result["sn"], result["detail"])
        except AgingCabError as exc:
            messagebox.showwarning("扫码", str(exc))
        finally:
            restore_scanner_focus(self.root, self.scan_entry)

    def worker(self):
        while self.running:
            self.heartbeat.tick(sourceConnected=self.core.sql_connected, sourceType="MYSQL",
                                sourceTable=self.core.sql_table)
            try:
                now = time.monotonic()
                if now - self._last_mysql_poll >= 60:
                    self._last_mysql_poll = now
                    report = self.core.poll_mysql_once()
                else:
                    report = {"read": 0, "added": 0}
                self.root.after(0, lambda r=report: self.status.set({
                    "zh": f'MySQL在线 · 读取 {r.get("read", 0)} · 新增 {r.get("added", 0)}',
                    "en": f'MYSQL ONLINE · READ {r.get("read", 0)} · ADDED {r.get("added", 0)}',
                    "vi": f'MYSQL TRỰC TUYẾN · ĐỌC {r.get("read", 0)} · THÊM {r.get("added", 0)}',
                }[self.locale.get()]))
            except Exception as exc:
                self.core.sql_connected = False
                self.root.after(0, lambda text=str(exc): self.status.set({
                    "zh":"MySQL离线: ", "en":"MYSQL OFFLINE: ", "vi":"MYSQL NGOẠI TUYẾN: "
                }[self.locale.get()] + text[:100]))
            try:
                excel = self.core.poll_excel_once()
                if excel.get('read') or excel.get('files') or excel.get('error'):
                    self.root.after(0, lambda r=excel: self.status.set({
                        "zh": f'Excel递归读取 路 文件 {r.get("files", 0)} 路 记录 {r.get("read", 0)} 路 新增 {r.get("added", 0)}',
                        "en": f'EXCEL RECURSIVE READ / FILES {r.get("files", 0)} / ROWS {r.get("read", 0)} / ADDED {r.get("added", 0)}',
                        "vi": f'EXCEL DOC / FILE {r.get("files", 0)} / ROW {r.get("read", 0)} / NEW {r.get("added", 0)}',
                    }[self.locale.get()]))
            except Exception as exc:
                self.root.after(0, lambda text=str(exc): self.status.set('Excel读取错误: ' + text[:100]))
            self.core.sync_once()
            self.root.after(0, self.refresh)
            time.sleep(2)

    def scanner(self):
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", 1009)); server.listen(5); server.settimeout(1)
            while self.running:
                try:
                    client, _address = server.accept()
                    value = client.recv(4096).decode(errors="ignore").strip(); client.close()
                    if value:
                        self.root.after(0, lambda text=value: (self.scan.set(text), self.check()))
                except socket.timeout:
                    pass
        except OSError as exc:
            self.root.after(0, lambda: self.status.set(f"扫码端口错误: {exc}"))
        finally:
            server.close()

    def refresh(self):
        snapshot = self.core.snapshot()
        self._alarm_ng_results(snapshot.get("results", []))
        self._refresh_analytics(snapshot)
        sql = snapshot.get("sql") or {}
        host = f'{sql.get("host", "--")}:{sql.get("port", "--")}'
        state = "ONLINE" if sql.get("connected") else "OFFLINE"
        self.sql_source_var.set(
            f'MYSQL {state} · {host} · DB: {sql.get("database", "--")} · TABLE: {sql.get("table", "--")}'
        )
        self.product_gate.update(snapshot.get("arrival", {}))
        native = snapshot["native"]
        signature = tuple((row["cabinet"], row["addr"], row["sn"], row["state"], row["updated_at"])
                          for row in native)
        # SQL result rows are independent of cabinet-slot changes; refresh the
        # read-only SQL table even when the cabinet layout is unchanged.
        sql_rows = [(x.get("source_table", ""), x.get("test_time", ""),
                     x.get("sn", ""), x.get("result", ""),
                     x.get("source_table", "")) for x in snapshot.get("results", [])[:500]]
        # In the safe UI preview there is no SQL connection.  Still show the
        # current cabinet records as rows (rather than only showing a table
        # name), and label them explicitly so they cannot be mistaken for
        # production SQL data.
        if not sql_rows and not sql.get("connected"):
            sql_rows = [("PREVIEW_NATIVE", fmt(x.get("updated_at")),
                         x.get("sn", ""), x.get("state", ""),
                         "CABINET %s / SLOT %s" % (x.get("cabinet", ""), x.get("addr", "")))
                        for x in native if x.get("sn")][:500]
        self.fill("SQL TABLE", sql_rows)
        if signature == getattr(self, "_last_signature", None):
            return
        self._last_signature = signature
        now = int(time.time() * 1000)
        grouped = {number: [] for number in range(1, self.CABINET_COUNT + 1)}
        for row in native:
            cabinet = int(row["cabinet"] or 0)
            if cabinet in grouped:
                grouped[cabinet].append(row)
        total_slots = total_active = total_ng = 0
        for cabinet, rows in grouped.items():
            content = self.cabinet_frames[cabinet]
            for child in content.winfo_children():
                child.destroy()
            rows.sort(key=lambda row: int(row["addr"] or 0))
            occupied = sum(1 for row in rows if row["sn"])
            ng_count = sum(1 for row in rows if str(row["state"]).upper() in ("NG", "FAIL"))
            total_slots += len(rows); total_active += occupied; total_ng += ng_count
            summaries = {
                "zh": f"柜体 {cabinet} · 槽位 {len(rows)} · 在柜 {occupied} · NG {ng_count}" if rows else f"柜体 {cabinet} · 等待 MySQL 槽位数据",
                "en": f"CABINET {cabinet} · SLOTS {len(rows)} · OCCUPIED {occupied} · NG {ng_count}" if rows else f"CABINET {cabinet} · WAITING FOR MYSQL SLOT DATA",
                "vi": f"TỦ {cabinet} · VỊ TRÍ {len(rows)} · ĐANG DÙNG {occupied} · NG {ng_count}" if rows else f"TỦ {cabinet} · ĐANG CHỜ DỮ LIỆU VỊ TRÍ MYSQL",
            }
            self.cabinet_summary[cabinet].set(summaries[self.locale.get()])
            if not rows:
                tk.Label(content, text=self.tr("等待97 MySQL数据 / WAITING FOR MYSQL"), bg="#07111f",
                         fg="#64748b", font=("Microsoft YaHei UI", 15, "bold"), pady=80).pack(fill="x")
                continue
            for index, row in enumerate(rows):
                state = str(row["state"] or "WAIT").upper()
                sn = str(row["sn"] or "—")
                failed = state in ("NG", "FAIL")
                active = bool(row["sn"])
                bg = "#7f1d1d" if failed else "#064e3b" if active else "#1e293b"
                border = "#ef4444" if failed else "#22c55e" if active else "#475569"
                card = tk.Frame(content, bg=bg, highlightbackground=border, highlightthickness=2,
                                width=245, height=112)
                card.grid(row=index // 5, column=index % 5, sticky="nsew", padx=5, pady=5)
                card.grid_propagate(False)
                elapsed = row["elapsed"] or duration(now - (row["started_at"] or now))
                slot_word = {"zh":"槽位", "en":"SLOT", "vi":"VỊ TRÍ"}[self.locale.get()]
                tk.Label(card, text=f'{slot_word} {row["addr"]}\n{sn}\n{state} · {elapsed}',
                         bg=bg, fg="white", font=("Consolas", 10, "bold"), justify="left",
                         anchor="w").pack(fill="both", expand=True, padx=8)
                current = row["current"] or "--"
                voltage = row["voltage"] or "--"
                reason = row["reason"] or "--"
                recorded = row["record_time"] or "--"
                tk.Label(card, text=f"I={current}  V={voltage}  R={reason}\n{recorded}",
                         bg=bg, fg="#cbd5e1", font=("Consolas", 8), justify="left",
                         anchor="w").pack(fill="x", padx=8, pady=(0, 4))
                content.grid_columnconfigure(index % 5, weight=1)
        active_cabinets = sum(1 for rows in grouped.values() if any(row.get("sn") for row in rows))
        self.summary.set({
            "zh":f"7个柜体 · 已发现槽位 {total_slots} · 在柜 {total_active} · NG {total_ng}",
            "en":f"7 CABINETS · SLOTS {total_slots} · OCCUPIED {total_active} · NG {total_ng}",
            "vi":f"7 TỦ · VỊ TRÍ {total_slots} · ĐANG DÙNG {total_active} · NG {total_ng}",
        }[self.locale.get()])
        self.sql_source_var.set(self.sql_source_var.get().split(" · DATA ", 1)[0] + f" · DATA {active_cabinets}/{self.CABINET_COUNT}")
        self.fill("测试结果", [(x["test_time"], x["sn"], x["result"], x["source_table"])
                            for x in snapshot["results"][:500]])
        self.fill("NG", [(x["test_time"], x["sn"], x["source_table"]) for x in snapshot["ng"][:500]])
        self.fill("MES通信", [(x["event_id"], x["event_type"], x["status"], x["last_error"])
                            for x in snapshot["outbox"][:500]])
        sqlite_rows = [
            ("source_results", len(snapshot["results"]), snapshot["results"][0]["test_time"] if snapshot["results"] else "-", str(self.core.db_path)),
            ("aging_native_sessions", len(snapshot["native"]), "-", str(self.core.db_path)),
            ("aging_batches", len(snapshot["batches"]), "-", str(self.core.db_path)),
            ("aging_batch_members", len(snapshot["batch_members"]), "-", str(self.core.db_path)),
            ("event_outbox", len(snapshot["outbox"]), "-", str(self.core.db_path)),
        ]
        self.fill("SQLite", sqlite_rows)
        self.fill("MySQL SOURCE", [(x["source_table"], x["test_time"], x["sn"], x["result"])
                                   for x in snapshot["results"][:500]])
        sql = snapshot["sql"]
        self.fill("设置", [("MySQL", f'{sql["host"]}:{sql["port"]}'), ("Database", sql["database"]),
                         ("Table", sql["table"]), ("Connected", sql["connected"]),
                         (self.tr("柜体数量"), self.CABINET_COUNT),
                         (self.tr("要求老化"), duration(EXPECTED_AGING_MS))])

    def close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    _instance_mutex = True if UI_PREVIEW else acquire_single_instance("MANU_AGING_CAB_AGENT")
    if _instance_mutex is None:
        raise SystemExit("Aging Cab Agent is already running")
    root = tk.Tk()
    app = AgingCab2D(root)
    if not UI_PREVIEW:
        from station_retest import install_station_retest_panel
        install_station_retest_panel(root, STATION_CODE, MES_URL, test_station=False)
        from station_repair_workflow import install_repair_workflow
        install_repair_workflow(root, STATION_CODE, MES_URL, "成品老化")
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()
