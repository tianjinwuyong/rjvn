# -*- coding: utf-8 -*-
import json,math,sys,threading,time
from PySide6.QtCore import QPointF,Qt,QTimer
from PySide6.QtGui import QColor,QPainter,QPen,QPolygonF
from PySide6.QtWidgets import QApplication,QHeaderView,QLabel,QLineEdit,QMainWindow,QMessageBox,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,QVBoxLayout,QHBoxLayout,QWidget
from supersonic_core import SupersonicCore,SupersonicError

class Product3D(QWidget):
 def __init__(self):super().__init__();self.row=None;self.yaw=-.35;self.pitch=.55;self.last=None;self.setMinimumHeight(500)
 def set_row(self,row):self.row=row;self.update()
 def mousePressEvent(self,e):self.last=e.position()
 def mouseMoveEvent(self,e):
  if self.last:d=e.position()-self.last;self.yaw+=d.x()*.008;self.pitch=max(.15,min(1.2,self.pitch+d.y()*.006));self.last=e.position();self.update()
 def mouseReleaseEvent(self,e):self.last=None
 def p(self,x,y,z):
  c,s=math.cos(self.yaw),math.sin(self.yaw);rx=x*c-y*s;ry=x*s+y*c;return QPointF(self.width()/2+rx,self.height()/2+ry*math.cos(self.pitch)-z)
 def paintEvent(self,e):
  p=QPainter(self);p.fillRect(self.rect(),QColor('#07111f'));p.setRenderHint(QPainter.Antialiasing);color=QColor('#22c55e' if self.row and self.row['result']=='OK' else '#ef4444' if self.row else '#334155');poly=QPolygonF([self.p(-220,-110,40),self.p(220,-110,40),self.p(220,110,40),self.p(-220,110,40)]);p.setBrush(color);p.setPen(QPen(QColor('#e2e8f0'),4));p.drawPolygon(poly);p.setPen(Qt.white);p.drawText(self.rect(),Qt.AlignCenter,(self.row['sn']+'\n'+self.row['result']) if self.row else 'WAITING\nSQL SERVER')

class Supersonic3D(QMainWindow):
 def __init__(self):
  super().__init__();self.core=SupersonicCore();self.running=True;self.setWindowTitle('超声工站 / SUPERSONIC · 3D');self.resize(1500,900);self.build();self.refresh();self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(1000);threading.Thread(target=self.worker,daemon=True).start()
 def build(self):
  root=QWidget();self.setCentralWidget(root);root.setStyleSheet("QWidget{background:#0f172a;color:#f8fafc} QTabBar::tab{background:#1e293b;color:white;padding:10px 16px} QTabBar::tab:selected{background:#0891b2} QTableWidget{background:#111827;gridline-color:#475569}");v=QVBoxLayout(root);h=QHBoxLayout();self.scan=QLineEdit();self.scan.setPlaceholderText('扫码只检查NG/重复');self.scan.returnPressed.connect(self.check);b=QPushButton('检查');b.clicked.connect(self.check);self.status=QLabel('SQL Server连接中');h.addWidget(QLabel('超声 · 单SN 3D'));h.addWidget(self.scan,1);h.addWidget(b);h.addWidget(self.status);v.addLayout(h);self.tabs=QTabWidget();v.addWidget(self.tabs);self.scene=Product3D();self.tabs.addTab(self.scene,'3D实时');self.tables={};specs={'测试结果':['时间','SN','结果','频率','振幅','波时','能量','功率','来源'],'NG':['时间','SN','来源'],'报到记录':['到站时间','SN','预发','状态','MES确认'],'报到异常':['时间','SN','原因','说明','维修工单'],'维修工单':['本地工单','MES工单','SN','部门','状态'],'历史封存':['批次','记录数','哈希','时间'],'MES通信':['事件','类型','状态','错误'],'设置':['项目','值'],'修改记录':['编号','版本','原因','内容']}
  for n,c in specs.items():t=QTableWidget();t.setColumnCount(len(c));t.setHorizontalHeaderLabels(c);t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.tables[n]=t;self.tabs.addTab(t,n)
 def fill(self,n,rows):
  t=self.tables[n];t.setRowCount(len(rows))
  for y,row in enumerate(rows):
   for x,val in enumerate(row):t.setItem(y,x,QTableWidgetItem(str(val)))
 def check(self):
  try:r=self.core.check_scan(self.scan.text());self.scan.clear();self.status.setText(f'{r["status"]}: {r["sn"]}');QMessageBox.warning(self,'扫码拦截',r['detail']) if r['blocked'] else None
  except SupersonicError as e:QMessageBox.warning(self,'扫码',str(e))
 def worker(self):
  while self.running:
   try:r=self.core.poll_sql_once();self.status.setText(f'SQL在线 · 新增{r["added"]}')
   except Exception as e:self.core.sql_connected=False
   self.core.sync_once();time.sleep(2)
 def refresh(self):
  s=self.core.snapshot();signature=json.dumps(s,sort_keys=True,default=str,ensure_ascii=False)
  if signature==getattr(self,'_last_ui_signature',None):return
  self._last_ui_signature=signature;r=s['results'];self.scene.set_row(r[0] if r else None);self.fill('测试结果',[(x['test_time'],x['sn'],x['result'],x['frequency'],x['amplitude'],x['wavetime'],x['energy'],x['power'],x['source_table']) for x in r]);self.fill('NG',[(x['test_time'],x['sn'],x['source_table']) for x in s['ng']]);a=s['arrival'];self.fill('报到记录',[(x['arrived_at'],x['sn'],'YES' if x['expected'] else 'NO',x['arrival_status'],x['mes_reported_at'] or '') for x in a['arrivals']]);self.fill('报到异常',[(x['created_at'],x['sn'],x['reason_code'],x['reason_detail'],x['maintenance_case_id']) for x in a['exceptions']]);self.fill('维修工单',[(x['local_case_id'],x['mes_work_order_id'] or '',x['sn'],x['department'],x['status']) for x in s['maintenance']['cases']]);self.fill('历史封存',[(x['archive_batch_id'],x['record_count'],x['content_hash'],x['sealed_at']) for x in s['history']['batches']]);self.fill('MES通信',[(x['event_id'],x['event_type'],x['status'],x['last_error']) for x in s['outbox']]);q=s['sql'];self.fill('设置',[('SQL Server',f'{q["host"]}:{q["port"]}'),('Database',q['database']),('Table',q['table']),('Connected',q['connected']),('数据流向','SQL Server → 本地SQLite → MES'),('NG策略','记录/标记；不报警')]);self.fill('修改记录',[(x['change_id'],x['version'],x['reason'],x['summary']) for x in s['changes']])
 def closeEvent(self,e):self.running=False;e.accept()
if __name__=='__main__':app=QApplication(sys.argv);w=Supersonic3D();w.showMaximized();raise SystemExit(app.exec())
