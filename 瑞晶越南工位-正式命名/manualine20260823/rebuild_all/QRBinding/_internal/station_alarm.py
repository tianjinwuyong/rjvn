# -*- coding: utf-8 -*-
"""Shared blocking alarm and MES lifecycle reporting for auto-line agents."""
import json
import subprocess
import threading
import time
import tkinter as tk
import urllib.request
import uuid
import winsound

from station_ui_primitives import present_new_alarm_once


class StationAlarm:
    def __init__(self, root, on_release=None, station_code="", mes_url=""):
        self.root = root
        self.on_release = on_release
        self.station_code = str(station_code or "")
        self.mes_url = str(mes_url or "")
        self.window = None
        self.active = False
        self.timers = []
        self.alarm_id = ""
        self.started_at = 0
        self.title = ""
        self.detail = ""
        self.sns = []

    def _report(self, event_type, payload):
        if not self.station_code or not self.mes_url:
            return
        event = {
            "from": self.station_code,
            "to": "mes_server",
            "type": event_type,
            "stationCode": self.station_code,
            "priority": "critical" if event_type == "ALARM_STARTED" else "normal",
            "payload": payload,
        }

        def send():
            try:
                request = urllib.request.Request(
                    self.mes_url,
                    data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(request, timeout=3).read()
            except Exception:
                pass

        threading.Thread(target=send, daemon=True).start()

    def trigger(self, title, sns, detail=""):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
        self.active = True
        self.sns = [str(value) for value in (sns or []) if str(value).strip()]
        self.alarm_id = str(uuid.uuid4())
        self.started_at = int(time.time() * 1000)
        self.title = str(title)
        self.detail = str(detail)
        self._report("ALARM_STARTED", {
            "alarmId": self.alarm_id,
            "sns": self.sns,
            "reason": self.title,
            "detail": self.detail,
            "startedAt": self.started_at,
            "status": "ALARMING",
        })
        sn_text = " / ".join(self.sns) or "-"
        win = self.window = tk.Toplevel(self.root)
        win.title(self.title)
        win.configure(bg="#8b0000")
        win.attributes("-topmost", True)
        try:
            win.state("zoomed")
        except tk.TclError:
            win.attributes("-fullscreen", True)
        # Keep the alarm visible without taking keyboard/scanner focus.
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        heading = tk.Label(win, text=self.title, bg="#8b0000", fg="white", font=("Microsoft YaHei", 42, "bold"))
        heading.pack(fill="x", padx=30, pady=(45, 16))
        serials = tk.Label(win, text="SN: " + sn_text, bg="#8b0000", fg="white", font=("Consolas", 32, "bold"))
        serials.pack(fill="x", padx=30, pady=12)
        message = tk.Label(win, text=self.detail, bg="#8b0000", fg="white", font=("Microsoft YaHei", 22, "bold"), wraplength=1200)
        message.pack(fill="both", expand=True, padx=50, pady=25)
        labels = (heading, serials, message)

        def flash(on=False):
            if not self.active or not win.winfo_exists():
                return
            bg, fg = ("#ffff00", "#000000") if on else ("#8b0000", "#ffffff")
            win.configure(bg=bg)
            for label in labels:
                label.configure(bg=bg, fg=fg)
            try:
                winsound.MessageBeep(winsound.MB_ICONHAND)
            except RuntimeError:
                pass
            # One brief cue only. Persistent state remains visible and calm.

        def speak():
            if not self.active or not win.winfo_exists():
                return
            voice = (self.title + ". " + sn_text + ". " + self.detail)
            voice = (voice.replace("ATE", "A, T, E").replace("ate", "A, T, E")
                    .replace("AOI", "A, O, I").replace("aoi", "A, O, I").replace("'", "''"))
            try:
                subprocess.Popen([
                    "powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                    "Add-Type -AssemblyName System.Speech;$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                    + "$v.Volume=100;$v.Speak('" + voice + "')",
                ], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                pass

        tk.Button(win, text="解除报警 / ACKNOWLEDGE", command=lambda: self.release(self.sns), bg="#fef08a", fg="#7f1d1d", font=("Microsoft YaHei", 22, "bold"), padx=34, pady=14).place(relx=0.5, rely=0.92, anchor="center")
        cue_timer = present_new_alarm_once(win, self.root)
        if cue_timer:
            self.timers.append(cue_timer)
        flash()
        speak()

    def release(self, sns=None):
        resolved_at = int(time.time() * 1000)
        released_sns = list(sns or self.sns)
        if self.alarm_id:
            common = {
                "alarmId": self.alarm_id,
                "sns": released_sns,
                "reason": self.title,
                "detail": self.detail,
                "startedAt": self.started_at,
                "acknowledgedAt": resolved_at,
                "resolvedAt": resolved_at,
                "durationMs": max(0, resolved_at - self.started_at),
                "operator": "LOCAL_OPERATOR",
            }
            self._report("ALARM_ACKNOWLEDGED", dict(common, status="ACKNOWLEDGED"))
            self._report("ALARM_RESOLVED", dict(common, status="RESOLVED"))
        self.active = False
        if self.window and self.window.winfo_exists():
            for timer in self.timers:
                try:
                    self.window.after_cancel(timer)
                except tk.TclError:
                    pass
            try:
                self.window.grab_release()
            except tk.TclError:
                pass
            self.window.destroy()
        self.timers = []
        self.alarm_id = ""
        if self.on_release:
            self.on_release(released_sns)
