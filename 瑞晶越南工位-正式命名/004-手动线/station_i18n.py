# -*- coding: utf-8 -*-
"""Shared trilingual UI helpers for manual-line station applications."""

from __future__ import annotations

import tkinter as tk


def translated(original: str, language: str) -> str:
    """Return the station label for the requested language.

    Station labels are already authored in Chinese in the current manual-line
    applications.  Keeping this function as a stable compatibility boundary
    lets older station builds start even when no translation catalog is present.
    """
    return str(original)


class TrilingualController:
    """Small, non-overlapping language selector used by station headers."""

    def __init__(self, root, header, use_place=True, on_change=None, show_buttons=True):
        self.root = root
        self.header = header
        self.language = "zh"
        self.on_change = on_change
        self.frame = tk.Frame(header, bg="#0b1f35")
        self.buttons = {}
        if show_buttons:
            self.frame.pack(side="right", padx=(10, 0))
            for code, label in (("zh", "中文"), ("en", "EN"), ("vi", "VI")):
                button = tk.Button(
                    self.frame,
                    text=label,
                    command=lambda value=code: self.set(value),
                    font=("Segoe UI", 9, "bold"),
                    bg="#164e63",
                    fg="white",
                    relief="flat",
                    padx=7,
                    pady=3,
                )
                button.pack(side="left", padx=2)
                self.buttons[code] = button

    def set(self, language: str) -> None:
        self.language = language
        if self.on_change:
            self.on_change(language)

