# -*- coding: utf-8 -*-
"""Unified visual language and blocking alarm used by every manual-line ATE UI."""
import subprocess
import tkinter as tk
import winsound

from station_i18n import TrilingualController, translated


class AteUi:
    def __init__(self, root, header):
        self.root = root
        self.language = "zh"
        self.controller = TrilingualController(root, header, use_place=False, on_change=self._changed)
        self.alarm = None
        self.active = False
        self.timers = []
        self.voice_process = None

    def _changed(self, language):
        self.language = language

    def tr(self, value):
        return translated(value, self.language)

    def show_alarm(self, status, sn, detail):
        self.close_alarm()
        duplicate = "DUP" in str(status).upper() or "重复" in str(status)
        text = {
            "zh": ("重复编码报警" if duplicate else "NG 拦截报警", "解除报警", "发现重复编码，禁止继续" if duplicate else "发现不良品，禁止继续"),
            "en": ("DUPLICATE CODE ALARM" if duplicate else "NG BLOCKING ALARM", "ACKNOWLEDGE ALARM", "Duplicate code detected. Operation blocked" if duplicate else "NG detected. Operation blocked"),
            "vi": ("CẢNH BÁO TRÙNG MÃ" if duplicate else "CẢNH BÁO CHẶN NG", "XÁC NHẬN CẢNH BÁO", "Phát hiện mã trùng. Đã chặn thao tác" if duplicate else "Phát hiện NG. Đã chặn thao tác"),
        }[self.language]
        self.active = True
        win = self.alarm = tk.Toplevel(self.root)
        win.title(text[0]); win.configure(bg="#8b0000"); win.attributes("-topmost", True)
        try: win.state("zoomed")
        except tk.TclError: win.attributes("-fullscreen", True)
        win.grab_set(); win.protocol("WM_DELETE_WINDOW", lambda: None)
        labels = [
            tk.Label(win,text=text[0],bg="#8b0000",fg="white",font=("Microsoft YaHei",42,"bold")),
            tk.Label(win,text=f"SN: {sn}",bg="#8b0000",fg="#fef08a",font=("Consolas",34,"bold")),
            tk.Label(win,text=str(detail),bg="#8b0000",fg="white",font=("Microsoft YaHei",22,"bold"),wraplength=1200),
        ]
        labels[0].pack(fill="x",padx=30,pady=(45,16)); labels[1].pack(fill="x",padx=30,pady=12); labels[2].pack(fill="both",expand=True,padx=50,pady=25)
        tk.Button(win,text=text[1],command=self.close_alarm,bg="#fef08a",fg="#7f1d1d",font=("Microsoft YaHei",22,"bold"),padx=34,pady=14).place(relx=.5,rely=.92,anchor="center")
        def flash(on=False):
            if not self.active or not win.winfo_exists(): return
            bg,fg=("#ffff00","#000000") if on else ("#8b0000","#ffffff")
            win.configure(bg=bg)
            for label in labels: label.configure(bg=bg,fg=fg)
            try: winsound.MessageBeep(winsound.MB_ICONHAND)
            except RuntimeError: pass
            win.lift(); win.attributes("-topmost",True)
            self.timers.append(win.after(420,lambda:flash(not on)))
        def voice():
            if not self.active or not win.winfo_exists(): return
            phrase=f"{text[2]}. SN {sn}. {detail}".replace("'","''")
            try:
                self.voice_process=subprocess.Popen(["powershell","-NoProfile","-WindowStyle","Hidden","-Command","Add-Type -AssemblyName System.Speech;$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;$v.Volume=100;$v.Rate=1;$v.Speak('%s')"%phrase],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            except Exception: pass
            self.timers.append(win.after(4500,voice))
        flash(); voice()

    def close_alarm(self):
        self.active=False
        if self.alarm and self.alarm.winfo_exists():
            for timer in self.timers:
                try:self.alarm.after_cancel(timer)
                except tk.TclError:pass
            try:self.alarm.grab_release()
            except tk.TclError:pass
            self.alarm.destroy()
        self.timers=[]
        if self.voice_process and self.voice_process.poll() is None:
            try:self.voice_process.terminate()
            except Exception:pass

