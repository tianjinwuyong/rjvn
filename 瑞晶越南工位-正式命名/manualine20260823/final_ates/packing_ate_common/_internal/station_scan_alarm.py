# -*- coding: utf-8 -*-
"""Persistent operator alarm for every blocked NG or duplicate scan."""
import ctypes
import json
import os
import re
import subprocess
import threading
import time
import tkinter as tk
import urllib.request
import uuid
import winsound

def present_new_alarm_once(win, root):
    """Keep the alarm visible after Tk finishes placing the full-screen window."""
    try:
        return win.after(150, lambda: (win.deiconify(), win.lift(), win.focus_force()))
    except Exception:
        return None

STATION_NAMES = {
    "auto_ict": "ICT",
    "auto_fct": "FCT",
    "auto_depanel": "分板",
    "auto_assem_ate": "组装 ATE",
    "auto_supersonic": "超声",
    "auto_aging": "老化",
    "auto_hivolt_ate": "高压 ATE",
    "auto_packing_ate_left": "包装 ATE 左",
    "auto_packing_ate_right": "包装 ATE 右",
    "auto_qrbinding": "绑码",
}


def readable_detail(detail):
    text = str(detail or "")
    for code, name in STATION_NAMES.items():
        text = re.sub(rf"\b{re.escape(code)}\b", name, text, flags=re.I)
    return text or "MES 已判定该 SN 不允许进入本站"


def show_blocking_alarm(root, status, sn, detail, station_code="", mes_url="", voice_enabled=True):
    pending = getattr(root, "_pending_scan_alarms", None)
    if pending is None:
        pending = []
        root._pending_scan_alarms = pending
    if getattr(root, "_scan_alarm_active", False):
        pending.append((status, sn, detail, station_code, mes_url, voice_enabled))
        return
    root._scan_alarm_active = True
    duplicate = "DUP" in str(status).upper()
    station_code = str(station_code or "").strip()
    mes_url = str(mes_url or os.environ.get("MES_API_URL", "http://192.168.6.155:8080/api/pda/events")).strip()
    alarm_id = str(uuid.uuid4())
    started_at = int(time.time() * 1000)

    def report(event_type, payload):
        if not station_code.startswith("auto_") or not mes_url:
            return
        event = {"from": station_code, "to": "mes_server", "type": event_type,
                 "stationCode": station_code, "priority": "critical", "payload": payload}
        def send():
            try:
                request = urllib.request.Request(
                    mes_url, data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                urllib.request.urlopen(request, timeout=3).read()
            except Exception:
                pass
        threading.Thread(target=send, daemon=True).start()

    report("ALARM_STARTED", {"alarmId": alarm_id, "sns": [str(sn)],
        "reason": "DUPLICATE_SN" if duplicate else "UPSTREAM_NG_SCAN",
        "detail": str(detail or ""), "startedAt": started_at, "status": "ALARMING"})
    title = "DUP 重码报警" if duplicate else "NG 拦截报警"
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg="#b91c1c")
    win.attributes("-topmost", True)
    try:
        win.attributes("-fullscreen", True)
    except tk.TclError:
        try:
            win.state("zoomed")
        except tk.TclError:
            pass
    win.transient(root)
    # Capture input while the blocking alarm is active.  Without grab_set,
    # scanner keyboard events can continue reaching the station behind it.
    win.protocol("WM_DELETE_WINDOW", lambda: None)
    win.update_idletasks()

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("hwnd", ctypes.c_void_p),
            ("dwFlags", ctypes.c_uint),
            ("uCount", ctypes.c_uint),
            ("dwTimeout", ctypes.c_uint),
        ]

    try:
        flash_info = FLASHWINFO(
            ctypes.sizeof(FLASHWINFO),
            win.winfo_id(),
            0x00000003,  # brief caption + taskbar cue
            2,
            0,
        )
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(flash_info))
    except Exception:
        pass
    title_label = tk.Label(
        win, text=title, bg="#b91c1c", fg="white",
        font=("Microsoft YaHei", 42, "bold"),
    )
    title_label.pack(fill="x", padx=30, pady=(45, 16))
    sn_label = tk.Label(
        win, text=f"SN：{sn}", bg="#b91c1c", fg="#fef08a",
        font=("Consolas", 34, "bold"),
    )
    sn_label.pack(fill="x", padx=30, pady=12)
    detail_label = tk.Label(
        win, text=readable_detail(detail), bg="#b91c1c", fg="white",
        font=("Microsoft YaHei", 22, "bold"), justify="left",
        wraplength=1200,
    )
    detail_label.pack(fill="both", expand=True, padx=50, pady=25)
    active = {"value": True}
    timers = {"flash": None, "voice": None}
    voice_process = {"value": None}

    def flash_cycle():
        if active["value"] and win.winfo_exists():
            flash_on = not bool(getattr(flash_cycle, "flash_on", False))
            flash_cycle.flash_on = flash_on
            background = "#ffff00" if flash_on else "#8b0000"
            foreground = "#000000" if flash_on else "#ffffff"
            win.configure(bg=background)
            # Keep the alarm fully opaque. Layered-window alpha can prevent
            # Windows/RDP capture and some displays from showing the flash.
            try:
                win.attributes("-alpha", 1.0)
            except tk.TclError:
                pass
            for label in (title_label, sn_label, detail_label):
                label.configure(bg=background, fg=foreground)
            if flash_on:
                try:
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                except RuntimeError:
                    pass
            timers["flash"] = win.after(450, flash_cycle)

    def repeat_voice():
        if not voice_enabled:
            return
        if active["value"] and win.winfo_exists():
            voice = (
                "发现重复编码，禁止离开本站。"
                if duplicate else
                "发现不良品，禁止离开本站。"
            )
            try:
                previous = voice_process["value"]
                if previous is None or previous.poll() is not None:
                    safe = (voice.replace("ATE", "A, T, E").replace("ate", "A, T, E")
                            .replace("AOI", "A, O, I").replace("aoi", "A, O, I").replace("'", "''"))
                    voice_process["value"] = subprocess.Popen(
                        [
                            "powershell", "-NoProfile", "-WindowStyle", "Hidden",
                            "-Command",
                            "Add-Type -AssemblyName System.Speech;"
                            "$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                            f"$v.Volume=100;$v.Rate=0;$v.Speak('{safe}')",
                        ],
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
            except Exception:
                winsound.MessageBeep(winsound.MB_ICONHAND)
            timers["voice"] = win.after(3000, repeat_voice)

    def repeat_voice_standard():
        if not voice_enabled or not active["value"] or not win.winfo_exists():
            return
        try:
            winsound.MessageBeep(winsound.MB_ICONHAND)
            voice = f"NG alarm. Serial number {sn}. Stop."
            safe = voice.replace("'", "''")
            previous = voice_process["value"]
            if previous is None or previous.poll() is not None:
                voice_process["value"] = subprocess.Popen(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                     "Add-Type -AssemblyName System.Speech;"
                     "$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                     f"$v.Volume=100;$v.Rate=0;$v.Speak('{safe}')"],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
        except Exception:
            pass
        timers["voice"] = win.after(3000, repeat_voice_standard)

    def acknowledge():
        resolved_at = int(time.time() * 1000)
        common = {"alarmId": alarm_id, "sns": [str(sn)],
            "reason": "DUPLICATE_SN" if duplicate else "UPSTREAM_NG_SCAN",
            "detail": str(detail or ""), "startedAt": started_at,
            "acknowledgedAt": resolved_at, "resolvedAt": resolved_at,
            "durationMs": max(0, resolved_at - started_at), "operator": "LOCAL_OPERATOR"}
        report("ALARM_ACKNOWLEDGED", dict(common, status="ACKNOWLEDGED"))
        report("ALARM_RESOLVED", dict(common, status="RESOLVED"))
        active["value"] = False
        try:
            stop_info = FLASHWINFO(
                ctypes.sizeof(FLASHWINFO), win.winfo_id(), 0, 0, 0
            )
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(stop_info))
        except Exception:
            pass
        for timer_id in timers.values():
            if timer_id:
                try:
                    win.after_cancel(timer_id)
                except tk.TclError:
                    pass
        process = voice_process["value"]
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
        try:
            win.grab_release()
        except tk.TclError:
            pass
        win.destroy()
        root._scan_alarm_active = False
        if pending:
            next_alarm = pending.pop(0)
            root.after(80, lambda item=next_alarm: show_blocking_alarm(root, *item))

    acknowledge_button = tk.Button(
        win, text="解除报警 / ACKNOWLEDGE", command=acknowledge,
        bg="#fef08a", fg="#7f1d1d",
        font=("Microsoft YaHei", 22, "bold"), padx=34, pady=14,
    )
    acknowledge_button.place(relx=0.5, rely=0.92, anchor="center")
    win.update_idletasks()
    try:
        # Some Windows/Tk combinations create a Toplevel in a withdrawn or
        # stale z-order state. Explicitly show and size it before grabbing
        # input so the operator always sees the NG alarm.
        win.deiconify()
        win.geometry(f"{win.winfo_screenwidth()}x{win.winfo_screenheight()}+0+0")
        win.lift()
        win.focus_force()
        win.grab_set()
        acknowledge_button.focus_set()
    except tk.TclError:
        pass
    timers["settle"] = present_new_alarm_once(win, root)
    flash_cycle()
    repeat_voice()
