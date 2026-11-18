# -*- coding: utf-8 -*-
"""Local Three.js viewer backed by the station 57 SQL Server reader."""
import argparse
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANUAL_SHARED = HERE.parent.parent / "002-自动线"
if MANUAL_SHARED.exists():
    sys.path.insert(0, str(MANUAL_SHARED))

from aging_cab_core import AgingCabCore

PORT = 8757


class LiveState:
    def __init__(self):
        self.core = AgingCabCore()
        self.lock = threading.RLock()
        self.error = "正在连接 SQL Server…"
        self.updated_at = ""

    def poll_forever(self):
        while True:
            try:
                self.core.poll_sql_once()
                self.core.sync_once()
                with self.lock:
                    self.error = ""
                    self.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as exc:
                with self.lock:
                    self.error = str(exc)[:300]
            time.sleep(2)

    def payload(self):
        with self.lock:
            areas = list(self.core.area_state)
            slots = list(self.core.stand_slots)
            error = self.error
            updated_at = self.updated_at
        active = {
            str(v) for row in areas for v in (row.get("leftStand"), row.get("rightStand"))
            if str(v).isdigit() and str(v) != "0"
        }
        slot_map = {}
        for row in slots:
            stand = str(row.get("stand", ""))
            if stand in active:
                slot_map.setdefault(stand, []).append(row)
        return {
            "ok": not bool(error), "error": error, "updatedAt": updated_at,
            "areas": areas, "slots": slot_map,
            "positionCount": len(areas), "standCount": len(active),
            "occupiedCount": sum(1 for row in areas for key in ("leftStand", "rightStand")
                                 if str(row.get(key, "0")).isdigit() and str(row.get(key)) != "0"),
        }


def asset_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def make_handler(state):
    root = asset_root()

    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            clean = path.split("?", 1)[0].split("#", 1)[0].lstrip("/") or "aging-line.html"
            return str(root / clean)

        def do_GET(self):
            if self.path.split("?", 1)[0] == "/api/state":
                body = json.dumps(state.payload(), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def log_message(self, _format, *_args):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    state = LiveState()
    threading.Thread(target=state.poll_forever, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
