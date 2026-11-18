# -*- coding: utf-8 -*-
import datetime,os,sys,subprocess,threading,tkinter as tk
from pathlib import Path
from types import SimpleNamespace
from tkinter import filedialog,messagebox,simpledialog,ttk

APP_DIR=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.dirname(APP_DIR))
from station_common_bootstrap import attach_common_agent
COMMON_AGENT = attach_common_agent("manu_pallet_binding", __file__, "pallet-binding")

from pallet_binding_core import PalletBindingStore,PalletError
from station_retest import install_station_retest_panel
from station_i18n import TrilingualController
from station_ui_primitives import UI_PREVIEW, add_preview_watermark, configure_tk_station, register_scanner_entry, restore_scanner_focus
from station_arrival_ui import ProductGateComponent


class _PalletPreviewStore:
 def active_work_order(self):return "WO-PREVIEW-20260804"
 def selected_print_template(self):return "PREVIEW_LABEL.btw"
 def work_order_codes(self):return ["WO-PREVIEW-20260804"]
 def available_print_templates(self):return [SimpleNamespace(name="PREVIEW_LABEL.btw")]
 def work_order_bypass(self):return False
 def snapshot(self,*_args):
  cartons=[{"position":i,"carton_sn":f"BOX-PREVIEW-{i:03d}","upstream_verified":i<7} for i in range(1,9)]
  return [{"pallet_sn":"PLT-PREVIEW-0001","work_order_code":"WO-PREVIEW-20260804","carton_count":8,"target_cartons":20,"status":"OPEN","mes_synced":False,"cartons":cartons}]
 def resource_tables(self,*_args):return {}
 def search_pallets(self,*_args):return []
 def refresh_mes_context(self):return None
 def sync_once(self):return None
 def heartbeat_once(self):return None
 def _blocked(self,*_args,**_kwargs):raise PalletError("UI_PREVIEW blocks production writes")
 create_pallet=add_carton=remove_carton=seal_pallet=set_print_template=import_print_template=select_work_order=set_work_order_bypass=reprint_pallet_label=_print_pallet_label=_blocked

def speak(t):subprocess.Popen(["powershell","-NoProfile","-Command","Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;$s.Speak('%s')"%t],creationflags=0x08000000)

class Pallet2D:
 def __init__(self,root):
  self.root,self.store,self.current=root,(_PalletPreviewStore() if UI_PREVIEW else PalletBindingStore()),("PLT-PREVIEW-0001" if UI_PREVIEW else "");self._sync_lock=threading.Lock();root.title("栈板绑码 / PALLET BINDING 2D");configure_tk_station(root);add_preview_watermark(root);self.status=tk.StringVar(value="PREVIEW · deterministic sample · all writes blocked" if UI_PREVIEW else "等待 MES 下发工单 WO");self.wo=tk.StringVar(value="MES WO: --");self.wo_choice=tk.StringVar(value=self.store.active_work_order());self.target=tk.StringVar(value="20");self.carton=tk.StringVar();self.print_template=tk.StringVar(value=self.store.selected_print_template());self._build();self.language=TrilingualController(root,self.header_actions,use_place=False);self.refresh()
  if not UI_PREVIEW:root.after(500,self.heartbeat_tick);root.after(2000,self.tick)
 def _build(self):
  s=ttk.Style();s.theme_use("clam");h=tk.Frame(self.root,bg="#10243b",padx=18,pady=10);self.header=h;h.pack(fill="x");tk.Label(h,text="栈板绑码  PALLET BINDING",bg="#10243b",fg="white",font=("Microsoft YaHei UI",20,"bold")).pack(side="left");tk.Label(h,textvariable=self.status,bg="#10243b",fg="#38bdf8",font=("Microsoft YaHei UI",12,"bold")).pack(side="right",padx=(12,16));action_strip=tk.Frame(self.root,bg="#101d27",padx=18,pady=6);action_strip.pack(fill="x");self.header_actions=tk.Frame(action_strip,bg="#101d27");self.header_actions.pack(side="right");self.root._retest_host=self.header_actions
  self.product_gate=ProductGateComponent(self.root)
  bar=tk.Frame(self.root,bg="#07111f",padx=18,pady=14);bar.pack(fill="x");
  tk.Label(bar,text="MES WO",bg="#07111f",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=(0,4))
  self.wo_box=ttk.Combobox(bar,textvariable=self.wo_choice,values=self.store.work_order_codes(),state="readonly",width=18,font=("Consolas",14));self.wo_box.pack(side="left",padx=(0,8));self.wo_box.bind("<<ComboboxSelected>>",self.select_wo)
  self.wo_bypass_btn=tk.Button(bar,text="临时绕过 WO 锁",command=self.toggle_wo_bypass,width=15,bg="#334155",fg="white",font=("Microsoft YaHei UI",11,"bold"));self.wo_bypass_btn.pack(side="left",padx=(0,8))
  for label,var,w in (("目标箱数",self.target,6),("外箱码",self.carton,20)):
   tk.Label(bar,text=label,bg="#07111f",fg="white",font=("Microsoft YaHei UI",12)).pack(side="left",padx=(8,3))
   if var is self.target:e=ttk.Combobox(bar,textvariable=var,values=("20","24"),state="normal",width=w,font=("Consolas",16))
   else:e=tk.Entry(bar,textvariable=var,width=w);register_scanner_entry(self.root,e)
   e.pack(side="left")
   if var is self.carton:self.carton_entry=e;e.bind("<Return>",lambda _e:self.add());restore_scanner_focus(self.root,e)
  tk.Button(bar,text="加入外箱",command=self.add,bg="#059669",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=8)
  tk.Button(bar,text="移除破损外箱",command=self.remove_broken,bg="#b91c1c",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=4)
  tk.Button(bar,text="尾数封栈",command=self.seal_partial,bg="#7c3aed",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=4)
  tk.Button(bar,text="补打标签",command=self.open_reprint_tab,bg="#d97706",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=4)
  tplbar=tk.Frame(self.root,bg="#07111f",padx=18);tplbar.pack(fill="x",pady=(0,10))
  tk.Label(tplbar,text="打印模板",bg="#07111f",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=(0,5))
  self.template_box=ttk.Combobox(tplbar,textvariable=self.print_template,values=[p.name for p in self.store.available_print_templates()],state="readonly",width=34,font=("Segoe UI",11));self.template_box.pack(side="left",padx=(0,8));self.template_box.bind("<<ComboboxSelected>>",self.template_changed)
  tk.Button(tplbar,text="添加打印模板",command=self.add_print_template,bg="#0369a1",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left")
  self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill="both",expand=True,padx=18,pady=(0,10));live=tk.Frame(self.tabs,bg="#07111f");self.tabs.add(live,text="实时绑定 / LIVE")
  visual=tk.LabelFrame(live,text=" 栈板外箱可视化 / PALLET BOXES ",bg="#0f1e31",fg="white",font=("Microsoft YaHei UI",13,"bold"));visual.pack(fill="x",padx=6,pady=(4,8))
  self.slot_panel=tk.Frame(visual,bg="#0f1e31");self.slot_panel.pack(fill="x",padx=12,pady=10);self.slot_labels=[]
  body=tk.Frame(live,bg="#07111f",padx=6);body.pack(fill="both",expand=True);self.items=ttk.Treeview(body,columns=("pos","carton","verified"),show="headings");self.items.heading("pos",text="#");self.items.heading("carton",text="外箱码");self.items.heading("verified",text="上游确认");self.items.column("pos",width=60,anchor="center");self.items.column("verified",width=120,anchor="center");self.items.pack(side="left",fill="both",expand=True,padx=(0,8));self.history=ttk.Treeview(body,columns=("pallet","wo","count","target","status","mes"),show="headings");
  for k,t in (("pallet","栈板码"),("wo","工单 WO"),("count","箱数"),("target","目标"),("status","状态"),("mes","MES")):self.history.heading(k,text=t)
  self.history.pack(side="left",fill="both",expand=True,padx=(8,0));self.history.bind("<<TreeviewSelect>>",self.select)
  self.carton_menu=tk.Menu(self.root,tearoff=0);self.carton_menu.add_command(label="移除破损外箱",command=self.remove_broken)
  self.items.bind("<Button-3>",self.show_carton_actions);self.items.bind("<Double-1>",self.show_carton_actions)
  self.resource_frames={}
  reprint=tk.Frame(self.tabs,bg="#07111f");self.reprint_tab=reprint;self.tabs.add(reprint,text="补打标签 / REPRINT")
  reprint_bar=tk.Frame(reprint,bg="#07111f",padx=14,pady=12);reprint_bar.pack(fill="x")
  tk.Label(reprint_bar,text="产品SN / 外箱SN / 栈板SN",bg="#07111f",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left")
  self.reprint_search=tk.StringVar();entry=tk.Entry(reprint_bar,textvariable=self.reprint_search,width=28,font=("Consolas",15));entry.pack(side="left",padx=8)
  entry.bind("<Return>",lambda _e:self.refresh_reprint())
  tk.Button(reprint_bar,text="查找",command=self.refresh_reprint,bg="#2563eb",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=4)
  tk.Button(reprint_bar,text="补打所选标签",command=self.reprint_selected,bg="#d97706",fg="white",font=("Microsoft YaHei UI",11,"bold")).pack(side="left",padx=4)
  self.reprint_tree=ttk.Treeview(reprint,columns=("pallet","wo","count","target","time"),show="headings",selectmode="extended")
  for key,title in (("pallet","栈板 SN"),("wo","工单 WO"),("count","箱数"),("target","目标"),("time","封板时间")):self.reprint_tree.heading(key,text=title)
  self.reprint_tree.pack(fill="both",expand=True,padx=14,pady=(0,14))
  for name in self.store.resource_tables(1):
   if any(term in name for term in ("预发","报到","ARRIVAL","EXPECTED","EXCEPTION")):continue
   frame=tk.Frame(self.tabs,bg="#0f172a");self.tabs.add(frame,text=name.split("/")[0].strip());self.resource_frames[name]=frame
 def template_changed(self,_e=None):
  try:
   self.store.set_print_template(self.print_template.get());self.status.set("打印模板已选择: "+self.print_template.get())
  except PalletError as exc:messagebox.showerror("模板错误",str(exc))
 def add_print_template(self):
  source=filedialog.askopenfilename(title="添加 BarTender 打印模板",filetypes=(("BarTender 模板","*.btw"),("所有文件","*.*")))
  if not source:return
  try:
   name=self.store.import_print_template(source);self.template_box.configure(values=[p.name for p in self.store.available_print_templates()]);self.print_template.set(name);self.status.set("打印模板已添加并选择: "+name)
  except Exception as exc:messagebox.showerror("添加模板失败",str(exc))
 def select_wo(self,_e=None):
  try:
   code=self.store.select_work_order(self.wo_choice.get());self.wo.set("MES WO: "+code);self.status.set("真实工单已选择: "+code)
  except Exception as e:self.fail(e)
 def toggle_wo_bypass(self):
  enabled=self.store.set_work_order_bypass(not self.store.work_order_bypass())
  self.status.set("临时模式：无需MES工单" if enabled else "正式模式：需要MES工单")
  self.refresh()
 def _print_pallet(self, result):
    try:
        self.store._print_pallet_label(result)
    except Exception:
        pass

 def add(self):
   code=self.carton.get().strip()
   if COMMON_AGENT.local_confirmed_ng(code):
    self.carton.set("");self.status.set("NG：禁止绑定不良外箱 %s"%code);speak("NG，禁止绑定不良品");self.carton_entry.focus_set();return
   try:
    if not self.current:self.current=self.store.create_pallet("",self.target.get())
    r=self.store.add_carton(self.current,code);self.carton.set("")
    if "cartonSns" in r:
     self.status.set("满栈完成，栈板码已自动生成: "+r.get("palletSn",""));speak("满栈完成，栈板码已生成");self.current="";self.refresh()
     self._print_pallet(r)
    else:
     self.status.set("外箱已加入，还差 %d 箱%s"%(r.get("remaining",0),"；上游未确认，仅标注" if not r.get("verified") else ""));self.refresh()
    self.carton_entry.focus_set()
   except PalletError as e:self.fail(e)
 def remove_broken(self):
  try:
   selected=self.items.selection()
   if not selected:raise PalletError("请先在外箱列表中选择破损外箱")
   values=self.items.item(selected[0],"values");carton=str(values[1])
   if not messagebox.askyesno("确认删除","从当前未封板栈板中删除外箱：\n%s？"%carton):return
   reason=simpledialog.askstring("删除原因","请输入删除 %s 的原因："%carton,parent=self.root)
   if reason is None:return
   reason=reason.strip()
   if not reason:raise PalletError("删除外箱必须填写原因")
   result=self.store.remove_carton(self.current,carton,reason)
   self.status.set("破损外箱已移除，可补扫新箱；还差 %d 箱"%result["remaining"])
   speak("破损外箱已移除，请补扫新箱");self.refresh();self.carton_entry.focus_set()
  except PalletError as e:self.fail(e)
 def seal_partial(self):
  try:
   if not self.current:raise PalletError("当前没有正在装载的栈板")
   row=next((x for x in self.store.snapshot(100) if x["pallet_sn"]==self.current),None)
   if not row or row["carton_count"]<1:raise PalletError("当前栈板没有外箱")
   if not messagebox.askyesno("确认尾数封栈","当前 %d / %d 箱。\n确认作为工单尾数封栈？"%(row["carton_count"],row["target_cartons"])):return
   result=self.store.seal_pallet(self.current,True,"WORK_ORDER_TAIL")
   self.status.set("尾数栈板已完成：%s / %d 箱"%(result["palletSn"],result["cartonCount"]))
   speak("尾数封栈完成");self.current="";self.refresh();self._print_pallet(result)
  except PalletError as e:self.fail(e)
 def show_carton_actions(self,event):
  row_id=self.items.identify_row(event.y)
  if not row_id:return
  self.items.selection_set(row_id);self.items.focus(row_id)
  self.carton_menu.tk_popup(event.x_root,event.y_root)
 def refresh_reprint(self):
  term=self.reprint_search.get().strip().upper()
  self.reprint_tree.delete(*self.reprint_tree.get_children())
  for row in self.store.search_pallets(term,500):
   sealed=datetime.datetime.fromtimestamp(row["sealed_at"]).strftime("%Y-%m-%d %H:%M:%S") if row["sealed_at"] else ""
   self.reprint_tree.insert("","end",values=(row["pallet_sn"],row["work_order_code"],row["carton_count"],row["target_cartons"],sealed))
 def open_reprint_tab(self):
  self.refresh_reprint();self.tabs.select(self.reprint_tab)
 def reprint_selected(self):
  selected=self.reprint_tree.selection()
  if not selected:messagebox.showwarning("请选择栈板","请先选择需要补打的栈板标签");return
  if not messagebox.askyesno("确认补打","确认补打所选 %d 个栈板标签？"%len(selected)):return
  try:
   for item in selected:self.store.reprint_pallet_label(self.reprint_tree.item(item,"values")[0],"OPERATOR")
   self.status.set("已补打 %d 个栈板标签"%len(selected));speak("栈板标签补打完成")
  except PalletError as e:self.fail(e)
 def select_carton_position(self,position):
  rows=self.items.get_children()
  if position<1 or position>len(rows):return
  row_id=rows[position-1];self.items.selection_set(row_id);self.items.focus(row_id);self.items.see(row_id)
 def fail(self,e):self.status.set(str(e));speak("绑码失败");messagebox.showerror("禁止操作",str(e))
 def select(self,_e=None):
  sel=self.history.selection()
  if sel:
   values=self.history.item(sel[0],"values");self.current=values[0];self.refresh()
 def refresh(self):
  rows=self.store.snapshot();self.history.delete(*self.history.get_children());selected=None
  try:self.product_gate.update(self.store.arrivals.snapshot(1))
  except Exception:self.product_gate.update({})
  for p in rows:
   iid=self.history.insert("","end",values=(p["pallet_sn"],p["work_order_code"],p["carton_count"],p["target_cartons"],p["status"],"已同步" if p["mes_synced"] else "待同步"));selected=p if p["pallet_sn"]==self.current else selected
  self.items.delete(*self.items.get_children())
  if selected:
   for c in selected["cartons"]:self.items.insert("","end",values=(c["position"],c["carton_sn"],"已确认" if c["upstream_verified"] else "未确认/标注"))
  self.render_slots(int(selected["target_cartons"]) if selected else int(self.target.get() or 20),selected["cartons"] if selected else [])
  bypass=self.store.work_order_bypass()
  self.wo_bypass_btn.configure(text="临时模式：无需WO" if bypass else "临时绕过 WO 锁",bg="#dc2626" if bypass else "#334155")
  resources=self.store.resource_tables(500)
  for name,frame in self.resource_frames.items():
   for child in frame.winfo_children():child.destroy()
   rows=resources.get(name,[]);cols=tuple(rows[0].keys()) if rows else ("信息",)
   tree=ttk.Treeview(frame,columns=cols,show="headings")
   for col in cols:tree.heading(col,text=col);tree.column(col,width=150,anchor="center")
   for row in rows:tree.insert("","end",values=tuple(row.get(c,"") for c in cols))
   tree.pack(side="left",fill="both",expand=True);ttk.Scrollbar(frame,command=tree.yview).pack(side="right",fill="y")
 def render_slots(self,target,cartons):
  target=max(1,int(target));columns=5 if target<=20 else 6
  if len(self.slot_labels)!=target:
   for child in self.slot_panel.winfo_children():child.destroy()
   self.slot_labels=[]
   for i in range(target):
    label=tk.Label(self.slot_panel,text=str(i+1),width=18,height=3,bg="#1e293b",fg="#94a3b8",font=("Consolas",11,"bold"),relief="ridge",bd=3)
    label.bind("<Button-1>",lambda _e,pos=i+1:self.select_carton_position(pos))
    label.bind("<Double-1>",lambda _e,pos=i+1:(self.select_carton_position(pos),self.remove_broken()))
    label.grid(row=i//columns,column=i%columns,padx=6,pady=6,sticky="nsew");self.slot_labels.append(label)
   for col in range(columns):self.slot_panel.grid_columnconfigure(col,weight=1)
  for i,label in enumerate(self.slot_labels):
   if i<len(cartons):
    carton=cartons[i];verified=bool(carton["upstream_verified"])
    label.configure(text="%02d\n%s"%(i+1,carton["carton_sn"][-12:]),bg="#166534" if verified else "#92400e",fg="white")
   else:label.configure(text="%02d\nEMPTY"%(i+1),bg="#1e293b",fg="#64748b")
 def tick(self):
  def network():
   if not self._sync_lock.acquire(False):return
   try:self.store.refresh_mes_context();self.store.sync_once()
   except Exception:pass
   finally:self._sync_lock.release()
  threading.Thread(target=network,daemon=True).start()
  try:
   self.wo_box.configure(values=self.store.work_order_codes());self.wo_choice.set(self.store.active_work_order());self.wo.set("MES WO: "+(self.store.active_work_order() or "--"));self.refresh()
  except Exception:pass
  self.root.after(3000,self.tick)
 def heartbeat_tick(self):
  threading.Thread(target=self.store.heartbeat_once,daemon=True).start()
  self.root.after(5000,self.heartbeat_tick)
if __name__=="__main__":
 root=tk.Tk();Pallet2D(root)
 if not UI_PREVIEW:
  install_station_retest_panel(
   root,"manu_pallet_binding","http://192.168.6.155:8080")
  from station_repair_workflow import install_repair_workflow
  install_repair_workflow(root,"manu_pallet_binding","http://192.168.6.155:8080","栈板绑码")
 root.mainloop()
