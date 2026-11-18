from __future__ import annotations

from dataclasses import dataclass
import time
import uuid
import tkinter as tk
from tkinter import messagebox, ttk

from modular_contract import RepairPolicy
from modular_history import StationHistoryLedger
from visualizations.ng_route_timeline import NgRouteTimeline


TRANSITIONS={
"NG_DETECTED":{"CONFIRM_NG":"NG_CONFIRMED","MARK_ONLY":"NG_MARKED"},
"NG_MARKED":{"CLOSE":"CLOSED"},
"NG_CONFIRMED":{"SEND_REPAIR":"WAITING_RECEIPT","SCRAP":"SCRAPPED"},
"WAITING_RECEIPT":{"RECEIVE":"REPAIR_RECEIVED"},
"REPAIR_RECEIVED":{"ACTIVATE_ORDER":"REPAIR_ORDER_ACTIVE"},
"REPAIR_ORDER_ACTIVE":{"START_REPAIR":"REPAIR_IN_PROGRESS"},
"REPAIR_IN_PROGRESS":{"COMPLETE_REPAIR":"WAITING_RETEST"},
"WAITING_RETEST":{"AUTHORIZE_RETEST":"RETEST_AUTHORIZED"},
"RETEST_AUTHORIZED":{"START_RETEST":"RETEST_IN_PROGRESS"},
"RETEST_IN_PROGRESS":{"RETEST_PASS":"REPAIRED_PASS","RETEST_NG":"REPAIR_NG"},
"REPAIRED_PASS":{"RETURN_ROUTE":"RETURNED_TO_ROUTE"},
"RETURNED_TO_ROUTE":{"CLOSE":"CLOSED"},
"REPAIR_NG":{"REPEAT_REPAIR":"REPAIR_ORDER_ACTIVE","PRODUCT_REPLACE":"PRODUCT_REPLACED","SPECIAL_RELEASE":"SPECIAL_RELEASED","SCRAP":"SCRAPPED"},
"PRODUCT_REPLACED":{"RETURN_ROUTE":"RETURNED_TO_ROUTE"},
"SPECIAL_RELEASED":{"RETURN_ROUTE":"RETURNED_TO_ROUTE"},
"SCRAPPED":{"CLOSE":"CLOSED"}}

ACTION_ROLES={"CONFIRM_NG":{"OPERATOR","QC","LINE_LEADER"},"SEND_REPAIR":{"OPERATOR","QC","LINE_LEADER"},"RECEIVE":{"REPAIR"},"ACTIVATE_ORDER":{"REPAIR"},"START_REPAIR":{"REPAIR"},"COMPLETE_REPAIR":{"REPAIR"},"AUTHORIZE_RETEST":{"QC","LINE_LEADER","ENGINEER"},"START_RETEST":{"OPERATOR","QC"},"RETEST_PASS":{"OPERATOR","QC"},"RETEST_NG":{"OPERATOR","QC"},"REPEAT_REPAIR":{"REPAIR","ENGINEER"},"PRODUCT_REPLACE":{"QC","LINE_LEADER"},"SPECIAL_RELEASE":{"QC","ENGINEER"},"SCRAP":{"QC","LINE_LEADER","ENGINEER"},"RETURN_ROUTE":{"OPERATOR","QC"},"MARK_ONLY":{"QC"},"CLOSE":{"QC","LINE_LEADER"}}


@dataclass
class RepairCase:
    case_id:str; station_code:str; sn:str; failure:str; policy:RepairPolicy
    state:str="NG_DETECTED"; repair_attempts:int=0; created_at:int=0; received_at:int=0; closed_at:int=0
    def __post_init__(self): self.created_at=self.created_at or int(time.time()*1000)


class RepairWorkflowController:
    def __init__(self,ledger:StationHistoryLedger,case:RepairCase,preview=True):
        self.ledger,self.case,self.preview=ledger,case,preview
        self._record("NG_DETECTED","SYSTEM","SYSTEM",case.failure)
    def allowed_actions(self): return list(TRANSITIONS.get(self.case.state,{}))
    def execute(self,action,actor,role,reason):
        action,role=action.upper(),role.upper(); actor=actor.strip(); reason=reason.strip()
        if not self.preview: raise RuntimeError("Production repair command adapter is not connected")
        target=TRANSITIONS.get(self.case.state,{}).get(action)
        if not target: raise ValueError(f"{action} is not allowed from {self.case.state}")
        if role not in ACTION_ROLES.get(action,set()): raise PermissionError(f"{role} cannot perform {action}")
        if not actor or not reason: raise ValueError("Actor and reason are required")
        if action=="REPEAT_REPAIR":
            if self.case.repair_attempts>=self.case.policy.max_repair_attempts: raise ValueError("Maximum repair attempts reached")
            self.case.repair_attempts+=1
        if action=="START_REPAIR" and self.case.repair_attempts==0: self.case.repair_attempts=1
        now=int(time.time()*1000)
        if action=="RECEIVE": self.case.received_at=now
        if target=="CLOSED": self.case.closed_at=now
        previous=self.case.state; self.case.state=target; self._record(action,actor,role,reason,{"from":previous,"to":target,"repairAttempts":self.case.repair_attempts})
        return target
    def sla(self):
        now=int(time.time()*1000); receipt_deadline=self.case.created_at+self.case.policy.receipt_sla_minutes*60000; repair_start=self.case.received_at or now; repair_deadline=repair_start+self.case.policy.repair_sla_minutes*60000
        return {"receiptRemainingSeconds":max(0,(receipt_deadline-now)//1000),"receiptOverdue":not self.case.received_at and now>receipt_deadline,"repairRemainingSeconds":max(0,(repair_deadline-now)//1000)}
    def _record(self,event,actor,role,reason,payload=None):
        body={"caseId":self.case.case_id,"state":self.case.state,"role":role,"reason":reason}; body.update(payload or {})
        self.ledger.append(self.case.station_code,event,sn=self.case.sn,result=self.case.state,actor=actor,source="LOCAL_PREVIEW" if self.preview else "MES",policy_version=self.case.policy.policy_version,reference=self.case.case_id,payload=body)


class RepairWorkflowWindow:
    def __init__(self,parent,controller:RepairWorkflowController):
        self.controller=controller; self.window=tk.Toplevel(parent); self.window.title("REPAIR CLOSED LOOP · FULL FUNCTION PREVIEW"); self.window.geometry("1240x760"); self.window.configure(bg="#08131f")
        self.window.geometry("1440x820"); self.window.minsize(1180,700)
        self.actor=tk.StringVar(value="VN_OP_001"); self.role=tk.StringVar(value="OPERATOR"); self.reason=tk.StringVar(value="Preview workflow verification"); self.state=tk.StringVar(); self.sla=tk.StringVar(); self.history_status=tk.StringVar(); self._build(); self.refresh()
    def _build(self):
        case=self.controller.case; head=tk.Frame(self.window,bg="#10243b",padx=16,pady=10); head.pack(fill="x")
        tk.Label(head,text=f"{case.sn}  ·  {case.failure}",bg="#10243b",fg="white",font=("Microsoft YaHei UI",15,"bold")).pack(side="left")
        tk.Label(head,textvariable=self.state,bg="#10243b",fg="#f2b84b",font=("Microsoft YaHei UI",12,"bold")).pack(side="right")
        content=tk.PanedWindow(self.window,orient="horizontal",bg="#08131f",sashwidth=6,sashrelief="flat")
        content.pack(fill="both",expand=True,padx=12,pady=10)
        route_tab=tk.Frame(content,bg="#08131f"); history_tab=tk.Frame(content,bg="#10243b")
        content.add(route_tab,minsize=500,stretch="always"); content.add(history_tab,minsize=570,stretch="always")
        tk.Label(route_tab,text="NG ROUTE / NG 路由",bg="#08131f",fg="white",font=("Microsoft YaHei UI",12,"bold"),anchor="w").pack(fill="x",padx=8,pady=(4,2))
        self.timeline=NgRouteTimeline(route_tab,case.policy,"DETECTED"); self.timeline.pack(fill="both",expand=True)
        history_head=tk.Frame(history_tab,bg="#10243b",padx=10,pady=8); history_head.pack(fill="x")
        tk.Label(history_head,text="REPAIR HISTORY / 维修历史",bg="#10243b",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left")
        tk.Label(history_head,textvariable=self.history_status,bg="#10243b",fg="#18c6d9",font=("Microsoft YaHei UI",10,"bold")).pack(side="right")
        cols=("time","event","state","actor","role","reason","policy")
        self.history_tree=ttk.Treeview(history_tab,columns=cols,show="headings")
        for key,width in zip(cols,(160,180,170,100,100,280,130)): self.history_tree.heading(key,text=key.upper()); self.history_tree.column(key,width=width,anchor="center")
        scroll=ttk.Scrollbar(history_tab,orient="vertical",command=self.history_tree.yview); self.history_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right",fill="y",padx=(0,6),pady=(0,8)); self.history_tree.pack(side="left",fill="both",expand=True,padx=(8,0),pady=(0,8))
        form=tk.Frame(self.window,bg="#142c46",padx=12,pady=10); form.pack(fill="x",padx=16)
        for label,var,width in (("Actor",self.actor,16),("Role",self.role,16),("Reason",self.reason,38)):
            tk.Label(form,text=label,bg="#142c46",fg="#9eb0bc").pack(side="left",padx=(8,4)); tk.Entry(form,textvariable=var,width=width).pack(side="left")
        tk.Label(form,textvariable=self.sla,bg="#142c46",fg="#18c6d9",font=("Microsoft YaHei UI",9,"bold")).pack(side="right",padx=8)
        self.actions=tk.Frame(self.window,bg="#08131f",padx=16,pady=12); self.actions.pack(fill="both",expand=True)
        tk.Label(self.window,text="Preview only · every transition is authorized, state-checked and appended to immutable history · no MES production write",bg="#08131f",fg="#f2b84b",font=("Microsoft YaHei UI",9,"bold")).pack(pady=(0,12))
    def refresh(self):
        case=self.controller.case; self.state.set(f"STATE: {case.state}  ·  CASE: {case.case_id}  ·  ATTEMPT: {case.repair_attempts}/{case.policy.max_repair_attempts}")
        data=self.controller.sla(); self.sla.set(f"Receipt SLA {data['receiptRemainingSeconds']//60:02d}:{data['receiptRemainingSeconds']%60:02d}  ·  Repair SLA {data['repairRemainingSeconds']//60:02d}:{data['repairRemainingSeconds']%60:02d}")
        for child in self.actions.winfo_children(): child.destroy()
        for index,action in enumerate(self.controller.allowed_actions()):
            tk.Button(self.actions,text=action.replace("_"," "),command=lambda a=action:self.run(a),bg="#f05252" if action in {"SCRAP","RETEST_NG"} else "#4c8dff",fg="white",relief="flat",font=("Microsoft YaHei UI",10,"bold"),padx=15,pady=11).grid(row=index//4,column=index%4,sticky="ew",padx=5,pady=5)
        for col in range(4): self.actions.grid_columnconfigure(col,weight=1)
        self._refresh_history()
        self.window.after(1000,self._tick)
    def _refresh_history(self):
        self.history_tree.delete(*self.history_tree.get_children())
        count=0
        for row in self.controller.ledger.list(self.controller.case.station_code):
            if row.get("reference")!=self.controller.case.case_id: continue
            try:
                import json
                payload=json.loads(row.get("payload_json") or "{}")
            except Exception: payload={}
            stamp=time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(row["occurred_at"]/1000))
            self.history_tree.insert("","end",values=(stamp,row["event_type"],row["result"],row["actor"],payload.get("role",""),payload.get("reason",""),row["policy_version"]))
            count+=1
        self.history_status.set(f"{count} EVENT{'S' if count != 1 else ''} · LIVE")
    def _tick(self):
        if self.window.winfo_exists():
            data=self.controller.sla(); self.sla.set(f"Receipt SLA {data['receiptRemainingSeconds']//60:02d}:{data['receiptRemainingSeconds']%60:02d}  ·  Repair SLA {data['repairRemainingSeconds']//60:02d}:{data['repairRemainingSeconds']%60:02d}"); self.window.after(1000,self._tick)
    def run(self,action):
        try: self.controller.execute(action,self.actor.get(),self.role.get(),self.reason.get()); self.refresh()
        except Exception as exc: messagebox.showerror("Action blocked",str(exc),parent=self.window)


def create_preview_case(station_code,sn,failure,policy): return RepairCase("RPR-"+uuid.uuid4().hex[:10].upper(),station_code,sn,failure,policy)
