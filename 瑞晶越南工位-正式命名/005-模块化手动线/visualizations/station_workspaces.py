from __future__ import annotations

import tkinter as tk


C={"bg":"#142c46","well":"#0c1c2c","line":"#27445e","text":"#edf7ff","muted":"#9eb0bc","cyan":"#18c6d9","green":"#22d887","amber":"#f2b84b","red":"#f05252","blue":"#4c8dff"}


class StationWorkspace(tk.Frame):
    def __init__(self,parent,adapter,preview=True):
        super().__init__(parent,bg=C["bg"]); self.adapter=adapter; self.preview=preview; self._build()

    def title(self,text,detail=""):
        tk.Label(self,text=text,bg=C["bg"],fg=C["text"],font=("Microsoft YaHei UI",15,"bold")).pack(anchor="w")
        tk.Label(self,text=detail,bg=C["bg"],fg=C["muted"],font=("Microsoft YaHei UI",9)).pack(anchor="w",pady=(2,10))

    def card(self,parent,title,value="WAITING",color=None,row=0,col=0,span=1):
        box=tk.Frame(parent,bg=C["well"],highlightthickness=2,highlightbackground=color or C["line"],padx=10,pady=8)
        box.grid(row=row,column=col,columnspan=span,sticky="nsew",padx=4,pady=4)
        tk.Label(box,text=title,bg=C["well"],fg=C["muted"],font=("Microsoft YaHei UI",9,"bold")).pack(anchor="w")
        tk.Label(box,text=value,bg=C["well"],fg=color or C["text"],font=("Consolas",11,"bold"),wraplength=180).pack(anchor="w",pady=(8,0))
        return box

    def grid(self,cols=4):
        grid=tk.Frame(self,bg=C["bg"]); grid.pack(fill="both",expand=True)
        for col in range(cols): grid.grid_columnconfigure(col,weight=1)
        return grid

    def _build(self):
        method=getattr(self,"_"+self.adapter,None)
        (method or self._generic)()

    def _pda_material(self):
        self.title("PDA MATERIAL LOADING","Strict scan order · machine → channel → feeder → material")
        g=self.grid(5)
        for i,(a,b) in enumerate((("WORK ORDER","WO-MOD-001"),("MACHINE","AI-01"),("CHANNEL","CH-06"),("FEEDER","FDR-024"),("MATERIAL","MAT-88320"))): self.card(g,a,b,C["green"] if i<4 else C["amber"],0,i)
        self.card(g,"MES USAGE REPORT","Quantity, lot, supplier, position and operator are recorded",C["cyan"],1,0,5)

    def _aoi_result(self):
        self.title("A-O-I DEFECT REVIEW","Initial decision, image evidence and review are retained")
        g=self.grid(3); canvas=tk.Canvas(g,bg="#07111f",highlightthickness=1,highlightbackground=C["line"],height=250); canvas.grid(row=0,column=0,columnspan=2,sticky="nsew",padx=4,pady=4)
        for x in range(35,420,45):
            for y in range(35,220,45): canvas.create_rectangle(x,y,x+24,y+16,fill=C["green"],outline="")
        canvas.create_oval(245,105,275,135,fill=C["red"],outline="white",width=2); canvas.create_text(260,150,text="DEFECT 23",fill=C["red"],font=("Consolas",10,"bold"))
        self.card(g,"INITIAL","NG · solder bridge",C["red"],0,2); self.card(g,"REVIEW","Pending QC",C["amber"],1,2); self.card(g,"ROUTE","MARK_ONLY · preserve evidence",C["cyan"],2,2)

    def _ict_result(self): self._board_test("I-C-T MOTHERBOARD TEST")
    def _fct_result(self): self._board_test("F-C-T FUNCTION TEST")
    def _board_test(self,title):
        self.title(title,"3 × 4 motherboard/daughter layout · each SN has an independent result")
        g=self.grid(4)
        for i in range(12): self.card(g,f"POSITION {i+1:02d}",f"RJ-PCBA-{i+1:04d}\n"+("NG · R17" if i==5 else "PASS"),C["red"] if i==5 else C["green"],i//4,i%4)

    def _depanel(self):
        self.title("PCBA DEPANEL","MES checks upstream I-C-T/F-C-T before physical separation")
        g=self.grid(4); self.card(g,"MOTHERBOARD","MB-RJ-000128",C["blue"],0,0,4)
        for i in range(4): self.card(g,f"DAUGHTER {i+1}",f"DB-RJ-{i+1:04d}\n"+("REMOVE NOW" if i==2 else "READY"),C["red"] if i==2 else C["green"],1,i)

    def _case_binding(self): self._binding("PCBA / SHELL BINDING",("MOTHERBOARD SN","DAUGHTER SN","SHELL SN"))
    def _binding(self,title,items):
        self.title(title,"MES-controlled relationship · old bindings remain auditable")
        g=self.grid(len(items))
        for i,item in enumerate(items): self.card(g,item,f"RJ-{i+1:02d}-000482",C["blue"],0,i)
        self.card(g,"BINDING GRAPH","  →  ".join(items)+"\nVALIDATED BY MES",C["green"],1,0,len(items))

    def _supersonic(self):
        self.title("ULTRASONIC / VISUAL","Equipment parameters and exterior evidence")
        g=self.grid(3); self.card(g,"PRODUCT","RJ-PROD-009812",C["blue"],0,0); self.card(g,"AMPLITUDE","72.4 %",C["green"],0,1); self.card(g,"WELD TIME","1.82 s",C["green"],0,2); self.card(g,"VISUAL RESULT","NG · shell gap",C["red"],1,0); self.card(g,"ACTION","REMOVE → DISASSEMBLE → REBIND",C["cyan"],1,1,2)

    def _aging_7cab(self):
        self.title("7-CABINET AGING","Current SN and final cycle record · only latest cycle determines release")
        g=self.grid(7)
        for cab in range(7):
            value="\n".join(f"{slot+1:02d}  RJ-{cab+1}{slot+1:02d}  "+("NG" if cab==3 and slot==2 else "PASS") for slot in range(4))
            self.card(g,f"CABINET {cab+1}",value,C["red"] if cab==3 else C["green"],0,cab)

    def _outer_box_48sn(self):
        self.title("OUTER BOX · 48 SN","Real SN positions · work-order binding · no black placeholders")
        g=self.grid(8)
        for i in range(48): self.card(g,f"{i+1:02d}",f"RJ-{i+1:06d}",C["red"] if i==17 else C["green"],i//8,i%8)

    def _pallet_binding(self):
        self.title("PALLET BINDING","Pallet QR, carton QR and position are one MES relationship")
        g=self.grid(4)
        for i in range(12): self.card(g,f"PALLET POS {i+1:02d}",f"BOX-RJ-{i+1:04d}\nQR VERIFIED",C["green"],i//4,i%4)

    def _generic(self):
        self.title("STATION WORKSPACE",self.adapter); g=self.grid(2); self.card(g,"ADAPTER",self.adapter,C["cyan"],0,0); self.card(g,"STATUS","Waiting for real adapter",C["amber"],0,1)
