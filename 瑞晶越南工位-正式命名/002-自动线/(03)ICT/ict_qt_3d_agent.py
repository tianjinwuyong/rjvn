"""PySide6 shell for the ICT production Agent and its WebGL digital twin.

The production engine remains ict_agent.py.  This shell supervises that process
and embeds the read-only MES 3D projection.  A WebGL failure cannot stop CSV,
scanner, SQLite, alarm, or outbox processing in the production engine.
"""

from __future__ import annotations

import os
import pathlib
import sys
import json
import random
import time

# Must be set before QtWebEngine initializes. Some industrial PCs blacklist
# their integrated GPU even though WebGL works correctly in software fallback.
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-webgl --ignore-gpu-blocklist")

MANUAL_LINE_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(MANUAL_LINE_DIR) not in sys.path:
    sys.path.insert(0, str(MANUAL_LINE_DIR))

from qt_compat import (  # noqa: E402
    QApplication, QColor, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPalette, QProcess, QPushButton, QScrollArea, QTimer, QUrl, Qt,
    QVBoxLayout, QWebEngineView, QWidget, QT_API, validate_runtime,
)
from qt_sqlite_viewer import show_sqlite
try:
    from PySide6.QtWidgets import QLineEdit, QMenu, QScrollArea
except ImportError:
    from PySide2.QtWidgets import QLineEdit, QMenu, QScrollArea


BASE_DIR = pathlib.Path(__file__).resolve().parent
ENGINE_PATH = BASE_DIR / "ict_agent.py"
COMMAND_PATH = BASE_DIR / "ict_qt_command.json"
DEFAULT_3D_URL = "http://192.168.6.155:5178/#ict-agent-3d"


class IctQt3dAgent(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ICT 3D Station Agent / ICT 三维工位代理")
        self.resize(1480, 900)
        self.setMinimumSize(1080, 680)
        self.engine = QProcess(self)
        self.engine.setProcessChannelMode(QProcess.MergedChannels)
        self.engine.started.connect(self._engine_started)
        self.engine.finished.connect(self._engine_finished)
        self.engine.errorOccurred.connect(self._engine_error)
        self._build_ui()
        QTimer.singleShot(250, self.start_engine)

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame(root)
        toolbar.setObjectName("toolbar")
        toolbar.setMinimumWidth(1700)
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(18, 11, 18, 11)

        title = QLabel("ICT 3D STATION AGENT  ·  ICT 三维工位代理")
        title.setObjectName("title")
        bar.addWidget(title)
        bar.addStretch(1)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusOffline")
        self.status_text = QLabel("Production engine starting…")
        bar.addWidget(self.status_dot)
        bar.addWidget(self.status_text)

        self.scanner_input = QLineEdit()
        self.scanner_input.setPlaceholderText("扫描 SN / SCAN SN")
        self.scanner_input.setMinimumWidth(235)
        self.scanner_input.returnPressed.connect(self.submit_scanner_sn)
        bar.addWidget(self.scanner_input)

        self.start_button = QPushButton("启动 ICT Agent")
        self.start_button.clicked.connect(self.start_engine)
        bar.addWidget(self.start_button)

        self.simulate_button = QPushButton("创建测试母板")
        self.simulate_button.setObjectName("simulateButton")
        self.simulate_button.clicked.connect(self.simulate_motherboard)
        bar.addWidget(self.simulate_button)

        self.bypass_test_button = QPushButton("测试重码旁路")
        self.bypass_test_button.setObjectName("bypassTestButton")
        self.bypass_test_button.setToolTip("仅本按钮生成的一盘模拟SN跳过重码；真实扫码和真实CSV不旁路")
        self.bypass_test_button.clicked.connect(self.test_duplicate_bypass)
        bar.addWidget(self.bypass_test_button)

        self.retest_button = QPushButton("确认复检")
        self.retest_button.setObjectName("retestButton")
        self.retest_button.setToolTip("下一次扫码或CSV作为一次复检，不按重码处理；使用后自动恢复")
        self.retest_button.clicked.connect(self.arm_retest_scan)
        bar.addWidget(self.retest_button)

        self.view_button = QPushButton("刷新 3D")
        self.view_button.clicked.connect(self.reload_view)
        bar.addWidget(self.view_button)
        self.language_index = 0
        self.language_button = QPushButton("中文 / EN / VI")
        self.language_button.clicked.connect(self.cycle_language)
        bar.addWidget(self.language_button)
        self.command_buttons = {}
        for label, command in (("SN SQLite", "show_sn_sqlite"), ("NG SQLite", "show_ng_sqlite"),
                               ("快速解除报警", "release_duplicate_alarm")):
            button = QPushButton(label)
            self.command_buttons[command] = button
            if command in ("show_sn_sqlite", "show_ng_sqlite"):
                button.clicked.connect(lambda _checked=False, c=command: self.open_local_sqlite(c))
            else:
                button.clicked.connect(lambda _checked=False, c=command: self._write_engine_command(c))
            bar.addWidget(button)

        # Less frequently used production controls live in one compact menu.
        # Every action is executed by the original 2D production engine so the
        # 2D and 3D shells cannot develop different business rules.
        self.functions_button = QPushButton("更多功能 / FUNCTIONS")
        self.functions_menu = QMenu(self.functions_button)
        for label, command in (
            ("超时复检许可 / Overtime retest", "grant_overtime_retest"),
            ("维修复活接收单 / Repair return", "show_handover_sheet"),
            ("确认去向 / Confirm route", "confirm_route"),
            ("系统自检 / Self-test", "run_self_test"),
            ("清空本地 SQLite / Clear local data", "clear_local_sqlite"),
        ):
            action = self.functions_menu.addAction(label)
            action.triggered.connect(lambda _checked=False, c=command: self._write_engine_command(c))
        self.functions_button.setMenu(self.functions_menu)
        bar.addWidget(self.functions_button)

        self.web = QWebEngineView(root)
        self.web.setContextMenuPolicy(Qt.NoContextMenu)
        self.web.loadStarted.connect(lambda: self.view_status.setText("3D loading…"))
        self.web.loadFinished.connect(self._view_loaded)

        footer = QFrame(root)
        footer.setObjectName("footer")
        foot = QHBoxLayout(footer)
        foot.setContentsMargins(18, 8, 18, 8)
        self.view_status = QLabel("3D initializing…")
        authority = QLabel("3D只显示和报警，不锁定、不放行、不改变工位活动  ·  生产控制由本机 ICT Agent 执行")
        authority.setObjectName("authority")
        foot.addWidget(self.view_status)
        foot.addStretch(1)
        foot.addWidget(authority)

        toolbar_scroll = QScrollArea(root)
        toolbar_scroll.setWidgetResizable(False)
        toolbar_scroll.setFrameShape(QFrame.NoFrame)
        toolbar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        toolbar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        toolbar_scroll.setWidget(toolbar)
        layout.addWidget(toolbar_scroll)
        layout.addWidget(self.web, 1)
        layout.addWidget(footer)
        self.setCentralWidget(root)
        self.setStyleSheet(
            """
            QMainWindow,QWidget { background:#07111f; color:#dbeafe; font-family:'Segoe UI'; }
            #toolbar { background:#0b1728; border-bottom:1px solid #263850; }
            #footer { background:#0b1728; border-top:1px solid #263850; }
            #title { font-size:15px; font-weight:800; color:#e0f2fe; letter-spacing:1px; }
            #statusOffline { color:#ef4444; font-size:17px; }
            #statusOnline { color:#22c55e; font-size:17px; }
            #authority { color:#7dd3fc; font-size:11px; }
            QPushButton { background:#0c4a6e; border:1px solid #38bdf8; border-radius:6px;
                          color:white; padding:7px 12px; font-weight:700; }
            QPushButton:hover { background:#075985; }
            #simulateButton { background:#047857; border-color:#34d399; }
            #simulateButton:hover { background:#059669; }
            #bypassTestButton { background:#6d28d9; border-color:#a78bfa; }
            #bypassTestButton:hover { background:#7c3aed; }
            #retestButton { background:#9a3412; border-color:#fb923c; }
            #retestButton:hover { background:#c2410c; }
            QPushButton:disabled { color:#64748b; border-color:#334155; background:#172033; }
            """
        )
        self.reload_view()

    def start_engine(self) -> None:
        if self.engine.state() != QProcess.NotRunning:
            return
        if not ENGINE_PATH.exists():
            QMessageBox.critical(self, "ICT Agent", f"Missing production engine:\n{ENGINE_PATH}")
            return
        self.status_text.setText("Starting production engine…")
        self.start_button.setEnabled(False)
        self.engine.setWorkingDirectory(str(BASE_DIR))
        environment = self.engine.processEnvironment()
        if environment.isEmpty():
            from qt_compat import QProcessEnvironment
            environment = QProcessEnvironment.systemEnvironment()
        environment.insert("ICT_EMBEDDED_ENGINE", "1")
        self.engine.setProcessEnvironment(environment)
        self.engine.start(sys.executable, [str(ENGINE_PATH)])

    def reload_view(self) -> None:
        url = os.environ.get("ICT_3D_URL", DEFAULT_3D_URL).strip() or DEFAULT_3D_URL
        self.web.setUrl(QUrl(url))

    def simulate_motherboard(self) -> None:
        self._request_simulation("normal_simulation")

    def submit_scanner_sn(self) -> None:
        sn = self.scanner_input.text().strip().upper()
        self.scanner_input.clear()
        if sn:
            self._write_engine_command("scan_sn", sn=sn)
            self.view_status.setText(f"Scanner submitted · {sn}")
        self.scanner_input.setFocus()

    def cycle_language(self) -> None:
        locales = ("zh-CN", "en-US", "vi-VN")
        self.language_index = (self.language_index + 1) % len(locales)
        locale = locales[self.language_index]
        self.web.page().runJavaScript(
            "window.dispatchEvent(new CustomEvent('station-language',{detail:{locale:'" + locale + "'}}))"
        )
        self.language_button.setText({"zh-CN":"中文 / EN / VI", "en-US":"English / 中文 / VI", "vi-VN":"Tiếng Việt / 中文 / EN"}[locale])

    def open_local_sqlite(self, view: str) -> None:
        preferred = ("all_sns", "sn_records") if view == "show_sn_sqlite" else ("ng_batches", "ng_boards", "confirmed_ng")
        show_sqlite(self, BASE_DIR / "ict_ng.db", "ICT Local SQLite / ICT 本地数据库", preferred)

    def test_duplicate_bypass(self) -> None:
        """Create one simulated batch whose generated SNs bypass DUP checks."""
        self._request_simulation("duplicate_bypass_test")

    def arm_retest_scan(self) -> None:
        if self.engine.state() == QProcess.NotRunning:
            QMessageBox.warning(self, "ICT Agent", "ICT production engine is not running")
            return
        self._write_engine_command("arm_retest_scan")
        self.retest_button.setText("复检已确认：请扫码")
        self.retest_button.setEnabled(False)
        self.view_status.setText("One-shot retest armed · scanner or next CSV · DUP bypass once")
        QTimer.singleShot(12_000, self._retest_button_ready)

    def _retest_button_ready(self) -> None:
        self.retest_button.setText("确认复检")
        self.retest_button.setEnabled(True)

    def _write_engine_command(self, command: str, **payload) -> str:
        request_id = f"qt-{int(time.time() * 1000)}"
        temporary = COMMAND_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps({"command": command, "requestId": request_id, **payload}), encoding="utf-8")
        temporary.replace(COMMAND_PATH)
        return request_id

    def _request_simulation(self, mode: str) -> None:
        if self.engine.state() == QProcess.NotRunning:
            QMessageBox.warning(self, "ICT Agent", "ICT production engine is not running")
            return
        request_id = f"qt-{int(time.time() * 1000)}"
        fail_slots = sorted(random.sample(range(1, 7), random.randint(1, 3)))
        self._write_engine_command("simulate_motherboard", mode=mode, failSlots=fail_slots)
        self.simulate_button.setEnabled(False)
        self.bypass_test_button.setEnabled(False)
        self.simulate_button.setText("正在创建6片母板…")
        self.view_status.setText(
            ("DUP bypass test (simulated SN only) · " if mode == "duplicate_bypass_test" else "Simulation requested · ")
            + request_id
        )
        self.web.page().runJavaScript(
            "window.dispatchEvent(new CustomEvent('ict-simulation-start', {detail: {failSlots: "
            + json.dumps(fail_slots)
            + "}}))"
        )
        QTimer.singleShot(3500, self._simulation_button_ready)

    def _simulation_button_ready(self) -> None:
        self.simulate_button.setText("创建测试母板")
        self.simulate_button.setEnabled(True)
        self.bypass_test_button.setEnabled(True)

    def _engine_started(self) -> None:
        self.status_dot.setObjectName("statusOnline")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.status_text.setText(f"ICT production engine running · PID {self.engine.processId()}")
        self.start_button.setText("ICT Agent 已运行")
        self.start_button.setEnabled(False)

    def _engine_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self.status_dot.setObjectName("statusOffline")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.status_text.setText(f"ICT production engine stopped · exit {exit_code}")
        self.start_button.setText("重新启动 ICT Agent")
        self.start_button.setEnabled(True)

    def _engine_error(self, _error: QProcess.ProcessError) -> None:
        self.status_text.setText(self.engine.errorString())
        self.start_button.setEnabled(True)

    def _view_loaded(self, ok: bool) -> None:
        self.view_status.setText("3D connected" if ok else "3D unavailable — ICT production engine remains active")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.engine.state() == QProcess.NotRunning:
            event.accept()
            return
        answer = QMessageBox.question(
            self,
            "关闭窗口",
            "关闭3D窗口不会自动停止生产引擎。是否保持 ICT Agent 运行？",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Cancel:
            event.ignore()
        elif answer == QMessageBox.No:
            self.engine.terminate()
            if not self.engine.waitForFinished(3000):
                self.engine.kill()
            event.accept()
        else:
            self.engine.setParent(None)
            event.accept()


def main() -> int:
    validate_runtime(os.environ.get("RUIJING_RUNTIME_PROFILE", ""))
    app = QApplication(sys.argv)
    app.setApplicationName(f"Ruijing ICT 3D Station Agent ({QT_API})")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#07111f"))
    palette.setColor(QPalette.WindowText, QColor("#dbeafe"))
    app.setPalette(palette)
    window = IctQt3dAgent()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
