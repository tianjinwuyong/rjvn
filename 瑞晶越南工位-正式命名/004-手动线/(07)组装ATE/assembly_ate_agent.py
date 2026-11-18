
# -*- coding: utf-8 -*-
"""Assembly ATE 2D UI. Business/data authority lives in assembly_ate_core."""
import socket
import os
import ctypes
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from station_common_bootstrap import attach_common_agent
from station_repair_workflow import install_repair_workflow
COMMON_AGENT = attach_common_agent(os.environ.get("ATE_STATION_CODE", "manu_assembly_ate"), __file__, "ate-agent")

from assembly_ate_core import AssemblyAteCore, AssemblyAteError, MES_URL, STATION_CODE, read_ate_rows
from station_heartbeat import StationHeartbeat
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from station_scan_alarm import show_blocking_alarm
from station_language import install_language_menu
from station_ui_primitives import UI_PREVIEW, add_preview_watermark, configure_tk_station, register_scanner_entry, restore_scanner_focus

try:
    _hkl = ctypes.windll.user32.LoadKeyboardLayoutW("00000409", 1)
    if _hkl:
        ctypes.windll.user32.ActivateKeyboardLayout(_hkl, 0)
except Exception:
    pass
from station_arrival_ui import ProductGateComponent
from station_resource_viewer import read_tabular_resource


class _AssemblyPreviewCore:
    """Deterministic, read-only UI data source used only with UI_PREVIEW=1."""
    watch_dir = Path("PREVIEW-NO-FILESYSTEM-WATCH")

    def snapshot(self):
        results = []
        for index in range(1, 9):
            results.append({
                "test_time": f"2026-08-04 09:{index:02d}:00", "channel": f"L{index}",
                "sn": f"RJ-A7-L{index}-000{index}", "result": "FAIL" if index == 3 else "PASS",
                "error_code": "ATE-RES-014" if index == 3 else "", "duplicate": False,
                "mes_synced": index != 8, "source_file": "preview.xlsx", "source_row": index,
                "test_cycle_id": "PREVIEW-CYCLE-001",
            })
        return {
            "results": results, "arrival": {
                "expected": [{"expected_at":"2026-08-04 09:12:00","sn":"RJ-A7-L3-0003","source_station":"SUPERSONIC","arrival_status":"EXPECTED","arrived_at":""}],
                "arrivals": [{"arrived_at":"2026-08-04 09:10:00","sn":"RJ-A7-L3-0003","expected":False,"arrival_status":"AUTHORIZED_EXEMPTION","mes_reported_at":"2026-08-04 09:10:02","source_type":"SCANNER"}],
                "exceptions": [],
                "route": {
                    "sn":"RJ-A7-L3-0003","identity_type":"PCBA","identity":"RJ-A7-L3-0003",
                    "gate_state":"ALLOW","reason":"Authorized process exemption · MES R17",
                    "decision_time":"2026-08-04 09:10:02","authorization_reference":"EXEMPT-20260804-017",
                    "current_station":"ASSEMBLY_ATE","route_revision":"R17",
                    "cycle":"2","decision":"AUTHORIZED_EXEMPTION",
                    "next_action":"按豁免路线继续至成品老化 / Continue to Aging",
                    "steps":[
                        {"station":"ICT","state":"COMPLETED"},{"station":"FCT","state":"COMPLETED"},
                        {"station":"DEPANEL","state":"AUTHORIZED"},{"station":"ASSEMBLY ATE","state":"CURRENT"},
                        {"station":"AGING","state":"EXPECTED"},
                    ],
                },
            },
            "maintenance": {"cases": []}, "history": {"batches": []},
            "checks": [{"created_at": "2026-08-04 09:10:00", "sn": "RJ-A7-L3-0003", "status": "NG", "detail": "Preview resistance failure"}],
            "outbox": [{"event_id": "PREVIEW-EVT-001", "sent_at": "", "retry_count": 0, "last_error": "WRITE BLOCKED BY UI_PREVIEW"}],
            "watch_dir": "PREVIEW / NO FILE ACCESS", "source_connected": True, "changes": [],
        }

    def check_scan(self, value):
        return {"status": "PREVIEW", "sn": value or "RJ-A7-DEMO-0001", "detail": "No production lookup performed", "blocked": False}

    def set_watch_dir(self, _value): raise RuntimeError("UI_PREVIEW blocks filesystem changes")
    def ingest_once(self): return {"added": [], "errors": []}
    def ingest_partial_once(self): return {"added": [], "errors": []}
    def sync_once(self): return None


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
        self.root=root; self.core=_AssemblyPreviewCore() if UI_PREVIEW else AssemblyAteCore(); self.running=True
        self.heartbeat=None if UI_PREVIEW else StationHeartbeat(STATION_CODE, MES_URL, "assembly_ate_agent")
        self.observer=None;self.event_lock=threading.Lock();self.event_timer=None
        self._initial_ingest_done=threading.Event()
        root.title(os.environ.get("ATE_WINDOW_TITLE", "组装 ATE / Assembly ATE · 2D")); configure_tk_station(root)
        self.status=tk.StringVar(value="启动中"); self.scan_result=tk.StringVar(value="SN 状态 / SN STATUS: 等待扫描 / WAITING FOR SCAN"); self.machine_status=tk.StringVar(value="正在读取历史记录 / READING HISTORY")
        self.scan=tk.StringVar(); self.cards={}; self._snapshot_cache=None
        # Only local tester-file ingestion may set this flag. MES and SQLite
        # background work never refreshes the operator visualization directly.
        self._local_visual_dirty = True
        self._local_visual_signature = None
        self._cards_enabled = False
        self._pending_card_rows = []
        # The first/live tab is intentionally session-live only: historical
        # rows and background MES refreshes must never repopulate it.
        self._live_result_rows = []
        self._live_since_ms = int(time.time() * 1000)
        self.latest_mes_ng=tk.StringVar(value="MES NG：等待下发 / WAITING FOR MES NG")
        self.file_update_status=tk.StringVar(value="文件监控：等待 Excel 更新 / FILE WATCH: WAITING")
        install_language_menu(root); add_preview_watermark(root); self._build(); self.refresh()
        self._set_machine_status(self.machine_status.get())
        if UI_PREVIEW:
            self.status.set("PREVIEW · deterministic sample · all writes blocked")
            if os.environ.get("UI_PREVIEW_OPEN_ARRIVAL") == "1":
                root.after(600, self.arrival_route.open_details)
        else:
            threading.Thread(target=self._worker,daemon=True).start()
            # Keep historical reconciliation separate from the live update
            # path.  History is intentionally slow and must never hold up a
            # newly written tester result.
            threading.Thread(target=self._history_worker, daemon=True,
                             name="assembly-ate-history-ingest").start()
            # MES NG/expected-SN delivery must not wait behind Excel history
            # parsing. Keep the MES cursor on its own short polling loop.
            threading.Thread(target=self._mes_sync_worker, daemon=True,
                             name="assembly-ate-mes-sync").start()
            threading.Thread(target=self._file_status_worker, daemon=True,
                             name="assembly-ate-file-status").start()
            threading.Thread(target=self._scanner,daemon=True).start()
            self.start_excel_watcher()
            # Scanner guns send the scan followed by Enter. Keep the input
            # target active from startup so keyboard-wedge scans are checked
            # automatically without requiring the operator to click Check.
            self.root.after(300, lambda: restore_scanner_focus(self.root, self.scan_entry))
            self.root.after(250, self._ui_tick)
            # Silently ingest all existing complete tester rows on first
            # startup; do not wait for a filesystem-change event or alarm.
            threading.Thread(target=self._initial_ingest, daemon=True,
                             name="assembly-ate-initial-ingest").start()

    def _mes_sync_worker(self):
        while self.running:
            try:
                report = self.core.refresh_mes_only()
                expected = report.get("mes_expected_sns") or []
                ng = report.get("mes_ng_sns") or []
                if expected:
                    self._queue_machine_status(
                        f"MES 新SN → 本地更新 / MES NEW SN TO LOCAL: {', '.join(expected)[:90]}"
                    )
                # Refresh the visible cache table only for a real MES delta.
                # A normal unchanged poll must not rewrite/reorder the table.
                if ng:
                    self._queue_machine_status(
                        f"MES NG → 本地更新 / MES NG TO LOCAL: {', '.join(ng)[:90]}"
                    )
                    # MES updates are backend-only. They must not refresh any
                    # operator visualization; only local tester-file records
                    # are allowed to trigger a visual refresh.
                    latest = self.core.snapshot().get("mes_ng_cache", [])
                    if latest:
                        item = latest[0]
                        text = f"最新 MES NG / LATEST MES NG：{item.get('sn','')}  | 来源 / SOURCE：{item.get('source_station','')}  | 原因 / REASON：{item.get('reason','')}"
                        self.root.after(0, lambda value=text: self.latest_mes_ng.set(value))
            except Exception as exc:
                self.root.after(0, lambda e=exc: self.status.set(
                    f"MES同步失败: {type(e).__name__}: {e}"))
            time.sleep(5)

    def _initial_ingest(self):
        try:
            # Startup priority: make the newest tester update visible first.
            # The periodic worker performs the full historical reconciliation
            # only after this fast path releases the UI.
            latest = self.core.today_files()
            report = {"added": [], "errors": []}
            if latest:
                report["added"] = self.core.ingest_file(latest[0], allow_partial=True)
            if report.get("added"):
                self._append_live_rows(report["added"])
                self._queue_machine_status(
                    f"最新记录已读取 / LATEST RECORDS READ: {len(report['added'])}"
                )
                self._mark_local_visual_dirty()
                self.root.after(0, self._refresh_after_local_ingest)
            self._background_snapshot()
            self.root.after(0, lambda: self._set_machine_status("最新记录已显示，历史后台读取中 / LATEST SHOWN, HISTORY IN BACKGROUND"))
        except Exception:
            # Startup recovery must remain silent; normal watcher errors are
            # shown only when the operator explicitly refreshes/checks.
            pass
        finally:
            self._initial_ingest_done.set()

    def _history_worker(self):
        """Read older tester files once in the background after startup."""
        self._initial_ingest_done.wait()
        # Give the live-update worker first access to SQLite. Historical
        # reconciliation must never delay newly written tester rows.
        time.sleep(15)
        if not self.running:
            return
        try:
            report = self.core.ingest_history_once()
            if report.get("added"):
                self._queue_machine_status(
                    f"历史后台读取完成 / HISTORY READ COMPLETE: {len(report['added'])}"
                )
                # History is persisted silently. It must never refresh the
                # operator's live cards/results or make old data look new.
            if report.get("errors"):
                self._queue_machine_status(
                    f"历史后台有 {len(report['errors'])} 个文件暂时无法读取 / HISTORY FILES PENDING"
                )
        except Exception as exc:
            self.root.after(0, lambda e=exc: self.status.set(
                f"历史后台读取失败: {type(e).__name__}: {e}"))

    def _set_machine_status(self, value):
        if hasattr(self, "machine_status"):
            self.machine_status.set(value)
        if hasattr(self, "machine_status_label"):
            dynamic = any(token in value for token in ("正在", "READING", "UPDATING", "SIMULATING", "FOUND", "清理"))
            self._machine_status_dynamic = dynamic
            if dynamic:
                self._flash_machine_status()
            else:
                self.machine_status_label.configure(fg="#86efac")

    @staticmethod
    def _vietnam_time(value):
        try:
            number = float(value)
            return datetime.fromtimestamp(number / 1000, timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError, OverflowError):
            return str(value or "")

    def _flash_machine_status(self):
        if not getattr(self, "_machine_status_dynamic", False) or not self.running:
            return
        current = self.machine_status_label.cget("fg")
        self.machine_status_label.configure(fg="#facc15" if current != "#facc15" else "#f8fafc")
        self.root.after(450, self._flash_machine_status)

    def _queue_machine_status(self, value):
        if self.running:
            self.root.after(0, lambda v=value: self._set_machine_status(v))

    def _mark_local_visual_dirty(self):
        """Request a visualization refresh only after local file ingestion."""
        self._local_visual_dirty = True

    def _append_live_rows(self, rows):
        """Append only newly ingested rows to the first/live tab."""
        seen={(str(r.get("source_file", "")), str(r.get("source_row", "")))
              for r in self._live_result_rows}
        for row in rows or []:
            key=(str(row.get("source_file", "")), str(row.get("source_row", "")))
            if key not in seen:
                self._live_result_rows.append(row)
                seen.add(key)

    def _refresh_after_local_ingest(self):
        """Refresh the complete visualization on Tk's main thread."""
        if not self.running:
            return
        try:
            self._local_visual_dirty = False
            self.refresh(self.core.snapshot())
            pending = list(self._pending_card_rows)
            self._pending_card_rows.clear()
            # Historical/startup refreshes must never populate the live cards.
            # Enable cards only when this refresh was caused by actual new
            # local-file rows.
            if not pending:
                return
            self._append_live_rows(pending)
            self._cards_enabled = True
            # Repaint from the latest local-result snapshot so every card is
            # updated consistently for a complete L1-L8/R1-R8 group.
            self._refresh_live_components(self.core.snapshot(), update_cards=True)
            for row in pending:
                channel = str(row.get("channel", "")).upper()
                card = self.cards.get(channel)
                if card:
                    card.config(
                        text=f'{channel}\n{row.get("sn", "--")}',
                        bg="#991b1b" if row.get("result") == "FAIL" else "#166534",
                    )
        except Exception as exc:
            self.status.set(f"本地记录可视化刷新失败: {type(exc).__name__}: {exc}")

    def _refresh_mes_cache_only(self):
        """Show MES cache changes without changing ATE result visualization."""
        if not self.running:
            return
        try:
            snap = self.core.snapshot()
            items = sorted(snap.get("mes_ng_cache", []),
                           key=lambda r: float(r.get("synced_at") or 0), reverse=True)
            tree = self.trees.get("MES本地NG缓存")
            if not tree:
                return
            tree.delete(*tree.get_children())
            for index, row in enumerate(items, 1):
                label = "🟩 ★ 最新 / LATEST" if index == 1 else f"🔴 NG {index}"
                tree.insert("", "end", values=(
                    label, row.get("sn", ""), row.get("source_station", ""),
                    row.get("reason", ""), self._vietnam_time(row.get("synced_at", ""))))
        except Exception as exc:
            self.status.set(f"MES缓存显示失败: {type(exc).__name__}: {exc}")

    def _ui_tick(self):
        if not self.running:
            return
        try:
            # Poll only the local-result fingerprint. This catches file
            # updates even when Windows sends no watcher event, while MES
            # cache changes remain isolated from the ATE visualization.
            snap = self.core.snapshot()
            results = snap.get("results", [])
            # Recover live rows even if a filesystem event was missed. Only
            # rows ingested after this process started are eligible; history
            # remains excluded from the first tab.
            before_live = len(self._live_result_rows)
            self._append_live_rows([
                r for r in results
                if int(r.get("created_at") or 0) >= self._live_since_ms
            ])
            if len(self._live_result_rows) > before_live:
                self._cards_enabled = True
            stable_results = sorted(
                results,
                key=lambda r: (str(r.get("source_file", "")),
                                int(r.get("source_row") or 0)),
            )
            signature = (
                len(stable_results),
                tuple((r.get("source_file"), r.get("source_row"), r.get("sn"),
                       r.get("result"), r.get("error_code")) for r in stable_results),
                tuple((r.get("source_file"), r.get("source_row"))
                      for r in sorted(
                          snap.get("ng_records", []),
                          key=lambda r: (str(r.get("source_file", "")),
                                         int(r.get("source_row") or 0)))),
            )
            if self._local_visual_dirty or signature != self._local_visual_signature:
                self._local_visual_dirty = False
                self._local_visual_signature = signature
                # A local tester-file update must refresh every operator
                # visible component, not only the live/NG tables. MES and
                # SQLite background work never sets this flag.
                self._refresh_live_components(snap, update_cards=self._cards_enabled)
                self._refresh_scan_components(snap)
                self._refresh_static_components(snap)
            # Keep the first tab and cards bound to the live buffer even when
            # the database fingerprint is unchanged after an asynchronous
            # ingest callback.
            if self._live_result_rows:
                self._cards_enabled = True
                self._refresh_live_components(snap, update_cards=True)
        except Exception as exc:
            self.status.set(f"ATE界面刷新失败: {type(exc).__name__}: {exc}")
        finally:
            if self.running:
                self.root.after(250, self._ui_tick)

    def _build(self):
        head=tk.Frame(self.root,bg="#111827");head.pack(fill="x")
        tk.Label(head,text=os.environ.get("ATE_DISPLAY_NAME", "组装 ATE · 2D"),font=("Microsoft YaHei",20,"bold"),fg="white",bg="#111827").pack(side="left",padx=16,pady=10)
        self.machine_status_label=tk.Label(head,textvariable=self.machine_status,font=("Microsoft YaHei",11,"bold"),fg="#facc15",bg="#111827")
        self.machine_status_label.place(relx=0.5,rely=0.5,anchor="center")
        tk.Label(head,textvariable=self.status,font=("Microsoft YaHei",11,"bold"),fg="#67e8f9",bg="#111827").pack(side="right",padx=16)
        tk.Label(self.root,textvariable=self.latest_mes_ng,font=("Microsoft YaHei",11,"bold"),fg="#facc15",bg="#422006",anchor="w",padx=12).pack(fill="x",padx=12,pady=(4,0))
        tk.Label(self.root,textvariable=self.file_update_status,font=("Microsoft YaHei",10,"bold"),fg="#93c5fd",bg="#172554",anchor="w",padx=12).pack(fill="x",padx=12,pady=(2,0))
        scan=tk.Frame(self.root,bg="#422006");scan.pack(fill="x",padx=12,pady=6)
        tk.Label(scan,text="扫码检查（只检查 NG / 重复，不生成测试结果）",bg="#422006",fg="#fde047",font=("Microsoft YaHei",11,"bold")).pack(side="left",padx=8)
        ent=tk.Entry(scan,textvariable=self.scan,width=32);register_scanner_entry(self.root,ent);self.scan_entry=ent;ent.pack(side="left",padx=8,pady=8,ipady=7)
        tk.Button(scan,text="检查",command=self.check_scan).pack(side="left")
        self.scan_result_label=tk.Label(scan,textvariable=self.scan_result,bg="#422006",fg="#facc15",font=("Microsoft YaHei",11,"bold"),anchor="w")
        self.scan_result_label.pack(side="left",padx=14)
        tk.Button(scan,text="模拟 L8 → R8",command=self.simulate_cycle,bg="#2563eb",fg="white").pack(side="left",padx=6)
        tk.Button(scan,text="模拟 MES 下发",command=self.simulate_mes_downstream,bg="#0891b2",fg="white").pack(side="left",padx=6)
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
        table_style=ttk.Style(self.root);table_style.theme_use("clam")
        table_style.map("Treeview", background=[("selected", "#dc2626")], foreground=[("selected", "#ffffff")])
        specs=[("实时结果",("文件 / FILE","SN","测试结果 / RESULT","测试时间 / TEST TIME","通道","错误","重复","MES")),("MES本地NG缓存",("队列","SN","来源","原因","本地缓存到达时间 / LOCAL CACHE ARRIVAL TIME")),("维修工单",("本地工单","MES工单","SN","原因","部门","状态","创建时间")),("历史封存",("封存批次","原因","记录数","总哈希","封存时间","人员")),("本地解析NG",("队列","SN","原因","解析时间")),("扫码检查",("时间","SN","状态","说明")),("设置",("项目","值")),("修改记录",("编号","版本","组件","原因","内容","验证","时间"))]
        self.trees={}
        for name,cols in specs:
            frame=tk.Frame(self.tabs);self.tabs.add(frame,text=name);tree=ttk.Treeview(frame,columns=cols,show="headings")
            for col in cols:tree.heading(col,text=col);tree.column(col,width=150,anchor="center")
            if name=="MES本地NG缓存":
                tree.tag_configure("latest_mes_ng", background="#22c55e", foreground="#052e16")
                tree.tag_configure("matched_ng", background="#dc2626", foreground="#ffffff")
            tree.pack(side="left",fill="both",expand=True);ttk.Scrollbar(frame,command=tree.yview).pack(side="right",fill="y");self.trees[name]=tree
        self.resource_tab = tk.Frame(self.tabs, bg="#0f172a")
        self.tabs.add(self.resource_tab, text="资源查看 / RESOURCES")
        self._build_resource_view(self.resource_tab)

    def _build_resource_view(self, parent):
        """Read-only, human-readable Excel/CSV viewer for local station resources."""
        toolbar = tk.Frame(parent, bg="#0b1f35", padx=8, pady=6)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text="Excel/CSV 文件查看 · READ ONLY", bg="#0b1f35", fg="#bae6fd",
                 font=("Microsoft YaHei", 11, "bold")).pack(side="left")
        self.resource_path = tk.StringVar(value="资源路径 / RESOURCE PATH: -")
        tk.Label(toolbar, textvariable=self.resource_path, bg="#0b1f35", fg="#fef08a",
                 anchor="w").pack(side="left", fill="x", expand=True, padx=16)
        tk.Button(toolbar, text="刷新文件", command=self._refresh_resource_files,
                  bg="#0e7490", fg="white").pack(side="right")
        self.resource_status = tk.StringVar(value="选择文件查看前 500 行")
        tk.Label(toolbar, textvariable=self.resource_status, bg="#0b1f35", fg="#cbd5e1").pack(side="right", padx=12)
        body = tk.PanedWindow(parent, orient="horizontal", sashrelief="raised", bg="#0f172a")
        body.pack(fill="both", expand=True, padx=8, pady=8)
        left = tk.Frame(body, bg="#111827")
        right = tk.Frame(body, bg="#111827")
        body.add(left, minsize=300)
        body.add(right, minsize=620)
        tk.Label(left, text="可用文件 / AVAILABLE FILES", bg="#111827", fg="#e2e8f0",
                 font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", padx=8, pady=6)
        self.resource_files_tree = ttk.Treeview(left, columns=("file", "type", "size", "modified", "rows", "ng"), show="headings")
        for key, label, width in (("file", "文件", 230), ("type", "类型", 75), ("size", "大小", 85), ("modified", "修改时间", 145), ("rows", "记录数", 75), ("ng", "NG数", 65)):
            self.resource_files_tree.heading(key, text=label)
            self.resource_files_tree.column(key, width=width, anchor="w")
        self.resource_files_tree.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.resource_files_tree.bind("<<TreeviewSelect>>", self._show_resource_file)
        tk.Label(right, text="表格预览 / TABLE PREVIEW", bg="#111827", fg="#e2e8f0",
                 font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", padx=8, pady=6)
        preview_frame = tk.Frame(right, bg="#111827")
        preview_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.resource_preview = ttk.Treeview(preview_frame, show="headings")
        y_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.resource_preview.yview)
        x_scroll = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.resource_preview.xview)
        self.resource_preview.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.resource_preview.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)
        self._refresh_resource_files()

    def _resource_paths(self):
        root = Path(self.core.watch_dir)
        if not root.exists():
            return []
        paths = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in (".xlsx", ".xlsm", ".csv")
                 and not path.name.startswith("~$")]
        return sorted(paths, key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)[:200]

    def _refresh_resource_files(self):
        if not hasattr(self, "resource_files_tree"):
            return
        self.resource_files_tree.delete(*self.resource_files_tree.get_children())
        paths = self._resource_paths()
        self.resource_path.set(f"资源路径 / RESOURCE PATH: {self.core.watch_dir}")
        total_rows = total_ng = 0
        for path in paths:
            stat = path.stat()
            try:
                parsed = read_ate_rows(path)
                row_count = len(parsed)
                ng_count = sum(1 for row in parsed if row.get("result") == "FAIL")
            except Exception:
                row_count = ng_count = 0
            total_rows += row_count
            total_ng += ng_count
            self.resource_files_tree.insert("", "end", iid=str(path), values=(
                path.name, path.suffix.upper().lstrip("."), f"{stat.st_size:,} B",
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)), row_count, ng_count))
        self.resource_status.set(f"{len(paths)} 个文件 · 记录 {total_rows} · NG {total_ng} · 动态统计")

    def _show_resource_file(self, _event=None):
        selected = self.resource_files_tree.selection()
        if not selected:
            return
        path = Path(selected[0])
        view = read_tabular_resource(path, limit=500)
        columns = list(view.get("columns") or [])
        self.resource_preview.delete(*self.resource_preview.get_children())
        self.resource_preview.configure(columns=columns)
        for column in columns:
            self.resource_preview.heading(column, text=column)
            self.resource_preview.column(column, width=max(120, min(260, len(column) * 12)), anchor="w")
        for row in view.get("rows", []):
            self.resource_preview.insert("", "end", values=[str(row.get(column, ""))[:500] for column in columns])
        if view.get("error"):
            self.resource_status.set(f"读取失败: {view['error']}")
        else:
            self.resource_status.set(f"{path.name} · {len(view.get('rows', []))} 行 · 只读")

    def check_scan(self):
        try:
            raw=self.scan.get(); code=str(raw or "").strip().upper()
            result=({"status":"NG","sn":code,"blocked":True,"detail":"MES confirmed NG (LOCAL SQLITE)"}
                    if code and COMMON_AGENT.local_confirmed_ng(code) else self.core.check_scan(raw)); self.scan.set("")
            self._apply_scan_result(result)
        except AssemblyAteError as exc:messagebox.showwarning("扫码",str(exc))
        self._refresh_scan_components()

    def _apply_scan_result(self, result):
        message=f'{result["status"]}: {result["sn"]} {result["detail"]}'
        self.status.set(message)
        self.scan_result.set(f'SN: {result["sn"]}  |  STATUS: {result["status"]}  |  {result["detail"]}')
        self.scan_result_label.config(fg="#f87171" if result["blocked"] else "#86efac")
        self._highlight_ng_row(result["sn"] if result["blocked"] else "")
        if result["blocked"]:
            show_blocking_alarm(self.root,result["status"],result["sn"],result["detail"],voice_enabled=True)
        self._refresh_scan_components()

    def _highlight_ng_row(self, sn):
        """Select the matching MES-cache row so the NG source is visible."""
        tree=self.trees.get("MES本地NG缓存")
        code=str(sn or "").strip().upper()
        if not tree or not code:
            return
        for item in tree.get_children(""):
            values=tree.item(item,"values")
            if len(values)>1 and str(values[1]).strip().upper()==code:
                tree.selection_set(item)
                tree.focus(item)
                tree.see(item)
                tree.item(item,tags=("matched_ng",))
                break
        restore_scanner_focus(self.root, self.scan_entry)

    def simulate_cycle(self):
        if getattr(self, "_simulation_running", False):
            return
        self._simulation_running = True
        threading.Thread(target=self._simulate_cycle_worker, daemon=True).start()

    def simulate_mes_downstream(self):
        if getattr(self, "_mes_simulation_running", False):
            return
        self._mes_simulation_running = True
        threading.Thread(target=self._simulate_mes_downstream_worker, daemon=True).start()

    def _simulate_mes_downstream_worker(self):
        expected, ng = self.core.simulate_mes_downstream()
        self._queue_machine_status(f"MES 新SN → 本地更新 / MES NEW SN TO LOCAL: {', '.join(expected)}")
        self._background_snapshot()
        time.sleep(2)
        self._queue_machine_status(f"MES NG → 本地更新 / MES NG TO LOCAL: {', '.join(ng)}")
        self._background_snapshot()
        time.sleep(3)
        self.core.clear_mes_simulation(expected, ng)
        self._background_snapshot()
        self.root.after(0, lambda: self._set_machine_status("MES模拟完成，数据已删除 / MES SIMULATION REMOVED"))
        self._mes_simulation_running = False

    def _simulate_cycle_worker(self):
        records = []
        try:
            for side in ("L", "R"):
                group = self.core.simulate_excel_rows(side, 8)
                records.extend(group)
                sns = ", ".join(row["sn"] for row in group)
                self._queue_machine_status(f"模拟写入实时表 / SIMULATING {side}1-{side}8 TOGETHER: {sns[:90]}")
                self._background_snapshot()
                time.sleep(2)
            self._queue_machine_status("模拟完成，正在清理 / SIMULATION FINISHED, CLEANING UP")
            time.sleep(2)
        finally:
            self.core.clear_simulation(records)
            self._background_snapshot()
            self.root.after(0, lambda: self._set_machine_status("模拟数据已删除 / SIMULATION DATA REMOVED"))
            self._simulation_running = False

    def choose_dir(self):
        value=filedialog.askdirectory(initialdir=str(self.core.watch_dir))
        if value:self.core.set_watch_dir(value);self.start_excel_watcher();self.refresh()

    def _worker(self):
        # The initial historical import owns the database scan. Do not let
        # the periodic worker parse the same 19 Excel files concurrently.
        self._initial_ingest_done.wait()
        while self.running:
            # Reconcile periodically in case Windows misses or coalesces a
            # filesystem event. Checkpoints make this safe and incremental.
            report = {"added": [], "errors": []}
            try:
                # Live path: newest file only. MES has its own thread; this
                # loop must remain independent of both MES and history.
                report = self.core.ingest_latest_once()
                if report.get("added"):
                    count = len(report["added"])
                    sns = ", ".join(str(row.get("sn", "")) for row in report["added"] if row.get("sn"))
                    # Keep the added SN visible in the main machine-status
                    # indicator long enough for the operator to see it.
                    self._queue_machine_status(
                        f"新增 SN / NEW SN ({count}): {sns[:180]}")
                    self._pending_card_rows.extend(report["added"])
                    file_name = Path(str(report["added"][0].get("source_file", ""))).name
                    self.root.after(0, lambda f=file_name, s=sns: self.file_update_status.set(
                        f"文件更新 / FILE UPDATED: {f} · 新增 SN / NEW SN: {s[:180]}"))
                    self._announce_file_update(file_name, sns)
                    self._mark_local_visual_dirty()
                    self.root.after(0, self._refresh_after_local_ingest)
                    ng_sns = ", ".join(str(row.get("sn", "")) for row in report["added"]
                                       if row.get("result") == "FAIL" and row.get("sn"))
                    if ng_sns:
                        self._queue_machine_status(f"NG 更新到 MES / NG UPDATING TO MES: {ng_sns[:90]}")
            except Exception as exc:
                # Do not silently hide a watcher/parser failure; keep the
                # station running and expose the cause in the operator UI.
                self.root.after(0, lambda e=exc: self.status.set(
                    f"ATE数据读取失败: {type(e).__name__}: {e}"))
            self.heartbeat.tick(sourceConnected=self.core.watch_dir.exists(), sourceType="XLSX")
            time.sleep(1)

    def _file_status_worker(self):
        """Watch every report file and report changes without touching UI data."""
        previous = {}
        initialized = False
        while self.running:
            current = {}
            try:
                for path in self.core.latest_files():
                    try:
                        stat = path.stat()
                        current[str(path)] = (stat.st_mtime_ns, stat.st_size)
                    except OSError:
                        continue
                if initialized:
                    changed = [name for name, stamp in current.items()
                               if previous.get(name) != stamp]
                    removed = [name for name in previous if name not in current]
                    if changed or removed:
                        labels = [Path(name).name for name in changed[:3]]
                        if removed:
                            labels.append(f"removed={len(removed)}")
                        message = "文件更新 / FILE UPDATED: " + ", ".join(labels)
                        self.root.after(0, lambda text=message: self.file_update_status.set(text))
                previous = current
                initialized = True
            except Exception as exc:
                self.root.after(0, lambda e=exc: self.status.set(
                    f"文件监控失败 / FILE WATCH FAILED: {type(e).__name__}: {e}"))
            time.sleep(2)

    def _announce_file_update(self, file_name, sns):
        """Announce parsed Excel updates without blocking the UI thread."""
        def speak():
            wav_path = None
            try:
                count = len([item for item in sns.split(", ") if item.strip()])
                text = f"文件更新，{count}条数据。"
                # Use the installed Windows SAPI device directly first. This
                # avoids PowerShell/window/session routing problems on remote
                # stations and keeps the voice call synchronous in this worker.
                import win32com.client
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Volume = 100
                voice.Rate = 0
                voice.Speak(text, 0)
                return
            except Exception as direct_error:
                try:
                    # Fallback for machines where the COM voice is unavailable.
                    escaped = text.replace("'", "''")
                    wav_path = tempfile.mktemp(prefix="ate_voice_", suffix=".wav")
                    safe_path = wav_path.replace("'", "''")
                    command = ("Add-Type -AssemblyName System.Speech; "
                               "$v=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                               "$v.Volume=100; $v.Rate=0; "
                               f"$v.SetOutputToWaveFile('{safe_path}'); $v.Speak('{escaped}'); $v.Dispose()")
                    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    subprocess.run(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command],
                                   check=True, timeout=20, creationflags=flags)
                    import winsound
                    winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_SYNC)
                except Exception as fallback_error:
                    self._queue_machine_status(
                        f"语音失败 / VOICE FAILED: {type(fallback_error).__name__}")
            finally:
                if wav_path:
                    try:
                        Path(wav_path).unlink(missing_ok=True)
                    except Exception:
                        pass
        threading.Thread(target=speak, daemon=True, name="ate-file-update-voice").start()

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
        if is_directory or Path(name).suffix.lower() not in {".xlsx", ".xlsm", ".xls", ".csv"} or name.startswith("~$"):
            return
        with self.event_lock:
            if self.event_timer:self.event_timer.cancel()
            # A tester may write the report in several filesystem events.  Give
            # it one second to finish the current write, then ingest whatever
            # rows are present; do not wait for a complete group of eight.
            self.event_timer=threading.Timer(1.0,self.process_excel_event)
            self.event_timer.daemon=True;self.event_timer.start()

    def process_excel_event(self):
        if not self.running:return
        report=self.core.ingest_latest_once()
        if report["added"]:
            self.core.sync_once()
            self._pending_card_rows.extend(report["added"])
            self._mark_local_visual_dirty()
            self.root.after(0, self._refresh_after_local_ingest)
            self.root.after(0,lambda r=report:self._after_poll(r))

    def _after_poll(self,report):
        if report["added"]:self.status.set(f'新增 {len(report["added"])} 条 Excel 测试记录')
        elif report["errors"]:self.status.set("有 Excel 文件暂时无法读取")
        if report["added"]:
            self._append_live_rows(report["added"])
            sns = ", ".join(str(row.get("sn", "")) for row in report["added"] if row.get("sn"))
            self._set_machine_status(f"更新读取完成 / READ UPDATE FINISHED · {len(report['added'])}: {sns[:90]}")
        self._refresh_result_components()

    def partial_test(self):
        self.status.set("正在读取部分 ATE 测试记录…")
        threading.Thread(target=self._partial_test_worker, daemon=True).start()

    def _partial_test_worker(self):
        report = self.core.ingest_partial_once()
        if report["added"]:
            self.core.sync_once()
            self._mark_local_visual_dirty()
        self.root.after(0, lambda r=report: self._after_partial_test(r))

    def _after_partial_test(self, report):
        if report["added"]:
            self._append_live_rows(report["added"])
            self.status.set(f'部分测试已读取 {len(report["added"])} 条记录')
        elif report["errors"]:
            self.status.set("部分测试文件暂时无法读取")
            messagebox.showwarning("部分测试", report["errors"][0]["error"])
        else:
            self.status.set("没有待处理的 1–7 条新记录")
        self._refresh_result_components()

    def _scanner(self):
        server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        debug_path=Path(__file__).with_name("scanner_debug.log")
        try:
            server.bind(("0.0.0.0",int(os.environ.get("ATE_SCANNER_PORT", "1003"))));server.listen(5);server.settimeout(1)
            while self.running:
                try:
                    conn,_=server.accept();conn.settimeout(2)
                    with conn:
                        while self.running:
                            data=conn.recv(4096).decode(errors="ignore")
                            if not data: break
                            for item in data.replace("\r","\n").splitlines():
                                item=item.strip()
                                if not item: continue
                                with debug_path.open("a",encoding="utf-8") as log: log.write(f"RX {time.strftime('%Y-%m-%d %H:%M:%S')} {item!r}\n")
                                code=item.upper()
                                result=({"status":"NG","sn":code,"blocked":True,"detail":"MES confirmed NG (LOCAL SQLITE)"}
                                         if code and COMMON_AGENT.local_confirmed_ng(code) else self.core.check_scan(item))
                                self.root.after(0,lambda r=result:self._apply_scan_result(r))
                except socket.timeout:pass
                except Exception as exc:
                    with debug_path.open("a",encoding="utf-8") as log: log.write(f"ERROR {time.strftime('%Y-%m-%d %H:%M:%S')} {type(exc).__name__}: {exc}\n")
        except OSError as exc:self.root.after(0,lambda:self.status.set(f"扫码端口不可用: {exc}"))
        finally:server.close()

    def _fill(self,tree,rows):
        tree.delete(*tree.get_children())
        for row in rows:tree.insert("","end",values=row)

    def _background_snapshot(self):
        if not self.running:return
        try:
            snap=self.core.snapshot()
            self.root.after(0,lambda s=snap:self._refresh_result_components(s))
        except Exception as exc:
            self.root.after(0,lambda e=exc:self.status.set(f"ATE界面数据刷新失败: {type(e).__name__}: {e}"))

    def refresh(self, snap=None):
        """Full refresh used at startup and for deliberate directory changes."""
        if snap is not None:self._snapshot_cache=snap
        snap=self._snapshot_cache
        if snap is None:return
        self._refresh_result_components(snap)
        self._refresh_scan_components(snap)
        self._refresh_static_components(snap)

    def _get_snapshot(self, snap=None):
        if snap is not None:
            self._snapshot_cache=snap
        return self._snapshot_cache

    def _refresh_live_components(self, snap=None, update_cards=False):
        snap=self._get_snapshot(snap)
        if snap is None:return
        results=snap["results"]
        if update_cards and self._cards_enabled:
            latest={}
            for r in results:
                if r["channel"] in self.cards and r["channel"] not in latest:latest[r["channel"]]=r
            for channel,card in self.cards.items():
                r=latest.get(channel);card.config(text=f'{channel}\n{r["sn"] if r else "--"}',bg="#166534" if r and r["result"]=="PASS" else "#991b1b" if r else "#334155")
        self._fill(self.trees["实时结果"],[(Path(str(r.get("source_file", ""))).name,
                                             r.get("sn", ""), r.get("result", ""),
                                             r.get("test_time", ""), r.get("channel", ""),
                                             r.get("error_code", ""),
                                             "YES" if r.get("duplicate") else "",
                                             "SYNC" if r.get("mes_synced") else "QUEUED")
                                            for r in self._live_result_rows[-500:]])
        arrival=snap["arrival"]
        self.arrival_route.update(arrival)
        local_rows=[(r.get("sn",""),r.get("reason", ""),self._vietnam_time(r.get("received_at", ""))) for r in snap.get("ng", [])]
        mes_items=sorted(snap.get("mes_ng_cache", []), key=lambda r: float(r.get("synced_at") or 0), reverse=True)
        mes_rows=[(r.get("sn",""),r.get("source_station", ""),r.get("reason", ""),self._vietnam_time(r.get("synced_at", ""))) for r in mes_items]
        mes_tree=self.trees["MES本地NG缓存"]
        mes_tree.delete(*mes_tree.get_children())
        for index,row in enumerate(mes_rows,1):
            queue_label="🟩 ★ 最新 / LATEST" if index==1 else f"🔴 NG {index}"
            mes_tree.insert("","end",values=(queue_label,)+row,tags=("latest_mes_ng",) if index==1 else ())
        self._fill(self.trees["本地解析NG"],[(index,)+row for index,row in enumerate(local_rows,1)])

    def _refresh_result_components(self, snap=None):
        snap=self._get_snapshot(snap)
        if snap is None:return
        self._refresh_live_components(snap, update_cards=False)

    def _refresh_scan_components(self, snap=None):
        snap=self._get_snapshot(snap)
        if snap is None:return
        self._fill(self.trees["扫码检查"],[(r["created_at"],r["sn"],r["status"],r["detail"]) for r in snap["checks"]])
        self.arrival_route.update(snap["arrival"])

    def _refresh_static_components(self, snap=None):
        snap=self._get_snapshot(snap)
        if snap is None:return
        results=snap["results"]
        self._fill(self.trees["维修工单"],[(r["local_case_id"],r["mes_work_order_id"] or "",r["sn"],r["reason_code"],r["department"],r["status"],r["created_at"]) for r in snap["maintenance"]["cases"]])
        self._fill(self.trees["历史封存"],[(r["archive_batch_id"],r["reason"],r["record_count"],r["content_hash"],r["sealed_at"],r["created_by"]) for r in snap["history"]["batches"]])
        self._fill(self.trees["设置"],[("Excel 数据目录",snap["watch_dir"]),("数据源状态","ONLINE" if snap["source_connected"] else "MISSING"),("数据流向","本地 SQLite → MES"),("扫码规则","仅 NG / 重复检查")])
        self._fill(self.trees["修改记录"],[(r["change_id"],r["version"],r["component"],r["reason"],r["summary"],r["verification"],r["changed_at"]) for r in snap["changes"]])

    def close(self):
        self.running=False
        with self.event_lock:
            if self.event_timer:self.event_timer.cancel()
        if self.observer:self.observer.stop();self.observer.join(timeout=2)
        self.root.destroy()


if __name__=="__main__":
    root=tk.Tk();app=AssemblyAte2D(root)
    if not UI_PREVIEW:
        from station_retest import install_station_retest_panel
        install_station_retest_panel(root,STATION_CODE,MES_URL.replace("/api/pda/events",""))
    install_repair_workflow(root,STATION_CODE,MES_URL,os.environ.get("ATE_DISPLAY_NAME", "组装 ATE"),preview=UI_PREVIEW)
    root.protocol("WM_DELETE_WINDOW",app.close);root.mainloop()

