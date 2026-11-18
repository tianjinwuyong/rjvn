# -*- coding: utf-8 -*-
"""Standalone Rework 3D Qt agent with per-WO repair detail visualization."""
import json,math,threading,time
from PySide6.QtCore import Qt,QPointF,QTimer,Signal,QObject
from PySide6.QtGui import QColor,QFont,QPainter,QPen,QPolygonF,QPainterPath
from PySide6.QtWidgets import (QApplication,QHBoxLayout,QHeaderView,QLabel,QLineEdit,
    QMainWindow,QMessageBox,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,
    QVBoxLayout,QWidget,QCheckBox,QFrame,QScrollArea,QGridLayout,QGroupBox,
    QRadioButton,QTextEdit,QDialog,QVBoxLayout as QVVBox)
from rework_core import ReworkCore,ReworkError,STATION_CODE,REPAIR_STEPS,POST_REPAIR_TESTS

# Fix import name for tests
try:
    from rework_core import POST_REPAIR_TESTS as POST_REPAIR_TESTS_
except ImportError:
    POST_REPAIR_TESTS_ = POST_REPAIR_TESTS

POST_REPAIR_TESTS_ = POST_REPAIR_TESTS

LINE_SOURCE_MAP={
    'manu_ict':'ICT','manu_fct':'FCT','manu_depanel':'DEPANEL',
    'manu_assem_ate':'组装ATE','manu_supersonic':'超声','manu_agingcab':'老化',
    'manu_hivolt_ate':'高压','manu_package_ate':'包装ATE',
    'manu_smt_aoi':'SMT-AOI','manu_smt_paste':'SMT-印刷','manu_smt_pick':'SMT-贴片',
}
LINE_CATEGORY={'manu_ict':'MANUAL','manu_fct':'MANUAL','manu_depanel':'MANUAL',
               'manu_assem_ate':'MANUAL','manu_supersonic':'MANUAL','manu_agingcab':'AUTO',
               'manu_hivolt_ate':'AUTO','manu_package_ate':'AUTO',
               'manu_smt_aoi':'SMT','manu_smt_paste':'SMT','manu_smt_pick':'SMT'}
LINE_COLORS={'SMT':'#8b5cf6','AUTO':'#0891b2','MANUAL':'#16a34a'}

def line_tag(source):
    cat=LINE_CATEGORY.get(source,'')
    color=LINE_COLORS.get(cat,'#94a3b8')
    name=LINE_SOURCE_MAP.get(source,source or '?')
    return f'[{cat}/{name}]', color


# ── Visual step flow widget ──────────────────────────────────────────
class StepFlowWidget(QWidget):
    """Horizontal 5-step flow with completion status."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []   # list of 'pending'|'active'|'done'
        self.step_names = []
        self.setMinimumHeight(80)
        self.steps = ['pending'] * 5
        self.step_names = [n for _,n,_,_ in REPAIR_STEPS]

    def set_steps(self, confirmed_codes):
        confirmed = set(confirmed_codes)
        self.steps = []
        for code,_,_,_ in REPAIR_STEPS:
            if code in confirmed:
                self.steps.append('done')
            else:
                self.steps.append('pending')
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        step_w = (w - 60) / len(self.steps)
        for i, (label, state) in enumerate(zip(self.step_names, self.steps)):
            cx = 30 + i * step_w + step_w / 2
            r = 22
            if state == 'done':
                color = QColor('#22c55e')
                bg = QColor('#052e16')
            else:
                color = QColor('#475569')
                bg = QColor('#1e293b')
            # Node circle
            p.setPen(QPen(color, 3))
            p.setBrush(bg)
            p.drawEllipse(QPointF(cx, 32), r, r)
            # Step number
            p.setPen(color)
            p.setFont(QFont('Arial', 11, QFont.Bold))
            p.drawText(QPointF(cx - 4, 37), str(i + 1))
            # Label below
            short = label.split('/')[0].strip() if '/' in label else label[:6]
            p.setFont(QFont('Microsoft YaHei', 9))
            p.drawText(QPointF(cx - 30, 65), short)
            # Connecting line
            if i < len(self.steps) - 1:
                next_state = self.steps[i + 1]
                line_color = QColor('#22c55e') if (state == 'done' and next_state == 'done') else QColor('#334155')
                p.setPen(QPen(line_color, 2))
                p.drawLine(int(cx + r), 32, int(cx + step_w - r), 32)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.update()


# ── Isometric Board (PCB) View widget ──────────────────────────────────────────
class IsometricBoardView(QWidget):
    """Isometric 3D PCB board with component slots, drag-rotate, zoom, click-to-inspect."""
    SLOT_COLORS = {
        'NG':        ('#ef4444', '#2d0520'),   # red  - defect detected
        'FAIL':      ('#ef4444', '#2d0520'),   # red  - test failed
        'PASS':      ('#22c55e', '#052e16'),   # green- tested pass
        'REPAIRED':  ('#38bdf8', '#0c2d3d'),   # blue - component replaced
        'REPAIRING': ('#f59e0b', '#2d1f00'),   # amber- currently being repaired
        'EMPTY':     ('#475569', '#1e293b'),   # gray - no component
    }
    # Face brightness multipliers (top = brightest, sides darker)
    FACE_BRIGHT = {'top': 1.0, 'right': 0.72, 'front': 0.85, 'left': 0.60}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.wo_data = None       # {'ng_sn', 'batch_id', 'source_station', 'status', 'current_step'}
        self.slots = []           # [{'sn','slot','incoming_result','defect_code','repair_status','material_code','height'}]
        self.yaw = 32.0
        self.pitch = 38.0
        self.zoom = 1.0
        self._drag = None
        self._click_pos = None
        self.setMinimumHeight(420)
        self.setCursor(Qt.OpenHandCursor)

    def load_wo(self, wo_data, log_data=None):
        self.wo_data = wo_data or {}
        self.slots = []
        if not wo_data:
            self.update(); return
        # Build slots from log_data
        if log_data:
            # Sub-boards from motherboard_members
            for m in log_data.get('motherboard_members', []):
                self.slots.append({
                    'sn': m.get('sn',''),
                    'slot': m.get('slot'),
                    'incoming_result': m.get('incoming_result','NG'),
                    'defect_code': m.get('defect_code'),
                    'repair_status': m.get('repair_status','waiting'),
                    'material_code': '',
                    'height': 0.15,
                })
            # Replaced materials
            for m in log_data.get('materials', []):
                for s in self.slots:
                    if s['sn'].upper() == m.get('ng_sn','').upper():
                        s['material_code'] = m.get('material_code','')
                        s['repair_status'] = 'REPAIRED'
        else:
            # Fallback: single main SN
            self.slots.append({
                'sn': wo_data.get('ng_sn',''),
                'slot': 0,
                'incoming_result': 'NG',
                'defect_code': '',
                'repair_status': 'NG',
                'material_code': '',
                'height': 0.25,
            })
        self.update()

    def _slot_status(self, slot):
        rs = slot.get('repair_status','waiting').upper()
        ir = slot.get('incoming_result','NG').upper()
        if rs == 'REPAIRED': return 'REPAIRED'
        if rs == 'REPAIRING': return 'REPAIRING'
        if ir == 'FAIL' or ir == 'NG': return 'NG'
        if ir == 'PASS': return 'PASS'
        return 'EMPTY'

    def _bright(self, hex_color, factor):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        return f'#{r:02x}{g:02x}{b:02x}'

    def _project(self, v, w, h, scale, cy):
        x, y, z = v
        yr = x * math.cos(math.radians(self.yaw)) - y * math.sin(math.radians(self.yaw))
        xr = x * math.sin(math.radians(self.yaw)) + y * math.cos(math.radians(self.yaw))
        return QPointF(w / 2 + xr * scale,
                       cy + (yr * math.sin(math.radians(self.pitch)) - z * math.cos(math.radians(self.pitch))) * scale)

    def _depth(self, v):
        yr = v[0] * math.sin(math.radians(self.yaw)) + v[1] * math.cos(math.radians(self.yaw))
        return yr * math.cos(math.radians(self.pitch)) + v[2] * math.sin(math.radians(self.pitch))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        scale = min(w / 4.5, h / 3.2) * self.zoom
        cy = h * 0.62

        # Draw title info
        if self.wo_data:
            info = f"SN: {self.wo_data.get('ng_sn','?')}  Batch: {self.wo_data.get('batch_id','?')}  来源: {self.wo_data.get('source_station','?')}"
            p.setFont(QFont('Consolas', 10))
            p.setPen(QColor('#94a3b8'))
            p.drawText(QPointF(8, 18), info[:80])

        # Board base: PCB substrate (thin flat rectangle)
        bx0, bx1, by0, by1, bz0, bz1 = -1.8, 1.8, -1.2, 1.2, 0.0, 0.06
        base_faces = [
            ([(bx0,by0,bz0),(bx1,by0,bz0),(bx1,by1,bz0),(bx0,by1,bz0)], '#1a4a2e'),   # bottom shadow
            ([(bx0,by0,bz1),(bx1,by0,bz1),(bx1,by1,bz1),(bx0,by1,bz1)], '#1e6b3a'),   # top PCB surface
            ([(bx1,by0,bz0),(bx1,by1,bz0),(bx1,by1,bz1),(bx1,by0,bz1)], '#143a28'),   # right side
            ([(bx1,by1,bz0),(bx0,by1,bz0),(bx0,by1,bz1),(bx1,by1,bz1)], '#18522e'),   # front side
            ([(bx0,by1,bz0),(bx0,by0,bz0),(bx0,by0,bz1),(bx0,by1,bz1)], '#0f2e20'),   # left side
        ]
        all_faces = []
        for verts, color in base_faces:
            all_faces.append((verts, color, 0))
        # Slot components on board
        slot_count = max(len(self.slots), 1)
        cols = math.ceil(math.sqrt(slot_count))
        rows = math.ceil(slot_count / cols)
        sw = (bx1 - bx0) * 0.88 / cols   # slot width
        sh = (by1 - by0) * 0.88 / rows   # slot depth
        spx = (bx1 - bx0) * 0.06          # start padding x
        spy = (by1 - by0) * 0.06          # start padding y
        slot_h = 0.22

        for idx, slot in enumerate(self.slots):
            row, col = divmod(idx, cols)
            sx0 = bx0 + spx + col * (bx1 - bx0 - 2*spx) / cols
            sx1 = sx0 + sw
            sy0 = by0 + spy + row * (by1 - by0 - 2*spy) / rows
            sy1 = sy0 + sh
            status = self._slot_status(slot)
            fg_hex, bg_hex = self.SLOT_COLORS.get(status, self.SLOT_COLORS['EMPTY'])
            # 3 faces: top, right, front
            top_face = [(sx0,sy0,bz1+slot_h),(sx1,sy0,bz1+slot_h),(sx1,sy1,bz1+slot_h),(sx0,sy1,bz1+slot_h)]
            right_face = [(sx1,sy0,bz1),(sx1,sy1,bz1),(sx1,sy1,bz1+slot_h),(sx1,sy0,bz1+slot_h)]
            front_face = [(sx1,sy1,bz1),(sx0,sy1,bz1),(sx0,sy1,bz1+slot_h),(sx1,sy1,bz1+slot_h)]
            all_faces += [
                (top_face,   self._bright(fg_hex, self.FACE_BRIGHT['top']),   idx*3+1),
                (right_face,  self._bright(fg_hex, self.FACE_BRIGHT['right']),  idx*3+2),
                (front_face, self._bright(fg_hex, self.FACE_BRIGHT['front']), idx*3+3),
            ]
        # Sort by depth and draw
        for verts, color, _ in sorted(all_faces, key=lambda f: sum(self._depth(v) for v in f[0])/4):
            p.setPen(QPen(QColor('#c49a6c'), 1.5))
            p.setBrush(QColor(color))
            p.drawPolygon(QPolygonF([self._project(v,w,h,scale,cy) for v in verts]))
        # Slot labels on top faces
        p.setFont(QFont('Arial', 7, QFont.Bold))
        for idx, slot in enumerate(self.slots):
            row, col = divmod(idx, cols)
            sx0 = bx0 + spx + col * (bx1 - bx0 - 2*spx) / cols
            sx1 = sx0 + sw
            sy0 = by0 + spy + row * (by1 - by0 - 2*spy) / rows
            sy1 = sy0 + sh
            cx = (sx0 + sx1) / 2
            cy_s = (sy0 + sy1) / 2
            mid = self._project((cx, cy_s, bz1 + slot_h), w, h, scale, cy)
            status = self._slot_status(slot)
            color = self.SLOT_COLORS.get(status, self.SLOT_COLORS['EMPTY'])[0]
            p.setPen(QColor(color))
            lbl = f"#{idx+1}"
            if slot.get('defect_code'):
                lbl += f" {slot['defect_code'][:6]}"
            elif slot.get('material_code'):
                lbl += f" {slot['material_code'][:6]}"
            p.drawText(mid, lbl)
        # Draw step indicator
        if self.wo_data and self.wo_data.get('status'):
            step_txt = f"Status: {self.wo_data.get('status','')}"
            p.setFont(QFont('Microsoft YaHei', 10, QFont.Bold))
            p.setPen(QColor('#fbbf24'))
            p.drawText(QPointF(8, h - 10), step_txt)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._drag: return
        delta = event.position() - self._drag
        self._drag = event.position()
        self.yaw = (self.yaw + delta.x() * 0.45) % 360
        self.pitch = max(12, min(72, self.pitch + delta.y() * 0.25))
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag = None
            self.setCursor(Qt.OpenHandCursor)
            event.accept()

    def wheelEvent(self, event):
        self.zoom = max(0.5, min(1.5, self.zoom + (0.05 if event.angleDelta().y() > 0 else -0.05)))
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.yaw, self.pitch, self.zoom = 32.0, 38.0, 1.0
        self.update()


# ── WO Detail Card widget ───────────────────────────────────────────
class TestBarWidget(QWidget):
    """Shows 3 post-repair tests as labeled bars."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tests = {}   # code -> result
        self.test_meta = [(c, n, r) for c, n, _, r in POST_REPAIR_TESTS_]
        self.setMinimumHeight(60)

    def set_tests(self, test_list):
        # test_list: list of {test_code, result}
        self.tests = {t['test_code']: t['result'] for t in test_list}
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        bar_w = (w - 40) / len(self.test_meta)
        for i, (code, name, required) in enumerate(self.test_meta):
            result = self.tests.get(code)
            cx = 20 + i * bar_w + bar_w / 2
            if result == 'PASS':
                color = QColor('#22c55e'); bg = QColor('#052e16')
            elif result == 'FAIL':
                color = QColor('#ef4444'); bg = QColor('#2d0520')
            else:
                color = QColor('#94a3b8') if required else QColor('#475569')
                bg = QColor('#1e293b') if required else QColor('#1a1a2e')
            # Circle
            p.setPen(QPen(color, 2.5))
            p.setBrush(bg)
            p.drawEllipse(QPointF(cx, 24), 18, 18)
            # Icon
            icon = '✓' if result == 'PASS' else ('✗' if result == 'FAIL' else ('○' if required else '·'))
            p.setPen(color); p.setFont(QFont('Arial', 13, QFont.Bold))
            p.drawText(QPointF(cx - 6, 29), icon)
            # Label
            short = name.split('/')[0].strip() if '/' in name else name[:5]
            req = ' *' if required else ''
            p.setFont(QFont('Microsoft YaHei', 9))
            p.drawText(QPointF(cx - 25, 52), short + req)


# ── WO Detail Card widget ────────────────────────────────────────────
class WoDetailCard(QWidget):
    """Full per-WO repair detail: isometric board + step flow + materials + log."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wo_data = None
        self.log_data = None
        self._build()

    def _build(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(4, 4, 4, 4)
        ly.setSpacing(6)

        # Header row
        self.header_lbl = QLabel('选择维修工单查看详情 / Select a repair WO')
        self.header_lbl.setStyleSheet('font-size:14px; font-weight:bold; color:#67e8f9; padding:4px')
        ly.addWidget(self.header_lbl)

        # Status + source badge
        self.meta_lbl = QLabel('')
        self.meta_lbl.setStyleSheet('color:#94a3b8; font-size:12px; padding:2px')
        ly.addWidget(self.meta_lbl)

        # ── Isometric board view ─────────────────────────────────────────────
        board_grp = QGroupBox('PCB 3D视图 / Isometric Board View  (drag to rotate, scroll to zoom)')
        board_grp.setStyleSheet('QGroupBox{color:#67e8f9;border:1px solid #334155;font-size:12px;margin-top:6px} QGroupBox>*{padding:4px}')
        bly = QVBoxLayout(board_grp)
        self.board_view = IsometricBoardView()
        bly.addWidget(self.board_view)
        ly.addWidget(board_grp)

        # Step flow
        step_grp = QGroupBox('维修步骤 / Repair Steps')
        step_grp.setStyleSheet('QGroupBox{color:#94a3b8;border:1px solid #334155;font-size:12px;margin-top:6px} QGroupBox>*{padding:4px}')
        sly = QVBoxLayout(step_grp)
        self.step_flow = StepFlowWidget()
        sly.addWidget(self.step_flow)
        ly.addWidget(step_grp)

        # Test bar
        test_grp = QGroupBox('维修后测试 / Post-Repair Tests')
        test_grp.setStyleSheet('QGroupBox{color:#94a3b8;border:1px solid #334155;font-size:12px;margin-top:6px} QGroupBox>*{padding:4px}')
        tly = QVBoxLayout(test_grp)
        self.test_bar = TestBarWidget()
        tly.addWidget(self.test_bar)
        ly.addWidget(test_grp)

        # Materials table
        mat_grp = QGroupBox('更换物料 / Replacement Materials')
        mat_grp.setStyleSheet('QGroupBox{color:#94a3b8;border:1px solid #334155;font-size:12px;margin-top:6px} QGroupBox>*{padding:4px}')
        mly = QVBoxLayout(mat_grp)
        self.mat_tbl = QTableWidget(0, 5)
        self.mat_tbl.setHorizontalHeaderLabels(['物料编码','名称','数量','单位','操作员'])
        self.mat_tbl.horizontalHeader().setStretchLastSection(True)
        self.mat_tbl.setMaximumHeight(90)
        self.mat_tbl.setStyleSheet('QTableWidget{background:#111827;color:white;font-size:11px} QHeaderView::section{background:#334155;color:white}')
        mly.addWidget(self.mat_tbl)
        ly.addWidget(mat_grp)

        # Repair log table
        log_grp = QGroupBox('维修记录 / Repair Log')
        log_grp.setStyleSheet('QGroupBox{color:#94a3b8;border:1px solid #334155;font-size:12px;margin-top:6px} QGroupBox>*{padding:4px}')
        lly = QVBoxLayout(log_grp)
        self.log_tbl = QTableWidget(0, 5)
        self.log_tbl.setHorizontalHeaderLabels(['时间','动作','结果','方法/原因','操作员'])
        self.log_tbl.horizontalHeader().setStretchLastSection(True)
        self.log_tbl.setMaximumHeight(110)
        self.log_tbl.setStyleSheet('QTableWidget{background:#111827;color:white;font-size:11px} QHeaderView::section{background:#334155;color:white}')
        lly.addWidget(self.log_tbl)
        ly.addWidget(log_grp)

    def load_wo(self, wo_no):
        if not wo_no:
            self.header_lbl.setText('选择维修工单查看详情 / Select a repair WO')
            self.meta_lbl.setText('')
            return
        from rework_core import ReworkCore
        core = ReworkCore()
        log = core.fetch_repair_log(wo_no)
        self.log_data = log
        self.wo_data = log['work_order'] if log else None
        self._render()

    def _render(self):
        wo = self.wo_data
        if not wo:
            self.header_lbl.setText('工单不存在 / WO not found')
            return
        tag, tag_color = line_tag(wo.get('source_station',''))
        self.header_lbl.setText(f"WO: {wo['work_order_no']}  |  SN: {wo['ng_sn']}  |  Batch: {wo['batch_id']}")
        self.meta_lbl.setText(
            f"<span style='color:{tag_color}'>{tag}</span> "
            f"<span style='color:#f8fafc'>{wo.get('source_station','')}</span>  |  "
            f"Status: <b>{wo.get('status','')}</b>  |  "
            f"方法: {wo.get('repair_method') or '-'}  |  "
            f"结果: {wo.get('repair_result') or '-'}  |  "
            f"操作员: {wo.get('operator') or '-'}")

        # Steps
        confirmed = [s['step_code'] for s in (self.log_data or {}).get('steps',[]) if s.get('confirmed_at')]
        self.step_flow.set_steps(confirmed)

        # Isometric board view
        self.board_view.load_wo(wo, self.log_data)

        # Tests
        tests = (self.log_data or {}).get('tests', [])
        self.test_bar.set_tests(tests)

        # Materials
        mats = (self.log_data or {}).get('materials', [])
        self.mat_tbl.setRowCount(len(mats))
        for i, m in enumerate(mats):
            for j, key in enumerate(['material_code','material_name','quantity','unit','operator']):
                item = QTableWidgetItem(str(m.get(key,'') or ''))
                item.setForeground(QColor('#f8fafc'))
                self.mat_tbl.setItem(i, j, item)

        # Log
        records = (self.log_data or {}).get('records', [])
        self.log_tbl.setRowCount(len(records))
        for i, r in enumerate(records):
            for j, key in enumerate(['started_at','action','result','repair_method','operator']):
                val = r.get(key,'') or ''
                item = QTableWidgetItem(val[11:19] if isinstance(val,str) and len(val)>19 else str(val))
                item.setForeground(QColor('#f8fafc'))
                self.log_tbl.setItem(i, j, item)


# ── Main 3D Window ───────────────────────────────────────────────────
class Rework3D(QMainWindow):
    def __init__(self):
        super().__init__()
        self.core = ReworkCore()
        self.running = True
        self.setWindowTitle(f'回修站质量工位 · 3D / Repair Quality · 3D  [{STATION_CODE}]')
        self.resize(1600, 960)
        self.setStyleSheet('QMainWindow,QWidget{background:#0f172a;color:white}'
                           'QTabBar::tab{background:#1e293b;color:#94a3b8;padding:10px 14px}'
                           'QTabBar::tab:selected{background:#0891b2;color:white}'
                           'QPushButton{background:#1d4ed8;color:white;padding:8px 14px;border-radius:4px}'
                           'QPushButton:pressed{background:#1e40af}'
                           'QLineEdit,QTextEdit{background:#111827;color:white;border:1px solid #334155;padding:6px}'
                           'QTableWidget{background:#111827;color:white;gridline-color:#1e293b}'
                           'QHeaderView::section{background:#1e293b;color:#94a3b8;padding:4px}'
                           'QGroupBox{color:#94a3b8;border:1px solid #334155;font-size:12px;margin-top:8px}'
                           'QGroupBox>*{padding:2px}')
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setSpacing(4)

        # ── Top toolbar ──────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel(f'<b style="color:#67e8f9;font-size:15px">回修站 · 3D</b>  [{STATION_CODE}]'))
        self.scan = QLineEdit()
        self.scan.setPlaceholderText('扫码 SN 接收维修 / Scan SN to receive')
        self.scan.returnPressed.connect(self._on_scan)
        recv_btn = QPushButton('接收 / RECEIVE')
        recv_btn.setStyleSheet('background:#0891b2')
        recv_btn.clicked.connect(self._on_scan)
        self.status_lbl = QLabel('等待扫码 / Waiting for scan')
        self.status_lbl.setStyleSheet('color:#fbbf24;font-size:12px')
        ref_btn = QPushButton('刷新 / REFRESH')
        ref_btn.clicked.connect(self._refresh)
        toolbar.addWidget(self.scan, 1)
        toolbar.addWidget(recv_btn)
        toolbar.addWidget(self.status_lbl)
        toolbar.addWidget(ref_btn)
        v.addLayout(toolbar)

        # ── Workbench overview ────────────────────────────────────────
        bench = QHBoxLayout()
        bench.setSpacing(8)
        self.bench_labels = {}
        for label, color in [('待接收 PENDING', '#f59e0b'), ('维修中 REPAIRING', '#38bdf8'), ('待确认 PENDING_QC', '#22c55e'), ('已完成 COMPLETED', '#94a3b8')]:
            fr = QFrame()
            fr.setStyleSheet(f'background:#10243b;border:2px solid {color};border-radius:8px;padding:8px')
            lbl = QLabel('0')
            lbl.setStyleSheet(f'color:{color};font-size:32px;font-weight:bold')
            sub = QLabel(label)
            sub.setStyleSheet(f'color:{color};font-size:11px')
            box = QVBoxLayout(fr)
            box.addWidget(lbl); box.addWidget(sub); box.addStretch()
            bench.addWidget(fr)
            self.bench_labels[label.split()[0]] = lbl
        bench.addStretch()
        v.addLayout(bench)

        # ── Main: WO table + detail panel ─────────────────────────────
        main = QHBoxLayout()
        main.setStretch(0, 1)
        main.setStretch(1, 1)

        # Left: work orders table
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel('<b>维修工单列表 / Work Orders</b>'))
        self.wo_tbl = QTableWidget(0, 9)
        self.wo_tbl.setHorizontalHeaderLabels(['RWO工单号','NG SN','批次','来源','状态','完成时间','方法','结果','操作员'])
        self.wo_tbl.horizontalHeader().setStretchLastSection(True)
        self.wo_tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.wo_tbl.itemClicked.connect(self._on_wo_clicked)
        lv.addWidget(self.wo_tbl)

        # Right: detail panel
        right = QWidget()
        right.setMinimumWidth(520)
        rv = QVBoxLayout(right)
        rv.addWidget(QLabel('<b>工单详情 / Work Order Detail</b>'))
        self.detail_card = WoDetailCard()
        rv.addWidget(self.detail_card)

        main.addWidget(left)
        main.addWidget(right)
        v.addLayout(main)

        # ── Tabs ────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        v.addWidget(self.tabs)
        self.tables = {}
        for name, cols in (
            ('MES待接收',['RWO工单号','交接单','批次','来源','板数','送出时间','状态']),
            ('维修中',['RWO工单号','来源','批次','开始','已用','报警']),
            ('物料记录',['工单号','SN','物料编码','名称','数量','单位','操作员','记录时间']),
            ('维修日志',['时间','SN','动作','结果','方法/原因','操作员','耗时']),
            ('QC控制',['RWO工单号','SN','来源','状态','完成时间','维修方法','维修结果','复测次数']),
            ('扫码记录',['时间','SN','结果','MES']),
            ('NG拦截',['时间','SN','来源','缺陷']),
            ('MES缓存',['SN','来源','批次','版本','同步时间']),
            ('MES通信',['事件','SN','结果','重试','创建时间']),
            ('修改记录',['编号','版本','组件','原因','内容','验证','时间']),
        ):
            t = QTableWidget()
            t.setColumnCount(len(cols))
            t.setHorizontalHeaderLabels(cols)
            t.horizontalHeader().setStretchLastSection(True)
            self.tables[name] = t
            self.tabs.addTab(t, name)

        # ── Statistics tab ─────────────────────────────────────────────────────
        self._build_stats_tab()
        self._refresh_stats()

        # ── Worker + timer ────────────────────────────────────────────
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(4000)
        threading.Thread(target=self._worker, daemon=True).start()
        self._refresh()

    def _on_scan(self):
        sn = self.scan.text().strip().upper()
        self.scan.clear()
        if not sn:
            return
        try:
            r = self.core.receive_repair(sn)
            if not r.get('ok'):
                QMessageBox.critical(self, '拦截 / Blocked', f"{sn}\n{r.get('error_code')}\n{r.get('detail','')}")
                return
            self.status_lbl.setText(f"已接收 / RECEIVED: {r['batch_id']} · {sn}")
            self._refresh()
        except ReworkError as ex:
            QMessageBox.warning(self, 'Error', str(ex))

    def _on_wo_clicked(self, item):
        row = item.row()
        wo_no = self.wo_tbl.item(row, 0).text().strip()
        if wo_no:
            self.detail_card.load_wo(wo_no)

    def _fill(self, name, rows):
        t = self.tables[name]
        t.setRowCount(len(rows))
        for y, row in enumerate(rows):
            for x, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setForeground(QColor('#f8fafc'))
                t.setItem(y, x, item)

    def _refresh(self):
        try:
            s = self.core.fetch_all()
            # Bench counts
            self.bench_labels['待接收'].setText(str(len(s['pending_handovers'])))
            self.bench_labels['维修中'].setText(str(len(s['active_repairs'])))
            self.bench_labels['待确认'].setText(str(sum(1 for w in s['work_orders'] if w.get('status') == 'PENDING_QUALITY')))
            self.bench_labels['已完成'].setText(str(sum(1 for w in s['work_orders'] if w.get('repair_completed_at'))))
            # WO table
            self.wo_tbl.setRowCount(len(s['work_orders']))
            for y, w in enumerate(s['work_orders']):
                tag, tag_color = line_tag(w.get('source_station', ''))
                vals = [
                    w['work_order_no'],
                    w['ng_sn'],
                    w['batch_id'],
                    f'{tag} {w.get("source_station","")}',
                    w['status'],
                    (w.get('repair_completed_at') or '')[11:19],
                    w.get('repair_method') or '',
                    w.get('repair_result') or '',
                    w.get('operator') or '',
                ]
                for x, v in enumerate(vals):
                    item = QTableWidgetItem(v)
                    item.setForeground(QColor('#f8fafc'))
                    self.wo_tbl.setItem(y, x, item)
            # Tabs
            self._fill('MES待接收', [
                (r.get('repairWorkOrderNo','-'),
                 r.get('billNo') or r.get('requestId','-'),
                 r.get('batchId',''),
                 f'{line_tag(r.get("sourceStation",""))[0]} {r.get("sourceStation","")}',
                 len(r.get('motherboard',{}).get('subBoards') or []),
                 (r.get('submittedAt') or '')[-8:],
                 r.get('status',''))
                for r in s['pending_handovers']])
            self._fill('维修中', [
                (r.get('repairWorkOrderNo') or r.get('batchId',''),
                 f'{line_tag(r.get("sourceStation",""))[0]} {r.get("sourceStation","")}',
                 r.get('batchId',''),
                 (r.get('repairStartedAt') or '-')[11:19] if r.get('repairStartedAt') else '-',
                 f"{int(r.get('repairElapsedSeconds') or 0)//3600:02d}:{int(r.get('repairElapsedSeconds') or 0)%3600//60:02d}:{int(r.get('repairElapsedSeconds') or 0)%60:02d}",
                 'TIMEOUT' if r.get('repairAlarmAt') else 'REPAIRING')
                for r in s['active_repairs']])
            self._fill('物料记录', [
                (m['work_order_no'], m['ng_sn'] or '', m['material_code'] or '', m['material_name'] or '',
                 m['quantity'], m['unit'] or '', m['operator'] or '', m.get('recorded_at') or '')
                for m in s['materials']])
            self._fill('维修日志', [
                ((r['started_at'] or '')[11:19], r['sn'], r['action'], r.get('result') or '',
                 r.get('repair_method') or r.get('defect_code') or '', r.get('operator') or '', '')
                for r in s['history']])
            self._fill('QC控制', [
                (w['work_order_no'], w['ng_sn'],
                 f'{line_tag(w.get("source_station",""))[0]} {w.get("source_station","")}',
                 w['status'],
                 (w.get('repair_completed_at') or '')[11:19],
                 w.get('repair_method') or '',
                 w.get('repair_result') or '',
                 len(w.get('retest_history_parsed') or []))
                for w in s['work_orders']])
            self._fill('扫码记录', [
                ((x['last_seen'] or '')[11:19], x['sn'], x['result'], 'SYNC' if x['mes_synced'] else 'QUEUE')
                for x in s['scans']])
            self._fill('NG拦截', [
                ((x['detected_at'] or '')[11:19], x['sn'], x['source'], x['defect_code'] or '-')
                for x in s['ng_active']])
            self._fill('MES缓存', [
                (x['sn'], x['source_station'] or '', x['batch_id'] or '', x['registry_version'], x['synced_at'])
                for x in s['cached_ng']])
            self._fill('MES通信', [
                (o['event_type'], o['sn'], o['result'], o['attempts'], o['created_at'])
                for o in s['outbox']])
            self._fill('修改记录', [
                (c['change_id'], c['version'], c['component'], c['reason'], c['summary'], c['verification'], c['changed_at'])
                for c in s['changes']])
        except Exception as ex:
            self.status_lbl.setText(f'Refresh error: {ex}')

        # Refresh statistics tab
        try:
            if hasattr(self, 'stat_cards'):
                self._refresh_stats()
        except Exception:
            pass

    def _worker(self):
        while self.running:
            try:
                pending = self.core.fetch_pending_handovers()
                for r in pending:
                    wo = r.get('repairWorkOrderNo') or r.get('requestId', '')
                    sn = r.get('batchId', '')
                    if wo and sn:
                        try:
                            self.core.receive_repair(sn)
                        except Exception:
                            pass
                self.core.fetch_active_repairs()
                self.core.fetch_ng_releases()
                self.core.sync_ng_registry()
                self.core.sync_outbox()
                self.core.heartbeat()
            except Exception:
                pass
            time.sleep(5)

    def _build_stats_tab(self):
        """Build the 统计分析 tab with sub-widgets and summary cards."""
        stats_tab = QWidget()
        stats_tab_layout = QVBoxLayout(stats_tab)
        stats_tab_layout.setSpacing(8)

        # ── Summary cards row ──────────────────────────────────────────────────────
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.stat_cards = {}
        card_configs = [
            ('total_wos',     '工单总数 / Total WOs',         '#67e8f9'),
            ('completed',     '已完成 / Completed',            '#22c55e'),
            ('in_progress',  '维修中 / In Progress',         '#38bdf8'),
            ('queued',        '待接收 / Queued',               '#f59e0b'),
            ('scrapped',      '报废 / Scrapped',              '#ef4444'),
            ('completion_rate','完成率 % / Completion %',     '#a78bfa'),
            ('avg_repair_min','平均维修分钟 / Avg Repair Min', '#fbbf24'),
            ('scrapped_pct',  '报废率 % / Scrap %',          '#f97316'),
        ]
        for key, label, color in card_configs:
            fr = QFrame()
            fr.setStyleSheet(f'background:#10243b;border:2px solid {color};border-radius:8px;padding:6px;min-width:120px')
            lbl_val = QLabel('—')
            lbl_val.setStyleSheet(f'color:{color};font-size:22px;font-weight:bold')
            lbl_sub = QLabel(label)
            lbl_sub.setStyleSheet(f'color:{color};font-size:10px')
            box = QVBoxLayout(fr)
            box.addWidget(lbl_val); box.addWidget(lbl_sub); box.addStretch()
            cards.addWidget(fr)
            self.stat_cards[key] = lbl_val
        cards.addStretch()
        stats_tab_layout.addLayout(cards)

        # ── Generate report button ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.report_period_combo = QLineEdit()
        self.report_period_combo.setPlaceholderText('报表周期标签 e.g. 2026-07-W3')
        self.report_days_input = QLineEdit()
        self.report_days_input.setPlaceholderText('Days (default 30)')
        self.report_days_input.setText('30')
        self.report_days_input.setMaximumWidth(80)
        gen_btn = QPushButton('统计报告 / Statistics Report')
        gen_btn.setStyleSheet('background:#16a34a;padding:8px 16px;border-radius:4px;font-weight:bold')
        gen_btn.clicked.connect(self._generate_report)
        iqc_btn = QPushButton('物料质量报告 / IQC Report → MES')
        iqc_btn.setStyleSheet('background:#7c3aed;padding:8px 16px;border-radius:4px;font-weight:bold')
        iqc_btn.clicked.connect(self._generate_iqc_report)
        btn_row.addWidget(QLabel('报表周期:'))
        btn_row.addWidget(self.report_period_combo)
        btn_row.addWidget(QLabel('天数:'))
        btn_row.addWidget(self.report_days_input)
        btn_row.addWidget(gen_btn)
        btn_row.addWidget(iqc_btn)
        btn_row.addStretch()
        self.report_status_lbl = QLabel('')
        btn_row.addWidget(self.report_status_lbl)
        stats_tab_layout.addLayout(btn_row)

        # ── Sub-tab widget ───────────────────────────────────────────────────────
        sub_tabs = QTabWidget()
        sub_tabs.setStyleSheet('QTabWidget::pane{border:1px solid #334155} QTabBar::tab{background:#1e293b;color:#94a3b8;padding:6px 12px} QTabBar::tab:selected{background:#0891b2;color:white}')

        self.stat_tables = {}

        def make_sub_tab(name, cols, width_hint=120):
            w = QWidget(); ly = QVBoxLayout(w)
            t = QTableWidget(0, len(cols))
            t.setHorizontalHeaderLabels(cols)
            t.horizontalHeader().setStretchLastSection(True)
            for i in range(len(cols)):
                t.horizontalHeader().setSectionResizeMode(i, QHeaderView.Interactive)
                t.setColumnWidth(i, width_hint)
            self.stat_tables[name] = t
            ly.addWidget(t)
            sub_tabs.addTab(w, name)
            return t

        # Sub-tab: 缺陷分布 (defect distribution)
        make_sub_tab('缺陷分布', ['#', '缺陷代码', '缺陷名称', '次数', '占比%'], 90)
        # Sub-tab: 物料排名 (top materials)
        make_sub_tab('物料排名', ['排名', '物料编码', '名称', '使用次数', '总用量'], 110)
        # Sub-tab: 站别统计 (by station)
        make_sub_tab('站别统计', ['站别代码', '站别名称', '工单数', '类别'], 100)
        # Sub-tab: 类别汇总 (by line category: SMT/AUTO/MANUAL)
        make_sub_tab('类别汇总', ['类别', '工单数', '占比%'], 80)
        # Sub-tab: 工单状态 (WO status breakdown)
        make_sub_tab('工单状态', ['状态', '工单数'], 80)
        # Sub-tab: 维修方法 (repair method)
        make_sub_tab('维修方法', ['维修方法', '次数'], 120)
        # Sub-tab: 每日趋势 (daily trend)
        make_sub_tab('每日趋势', ['日期', '工单数', '图形'], 80)
        # Sub-tab: 站×物料 (station × material matrix)
        make_sub_tab('站×物料', ['物料编码', '物料名称', 'ICT', 'FCT', '组装ATE', '超声', '老化', '高压', '包装ATE', 'SMT', '其他'], 80)
        # Sub-tab: 站×缺陷 (station × defect)
        make_sub_tab('站×缺陷', ['缺陷代码', '缺陷名称', 'ICT', 'FCT', '组装ATE', '超声', '老化', '高压', '包装ATE', 'SMT', '其他'], 80)
        # Sub-tab: 物料追溯 (WMS material traceability with IQC status)
        make_sub_tab('物料追溯/IQC',
            ['工单号', 'SN', '物料编码', '批号', '供应商', '仓位',
             '收料时间', 'IQC判定', '入库事务', '领料事务', '领料时间', '操作员', '记录时间'], 100)

        stats_tab_layout.addWidget(sub_tabs)
        self.tabs.addTab(stats_tab, '统计分析 / Statistics')

    def _bar_text(self, count, max_count, width=20):
        """Return ASCII bar string."""
        if not max_count: return ''
        filled = int(count / max_count * width)
        return '█' * filled + '░' * (width - filled)

    def _generate_report(self):
        period = self.report_period_combo.text().strip() or None
        try:
            days = int(self.report_days_input.text().strip() or '30')
        except ValueError:
            days = 30
        try:
            result = self.core.submit_statistics_report(days=days, period_label=period)
            if result.get('ok'):
                self.report_status_lbl.setText(f"✔ 报告已提交 / Report submitted: {result['report_id']}")
                self.report_status_lbl.setStyleSheet('color:#22c55e;font-size:12px')
                self._refresh_stats()
            else:
                self.report_status_lbl.setText(f"✘ 提交失败: {result.get('response', {})}")
                self.report_status_lbl.setStyleSheet('color:#ef4444;font-size:12px')
        except Exception as ex:
            self.report_status_lbl.setText(f'Error: {ex}')
            self.report_status_lbl.setStyleSheet('color:#ef4444;font-size:12px')

    def _generate_iqc_report(self):
        """Submit material traceability + IQC quality report to MES."""
        self.report_status_lbl.setText('提交中...')
        self.report_status_lbl.setStyleSheet('color:#fbbf24;font-size:12px')
        try:
            result = self.core.submit_material_trace_report(days=90)
            if result.get('ok'):
                self.report_status_lbl.setText(
                    f"✔ 物料质量报告已提交 / IQC Report submitted: {result['report_id']} ({result['total_records']} records)")
                self.report_status_lbl.setStyleSheet('color:#22c55e;font-size:12px')
                self._refresh_stats()
            else:
                self.report_status_lbl.setText(f"✘ 提交失败: {result.get('response', {})}")
                self.report_status_lbl.setStyleSheet('color:#ef4444;font-size:12px')
        except Exception as ex:
            self.report_status_lbl.setText(f'Error: {ex}')
            self.report_status_lbl.setStyleSheet('color:#ef4444;font-size:12px')

    def _refresh_stats(self):
        try:
            stats = self.core.fetch_statistics(days=30)
            total = stats.get('total_wos', 0) or 1

            # Update cards
            self.stat_cards['total_wos'].setText(str(stats.get('total_wos', 0)))
            self.stat_cards['completed'].setText(str(stats.get('completed', 0)))
            self.stat_cards['in_progress'].setText(str(stats.get('in_progress', 0)))
            self.stat_cards['queued'].setText(str(len(self.core.fetch_pending_handovers())))
            self.stat_cards['scrapped'].setText(str(stats.get('scrapped', 0)))
            self.stat_cards['completion_rate'].setText(f"{stats.get('completion_rate', 0)}%")
            self.stat_cards['avg_repair_min'].setText(f"{stats.get('avg_repair_min', 0)}m")
            self.stat_cards['scrapped_pct'].setText(f"{stats.get('scrapped_pct', 0)}%")

            # Defect distribution
            t = self.stat_tables.get('缺陷分布')
            if t:
                total_def = sum(d['count'] for d in stats.get('defect_distribution', [])) or 1
                t.setRowCount(len(stats.get('defect_distribution', [])))
                for i, d in enumerate(stats.get('defect_distribution', [])):
                    pct = round(d['count'] / total_def * 100, 1)
                    for col, val in enumerate([i+1, d['code'], d['name'], d['count'], pct]):
                        item = QTableWidgetItem(str(val))
                        item.setForeground(QColor('#f8fafc'))
                        t.setItem(i, col, item)
                    bar_item = QTableWidgetItem(self._bar_text(d['count'], stats['defect_distribution'][0]['count'] if stats['defect_distribution'] else 1))
                    bar_item.setForeground(QColor('#f59e0b'))
                    t.setItem(i, 3, bar_item)

            # Top materials
            t = self.stat_tables.get('物料排名')
            if t:
                t.setRowCount(len(stats.get('top_materials', [])))
                for i, m in enumerate(stats.get('top_materials', [])):
                    for col, val in enumerate([i+1, m['code'], m['name'], m['usage_count'], m['total_qty']]):
                        item = QTableWidgetItem(str(val))
                        item.setForeground(QColor('#f8fafc'))
                        t.setItem(i, col, item)

            # Station breakdown
            t = self.stat_tables.get('站别统计')
            if t:
                st_map = {r['code']: r['station'] for r in stats.get('station_breakdown', [])}
                LINE_CAT = {'manu_ict':'MANUAL','manu_fct':'MANUAL','manu_depanel':'MANUAL',
                            'manu_assem_ate':'MANUAL','manu_supersonic':'MANUAL','manu_agingcab':'AUTO',
                            'manu_hivolt_ate':'AUTO','manu_package_ate':'AUTO',
                            'manu_smt_aoi':'SMT','manu_smt_paste':'SMT','manu_smt_pick':'SMT'}
                t.setRowCount(len(stats.get('station_breakdown', [])))
                for i, r in enumerate(stats.get('station_breakdown', [])):
                    for col, val in enumerate([r['code'], r['station'], r['count'], LINE_CAT.get(r['code'], 'OTHER')]):
                        item = QTableWidgetItem(str(val))
                        item.setForeground(QColor('#f8fafc'))
                        t.setItem(i, col, item)

            # Line category summary
            t = self.stat_tables.get('类别汇总')
            if t:
                grand = sum(r['count'] for r in stats.get('line_category_breakdown', [])) or 1
                t.setRowCount(len(stats.get('line_category_breakdown', [])))
                for i, r in enumerate(stats.get('line_category_breakdown', [])):
                    pct = round(r['count'] / grand * 100, 1)
                    for col, val in enumerate([r['category'], r['count'], pct]):
                        item = QTableWidgetItem(str(val))
                        item.setForeground(QColor('#f8fafc'))
                        t.setItem(i, col, item)
                    bar_item = QTableWidgetItem(self._bar_text(r['count'], stats['line_category_breakdown'][0]['count'] if stats['line_category_breakdown'] else 1))
                    bar_item.setForeground(QColor('#8b5cf6'))
                    t.setItem(i, 1, bar_item)

            # Status breakdown
            t = self.stat_tables.get('工单状态')
            if t:
                t.setRowCount(len(stats.get('status_breakdown', [])))
                for i, r in enumerate(stats.get('status_breakdown', [])):
                    for col, val in enumerate([r['status'], r['count']]):
                        item = QTableWidgetItem(str(val))
                        item.setForeground(QColor('#f8fafc'))
                        t.setItem(i, col, item)

            # Method distribution
            t = self.stat_tables.get('维修方法')
            if t:
                t.setRowCount(len(stats.get('method_distribution', [])))
                for i, r in enumerate(stats.get('method_distribution', [])):
                    for col, val in enumerate([r['method'], r['count']]):
                        item = QTableWidgetItem(str(val))
                        item.setForeground(QColor('#f8fafc'))
                        t.setItem(i, col, item)
                    bar_item = QTableWidgetItem(self._bar_text(r['count'], stats['method_distribution'][0]['count'] if stats['method_distribution'] else 1))
                    bar_item.setForeground(QColor('#38bdf8'))
                    t.setItem(i, 1, bar_item)

            # Daily trend
            t = self.stat_tables.get('每日趋势')
            if t:
                trend = stats.get('daily_trend', [])
                max_daily = max((d['count'] for d in trend), default=1)
                t.setRowCount(len(trend))
                for i, d in enumerate(trend):
                    for col, val in enumerate([d['day'], d['count'], self._bar_text(d['count'], max_daily)]):
                        item = QTableWidgetItem(str(val))
                        item.setForeground(QColor('#f8fafc') if col < 2 else QColor('#22c55e'))
                        t.setItem(i, col, item)

            # Station × Material matrix
            t = self.stat_tables.get('站×物料')
            if t:
                sm = stats.get('station_materials', {})
                LINE_CAT = {'manu_ict':'ICT','manu_fct':'FCT','manu_depanel':'DEPANEL',
                            'manu_assem_ate':'组装ATE','manu_supersonic':'超声','manu_agingcab':'老化',
                            'manu_hivolt_ate':'高压','manu_package_ate':'包装ATE',
                            'manu_smt_aoi':'SMT','manu_smt_paste':'SMT','manu_smt_pick':'SMT'}
                # Collect unique materials across all stations
                all_mats = {}
                for station, mats in sm.items():
                    for m in mats:
                        key = m['code']
                        if key not in all_mats:
                            all_mats[key] = {'name': m['name'], 'counts': {}}
                        all_mats[key]['counts'][station] = m['usage_count']
                rows = sorted(all_mats.keys(), key=lambda k: -sum(all_mats[k]['counts'].values()))
                t.setRowCount(len(rows))
                # Columns: code, name, ICT, FCT, 组装ATE, 超声, 老化, 高压, 包装ATE, SMT, 其他
                station_order = ['manu_ict','manu_fct','manu_assem_ate','manu_supersonic','manu_agingcab','manu_hivolt_ate','manu_package_ate','manu_smt_aoi']
                col_stations = [s for s in station_order if s in sm or any(s in all_mats[k]['counts'] for k in rows)]
                for i, code in enumerate(rows):
                    mat = all_mats[code]
                    item = QTableWidgetItem(code); item.setForeground(QColor('#67e8f9')); t.setItem(i, 0, item)
                    item = QTableWidgetItem(mat['name']); item.setForeground(QColor('#f8fafc')); t.setItem(i, 1, item)
                    for j, st in enumerate(col_stations):
                        cnt = mat['counts'].get(st, 0)
                        item = QTableWidgetItem(str(cnt) if cnt else '-')
                        item.setForeground(QColor('#22c55e') if cnt > 0 else QColor('#475569'))
                        t.setItem(i, j + 2, item)

            # Station × Defect matrix
            t = self.stat_tables.get('站×缺陷')
            if t:
                sd = stats.get('station_defects', {})
                station_order = ['manu_ict','manu_fct','manu_assem_ate','manu_supersonic','manu_agingcab','manu_hivolt_ate','manu_package_ate','manu_smt_aoi']
                all_defs = {}
                for station, defects in sd.items():
                    for d in defects:
                        key = d['code']
                        if key not in all_defs:
                            all_defs[key] = {'name': d['name'], 'counts': {}}
                        all_defs[key]['counts'][station] = d['count']
                rows = sorted(all_defs.keys(), key=lambda k: -sum(all_defs[k]['counts'].values()))[:30]
                t.setRowCount(len(rows))
                for i, code in enumerate(rows):
                    def_ = all_defs[code]
                    item = QTableWidgetItem(code); item.setForeground(QColor('#f59e0b')); t.setItem(i, 0, item)
                    item = QTableWidgetItem(def_['name']); item.setForeground(QColor('#f8fafc')); t.setItem(i, 1, item)
                    for j, st in enumerate(station_order):
                        cnt = def_['counts'].get(st, 0)
                        item = QTableWidgetItem(str(cnt) if cnt else '-')
                        item.setForeground(QColor('#ef4444') if cnt > 3 else (QColor('#fbbf24') if cnt > 0 else QColor('#475569')))
                        t.setItem(i, j + 2, item)

            # Material traceability / IQC sub-tab
            t = self.stat_tables.get('物料追溯/IQC')
            if t:
                try:
                    traces = self.core.fetch_material_trace(days=90, limit=500)
                except Exception:
                    traces = []
                t.setRowCount(len(traces))
                for i, r in enumerate(traces):
                    iqc = (r.get('iqc_status') or '').upper()
                    row_vals = [
                        r.get('wo_no', ''),
                        r.get('ng_sn', ''),
                        r.get('material_code', ''),
                        r.get('lot_no', ''),
                        r.get('supplier_code', ''),
                        r.get('location_code', ''),
                        (r.get('received_at') or '')[:19],
                        iqc,
                        r.get('inbound_tx_no', ''),
                        r.get('pick_tx_no', ''),
                        (r.get('pick_issued_at') or '')[:19],
                        r.get('operator', ''),
                        (r.get('replaced_at') or '')[:19],
                    ]
                    color = QColor('#22c55e') if iqc == 'RELEASED' else (
                        QColor('#ef4444') if iqc == 'REJECTED' else (
                            QColor('#f59e0b') if iqc == 'HOLD' else QColor('#94a3b8')))
                    for col, val in enumerate(row_vals):
                        item = QTableWidgetItem(str(val))
                        item.setForeground(color if col == 7 else QColor('#f8fafc'))
                        t.setItem(i, col, item)

        except Exception as ex:
            print(f'Stats refresh error: {ex}')

    def closeEvent(self, e):
        self.running = False
        e.accept()


if __name__ == '__main__':
    app = QApplication([])
    w = Rework3D()
    w.showMaximized()
    raise SystemExit(app.exec())
