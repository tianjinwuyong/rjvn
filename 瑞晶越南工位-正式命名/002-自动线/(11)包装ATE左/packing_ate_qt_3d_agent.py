# -*- coding: utf-8 -*-
"""Standalone Packaging ATE 3D UI using the same authoritative Core as 2D."""
import json
import math
import sys
import threading
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from PySide6.QtCore import QPointF

from packing_ate_core import PackingAteCore, PackingAteError, STATION_CODE
from station_retest import install_qt_retest_button


class AteScene(QWidget):
    def __init__(self):super().__init__();self.rows=[];self.yaw=-.25;self.pitch=.55;self.last=None;self.setMinimumHeight(360)
    def set_rows(self,rows):self.rows=rows;self.update()
    def mousePressEvent(self,e):self.last=e.position()
    def mouseMoveEvent(self,e):
        if self.last:
            d=e.position()-self.last;self.yaw+=d.x()*.008;self.pitch=max(.15,min(1.2,self.pitch+d.y()*.006));self.last=e.position();self.update()
    def mouseReleaseEvent(self,e):self.last=None
    def _p(self,x,y,z):
        cy,sy=math.cos(self.yaw),math.sin(self.yaw);rx=x*cy-y*sy;ry=x*sy+y*cy
        return QPointF(self.width()/2+rx,self.height()/2+ry*math.cos(self.pitch)-z-35)
    def paintEvent(self,e):
        p=QPainter(self);p.fillRect(self.rect(),QColor("#07111f"));p.setRenderHint(QPainter.Antialiasing)
        latest={}
        for r in self.rows:
            if r["channel"] not in latest:latest[r["channel"]]=r
        for side,offset in (("L",-250),("R",70)):
            for i in range(1,9):
                col=(i-1)%4;row=(i-1)//4;x=offset+col*75;y=(row-.5)*115;z=18
                r=latest.get(f"{side}{i}");color=QColor("#22c55e" if r and r["result"]=="PASS" else "#ef4444" if r else "#334155")
                poly=QPolygonF([self._p(x,y,z),self._p(x+62,y,z),self._p(x+62,y+85,z),self._p(x,y+85,z)])
                p.setPen(QPen(QColor("#cbd5e1"),2));p.setBrush(color);p.drawPolygon(poly)
                center=self._p(x+31,y+42,z);p.setPen(Qt.white);p.drawText(int(center.x()-32),int(center.y()),64,35,Qt.AlignCenter,f"{side}{i}\n{r['sn'][-8:] if r else '--'}")


class PackingAte3D(QMainWindow):
    def __init__(self):
        super().__init__();self.core=PackingAteCore();self.setWindowTitle("包装 ATE / Packaging ATE · 3D");self.resize(1500,900)
        self.setStyleSheet("QMainWindow,QWidget{background:#0f172a;color:#f8fafc} QTabBar::tab{background:#1e293b;color:#f8fafc;padding:10px 18px} QTabBar::tab:selected{background:#0891b2;color:white} QTableWidget{background:#111827;alternate-background-color:#182235;gridline-color:#475569} QHeaderView::section{background:#334155;color:white;padding:6px}")
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root)
        top=QHBoxLayout();self.status=QLabel("启动中");self.scan=QLineEdit();self.scan.setPlaceholderText("扫码检查：只检查 NG / 重复");self.scan.returnPressed.connect(self.check_scan)
        button=QPushButton("检查");button.clicked.connect(self.check_scan);top.addWidget(QLabel("包装 ATE 3D"));top.addWidget(self.scan,1);top.addWidget(button);self.retest_button=install_qt_retest_button(self,top,STATION_CODE);top.addWidget(self.status);layout.addLayout(top)
        self.tabs=QTabWidget();layout.addWidget(self.tabs);self.scene=AteScene();self.tabs.addTab(self.scene,"3D 实时")
        self.tables={}
        for name,cols in [("测试结果",["时间","通道","SN","结果","错误","重复","MES"]),("预发SN",["预发时间","SN","来源","状态","到站时间"]),("报到记录",["到站时间","SN","预发","状态","MES确认时间","来源"]),("未报到原因",["时间","SN","原因代码","原因说明","操作员","主管"]),("维修工单",["本地工单","MES工单","SN","原因","部门","状态","创建时间"]),("历史封存",["封存批次","原因","记录数","总哈希","封存时间","人员"]),("NG",["时间","通道","SN","错误"]),("扫码检查",["时间","SN","状态","说明"]),("原始数据",["源文件","行","周期","通道","SN","结果"]),("MES通信",["事件ID","状态","重试","错误"]),("设置",["项目","值"]),("修改记录",["编号","版本","组件","原因","内容","验证","时间"])]:
            table=QTableWidget();table.setColumnCount(len(cols));table.setHorizontalHeaderLabels(cols);table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);table.setAlternatingRowColors(True);self.tables[name]=table;self.tabs.addTab(table,name)
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(1000);self.refresh()
        self.running=True;threading.Thread(target=self.worker,daemon=True).start()
    def worker(self):
        while self.running:self.core.ingest_once();self.core.sync_once();time.sleep(1)
    def check_scan(self):
        try:
            r=self.core.check_scan(self.scan.text());self.scan.clear();self.status.setText(f'{r["status"]}: {r["sn"]}')
            if r["blocked"]:QMessageBox.warning(self,"扫码拦截",f'{r["status"]}: {r["sn"]}\n{r["detail"]}')
        except PackingAteError as exc:QMessageBox.warning(self,"扫码",str(exc))
        self.refresh()
    def fill(self,name,rows):
        t=self.tables[name];t.setRowCount(len(rows))
        for y,row in enumerate(rows):
            for x,value in enumerate(row):t.setItem(y,x,QTableWidgetItem(str(value)))
    def refresh(self):
        s=self.core.snapshot();signature=json.dumps(s,sort_keys=True,default=str,ensure_ascii=False)
        if signature == getattr(self, "_last_ui_signature", None): return
        self._last_ui_signature=signature;r=s["results"];self.scene.set_rows(r)
        self.fill("测试结果",[(x["test_time"],x["channel"],x["sn"],x["result"],x["error_code"],"YES" if x["duplicate"] else "","SYNC" if x["mes_synced"] else "QUEUED") for x in r[:500]])
        arrival=s["arrival"]
        self.fill("预发SN",[(x["expected_at"],x["sn"],x["source_station"],x["arrival_status"],x["arrived_at"] or "") for x in arrival["expected"]])
        self.fill("报到记录",[(x["arrived_at"],x["sn"],"YES" if x["expected"] else "NO",x["arrival_status"],x["mes_reported_at"] or "",x["source_type"]) for x in arrival["arrivals"]])
        self.fill("未报到原因",[(x["created_at"],x["sn"],x["reason_code"],x["reason_detail"],x["operator_id"],x["supervisor_id"]) for x in arrival["exceptions"]])
        self.fill("维修工单",[(x["local_case_id"],x["mes_work_order_id"] or "",x["sn"],x["reason_code"],x["department"],x["status"],x["created_at"]) for x in s["maintenance"]["cases"]])
        self.fill("历史封存",[(x["archive_batch_id"],x["reason"],x["record_count"],x["content_hash"],x["sealed_at"],x["created_by"]) for x in s["history"]["batches"]])
        self.fill("NG",[(x["test_time"],x["channel"],x["sn"],x["error_code"]) for x in r if x["result"]=="FAIL"])
        self.fill("扫码检查",[(x["created_at"],x["sn"],x["status"],x["detail"]) for x in s["checks"]])
        self.fill("原始数据",[(x["source_file"],x["source_row"],x["test_cycle_id"],x["channel"],x["sn"],x["result"]) for x in r])
        self.fill("MES通信",[(x["event_id"],"SENT" if x["sent_at"] else "QUEUED",x["retry_count"],x["last_error"]) for x in s["outbox"]])
        self.fill("设置",[("Excel 数据目录",s["watch_dir"]),("数据源状态","ONLINE" if s["source_connected"] else "MISSING"),("数据流向","本地 SQLite → MES"),("扫码规则","仅 NG / 重复检查")])
        self.fill("修改记录",[(x["change_id"],x["version"],x["component"],x["reason"],x["summary"],x["verification"],x["changed_at"]) for x in s["changes"]])
        self.status.setText(f'记录 {len(r)} · NG {sum(x["result"]=="FAIL" for x in r)} · 数据源 {"在线" if s["source_connected"] else "未找到"}')
    def closeEvent(self,e):self.running=False;e.accept()


if __name__=="__main__":app=QApplication(sys.argv);window=PackingAte3D();window.showMaximized();raise SystemExit(app.exec())
