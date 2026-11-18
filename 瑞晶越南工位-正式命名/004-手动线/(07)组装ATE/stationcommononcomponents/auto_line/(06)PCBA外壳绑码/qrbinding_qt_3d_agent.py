"""Qt/WebGL shell for the PCBA-to-shell binding production engine.

qrbinding.py remains the only business engine.  This file only supplies the
3D operator surface and forwards scanner/actions through the engine command
mailbox, keeping 2D and 3D behaviour identical.
"""
from __future__ import annotations

import os
import pathlib
import sys

BASE_DIR = pathlib.Path(__file__).resolve().parent
ICT_DIR = BASE_DIR.parent / "(03)ICT"
if str(ICT_DIR) not in sys.path:
    sys.path.insert(0, str(ICT_DIR))

import ict_qt_3d_agent as shared  # noqa: E402

shared.BASE_DIR = BASE_DIR
shared.ENGINE_PATH = BASE_DIR / "qrbinding.py"
shared.COMMAND_PATH = BASE_DIR / "qrbinding_qt_command.json"
shared.DEFAULT_3D_URL = "http://192.168.6.155:5178/#qrbinding-agent-3d"


class QrBindingQt3dAgent(shared.IctQt3dAgent):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PCBA Shell Binding 3D Station Agent / PCBA外壳绑码三维工位")
        self.simulate_button.hide()
        self.bypass_test_button.hide()
        self.scanner_input.setPlaceholderText("扫描板码或外壳码 / SCAN BOARD OR SHELL SN")
        self.scanner_input.setMinimumWidth(330)
        self.start_button.setText("启动绑码 Agent")
        self.command_buttons["show_sn_sqlite"].setText("绑定表 SQLite")
        self.command_buttons["show_ng_sqlite"].setText("拦截记录 SQLite")
        self.functions_button.setText("绑码功能 / BINDING")
        menu = self.functions_menu
        menu.clear()
        for label, command in (
            ("重置当前配对 / Reset pair", "reset_pair"),
            ("SN规则 / SN rules", "show_rules"),
            ("映射表 / Mapping table", "show_mapping_table"),
            ("导出 CSV / Export", "export_csv"),
            ("申请报废 / Scrap", "request_scrap"),
            ("快速解除报警 / Release alarm", "release_alarm"),
        ):
            action = menu.addAction(label)
            action.triggered.connect(lambda _checked=False, c=command: self._write_engine_command(c))
        for widget in self.findChildren(shared.QLabel):
            widget.setText(widget.text().replace("ICT", "QR BINDING").replace("CSV", "SCANNER"))

    def start_engine(self) -> None:
        if self.engine.state() != shared.QProcess.NotRunning:
            return
        if not shared.ENGINE_PATH.exists():
            shared.QMessageBox.critical(self, "QR Binding", f"Missing production engine:\n{shared.ENGINE_PATH}")
            return
        self.status_text.setText("Starting binding production engine…")
        self.start_button.setEnabled(False)
        self.engine.setWorkingDirectory(str(BASE_DIR))
        environment = self.engine.processEnvironment()
        if environment.isEmpty():
            from qt_compat import QProcessEnvironment
            environment = QProcessEnvironment.systemEnvironment()
        environment.insert("QRBINDING_EMBEDDED_ENGINE", "1")
        self.engine.setProcessEnvironment(environment)
        self.engine.start(sys.executable, [str(shared.ENGINE_PATH), "--worker"])

    def reload_view(self) -> None:
        url = os.environ.get("QRBINDING_3D_URL", shared.DEFAULT_3D_URL).strip() or shared.DEFAULT_3D_URL
        self.web.setUrl(shared.QUrl(url))

    def open_local_sqlite(self, view: str) -> None:
        from qt_sqlite_viewer import show_sqlite
        if view == "show_sn_sqlite":
            show_sqlite(self, BASE_DIR / "binding_records.db", "Binding Mapping SQLite / 绑码映射表", ("bindings", "shell_board_mapping"))
        else:
            show_sqlite(self, BASE_DIR / "binding_guard.db", "Binding Guard SQLite / 绑码拦截记录", ("duplicate_hits", "ng_hits", "binding_pairs"))

    def _engine_started(self) -> None:
        super()._engine_started()
        self.status_text.setText(f"Binding production engine running · PID {self.engine.processId()}")
        self.start_button.setText("绑码 Agent 已运行")


def main() -> int:
    shared.validate_runtime(os.environ.get("RUIJING_RUNTIME_PROFILE", ""))
    app = shared.QApplication(sys.argv)
    app.setApplicationName(f"Ruijing QR Binding 3D Station Agent ({shared.QT_API})")
    window = QrBindingQt3dAgent()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
