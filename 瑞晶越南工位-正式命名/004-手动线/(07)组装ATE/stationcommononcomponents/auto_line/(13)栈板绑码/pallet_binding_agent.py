# -*- coding: utf-8 -*-
import datetime,subprocess,threading,tkinter as tk
from tkinter import messagebox,ttk
from pallet_binding_core import PalletBindingStore,PalletError,MES_URL,STATION_CODE
from station_retest import install_station_retest_panel
from station_scan_alarm import show_blocking_alarm
from station_ui_primitives import install_station_tabs
from station_resource_startup import start_first_install_resource_read
start_first_install_resource_read(__import__('os').path.dirname(__file__))

def speak(t):subprocess.Popen(["powershell","-NoProfile","-Command","Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;$s.Speak('%s')"%t],creationflags=0x08000000)

class Pallet2D:
 def __init__(self,root):
  install_station_tabs(root)
  self.root,self.store,self.current=root,PalletBindingStore(),"";self._sync_lock=threading.Lock();root.title("栈板绑码 / PALLET BINDING 2D");root.geometry("1420x800");root.configure(bg="#07111f");self.status=tk.StringVar(value="等待 MES 下发工单 WO");self.wo=tk.StringVar(value="MES WO: --");self.pallet=tk.StringVar();self.target=tk.StringVar(value="20");self.carton=tk.StringVar();self._build();self.refresh();root.after(500,self.heartbeat_tick);root.after(2000,self.tick)
 def _build(self):
  s=ttk.Style();s.theme_use("clam");s.configure("Treeview",rowheight=29,font=("Segoe UI",11));h=tk.Frame(self.root,bg="#10243b",padx=18,pady=14);h.pack(fill="x");tk.Label(h,text="栈板绑码  PALLET BINDING",bg="#10243b",fg="white",font=("Microsoft YaHei UI",22,"bold")).pack(side="left");tk.Label(h,textvariable=self.status,bg="#10243b",fg="#38bdf8",font=("Microsoft YaHei UI",14,"bold")).pack(side="right")
  bar=tk.Frame(self.root,bg="#07111f",padx=18,pady=14);bar.pack(fill="x");
  tk.Label(bar,textvariable=self.wo,width=20,bg="#17324f",fg="#fbbf24",font=("Consolas",14,"bold"),padx=6,pady=6).pack(side="left",padx=(0,8))
  for label,var,w in (("栈板码",self.pallet,18),("目标箱数",self.target,6),("外箱码",self.carton,20)):
   tk.Label(bar,text=label,bg="#07111f",fg="white",font=("Microsoft YaHei UI",12)).pack(side="left",padx=(8,3));e=tk.Entry(bar,textvariable=var,width=w,font=("Consolas",16));e.pack(side="left")
   if var is self.carton:self.carton_entry=e;e.bind("<Return>",lambda _e:self.add())
  tk.Button(bar,text="建立栈板",command=self.create,bg="#2563eb",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=8);tk.Button(bar,text="加入外箱",command=self.add,bg="#059669",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=4);tk.Button(bar,text="确认满栈",command=self.seal,bg="#b91c1c",fg="white",font=("Microsoft YaHei UI",12,"bold")).pack(side="left",padx=4)
  self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill="both",expand=True,padx=18,pady=(0,10));live=tk.Frame(self.tabs,bg="#07111f");self.tabs.add(live,text="实时绑定 / LIVE");body=tk.Frame(live,bg="#07111f",padx=6);body.pack(fill="both",expand=True);self.items=ttk.Treeview(body,columns=("pos","carton","verified"),show="headings");self.items.heading("pos",text="#");self.items.heading("carton",text="外箱码");self.items.heading("verified",text="上游确认");self.items.column("pos",width=60,anchor="center");self.items.column("verified",width=120,anchor="center");self.items.pack(side="left",fill="both",expand=True,padx=(0,8));self.history=ttk.Treeview(body,columns=("pallet","wo","count","target","status","mes"),show="headings");
  for k,t in (("pallet","栈板码"),("wo","工单 WO"),("count","箱数"),("target","目标"),("status","状态"),("mes","MES")):self.history.heading(k,text=t)
  self.history.pack(side="left",fill="both",expand=True,padx=(8,0));self.history.bind("<<TreeviewSelect>>",self.select)
  self.resource_frames={}
  for name in self.store.resource_tables(1):
   frame=tk.Frame(self.tabs,bg="#0f172a");self.tabs.add(frame,text=name.split("/")[0].strip());self.resource_frames[name]=frame
 def create(self):
  try:self.current=self.store.create_pallet(self.pallet.get(),self.target.get());self.status.set("栈板已绑定工单 %s，请扫描外箱"%self.store.active_work_order());self.refresh();self.carton_entry.focus_set()
  except PalletError as e:self.fail(e)
 def _confirm_print_pallet(self, result):
    pallet = result.get("palletSn", "?")
    count = result.get("cartonCount", 0)
    msg = "栈板 %s 已封箱 (%d 箱)\n\n是否打印 PALLET ID 标签？" % (pallet, count)
    if messagebox.askyesno("打印标签", msg):
        try:
            self.store._print_pallet_label(result)
        except Exception:
            pass

 def add(self):
   try:
    r=self.store.add_carton(self.current or self.pallet.get(),self.carton.get());self.carton.set("")
    if "cartonSns" in r:
     self.status.set("满栈完成");speak("满栈完成");self.current="";self.refresh()
     self._confirm_print_pallet(r)
    else:
     self.status.set("外箱已加入，还差 %d 箱%s"%(r.get("remaining",0),"；上游未确认，仅标注" if not r.get("verified") else ""));self.refresh()
    self.carton_entry.focus_set()
   except PalletError as e:self.fail(e)
 def seal(self):
   try:
    result=self.store.seal_pallet(self.current or self.pallet.get());self.status.set("满栈完成");speak("栈板绑码成功");self.current="";self.refresh()
    self._confirm_print_pallet(result)
   except PalletError as e:self.fail(e)
 def fail(self,e):
  self.status.set(str(e));speak("绑码失败")
  alarm_code=getattr(self.store,"last_alarm_code","")
  if alarm_code in {"UPSTREAM_NG","DUPLICATE_SN","STATION_JUMPING"}:
   show_blocking_alarm(self.root,alarm_code,self.carton.get() or self.pallet.get(),str(e),STATION_CODE,MES_URL)
  else:messagebox.showerror("禁止操作",str(e))
 def select(self,_e=None):
  sel=self.history.selection()
  if sel:
   values=self.history.item(sel[0],"values");self.current=values[0];self.pallet.set(self.current);self.refresh()
 def refresh(self):
  rows=self.store.snapshot();self.history.delete(*self.history.get_children());selected=None
  for p in rows:
   iid=self.history.insert("","end",values=(p["pallet_sn"],p["work_order_code"],p["carton_count"],p["target_cartons"],p["status"],"已同步" if p["mes_synced"] else "待同步"));selected=p if p["pallet_sn"]==(self.current or self.pallet.get()) else selected
  self.items.delete(*self.items.get_children())
  if selected:
   for c in selected["cartons"]:self.items.insert("","end",values=(c["position"],c["carton_sn"],"已确认" if c["upstream_verified"] else "未确认/标注"))
  resources=self.store.resource_tables(500)
  for name,frame in self.resource_frames.items():
   for child in frame.winfo_children():child.destroy()
   rows=resources.get(name,[]);cols=tuple(rows[0].keys()) if rows else ("信息",)
   tree=ttk.Treeview(frame,columns=cols,show="headings")
   for col in cols:tree.heading(col,text=col);tree.column(col,width=150,anchor="center")
   for row in rows:tree.insert("","end",values=tuple(row.get(c,"") for c in cols))
   tree.pack(side="left",fill="both",expand=True);ttk.Scrollbar(frame,command=tree.yview).pack(side="right",fill="y")
 def tick(self):
  def network():
   if not self._sync_lock.acquire(False):return
   try:self.store.refresh_mes_context();self.store.sync_once()
   except Exception:pass
   finally:self._sync_lock.release()
  threading.Thread(target=network,daemon=True).start()
  try:self.wo.set("MES WO: "+(self.store.active_work_order() or "--"));self.refresh()
  except Exception:pass
  self.root.after(3000,self.tick)
 def heartbeat_tick(self):
  threading.Thread(target=self.store.heartbeat_once,daemon=True).start()
  self.root.after(5000,self.heartbeat_tick)
if __name__=="__main__":
 root=tk.Tk();app=Pallet2D(root)
 install_station_retest_panel(root,"auto_pallet_binding","http://192.168.6.155:8080",test_station=False,announcer=speak)
 from station_repair_workflow import install_repair_workflow
 install_repair_workflow(root,"auto_pallet_binding","http://192.168.6.155:8080","栈板绑码")
 root.mainloop()
