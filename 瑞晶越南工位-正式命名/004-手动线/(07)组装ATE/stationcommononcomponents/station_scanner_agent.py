# -*- coding: utf-8 -*-
"""Reusable station scanner agent based on the working FCT/ATE pattern."""
import os
import queue
import sqlite3
import threading
import time
import tkinter as tk
from datetime import datetime

from pynput import keyboard

TCP_PORT = int(os.environ.get("STATION_SCANNER_TCP_PORT", "1003"))
STATION_CODE = os.environ.get("STATION_CODE", "GENERIC_STATION")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", f"{STATION_CODE}.sqlite")
root_ref = [None]


class ScannerAgent:
    def __init__(self, root):
        self.root = root
        root_ref[0] = self
        self._kb_buf = ""
        self._kb_lock = threading.Lock()
        self._scan_queue = queue.Queue()
        self._tcp_socket = None
        self._listener = None
        self._running = True
        self._init_db()
        self._build_ui()
        self._start_keyboard_hook()
        threading.Thread(target=self._start_tcp_server, daemon=True, name="scanner-tcp").start()
        self.root.after(100, self._check_scan_queue)

    def _init_db(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with sqlite3.connect(DB_PATH) as db:
            db.execute("CREATE TABLE IF NOT EXISTS station_scans (id INTEGER PRIMARY KEY AUTOINCREMENT, sn TEXT NOT NULL, source TEXT NOT NULL, scanned_at TEXT NOT NULL)")

    def _build_ui(self):
        self.root.title(f"{STATION_CODE} Scanner Agent / 扫码 Agent")
        self.root.geometry("760x430")
        self.root.configure(bg="#0f172a")
        tk.Label(self.root, text=f"{STATION_CODE}  SCANNER AGENT", bg="#0f172a", fg="#67e8f9", font=("Segoe UI", 18, "bold")).pack(pady=(18, 5))
        self.status = tk.StringVar(value=f"LISTENING / 监听中  TCP:{TCP_PORT}")
        self.last = tk.StringVar(value="Waiting for scan / 等待扫码")
        tk.Label(self.root, textvariable=self.status, bg="#0f172a", fg="#86efac", font=("Segoe UI", 11, "bold")).pack()
        tk.Label(self.root, textvariable=self.last, bg="#1e293b", fg="#f8fafc", font=("Consolas", 24, "bold"), pady=22).pack(fill="x", padx=24, pady=18)
        self.log = tk.Text(self.root, height=9, bg="#020617", fg="#a7f3d0", state="disabled")
        self.log.pack(fill="both", expand=True, padx=24, pady=(0, 18))

    def _start_keyboard_hook(self):
        def on_press(key):
            try:
                if getattr(key, "char", None) and key.char.isalnum():
                    with self._kb_lock:
                        self._kb_buf += key.char.upper()
                elif key in (keyboard.Key.enter, keyboard.Key.tab):
                    with self._kb_lock:
                        raw, self._kb_buf = self._kb_buf.strip(), ""
                    if raw:
                        self._scan_queue.put((raw, "keyboard-wedge"))
            except Exception:
                pass
        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()

    def _start_tcp_server(self):
        import socket
        try:
            self._tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._tcp_socket.bind(("0.0.0.0", TCP_PORT))
            self._tcp_socket.listen(5)
            self._tcp_socket.settimeout(1.0)
            while self._running:
                try: client, _ = self._tcp_socket.accept()
                except socket.timeout: continue
                threading.Thread(target=self._handle_tcp, args=(client,), daemon=True).start()
        except Exception as exc:
            self.root.after(0, lambda: self.status.set(f"KEYBOARD ONLY / TCP failed: {exc}"))

    def _handle_tcp(self, client):
        try:
            raw = client.recv(4096).decode("utf-8", errors="ignore")
            for item in raw.replace("\r", "\n").split("\n"):
                if item.strip(): self._scan_queue.put((item.strip().upper(), f"tcp:{TCP_PORT}"))
            client.sendall(b"OK\r\n")
        finally:
            client.close()

    def _check_scan_queue(self):
        while not self._scan_queue.empty():
            sn, source = self._scan_queue.get()
            self._process_scan_input(sn, source)
        if self._running: self.root.after(100, self._check_scan_queue)

    def _process_scan_input(self, sn, source):
        sn = str(sn).strip().upper()
        if len(sn) < 3 or not sn.isalnum(): return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_PATH) as db:
            db.execute("INSERT INTO station_scans(sn,source,scanned_at) VALUES(?,?,?)", (sn, source, now))
        self.last.set(sn)
        self.log.configure(state="normal")
        self.log.insert("end", f"[{now}] CAPTURED {sn} ({source})\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self._say_heard()

    def _say_heard(self):
        def speak():
            try:
                import win32com.client
                win32com.client.Dispatch("SAPI.SpVoice").Speak("听见了", 1)
            except Exception: pass
        threading.Thread(target=speak, daemon=True).start()

    def close(self):
        self._running = False
        if self._listener: self._listener.stop()
        if self._tcp_socket: self._tcp_socket.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    agent = ScannerAgent(root)
    root.protocol("WM_DELETE_WINDOW", agent.close)
    root.mainloop()


if __name__ == "__main__":
    main()
