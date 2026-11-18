# -*- coding: utf-8 -*-
"""Read-only arrival lifecycle UI shared by manual-line Station Agents.

This component contains no MES calls and never mutates route or arrival data.
"""

import tkinter as tk
from tkinter import ttk

from station_ui_primitives import SEMANTIC_COLORS


class ProductGateComponent:
    """Compact product decision; full route evidence remains one click away."""

    def __init__(self, root, enabled=True, backend_note=""):
        self.root = root
        self.enabled = bool(enabled)
        self.backend_note = backend_note
        self.snapshot = {"expected": [], "arrivals": [], "exceptions": [], "route": {}}
        self.summary = tk.StringVar()
        self.reason = tk.StringVar()
        self.action = tk.StringVar()
        self.frame = tk.Frame(root, bg=SEMANTIC_COLORS["panel"], padx=12, pady=7)
        self.frame.pack(fill="x", padx=12, pady=(0, 6))
        self.frame.grid_columnconfigure(1, weight=1)
        tk.Label(self.frame, text="产品放行\nProduct Gate", bg=SEMANTIC_COLORS["panel"],
                 fg=SEMANTIC_COLORS["text"], font=("Microsoft YaHei UI", 11, "bold"), justify="left").grid(row=0, column=0, rowspan=2, sticky="w")
        self.summary_label = tk.Label(self.frame, textvariable=self.summary, bg=SEMANTIC_COLORS["panel"],
                 fg=SEMANTIC_COLORS["active"], font=("Consolas", 9, "bold"), anchor="w", justify="left")
        self.summary_label.grid(row=0, column=1, sticky="ew", padx=18)
        detail_line = tk.Frame(self.frame, bg=SEMANTIC_COLORS["panel"])
        detail_line.grid(row=1, column=1, sticky="ew", padx=18)
        tk.Label(detail_line, textvariable=self.reason, bg=SEMANTIC_COLORS["panel"],
                 fg=SEMANTIC_COLORS["muted"], font=("Microsoft YaHei UI", 10), anchor="w").pack(side="left")
        tk.Label(detail_line, textvariable=self.action, bg=SEMANTIC_COLORS["panel"],
                 fg=SEMANTIC_COLORS["attention"], font=("Microsoft YaHei UI", 10, "bold"), anchor="w").pack(side="left", padx=(18, 0))
        self.detail_button = tk.Button(
            self.frame, text="追溯 / Trace", command=self.open_details,
            bg=SEMANTIC_COLORS["info"], fg="white", font=("Microsoft YaHei UI", 11, "bold"),
            padx=14, pady=8, state="normal" if self.enabled else "disabled",
        )
        self.detail_button.grid(row=0, column=2, rowspan=2, sticky="e")
        self.update(self.snapshot)

    DECISIONS = {
        "EXPECTED_NEXT": ("EXPECTED NEXT / 预期下一站", "pass"),
        "EARLY_UNEXPECTED": ("EARLY / UNEXPECTED ARRIVAL / 提前或非预期到站", "attention"),
        "DUPLICATE_REPLAY": ("DUPLICATE NETWORK REPLAY / 网络重复回放", "info"),
        "SAME_STATION_RESCAN": ("SAME-STATION RESCAN / 同站重复扫描", "info"),
        "BLOCKED_FORWARD_JUMP": ("BLOCKED FORWARD JUMP / 缺站前跳拦截", "ng"),
        "AUTHORIZED_EXEMPTION": ("AUTHORIZED PROCESS EXEMPTION / 已授权工艺豁免", "active"),
        "AUTHORIZED_REPAIR_RETURN": ("AUTHORIZED REPAIR/RETEST RETURN / 已授权维修复测返回", "active"),
        "ACTIVE_NG_BLOCK": ("ACTIVE NG BLOCK / 有效NG拦截", "ng"),
        "OFFLINE_PENDING": ("OFFLINE DECISION PENDING / 离线待判定", "attention"),
        "ROUTE_VERSION_MISMATCH": ("ROUTE VERSION MISMATCH / 路由版本不一致", "attention"),
        "UNKNOWN": ("DECISION UNKNOWN / 判定未知", "muted"),
    }
    GATES = {
        "ALLOW": ("ALLOW / 放行", "pass"), "HOLD": ("HOLD / 暂停", "attention"),
        "REJECT": ("REJECT / 拒绝", "ng"), "REPAIR_ROUTE": ("REPAIR ROUTE / 维修路线", "active"),
        "COMPLETED": ("COMPLETED / 已完成", "info"), "UNKNOWN": ("UNKNOWN / 未判定", "muted"),
    }

    def update(self, arrival):
        data = arrival or {}
        self.snapshot = {
            "expected": list(data.get("expected") or []),
            "arrivals": list(data.get("arrivals") or []),
            "exceptions": list(data.get("exceptions") or []),
            "route": dict(data.get("route") or {}),
        }
        if not self.enabled:
            self.summary.set("IDENTITY -- · GATE UNKNOWN / 未判定")
            self.reason.set("Backend gap / 后端能力缺失")
            self.action.set(self.backend_note or "Arrival backend not integrated")
            return
        route = self.snapshot["route"]
        decision = str(route.get("decision") or "UNKNOWN").upper()
        gate = str(route.get("gate_state") or "UNKNOWN").upper()
        gate_label, semantic = self.GATES.get(gate, self.GATES["UNKNOWN"])
        identity_type = str(route.get("identity_type") or "PRODUCT").upper()
        identity = str(route.get("identity") or route.get("sn") or "--")
        self.summary.set(f"{identity_type} {identity} · {gate_label}")
        decision_label = self.DECISIONS.get(decision, self.DECISIONS["UNKNOWN"])[0]
        self.reason.set(str(route.get("reason") or decision_label))
        self.action.set(str(route.get("next_action") or "等待MES路由判定"))
        self.summary_label.configure(fg=SEMANTIC_COLORS[semantic])
        if getattr(self, "window", None) and self.window.winfo_exists():
            self._render_ledgers()

    def open_details(self):
        if not self.enabled:
            return
        if getattr(self, "window", None) and self.window.winfo_exists():
            self.window.lift()
            return
        self.window = tk.Toplevel(self.root)
        self.window.title("产品放行追溯 / Product Gate Trace")
        self.window.geometry("1120x640")
        self.window.configure(bg=SEMANTIC_COLORS["canvas"])
        route_frame = tk.LabelFrame(self.window, text="路线时间线 / Route Timeline", bg=SEMANTIC_COLORS["canvas"],
                                    fg=SEMANTIC_COLORS["text"], font=("Microsoft YaHei UI", 12, "bold"))
        route_frame.pack(fill="x", padx=12, pady=(12, 0))
        self.route_timeline = tk.Frame(route_frame, bg=SEMANTIC_COLORS["canvas"])
        self.route_timeline.pack(fill="x", padx=8, pady=8)
        tk.Label(route_frame, text="完成 COMPLETED · 当前 CURRENT · 预期 EXPECTED · 跳过 SKIPPED · 已授权 AUTHORIZED · 已拦截 BLOCKED",
                 bg=SEMANTIC_COLORS["canvas"], fg=SEMANTIC_COLORS["muted"],
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=8, pady=(0, 6))
        audit_frame = tk.LabelFrame(self.window, text="产品放行判定审计 / Product Gate Decision Audit",
                                    bg=SEMANTIC_COLORS["canvas"], fg=SEMANTIC_COLORS["text"],
                                    font=("Microsoft YaHei UI", 12, "bold"))
        audit_frame.pack(fill="both", expand=True, padx=12, pady=12)
        columns = ("时间", "产品身份", "放行判定", "原因", "下一步操作", "授权/引用")
        horizontal = ttk.Scrollbar(audit_frame, orient="horizontal")
        horizontal.pack(side="bottom", fill="x")
        self.audit_tree = ttk.Treeview(audit_frame, columns=columns, show="headings", xscrollcommand=horizontal.set)
        horizontal.configure(command=self.audit_tree.xview)
        widths = (150, 210, 140, 260, 300, 210)
        for column, width in zip(columns, widths):
            self.audit_tree.heading(column, text=column); self.audit_tree.column(column, width=width, anchor="center")
        self.audit_tree.pack(fill="both", expand=True)
        self._render_ledgers()

    def _render_ledgers(self):
        if not hasattr(self, "audit_tree"):
            return
        self.audit_tree.delete(*self.audit_tree.get_children())
        route = self.snapshot.get("route", {})
        rows = list(route.get("audit") or [route] if route else [])
        for row in rows:
            identity = f'{row.get("identity_type", "PRODUCT")} {row.get("identity") or row.get("sn") or "--"}'
            reference = row.get("authorization_reference") or row.get("reference") or row.get("route_revision") or "--"
            self.audit_tree.insert("", "end", values=(
                row.get("decision_time") or row.get("time") or "--", identity,
                row.get("gate_state") or "UNKNOWN", row.get("reason") or row.get("decision") or "--",
                row.get("next_action") or "--", reference,
            ))
        if hasattr(self, "route_timeline"):
            for child in self.route_timeline.winfo_children(): child.destroy()
            colors = {
                "COMPLETED": SEMANTIC_COLORS["pass"], "CURRENT": SEMANTIC_COLORS["active"],
                "EXPECTED": SEMANTIC_COLORS["info"], "SKIPPED": SEMANTIC_COLORS["muted"],
                "AUTHORIZED": SEMANTIC_COLORS["active"], "BLOCKED": SEMANTIC_COLORS["ng"],
            }
            for index, step in enumerate(self.snapshot.get("route", {}).get("steps") or []):
                state = str(step.get("state") or "EXPECTED").upper()
                card = tk.Frame(self.route_timeline, bg=colors.get(state, SEMANTIC_COLORS["raised"]), padx=8, pady=7)
                card.pack(side="left", padx=(0, 5), fill="x", expand=True)
                tk.Label(card, text=f'{index + 1}. {step.get("station", "--")}\n{state}', bg=card.cget("bg"),
                         fg="#08131D" if state in ("COMPLETED", "CURRENT", "AUTHORIZED") else "white",
                         font=("Microsoft YaHei UI", 9, "bold")).pack()


# Compatibility alias while station sources migrate incrementally.
ArrivalRouteComponent = ProductGateComponent


def render_streamlit_product_gate(st, route=None, backend_gap=False):
    """Read-only Streamlit presentation adapter; never creates a gate decision."""
    route = dict(route or {})
    gate = str(route.get("gate_state") or "UNKNOWN").upper()
    identity_type = str(route.get("identity_type") or "PRODUCT").upper()
    identity = str(route.get("identity") or route.get("sn") or "--")
    reason = str(route.get("reason") or ("BACKEND GAP" if backend_gap else "No MES gate decision supplied"))
    action = str(route.get("next_action") or "Wait for MES decision / 等待MES判定")
    color = {"ALLOW":"#22D887","HOLD":"#F2B84B","REJECT":"#F05252","REPAIR_ROUTE":"#18C6D9","COMPLETED":"#4C8DFF"}.get(gate,"#9EB0BC")
    st.markdown(
        f"""<div style='background:#101D27;border:1px solid #2C414F;border-radius:6px;padding:10px 14px;margin:8px 0'>
        <div style='color:#F2F6F8;font-weight:700'>产品放行 / Product Gate</div>
        <div style='color:{color};font-family:monospace;font-weight:700'>{identity_type} {identity} · {gate}</div>
        <div style='color:#9EB0BC'>Reason: {reason}</div><div style='color:#F2B84B'>Next: {action}</div></div>""",
        unsafe_allow_html=True,
    )

