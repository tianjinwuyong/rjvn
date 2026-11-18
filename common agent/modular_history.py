from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time
import uuid
import tkinter as tk
from tkinter import ttk


class StationHistoryLedger:
    """Append-only local edge ledger; MES remains the production audit authority."""
    def __init__(self, db_path=None):
        self.db_path=Path(db_path or Path(__file__).with_name("runtime").joinpath("modular_history.db"))
        self.db_path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def connect(self):
        db=sqlite3.connect(str(self.db_path)); db.row_factory=sqlite3.Row; return db
    def _init(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS station_history(
              event_id TEXT PRIMARY KEY, station_code TEXT NOT NULL, event_type TEXT NOT NULL,
              sn TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '', actor TEXT NOT NULL DEFAULT '',
              source TEXT NOT NULL, policy_version TEXT NOT NULL DEFAULT '', reference TEXT NOT NULL DEFAULT '',
              payload_json TEXT NOT NULL DEFAULT '{}', occurred_at INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_station_history_station_time ON station_history(station_code,occurred_at DESC);
            CREATE TRIGGER IF NOT EXISTS station_history_no_update BEFORE UPDATE ON station_history
              BEGIN SELECT RAISE(ABORT,'station history is immutable'); END;
            CREATE TRIGGER IF NOT EXISTS station_history_no_delete BEFORE DELETE ON station_history
              BEGIN SELECT RAISE(ABORT,'station history is immutable'); END;
            """)
    def append(self,station_code,event_type,sn="",result="",actor="PREVIEW",source="LOCAL_PREVIEW",policy_version="",reference="",payload=None,event_id=None):
        row=(event_id or str(uuid.uuid4()),station_code,event_type,str(sn),str(result),str(actor),str(source),str(policy_version),str(reference),json.dumps(payload or {},ensure_ascii=False,sort_keys=True),int(time.time()*1000))
        with self.connect() as db: db.execute("INSERT OR IGNORE INTO station_history VALUES(?,?,?,?,?,?,?,?,?,?,?)",row)
        return row[0]
    def list(self,station_code,limit=250):
        with self.connect() as db: return [dict(row) for row in db.execute("SELECT * FROM station_history WHERE station_code=? ORDER BY occurred_at DESC,event_id DESC LIMIT ?",(station_code,int(limit)))]


class StationHistoryWindow:
    def __init__(self,parent,ledger,station_code):
        self.ledger,self.station_code=ledger,station_code; self.window=tk.Toplevel(parent); self.window.title("Station History / 工站历史 / Lịch sử trạm"); self.window.geometry("1180x620"); self.window.configure(bg="#08131f")
        head=tk.Frame(self.window,bg="#10243b",padx=16,pady=10); head.pack(fill="x")
        tk.Label(head,text=f"IMMUTABLE STATION HISTORY  ·  {station_code}",bg="#10243b",fg="white",font=("Microsoft YaHei UI",15,"bold")).pack(side="left")
        tk.Button(head,text="REFRESH",command=self.refresh,bg="#4c8dff",fg="white",relief="flat",padx=16,pady=6).pack(side="right")
        cols=("time","event","sn","result","actor","source","policy","reference")
        self.tree=ttk.Treeview(self.window,columns=cols,show="headings")
        widths=(165,190,180,90,100,120,120,150)
        for key,width in zip(cols,widths): self.tree.heading(key,text=key.upper()); self.tree.column(key,width=width,anchor="center")
        self.tree.pack(fill="both",expand=True,padx=12,pady=12); self.refresh()
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for row in self.ledger.list(self.station_code):
            stamp=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(row["occurred_at"]/1000))
            self.tree.insert("","end",values=(stamp,row["event_type"],row["sn"],row["result"],row["actor"],row["source"],row["policy_version"],row["reference"]))
