# -*- coding: utf-8 -*-
"""Persistent PDA/MES heartbeat companion for the manual-line input node."""
import threading
import time
import tkinter as tk
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from station_common_bootstrap import attach_common_agent
from pda_core import PdaCore, STATION_CODE
from station_ui_primitives import install_station_tabs

COMMON_AGENT = attach_common_agent(STATION_CODE, __file__, "pda")


class PdaHeartbeatAgent:
    def __init__(self, root):
        self.root = root
        self.running = True
        self.core = PdaCore()
        root.title("PDA扫码上料 · MES心跳")
        root.geometry("560x220")
        root.configure(bg="#07111f")
        install_station_tabs(root)
        tk.Label(root, text="PDA扫码上料 / PDA LOADING", bg="#07111f", fg="#67e8f9",
                 font=("Microsoft YaHei UI", 20, "bold")).pack(pady=(28, 8))
        self.status = tk.StringVar(value="正在连接 MES...")
        tk.Label(root, textvariable=self.status, bg="#07111f", fg="#fbbf24",
                 font=("Microsoft YaHei UI", 14)).pack(pady=12)
        tk.Label(root, text=f"{STATION_CODE}  →  MES 192.168.6.155:8080",
                 bg="#07111f", fg="#94a3b8", font=("Consolas", 11)).pack()
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        while self.running:
            ok = self.core.heartbeat()
            try:
                self.core.sync_ng_cache(500)
                self.core.sync_outbox(20)
            except Exception:
                pass
            self.root.after(0, self.status.set,
                            "● ONLINE · 心跳每5秒" if ok else "● OFFLINE · 正在自动重连")
            time.sleep(5)

    def close(self):
        self.running = False
        self.root.destroy()


if __name__ == "__main__":
    app = tk.Tk()
    ui = PdaHeartbeatAgent(app)
    app.protocol("WM_DELETE_WINDOW", ui.close)
    app.mainloop()
