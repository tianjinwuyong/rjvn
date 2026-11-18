"""ManimGL replay of the SMT material-loading workflow.

This is a presentation/replay layer only. It never approves loading and never
writes MES data. Feed it an exported JSON event list from MES or use the
embedded sample events for a quick demo.

Render with ManimGL (the 3b1b repository):
    manimgl manim_smt_loading.py SmtLoadingReplay -w
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from manimlib import *  # type: ignore


SAMPLE_EVENTS = [
    {"step": "物料卷", "value": "RSN001-1", "ok": True},
    {"step": "机器", "value": "NPM-01", "ok": True},
    {"step": "通道", "value": "1L", "ok": True},
    {"step": "Feeder", "value": "FD-001", "ok": True},
    {"step": "MES校验", "value": "允许上料", "ok": True},
]


def load_events() -> list[dict[str, object]]:
    """Read an optional JSON path from ``SMT_EVENTS_JSON``."""
    raw_path = os.getenv("SMT_EVENTS_JSON", "").strip()
    if not raw_path:
        return SAMPLE_EVENTS
    path = Path(raw_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("event JSON must be an array")
    return [dict(item) for item in data if isinstance(item, dict)]


class SmtLoadingReplay(Scene):
    """Animated scan sequence for operator training and MES event replay."""

    def construct(self):
        title = Text("SMT Material Loading", font_size=42)
        subtitle = Text("MES/PDA scan replay — training view only", font_size=22)
        subtitle.next_to(title, DOWN, buff=0.18)
        self.play(Write(title), FadeIn(subtitle, shift=UP))
        self.wait(0.5)

        events = load_events()
        cards: list[Mobject] = []
        for index, event in enumerate(events):
            step = str(event.get("step", "Scan"))
            value = str(event.get("value", ""))
            ok = bool(event.get("ok", False))
            color = GREEN if ok else RED
            card = RoundedRectangle(width=5.8, height=0.92, corner_radius=0.12, color=color)
            label = Text(f"{index + 1}. {step}", font_size=25, color=color)
            detail = Text(value, font_size=22)
            detail.next_to(label, RIGHT, buff=0.35)
            group = VGroup(card, label, detail)
            group.move_to(ORIGIN)
            cards.append(group)
            self.play(FadeIn(group, shift=RIGHT), run_time=0.45)
            self.wait(0.3)

            if index < len(events) - 1:
                arrow = Arrow(DOWN * 0.1, DOWN * 0.7, buff=0.05, color=color)
                self.play(GrowArrow(arrow), run_time=0.2)
                self.play(group.animate.shift(UP * 1.05), run_time=0.3)

        final_ok = all(bool(event.get("ok", False)) for event in events)
        status_color = GREEN if final_ok else RED
        status_text = "READY FOR LOADING" if final_ok else "BLOCKED — CHECK SCAN"
        status = Text(status_text, font_size=30, color=status_color)
        status.to_edge(DOWN, buff=0.45)
        self.play(Write(status))
        self.wait(1.5)
