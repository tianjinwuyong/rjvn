from __future__ import annotations
import tkinter as tk

class AlarmBanner(tk.Frame):
    COLORS={"NORMAL":"#17283a","NEW":"#b42318","HISTORICAL":"#5c3b12","OFFLINE":"#8a5a00","UNAUTHORIZED":"#7f1d1d"}
    def __init__(self,parent,text,preview=False):
        super().__init__(parent,bg=self.COLORS["NORMAL"],height=48,padx=20); self.pack_propagate(False)
        self.preview=preview; self.seen=set(); self.label=tk.Label(self,text=text,bg=self.COLORS["NORMAL"],fg="#9eb0bc",font=("Microsoft YaHei UI",11,"bold")); self.label.pack(side="left",pady=13)
    def present(self,event_id,message,is_new=True):
        if not event_id: raise ValueError("Alarm event ID is required")
        new=is_new and event_id not in self.seen; self.seen.add(event_id)
        state="NEW" if new else "HISTORICAL"; self.configure(bg=self.COLORS[state]); self.label.configure(text=message,bg=self.COLORS[state],fg="white")
        if new: self.after(4000,lambda:self.present(event_id,message,is_new=False))
        return new
