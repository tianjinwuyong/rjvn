# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox, ttk


def show_operation_report(parent, agent):
    win = tk.Toplevel(parent)
    win.title("Operation Report / 操作报告 / Báo cáo vận hành")
    win.transient(parent); win.grab_set()
    fields = {}
    for row, (key, label, default) in enumerate([
        ("category", "Category / 类别 / Loại", "OTHER"),
        ("severity", "Severity / 严重程度 / Mức độ", "INFO"),
        ("operator", "Operator / 操作员 / Người vận hành", ""),
        ("downtime", "Downtime minutes / 停机分钟 / Phút dừng máy", "0"),
    ]):
        ttk.Label(win, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=5)
        value = tk.StringVar(value=default); fields[key] = value
        ttk.Entry(win, textvariable=value, width=42).grid(row=row, column=1, padx=10, pady=5)
    ttk.Label(win, text="Description / 描述 / Mô tả").grid(row=4, column=0, sticky="nw", padx=10, pady=5)
    description = tk.Text(win, width=42, height=6); description.grid(row=4, column=1, padx=10, pady=5)
    ttk.Label(win, text="Action taken / 已采取措施 / Hành động đã thực hiện").grid(row=5, column=0, sticky="nw", padx=10, pady=5)
    action = tk.Text(win, width=42, height=4); action.grid(row=5, column=1, padx=10, pady=5)

    def submit():
        try:
            report_id = agent.create_operation_report(
                category=fields["category"].get(), severity=fields["severity"].get(),
                description=description.get("1.0", "end").strip(), action_taken=action.get("1.0", "end").strip(),
                operator_id=fields["operator"].get(), downtime_minutes=int(fields["downtime"].get() or 0))
            messagebox.showinfo("Saved / 已保存 / Đã lưu", f"Report {report_id}\nQueued for MES", parent=win)
            win.destroy()
        except Exception as exc:
            messagebox.showerror("Report error / 报告错误 / Lỗi báo cáo", str(exc), parent=win)
    ttk.Button(win, text="Submit / 提交 / Gửi", command=submit).grid(row=6, column=1, sticky="e", padx=10, pady=10)
    return win


__all__ = ["show_operation_report"]
