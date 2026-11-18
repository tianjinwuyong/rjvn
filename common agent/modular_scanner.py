from __future__ import annotations
import re
import time
import tkinter as tk

class ScannerGatewayPanel(tk.Frame):
    def __init__(self,parent,on_scan,preview=True,duplicate_window_ms=1500):
        super().__init__(parent,bg="#142c46"); self.on_scan=on_scan; self.preview=preview; self.window=duplicate_window_ms; self.last={}; self.value=tk.StringVar(); self.status=tk.StringVar(value="SCANNER READY · keyboard wedge · PREVIEW" if preview else "SCANNER READY")
        tk.Label(self,text="SCANNER GATEWAY",bg="#142c46",fg="#18c6d9",font=("Microsoft YaHei UI",9,"bold")).pack(side="left",padx=(0,8))
        self.entry=tk.Entry(self,textvariable=self.value,font=("Consolas",14),bg="#07111f",fg="#edf7ff",insertbackground="#18c6d9",relief="flat"); self.entry.pack(side="left",fill="x",expand=True,ipady=7); self.entry.bind("<Return>",self.submit)
        tk.Button(self,text="SCAN",command=self.submit,bg="#4c8dff",fg="white",relief="flat",font=("Microsoft YaHei UI",9,"bold"),padx=16,pady=7).pack(side="left",padx=7)
        tk.Label(self,textvariable=self.status,bg="#142c46",fg="#9eb0bc",font=("Microsoft YaHei UI",8),width=31,anchor="w").pack(side="right")
    @staticmethod
    def normalize(raw): return re.sub(r"\s+","",str(raw or "")).upper()
    def submit(self,_event=None):
        raw=self.value.get(); self.value.set(""); normalized=self.normalize(raw)
        if not normalized: self.status.set("EMPTY SCAN BLOCKED"); return
        now=int(time.time()*1000)
        if now-self.last.get(normalized,0)<self.window: self.status.set("DUPLICATE BLOCKED · "+normalized); return
        self.last[normalized]=now; accepted=bool(self.on_scan(raw,normalized,"keyboard_wedge"))
        self.status.set(("ACCEPTED · " if accepted else "BLOCKED · ")+normalized)
        self.entry.focus_set()
