"""Qt/WebGL desktop shell for the manual-line depanel station."""
from __future__ import annotations
import os, pathlib, sys

BASE_DIR = pathlib.Path(__file__).resolve().parent
ICT_DIR = BASE_DIR.parent / "(03)ICT"
if str(ICT_DIR) not in sys.path: sys.path.insert(0, str(ICT_DIR))
import ict_qt_3d_agent as shared
shared.BASE_DIR = BASE_DIR
shared.ENGINE_PATH = BASE_DIR / "depanel_heartbeat_agent.py"
shared.COMMAND_PATH = BASE_DIR / "depanel_qt_command.json"
shared.DEFAULT_3D_URL = "http://192.168.6.155:5178/#depanel-agent-3d"

class DepanelQt3dAgent(shared.IctQt3dAgent):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Depanel 3D Station Agent / 分板机三维工位代理")
        self.simulate_button.hide(); self.bypass_test_button.hide()
        self.functions_button.hide()
        toolbar = self.findChild(shared.QFrame, "toolbar")
        self.scanner_input.setPlaceholderText("扫描任一子板 SN / SCAN ANY BOARD SN")
        self.scanner_input.setMinimumWidth(285)
        self.command_buttons["show_ng_sqlite"].hide()
        self.command_buttons["show_sn_sqlite"].setText("SN SQLite")
        for label, command in (("ICT NG","show_ict_ng_sqlite"),
                               ("FCT NG","show_fct_ng_sqlite"),("ICT+FCT NG","show_both_ng_sqlite")):
            button = shared.QPushButton(label)
            button.clicked.connect(lambda _checked=False, c=command: self._open_depanel_sqlite(c))
            toolbar.layout().addWidget(button)
        self.depanel_functions_button = shared.QPushButton("分板操作 / ACTIONS")
        try:
            from PySide6.QtWidgets import QMenu
        except ImportError:
            from PySide2.QtWidgets import QMenu
        menu = QMenu(self.depanel_functions_button)
        for label, command in (("确认 NG 发往回修站 / Send repair", "send_to_repair"),
                               ("申请报废 / Request scrap", "request_scrap")):
            action = menu.addAction(label)
            action.triggered.connect(lambda _checked=False, c=command: self._write_engine_command(c))
        self.depanel_functions_button.setMenu(menu)
        toolbar.layout().addWidget(self.depanel_functions_button)
        self._normalize_labels()
        self.label_timer = shared.QTimer(self); self.label_timer.timeout.connect(self._normalize_labels); self.label_timer.start(500)
        self.scanner_input.setFocus()

    def open_local_sqlite(self, command):
        self._open_depanel_sqlite(command)

    def _open_depanel_sqlite(self, command):
        from qt_sqlite_viewer import show_sqlite
        if command == "show_sn_sqlite":
            show_sqlite(self, BASE_DIR / "depanel_sn.db", "Depanel SN SQLite", ("all_sns",))
        else:
            preferred = {"show_ict_ng_sqlite": ("confirmed_ng", "motherboard_members"),
                         "show_fct_ng_sqlite": ("confirmed_ng", "motherboard_members"),
                         "show_both_ng_sqlite": ("motherboard_members", "confirmed_ng")}[command]
            show_sqlite(self, BASE_DIR / "depanel_ng.db", "Depanel NG SQLite / 分板NG数据库", preferred)

    def _normalize_labels(self):
        for widget in self.findChildren(shared.QLabel):
            widget.setText(widget.text().replace("ICT", "DEPANEL").replace("CSV", "SCANNER"))
        for widget in self.findChildren(shared.QPushButton):
            widget.setText(widget.text().replace("ICT Agent", "Depanel Agent"))

    def start_engine(self):
        if self.engine.state() != shared.QProcess.NotRunning: return
        self.engine.setWorkingDirectory(str(BASE_DIR))
        environment = self.engine.processEnvironment()
        if environment.isEmpty():
            from qt_compat import QProcessEnvironment
            environment = QProcessEnvironment.systemEnvironment()
        environment.insert("DEPANEL_EMBEDDED_ENGINE", "1")
        self.engine.setProcessEnvironment(environment)
        self.engine.start(sys.executable, [str(shared.ENGINE_PATH)])

    def reload_view(self):
        self.web.setUrl(shared.QUrl(os.environ.get("DEPANEL_3D_URL", shared.DEFAULT_3D_URL)))

def main():
    app=shared.QApplication(sys.argv)
    window=DepanelQt3dAgent(); window.show()
    return app.exec()

if __name__ == "__main__": raise SystemExit(main())
