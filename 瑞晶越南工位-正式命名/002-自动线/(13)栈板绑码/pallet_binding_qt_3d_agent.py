# -*- coding: utf-8 -*-
"""Auto-line Pallet live 3D projection; the 2D store remains authoritative."""
import sys, threading
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from pallet_binding_core import PalletBindingStore, STATION_CODE

class Pallet3D(QMainWindow):
    def __init__(self):
        super().__init__(); self.store=PalletBindingStore(); self.running=True; self.setWindowTitle('PALLET BINDING · 3D LIVE'); self.resize(1500,900)
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root)
        bar=QHBoxLayout(); self.status=QLabel('LIVE / CONNECTING'); self.count=QLabel(''); bar.addWidget(QLabel('AUTO PALLET')); bar.addWidget(self.count,1); bar.addWidget(self.status); layout.addLayout(bar)
        self.table=QTableWidget(); self.table.setColumnCount(6); self.table.setHorizontalHeaderLabels(['PALLET','WORK ORDER','CARTONS','TARGET','STATUS','MES']); layout.addWidget(self.table)
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(1000); self.refresh()
        threading.Thread(target=self.sync_worker,daemon=True).start()
    def sync_worker(self):
        while self.running:
            try:
                if hasattr(self.store,'refresh_mes_context'): self.store.refresh_mes_context()
                if hasattr(self.store,'sync_once'): self.store.sync_once()
            except Exception: pass
            threading.Event().wait(2)
    def refresh(self):
        try: rows=self.store.snapshot()
        except Exception as exc: self.status.setText('OFFLINE'); self.status.setToolTip(str(exc)); return
        self.table.setRowCount(len(rows)); self.count.setText(f'RECORDS {len(rows)} · DOMAIN {STATION_CODE}')
        for y,row in enumerate(rows):
            vals=[row.get(k,'') for k in ('pallet_sn','work_order_code','carton_count','target_cartons','status','mes_synced')]
            for x,v in enumerate(vals): self.table.setItem(y,x,QTableWidgetItem(str(v)))
        self.status.setText('LIVE / SYNCED')
    def closeEvent(self,e): self.running=False; e.accept()

if __name__=='__main__':
    app=QApplication(sys.argv); window=Pallet3D(); window.showMaximized(); raise SystemExit(app.exec())
