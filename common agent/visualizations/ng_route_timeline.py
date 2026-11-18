from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from typing import Iterable, List, Optional

from modular_contract import RepairPolicy


@dataclass(frozen=True)
class NgRouteStep:
    code: str
    title: str
    detail: str


def build_ng_route_steps(policy: RepairPolicy) -> List[NgRouteStep]:
    steps = [
        NgRouteStep("DETECTED", "NG detected", "Raw result and evidence preserved"),
        NgRouteStep("POLICY", "MES policy", f"{policy.action_mode} · {policy.policy_version}"),
    ]
    if policy.retest_limit:
        steps.append(NgRouteStep("RETEST", "Authorized retest", f"Maximum {policy.retest_limit} attempt(s)"))
    if policy.action_mode == "MARK_ONLY":
        steps.extend([
            NgRouteStep("MARK", "NG attribute retained", "Continue only when MES authorizes"),
            NgRouteStep("CLOSE", "Quality record closed", "History remains immutable"),
        ])
        return steps
    if policy.action_mode == "REMOVE_IMMEDIATELY":
        steps.append(NgRouteStep("REMOVE", "Remove immediately", "Physical isolation required"))
    else:
        steps.append(NgRouteStep("CONFIRMED", "Confirmed NG", "Normal production route is blocked"))
    steps.extend([
        NgRouteStep("SEND", "Send to repair", policy.repair_destination),
        NgRouteStep("RECEIPT", "Repair receipt", f"SLA {policy.receipt_sla_minutes} min"),
        NgRouteStep("REPAIR", "Repair work order", f"SLA {policy.repair_sla_minutes} min"),
        NgRouteStep("VERIFY", "Repair verification", "Evidence and replaced materials recorded"),
        NgRouteStep("RETURN", "MES return route", policy.return_route),
        NgRouteStep("CLOSE", "Close outcome", "Return / repeat / replace / release / scrap"),
    ])
    return steps


class NgRouteTimeline(tk.Frame):
    COLORS = {
        "bg": "#08131f", "card": "#10243b", "track": "#27445e",
        "future": "#63788a", "active": "#f05252", "done": "#22d887",
        "text": "#edf7ff", "muted": "#9eb0bc", "cyan": "#18c6d9",
    }

    def __init__(self, parent, policy: RepairPolicy, current_step: str = "DETECTED", **kwargs):
        super().__init__(parent, bg=self.COLORS["bg"], **kwargs)
        self.policy = policy
        self.steps = build_ng_route_steps(policy)
        self.current_step = current_step
        self.canvas = tk.Canvas(self, bg=self.COLORS["bg"], highlightthickness=0, height=330)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._redraw)

    def set_current_step(self, step_code: str) -> None:
        if step_code not in {step.code for step in self.steps}:
            raise ValueError("Unknown NG route step: " + step_code)
        self.current_step = step_code
        self._redraw()

    def _redraw(self, _event: Optional[object] = None) -> None:
        self.canvas.delete("all")
        width = max(760, self.canvas.winfo_width())
        margin, y, radius = 54, 94, 12
        count = max(1, len(self.steps) - 1)
        gap = (width - margin * 2) / count
        current_index = next((i for i, item in enumerate(self.steps) if item.code == self.current_step), 0)
        self.canvas.create_text(margin, 24, anchor="w", text="NG REPAIR ROUTE",
                                fill=self.COLORS["text"], font=("Microsoft YaHei UI", 16, "bold"))
        self.canvas.create_text(width - margin, 25, anchor="e",
                                text=f"MES policy · {self.policy.policy_version}",
                                fill=self.COLORS["cyan"], font=("Microsoft YaHei UI", 10, "bold"))
        self.canvas.create_line(margin, y, width - margin, y, fill=self.COLORS["track"], width=4)
        for index, step in enumerate(self.steps):
            x = margin + gap * index
            state = "done" if index < current_index else "active" if index == current_index else "future"
            color = self.COLORS[state]
            if index and index <= current_index:
                self.canvas.create_line(margin + gap * (index - 1), y, x, y,
                                        fill=self.COLORS["done"], width=4)
            self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                    fill=color, outline=self.COLORS["bg"], width=3)
            self.canvas.create_text(x, y, text="✓" if state == "done" else str(index + 1),
                                    fill="#061018" if state != "future" else self.COLORS["text"],
                                    font=("Microsoft YaHei UI", 9, "bold"))
            anchor = "n"
            self.canvas.create_text(x, y + 24, anchor=anchor, text=step.title,
                                    width=max(90, int(gap * .9)), justify="center",
                                    fill=self.COLORS["text"], font=("Microsoft YaHei UI", 9, "bold"))
            self.canvas.create_text(x, y + 59, anchor=anchor, text=step.detail,
                                    width=max(90, int(gap * .92)), justify="center",
                                    fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 8))
        footer_y = 245
        self.canvas.create_rectangle(margin, footer_y, width-margin, footer_y+56,
                                     fill=self.COLORS["card"], outline=self.COLORS["track"])
        active = self.steps[current_index]
        self.canvas.create_text(margin+18, footer_y+18, anchor="w", text=f"CURRENT · {active.title}",
                                fill=self.COLORS["active"], font=("Microsoft YaHei UI", 11, "bold"))
        self.canvas.create_text(margin+18, footer_y+39, anchor="w", text=active.detail,
                                fill=self.COLORS["text"], font=("Microsoft YaHei UI", 10))
        self.canvas.create_text(width-margin-18, footer_y+29, anchor="e",
                                text="Display only · MES owns the decision",
                                fill=self.COLORS["muted"], font=("Microsoft YaHei UI", 9))
