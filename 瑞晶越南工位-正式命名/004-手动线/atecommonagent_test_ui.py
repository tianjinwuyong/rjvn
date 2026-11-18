# -*- coding: utf-8 -*-
"""Small manual test UI for atecommonagent.py; not used by production ATEs."""
import tkinter as tk
import sys
import sqlite3
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from atecommonagent import AteCommonAgent, flexible_parse_file
sys.path.insert(0, str(Path(__file__).resolve().parent / "(07)组装ATE"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "002-自动线"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "station-component-reservoir" / "python"))
from assembly_ate_core import read_ate_rows


class CommonAgentTestUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ATE Common Agent · Test")
        self.root.geometry("900x560")
        self.agent = AteCommonAgent(
            db_path=Path.cwd() / "atecommonagent_test.db",
            watch_dir=r"D:\ATS\测试报表",
            parser=flexible_parse_file,
            station_code="COMMON_TEST",
        )
        self.agent.add_listener(self.on_new_rows)
        self.status = tk.StringVar(value="等待测试 / READY")
        tk.Label(root, text="ATE Common Agent 测试", font=("Microsoft YaHei", 18, "bold")).pack(pady=10)
        bar = tk.Frame(root)
        bar.pack(fill="x", padx=12)
        tk.Button(bar, text="测试语音", command=self.test_voice, width=18).pack(side="left", padx=5)
        tk.Button(bar, text="递归扫描文件", command=self.list_files, width=18).pack(side="left", padx=5)
        tk.Button(bar, text="测试 NG / 重复", command=self.test_guard, width=18).pack(side="left", padx=5)
        tk.Button(bar, text="MES切换语音", command=self.test_mes_switch, width=18).pack(side="left", padx=5)
        tk.Button(bar, text="MES新NG语音", command=self.test_mes_ng, width=18).pack(side="left", padx=5)
        tk.Label(root, textvariable=self.status, anchor="w", fg="#075985").pack(fill="x", padx=12, pady=8)
        cards = tk.LabelFrame(root, text="实时卡片 / LIVE CARDS")
        cards.pack(fill="x", padx=12, pady=5)
        self.cards = {}
        for index in range(1, 17):
            side = "L" if index <= 8 else "R"
            channel = f"{side}{index if index <= 8 else index - 8}"
            card = tk.Label(cards, text=f"{channel}\n--", width=16, height=3,
                            bg="#334155", fg="white", font=("Consolas", 10, "bold"), relief="ridge")
            card.grid(row=(index - 1) // 8, column=(index - 1) % 8, padx=3, pady=3)
            self.cards[channel] = card
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=8)
        result_frame = tk.Frame(self.tabs)
        mes_frame = tk.Frame(self.tabs)
        self.tabs.add(result_frame, text="实时结果 / LIVE RESULTS")
        self.tabs.add(mes_frame, text="MES NG缓存 / INCOMING MES NG")
        self.results = ttk.Treeview(result_frame, columns=("file", "sn", "result", "time", "channel"), show="headings")
        for key, label, width in (("file", "文件", 280), ("sn", "SN", 250), ("result", "结果", 90), ("time", "时间", 180), ("channel", "通道", 80)):
            self.results.heading(key, text=label)
            self.results.column(key, width=width, anchor="center")
        self.results.pack(fill="both", expand=True, padx=4, pady=4)
        self.mes_ng = ttk.Treeview(mes_frame, columns=("sn", "source", "reason", "time"), show="headings")
        for key, label, width in (("sn", "SN", 280), ("source", "来源工站", 160), ("reason", "原因", 360), ("time", "接收时间", 180)):
            self.mes_ng.heading(key, text=label)
            self.mes_ng.column(key, width=width, anchor="center")
        self.mes_ng.pack(fill="both", expand=True, padx=4, pady=4)
        self.agent.start_watching(interval=1.0, include_existing=True)
        self.status.set("Watchdog 已启动，等待新记录 / WATCHING")
        self.refresh_mes_cache()

    def write(self, text):
        self.status.set(str(text))

    def on_new_rows(self, rows):
        self.root.after(0, lambda: self._apply_rows(rows))

    def _apply_rows(self, rows):
        for row in rows:
            channel = str(row.get("channel", "")).upper()
            card = self.cards.get(channel)
            if card:
                color = "#991b1b" if row.get("result") == "FAIL" else "#166534"
                card.configure(text=f"{channel}\n{row.get('sn', '--')}", bg=color)
            self.results.insert("", "end", values=(
                Path(str(row.get("source_file", ""))).name,
                row.get("sn", ""), row.get("result", ""),
                row.get("test_time", ""), channel))
        self.status.set(f"新增 {len(rows)} 条 / {len(rows)} NEW RECORDS")

    def test_voice(self):
        self.agent.announce_updates([{"sn": "COMMON-VOICE-TEST"}])
        self.status.set("已调用：文件更新，1条数据。")
        self.write("VOICE: 文件更新，1条数据。")

    def list_files(self):
        files = self.agent.resource_files()
        self.status.set(f"递归找到 {len(files)} 个文件")
        self.write("FILES:")
        for path in files:
            self.write(path)
        self.status.set("Watchdog 已启动，等待新文件记录")

    def test_guard(self):
        self.agent.update_ng("COMMON-NG-TEST", "COMMON TEST NG")
        self.write(self.agent.check_scan("COMMON-NG-TEST"))
        self.write(self.agent.check_scan("COMMON-DUP-TEST"))
        self.write(self.agent.check_scan("COMMON-DUP-TEST"))
        self.status.set("NG / 重复检查完成")

    def test_mes_switch(self):
        self.agent.set_active_mes_endpoint("http://192.168.6.122:8080")
        self.agent.set_active_mes_endpoint("http://127.0.0.1:8080")
        self.status.set("MES切换语音已调用：155 → 122 → localhost")

    def test_mes_ng(self):
        sn = "COMMON-UI-MES-NG"
        self.agent.update_mes_ng(sn, "UI TEST NG", "manu_ict")
        self.mes_ng.insert("", "end", values=(sn, "manu_ict", "UI TEST NG", "NOW"))
        self.write(self.agent.check_scan(sn))
        self.status.set("MES新NG已缓存并拦截")

    def refresh_mes_cache(self):
        try:
            self.mes_ng.delete(*self.mes_ng.get_children())
            with sqlite3.connect(str(self.agent.db_path)) as db:
                rows = db.execute(
                    "SELECT sn,source_station,reason,updated_at FROM atecommon_scan_guard "
                    "WHERE result='NG' ORDER BY updated_at DESC LIMIT 200"
                ).fetchall()
            for sn, source, reason, updated in rows:
                try:
                    display_time = datetime.fromtimestamp(float(updated) / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
                except (TypeError, ValueError, OSError):
                    display_time = str(updated or "")
                self.mes_ng.insert("", "end", values=(sn, source, reason, display_time))
        except Exception:
            pass
        self.root.after(1000, self.refresh_mes_cache)


if __name__ == "__main__":
    app = tk.Tk()
    CommonAgentTestUI(app)
    app.mainloop()
