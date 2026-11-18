# -*- coding: utf-8 -*-
"""Auto-line Outer Box live 3D projection; the 2D store remains authoritative."""
import json, sys, threading
from pathlib import Path
APP_DIR=Path(__file__).resolve().parent
AUTO_ROOT=APP_DIR.parent
MANUAL_ROOT=AUTO_ROOT.parent/'002-自动线'
sys.path.insert(0,str(APP_DIR)); sys.path.insert(1,str(AUTO_ROOT)); sys.path.insert(2,str(MANUAL_ROOT)); sys.path.insert(3,str(MANUAL_ROOT/'(12)外箱绑码'))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from auto_case_binding_core import CaseBindingStore, STATION_CODE

class OuterBox3D(QMainWindow):
    def __init__(self):
        super().__init__(); self.store=CaseBindingStore(); self.running=True; self.setWindowTitle('OUTER BOX BINDING · 3D LIVE'); self.resize(1500,900)
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root)
        bar=QHBoxLayout(); self.status=QLabel('LIVE / CONNECTING'); self.count=QLabel(''); bar.addWidget(QLabel('AUTO OUTER BOX')); bar.addWidget(self.count,1); bar.addWidget(self.status); layout.addLayout(bar)
        self.table=QTableWidget(); self.table.setColumnCount(6); self.table.setHorizontalHeaderLabels(['CASE','WORK ORDER','COUNT','TARGET','STATUS','MES']); layout.addWidget(self.table)
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(1000); self.refresh()
        threading.Thread(target=self.sync_worker,daemon=True).start()
    def sync_worker(self):
        while self.running:
            try:
                if hasattr(self.store,'refresh_mes_context'): self.store.refresh_mes_context()
                if hasattr(self.store,'sync_once'): self.store.sync_once()
            except Exception: pass
            QTimer.singleShot(0, self.refresh)
            threading.Event().wait(2)
    def refresh(self):
        try: rows=self.store.snapshot()
        except Exception as exc: self.status.setText('OFFLINE'); self.status.setToolTip(str(exc)); return
        if isinstance(rows,dict): rows=rows.get('history') or rows.get('items') or []
        self.table.setRowCount(len(rows)); self.count.setText(f'RECORDS {len(rows)} · DOMAIN {STATION_CODE}')
        for y,row in enumerate(rows):
            vals=[row.get(k,'') for k in ('case_sn','work_order_code','carton_count','target_cartons','status','mes_synced')]
            for x,v in enumerate(vals): self.table.setItem(y,x,QTableWidgetItem(str(v)))
        self.status.setText('LIVE / SYNCED')
    def closeEvent(self,e): self.running=False; e.accept()

if __name__=='__main__':
    app=QApplication(sys.argv); window=OuterBox3D(); window.showMaximized(); raise SystemExit(app.exec())
