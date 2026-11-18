# -*- coding: utf-8 -*-
"""Shared 3x2 motherboard/daughter lookup UI for ICT, FCT and depanel."""
import json
import threading
import tkinter as tk
from tkinter import messagebox
import urllib.parse
import urllib.request


def install_motherboard_search(root, mes_url, line="auto"):
    base = str(mes_url).split("/api/")[0].rstrip("/")
    bar = tk.Frame(root, bg="#1e293b", bd=1, relief="raised")
    # Keep the query controls inside the visible client area even when the
    # station's main content is taller than the monitor.
    bar.place(relx=0, rely=1, anchor="sw", relwidth=1, height=46)
    bar.lift()
    value = tk.StringVar()
    status = tk.StringVar(value="输入母板号或任一子板 SN")
    tk.Label(bar, text="母板/子板查询", bg="#1e293b", fg="#f8fafc",
             font=("Microsoft YaHei", 11, "bold")).pack(side="left", padx=(12, 6), pady=6)
    entry = tk.Entry(bar, textvariable=value, font=("Consolas", 13), width=28)
    entry.pack(side="left", padx=4, pady=6)
    tk.Label(bar, textvariable=status, bg="#1e293b", fg="#7dd3fc").pack(
        side="right", padx=12)

    def render(data):
        motherboard = str(data.get("motherboardId") or data.get("ictBatchId") or "")
        members = list(data.get("members") or [])
        status.set(f"母板 {motherboard} · {len(members)} 个子板")
        win = tk.Toplevel(root)
        win.title(f"母板查询 · {motherboard}")
        win.configure(bg="#07111f")
        win.attributes("-topmost", True)
        tk.Label(win, text=f"母板号：{motherboard}", bg="#07111f", fg="#7dd3fc",
                 font=("Microsoft YaHei", 20, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=12)
        for index, member in enumerate(sorted(members, key=lambda x: int(x.get("slot") or 999))[:6]):
            slot = int(member.get("slot") or index + 1)
            sn = str(member.get("sn") or "—")
            ict = "NG" if member.get("ictNg") else "PASS"
            fct = "NG" if member.get("fctNg") else "PASS"
            result = str(member.get("result") or ("NG" if ict == "NG" or fct == "NG" else "PASS"))
            color = "#991b1b" if result.upper() in ("NG", "FAIL") else "#166534"
            text = f"槽位 {slot}\n{sn}\nICT {ict} · FCT {fct}\n{result}"
            tk.Label(win, text=text, bg=color, fg="white", width=27, height=6,
                     font=("Consolas", 12, "bold"), relief="ridge").grid(
                row=1 + index // 3, column=index % 3, padx=7, pady=7, sticky="nsew")
        tk.Button(win, text="关闭", command=win.destroy,
                  font=("Microsoft YaHei", 12, "bold")).grid(
            row=3, column=0, columnspan=3, pady=12)
        win.geometry("900x520")

    def worker(code):
        try:
            url = (f"{base}/api/station/confirmed-motherboards/search/"
                   f"{urllib.parse.quote(code)}?line={urllib.parse.quote(line)}")
            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            root.after(0, lambda: render(data))
        except Exception as exc:
            root.after(0, lambda: (
                status.set(f"未找到：{code}"),
                messagebox.showwarning("母板/子板查询", f"未找到母板关系：{code}\n{exc}", parent=root),
            ))

    def search(_event=None):
        code = value.get().strip().upper()
        if not code:
            return
        status.set(f"正在查询 {code}…")
        threading.Thread(target=worker, args=(code,), daemon=True).start()

    tk.Button(bar, text="查询", command=search, bg="#0369a1", fg="white",
              font=("Microsoft YaHei", 11, "bold")).pack(side="left", padx=5)
    entry.bind("<Return>", search)
    return bar
