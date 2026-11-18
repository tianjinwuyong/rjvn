# -*- coding: utf-8 -*-
"""Non-recursive AOI MySQL/MES companion with persistent heartbeat."""
import threading
import time
import tkinter as tk
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from station_common_bootstrap import attach_common_agent
from aoi_core import AoiCore, STATION_CODE
from station_ui_primitives import install_station_tabs

COMMON_AGENT = attach_common_agent(STATION_CODE, __file__, "aoi")


class AoiHeartbeatAgent:
    def __init__(self, root):
        self.root=root;self.running=True;self.core=AoiCore();install_station_tabs(root)
        root.title("AOI质量工位 · MES数据同步");root.geometry("620x250");root.configure(bg="#07111f")
        tk.Label(root,text="AOI质量工位 / AOI QUALITY",bg="#07111f",fg="#67e8f9",
                 font=("Microsoft YaHei UI",20,"bold")).pack(pady=(28,8))
        self.status=tk.StringVar(value="正在连接 MES...")
        self.source=tk.StringVar(value="MySQL：正在检查")
        tk.Label(root,textvariable=self.status,bg="#07111f",fg="#fbbf24",font=("Microsoft YaHei UI",14)).pack(pady=7)
        tk.Label(root,textvariable=self.source,bg="#07111f",fg="#94a3b8",font=("Microsoft YaHei UI",11)).pack()
        tk.Label(root,text=f"{STATION_CODE} → MES 192.168.6.155:8080",bg="#07111f",fg="#64748b",font=("Consolas",10)).pack(pady=8)
        threading.Thread(target=self.worker,daemon=True).start()
    def worker(self):
        while self.running:
            ok=self.core.heartbeat();source="MySQL：连接失败，继续重试"
            try:
                _last,added,error=self.core.process_mysql(500)
                self.core.sync_outbox(20)
                source=f"MySQL：{'正常' if not error else error} · 新增 {added}"
            except Exception as exc:source=f"MySQL：{str(exc)[:100]}"
            self.root.after(0,self.status.set,"● ONLINE · 心跳每5秒" if ok else "● OFFLINE · 正在自动重连")
            self.root.after(0,self.source.set,source);time.sleep(5)
    def close(self):self.running=False;self.root.destroy()

if __name__=="__main__":
    root=tk.Tk();app=AoiHeartbeatAgent(root);root.protocol("WM_DELETE_WINDOW",app.close);root.mainloop()
