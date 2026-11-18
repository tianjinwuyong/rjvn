from __future__ import annotations

import argparse
import os
import socket
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from modular_contract import StationViewModel
from modular_alarm import AlarmBanner
from modular_history import StationHistoryLedger, StationHistoryWindow
from modular_scanner import ScannerGatewayPanel
from modular_repair import RepairWorkflowController, RepairWorkflowWindow, create_preview_case
from modular_i18n import LOCALES, station_name, t, validate as validate_i18n
from station_registry import StationRegistry
from legacy_station_adapter import build_adapter
try:
    from station_common_agent import build_common_agent
except ImportError:  # modular line is kept separate but consumes the same runtime
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "004-手动线"))
    from station_common_agent import build_common_agent
from visualizations import AteEightSnPanel, NgRouteTimeline, StationWorkspace

COLORS = {"bg":"#08131f","panel":"#10243b","card":"#142c46","text":"#edf7ff","muted":"#9eb0bc","cyan":"#18c6d9","green":"#22d887","amber":"#f2b84b","red":"#f05252","blue":"#4c8dff"}


class ModularStationShell:
    def __init__(self, root: tk.Tk, model: StationViewModel, preview: bool = True, smoke: bool = False, on_station_change=None, station_codes=None, locale="en", on_locale_change=None, history_ledger=None, common_agent=None):
        self.root, self.model, self.preview, self.smoke = root, model, preview, bool(smoke)
        station = model.station
        policy = station.ng_policy
        self.on_station_change, self.station_codes = on_station_change, station_codes or []
        self.locale, self.on_locale_change = locale, on_locale_change
        self.history=history_ledger or StationHistoryLedger()
        self.common_agent = common_agent or build_common_agent(
            station.code,
            line_domain="MANUAL_LINE",
            config_version=policy.policy_version,
            equipment_adapter=station.adapter,
            preview=self.preview,
        )
        self.common_agent.register_plugin(station.adapter, build_adapter(station.code, station.adapter))
        self.history.append(model.station.code,"STATION_VIEW_OPENED",source="LOCAL_PREVIEW" if preview else "AGENT",policy_version=model.station.ng_policy.policy_version)
        root.title(f"{model.station.name_zh} / {model.station.name_en} · MODULAR MANUAL LINE")
        root.geometry("1366x768")
        root.minsize(1024, 700)
        root.configure(bg=COLORS["bg"])
        self._build()

    def label(self, parent, text, size=11, color=None, bold=False, **pack):
        widget = tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color or COLORS["text"],
                          font=("Microsoft YaHei UI", size, "bold" if bold else "normal"))
        widget.pack(**pack)
        return widget

    def _build(self):
        station, policy = self.model.station, self.model.station.ng_policy
        header = tk.Frame(self.root, bg=COLORS["panel"], height=68, padx=20, pady=10); header.pack(fill="x"); header.pack_propagate(False)
        self.label(header, f"{station.sequence:02d}  {station_name(self.locale,station.code)}", 18, bold=True, side="left")
        self.label(header, f"{station.code}", 10, COLORS["muted"], side="left", padx=16)
        for code,label in reversed((("zh","中"),("en","EN"),("vi","VI"))):
            tk.Button(header,text=label,command=lambda c=code:self.on_locale_change and self.on_locale_change(c),bg=COLORS["cyan"] if code==self.locale else COLORS["panel"],fg="#061018" if code==self.locale else COLORS["text"],relief="flat",font=("Microsoft YaHei UI",9,"bold"),padx=8).pack(side="right",padx=2,pady=8)
        self.label(header, t(self.locale,"preview") if self.preview else t(self.locale,"production"), 10,
                   COLORS["amber"] if self.preview else COLORS["green"], bold=True, side="right", padx=20)
        if self.on_station_change:
            selected=tk.StringVar(value=station.code)
            chooser=ttk.Combobox(header,textvariable=selected,values=self.station_codes,state="readonly",width=27)
            chooser.pack(side="right",padx=8,pady=8); chooser.bind("<<ComboboxSelected>>",lambda _e:self.on_station_change(selected.get()))

        self.alarm_banner=AlarmBanner(self.root,"●  "+t(self.locale,"no_alarm"),preview=self.preview); self.alarm_banner.pack(fill="x")

        body = tk.Frame(self.root, bg=COLORS["bg"], padx=12, pady=12); body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=COLORS["card"], width=285, padx=16, pady=14); left.pack(side="left", fill="y", padx=(0,10)); left.pack_propagate(False)
        center = tk.Frame(body, bg=COLORS["card"], padx=20, pady=16); center.pack(side="left", fill="both", expand=True, padx=(0,10))
        right = tk.Frame(body, bg=COLORS["card"], width=285, padx=16, pady=14); right.pack(side="right", fill="y"); right.pack_propagate(False)

        self.label(left, t(self.locale,"product_context"), 12, COLORS["cyan"], bold=True, anchor="w")
        for key, value in ((t(self.locale,"product_sn"), "--"),(t(self.locale,"work_order"), t(self.locale,"mes_controlled")),(t(self.locale,"gate"), "UNKNOWN"),(t(self.locale,"reason"), t(self.locale,"waiting_mes")),(t(self.locale,"normal_next"), station.normal_next)):
            row=tk.Frame(left,bg=COLORS["card"]); row.pack(fill="x",pady=7)
            self.label(row,key,9,COLORS["muted"],anchor="w")
            self.label(row,value,11,COLORS["text"],bold=key=="Product Gate",anchor="w")

        self.label(center, t(self.locale,"workspace"), 12, COLORS["cyan"], bold=True, anchor="w")
        self.label(center, "Station-specific adapter: " + station.adapter, 10, COLORS["muted"], anchor="w", pady=(3,10))
        self.scanner=ScannerGatewayPanel(center,self._handle_scan,preview=self.preview); self.scanner.pack(fill="x",pady=(0,8))
        if station.adapter == "ate_8sn":
            self.ate_panel=AteEightSnPanel(center,preview=self.preview,on_cycle_complete=self._ate_cycle_complete,show_scanner=False)
            self.ate_panel.pack(fill="both",expand=True)
            if self.preview:
                self.root.after(350,self.ate_panel.load_preview)
                if self.smoke: self.root.after(1000,self.ate_panel.start_cycle)
        else:
            workspace=StationWorkspace(center,station.adapter,preview=self.preview); workspace.pack(fill="both",expand=True)

        self.label(right,t(self.locale,"result_next"),12,COLORS["cyan"],bold=True,anchor="w")
        for text,color in ((t(self.locale,"idle"),COLORS["muted"]),(t(self.locale,"scan_gate"),COLORS["text"]),(t(self.locale,"authorization"),COLORS["amber"])):
            self.label(right,text,11,color,bold=text=="IDLE",anchor="w",pady=7)
        ttk.Separator(right).pack(fill="x",pady=12)
        self.label(right,t(self.locale,"repair_route"),12,COLORS["red"],bold=True,anchor="w")
        details=[(t(self.locale,"action"),policy.action_mode),(t(self.locale,"retest"),str(policy.retest_limit)),(t(self.locale,"destination"),policy.repair_destination),(t(self.locale,"receipt_sla"),f"{policy.receipt_sla_minutes} min"),(t(self.locale,"repair_sla"),f"{policy.repair_sla_minutes} min"),(t(self.locale,"return"),policy.return_route),(t(self.locale,"policy"),policy.policy_version)]
        for key,value in details:
            self.label(right,f"{key}: {value}",10,COLORS["text"],anchor="w",pady=3)
        tk.Button(right,text=t(self.locale,"open_repair"),command=self._repair_preview,bg=COLORS["red"],fg="white",relief="flat",font=("Microsoft YaHei UI",10,"bold"),pady=10).pack(fill="x",side="bottom")
        tk.Button(right,text="HISTORY / 历史 / LỊCH SỬ",command=lambda:StationHistoryWindow(self.root,self.history,station.code),bg=COLORS["panel"],fg="white",relief="flat",font=("Microsoft YaHei UI",10,"bold"),pady=9).pack(fill="x",side="bottom",pady=(0,7))

        health=tk.Frame(self.root,bg=COLORS["panel"],height=54,padx=16); health.pack(fill="x"); health.pack_propagate(False)
        host=socket.gethostname()
        common_health = self.common_agent.health(scanner_ready=True, equipment_ready=self.preview)
        for key,value in list(self.model.health.items())+[("Host",host),("Common",common_health["agentVersion"]),("Config",common_health["configVersion"])]:
            self.label(health,f"{key}: {value}",9,COLORS["muted"],side="left",padx=10,pady=17)

    def _repair_preview(self):
        if getattr(self,"repair_controller",None):
            RepairWorkflowWindow(self.root,self.repair_controller); return
        win=tk.Toplevel(self.root); win.title("NG Repair Closed Loop · Read-only preview"); win.geometry("1180x620"); win.configure(bg=COLORS["bg"])
        policy=self.model.station.ng_policy
        timeline=NgRouteTimeline(win,policy,current_step="DETECTED"); timeline.pack(fill="both",expand=True,padx=12,pady=12)
        controls=tk.Frame(win,bg=COLORS["bg"]); controls.pack(fill="x",padx=54,pady=(0,14))
        self.label(controls,"Preview state:",10,COLORS["muted"],side="left")
        selected=tk.StringVar(value="DETECTED")
        chooser=ttk.Combobox(controls,textvariable=selected,values=[step.code for step in timeline.steps],state="readonly",width=22); chooser.pack(side="left",padx=10)
        chooser.bind("<<ComboboxSelected>>",lambda _event: timeline.set_current_step(selected.get()))
        self.label(controls,"No MES write · no alarm replay",10,COLORS["amber"],side="right")


    def _handle_scan(self,raw,normalized,scanner_id):
        accepted=True if self.preview else False
        if hasattr(self,"ate_panel"): accepted=self.ate_panel.scan_value(normalized)
        self.history.append(self.model.station.code,"SCAN_ACCEPTED" if accepted else "SCAN_BLOCKED",sn=normalized,result="PREVIEW_ALLOW" if accepted and self.preview else "BLOCK",source="SCANNER",policy_version=self.model.station.ng_policy.policy_version,payload={"raw":raw,"normalized":normalized,"scannerId":scanner_id,"preview":self.preview})
        return accepted

    def _ate_cycle_complete(self, slots):
        ng=next((slot for slot in slots if slot.result=="NG"),None)
        if ng:
            self.model.result="NG_PENDING"; self.model.next_action="MES repair policy evaluation"
            for slot in slots:
                self.history.append(self.model.station.code,"ATE_CYCLE_RESULT",sn=slot.sn,result=slot.result,source="LOCAL_PREVIEW" if self.preview else "EQUIPMENT",policy_version=self.model.station.ng_policy.policy_version,reference=f"cycle-{slot.cycle}",payload={"slot":slot.slot,"failure":slot.failure})
            self.history.append(self.model.station.code,"NG_DETECTED",sn=ng.sn,result="NG_PENDING",source="LOCAL_PREVIEW" if self.preview else "EQUIPMENT",policy_version=self.model.station.ng_policy.policy_version,reference=f"cycle-{ng.cycle}",payload={"failure":ng.failure})
            self.alarm_banner.present(f"smoke-{self.model.station.code}-{getattr(self,'ate_panel').cycle}",f"NEW NG · {ng.sn} · {ng.failure}",is_new=True)
            self.repair_controller=RepairWorkflowController(self.history,create_preview_case(self.model.station.code,ng.sn,ng.failure,self.model.station.ng_policy),preview=self.preview)
            RepairWorkflowWindow(self.root,self.repair_controller)


def main():
    registry=StationRegistry()
    validate_i18n()
    parser=argparse.ArgumentParser(); parser.add_argument("--station",choices=[s.code for s in registry.all()],default=registry.all()[0].code); parser.add_argument("--production",action="store_true"); parser.add_argument("--smoke",action="store_true",help="Run deterministic preview smoke cycle; production writes remain blocked"); parser.add_argument("--gallery",action="store_true",help="Switch among all 13 manual-line station visualizations")
    args=parser.parse_args()
    production=args.production or os.getenv("MODULAR_STATION_PRODUCTION")=="1"
    if args.smoke and production: raise SystemExit("--smoke cannot be combined with --production")
    root=tk.Tk()
    history=StationHistoryLedger()
    current={"code":args.station,"locale":"en"}
    def show(code=None,locale=None):
        if code: current["code"]=code
        if locale: current["locale"]=locale
        for child in root.winfo_children(): child.destroy()
        ModularStationShell(root,StationViewModel(registry.get(current["code"])),preview=not production,smoke=args.smoke and current["code"]==args.station,on_station_change=lambda c:show(code=c) if args.gallery else None,station_codes=[s.code for s in registry.all()],locale=current["locale"],on_locale_change=lambda loc:show(locale=loc),history_ledger=history)
    show(); root.mainloop()


if __name__ == "__main__": main()
