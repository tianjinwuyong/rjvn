"""Qt/WebGL desktop shell for the FCT production Agent."""
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
shared.ENGINE_PATH = BASE_DIR / "fct_agent.py"
shared.COMMAND_PATH = BASE_DIR / "fct_qt_command.json"
shared.DEFAULT_3D_URL = "http://192.168.6.155:5178/#fct-agent-3d"


class FctQt3dAgent(shared.IctQt3dAgent):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FCT 3D Station Agent / FCT 三维工位代理")
        self.start_button.setText("启动 FCT Agent" if self.engine.state() == shared.QProcess.NotRunning else "FCT Agent 已运行")
        self._normalize_labels()
        self.retest_button.setText("确认复检")
        self.retest_button.setToolTip("确认下一次扫码或Excel组为复检；仅放行一次，随后自动恢复重码拦截")
        self.scanner_input.setPlaceholderText("扫描 FCT SN / SCAN FCT SN")

    def open_local_sqlite(self, view: str) -> None:
        from qt_sqlite_viewer import show_sqlite
        preferred = (("all_sns", "processed_groups") if view == "show_sn_sqlite"
                     else ("fct_batches", "fct_boards", "mes_event_outbox"))
        show_sqlite(self, BASE_DIR / "fct_agent.db", "FCT Local SQLite / FCT 本地数据库", preferred)

    def _normalize_labels(self) -> None:
        """Remove every inherited ICT caption from the FCT desktop shell."""
        for widget in self.findChildren(shared.QLabel):
            value = widget.text()
            if "ICT" in value:
                widget.setText(value.replace("ICT", "FCT").replace("CSV", "Excel"))
        for widget in self.findChildren(shared.QPushButton):
            value = widget.text()
            if "ICT" in value:
                widget.setText(value.replace("ICT", "FCT"))
            tip = widget.toolTip()
            if "ICT" in tip:
                widget.setToolTip(tip.replace("ICT", "FCT").replace("CSV", "Excel"))

    def start_engine(self) -> None:
        if self.engine.state() != shared.QProcess.NotRunning:
            return
        if not shared.ENGINE_PATH.exists():
            shared.QMessageBox.critical(self, "FCT Agent", f"Missing production engine:\n{shared.ENGINE_PATH}")
            return
        self.status_text.setText("Starting FCT production engine…")
        self.start_button.setEnabled(False)
        self.engine.setWorkingDirectory(str(BASE_DIR))
        environment = self.engine.processEnvironment()
        if environment.isEmpty():
            from qt_compat import QProcessEnvironment
            environment = QProcessEnvironment.systemEnvironment()
        environment.insert("FCT_EMBEDDED_ENGINE", "1")
        self.engine.setProcessEnvironment(environment)
        self.engine.start(sys.executable, [str(shared.ENGINE_PATH)])

    def reload_view(self) -> None:
        url = os.environ.get("FCT_3D_URL", shared.DEFAULT_3D_URL).strip() or shared.DEFAULT_3D_URL
        self.web.setUrl(shared.QUrl(url))

    def _engine_started(self) -> None:
        super()._engine_started()
        self.status_text.setText(f"FCT production engine running · PID {self.engine.processId()}")
        self.start_button.setText("FCT Agent 已运行")


def main() -> int:
    shared.validate_runtime(os.environ.get("RUIJING_RUNTIME_PROFILE", ""))
    app = shared.QApplication(sys.argv)
    app.setApplicationName(f"Ruijing FCT 3D Station Agent ({shared.QT_API})")
    window = FctQt3dAgent()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
