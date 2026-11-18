from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from typing import Callable, List, Optional


@dataclass
class AteSlotState:
    slot: int
    sn: str = ""
    result: str = "EMPTY"
    failure: str = ""
    cycle: int = 0


class AteEightSnPanel(tk.Frame):
    COLORS = {"bg":"#142c46","well":"#0c1c2c","empty":"#63788a","ready":"#4c8dff",
              "testing":"#f2b84b","pass":"#22d887","ng":"#f05252","text":"#edf7ff","muted":"#9eb0bc"}

    def __init__(self, parent, preview=True, on_gate: Optional[Callable[[str], bool]]=None,
                 on_cycle_complete: Optional[Callable[[List[AteSlotState]], None]]=None, show_scanner=True):
        super().__init__(parent,bg=self.COLORS["bg"])
        self.preview=preview; self.on_gate=on_gate; self.on_cycle_complete=on_cycle_complete; self.show_scanner=show_scanner
        self.slots=[AteSlotState(i+1) for i in range(8)]; self.slot_widgets=[]; self.cycle=0
        self.scan=tk.StringVar(); self.status=tk.StringVar(value="Waiting for 8 products")
        self._build()

    def _build(self):
        top=tk.Frame(self,bg=self.COLORS["bg"]); top.pack(fill="x")
        if self.show_scanner:
            tk.Label(top,text="SCAN PRODUCT SN",bg=self.COLORS["bg"],fg=self.COLORS["muted"],font=("Microsoft YaHei UI",9,"bold")).pack(anchor="w")
            entry=tk.Entry(top,textvariable=self.scan,font=("Consolas",16),bg="#07111f",fg=self.COLORS["text"],insertbackground="#18c6d9",relief="flat")
            entry.pack(side="left",fill="x",expand=True,ipady=9,pady=(4,10)); entry.bind("<Return>",self._scan)
            tk.Button(top,text="ADD",command=self._scan,bg="#4c8dff",fg="white",relief="flat",font=("Microsoft YaHei UI",10,"bold"),padx=20,pady=9).pack(side="right",padx=(8,0),pady=(4,10))
        grid=tk.Frame(self,bg=self.COLORS["bg"]); grid.pack(fill="both",expand=True)
        for index,state in enumerate(self.slots):
            card=tk.Frame(grid,bg=self.COLORS["well"],highlightthickness=2,highlightbackground="#27445e",padx=10,pady=8)
            card.grid(row=index//4,column=index%4,sticky="nsew",padx=4,pady=4)
            number=tk.Label(card,text=f"SLOT {state.slot}",bg=self.COLORS["well"],fg=self.COLORS["muted"],font=("Microsoft YaHei UI",9,"bold")); number.pack(anchor="w")
            sn=tk.Label(card,text="EMPTY",bg=self.COLORS["well"],fg=self.COLORS["text"],font=("Consolas",11,"bold"),wraplength=135); sn.pack(anchor="w",pady=(9,4))
            result=tk.Label(card,text="EMPTY",bg=self.COLORS["empty"],fg="white",font=("Microsoft YaHei UI",10,"bold"),padx=8,pady=4); result.pack(fill="x")
            failure=tk.Label(card,text="--",bg=self.COLORS["well"],fg=self.COLORS["muted"],font=("Microsoft YaHei UI",8),wraplength=135); failure.pack(anchor="w",pady=(6,0))
            self.slot_widgets.append((card,sn,result,failure))
        for col in range(4): grid.grid_columnconfigure(col,weight=1)
        for row in range(2): grid.grid_rowconfigure(row,weight=1)
        footer=tk.Frame(self,bg=self.COLORS["bg"]); footer.pack(fill="x",pady=(10,0))
        tk.Label(footer,textvariable=self.status,bg=self.COLORS["bg"],fg="#18c6d9",font=("Microsoft YaHei UI",10,"bold")).pack(side="left")
        self.run=tk.Button(footer,text="START A-T-E CYCLE",command=self.start_cycle,bg="#22d887",fg="#061018",relief="flat",font=("Microsoft YaHei UI",11,"bold"),padx=24,pady=9,state="disabled")
        self.run.pack(side="right")

    def _scan(self,_event=None):
        value=self.scan.get().strip().upper(); self.scan.set("")
        if not value: return
        if any(row.sn==value for row in self.slots): self.status.set("Duplicate SN blocked: "+value); return
        target=next((row for row in self.slots if not row.sn),None)
        if target is None: self.status.set("Cycle is full"); return
        allowed=True if self.preview or self.on_gate is None else bool(self.on_gate(value))
        if not allowed: self.status.set("MES Product Gate rejected: "+value); return
        target.sn=value; target.result="READY"; self._paint(target)
        loaded=sum(bool(row.sn) for row in self.slots); self.status.set(f"Loaded {loaded}/8 · Product Gate {'PREVIEW' if self.preview else 'ALLOW'}")
        self.run.configure(state="normal" if loaded==8 else "disabled")

    def scan_value(self,value):
        before=sum(bool(row.sn) for row in self.slots); self.scan.set(value); self._scan(); return sum(bool(row.sn) for row in self.slots)>before

    def load_preview(self):
        for index in range(8):
            self.scan.set(f"RJ-MOD-ATE-{index+1:04d}"); self._scan()

    def start_cycle(self):
        if any(not row.sn for row in self.slots): self.status.set("Eight valid SNs are required"); return
        self.cycle+=1; self.run.configure(state="disabled"); self.status.set(f"Cycle {self.cycle} running · equipment adapter PREVIEW")
        for row in self.slots: row.result="TESTING"; row.failure=""; row.cycle=self.cycle; self._paint(row)
        self.after(700,self._finish_preview if self.preview else self._wait_for_equipment)

    def _finish_preview(self):
        for row in self.slots:
            row.result="NG" if row.slot==3 else "PASS"
            row.failure="Insulation resistance below limit" if row.result=="NG" else "All checks passed"
            self._paint(row)
        self.status.set(f"Cycle {self.cycle} complete · PASS 7 · NG 1 · NG route opened")
        if self.on_cycle_complete: self.on_cycle_complete(list(self.slots))

    def _wait_for_equipment(self):
        self.status.set("Waiting for authorized equipment adapter result")

    def _paint(self,state:AteSlotState):
        card,sn,result,failure=self.slot_widgets[state.slot-1]
        key=state.result.lower(); color=self.COLORS.get(key,self.COLORS["empty"])
        card.configure(highlightbackground=color); sn.configure(text=state.sn or "EMPTY")
        result.configure(text=state.result,bg=color); failure.configure(text=state.failure or "--")
