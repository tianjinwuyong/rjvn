# -*- coding: utf-8 -*-
"""Automatic-line i18n facade using the validated shared language component."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_manual = next((p for p in _root.iterdir() if p.is_dir() and p.name.startswith("004-")), None) if _root.exists() else None
_shared = (_manual / "station_i18n.py") if _manual else None
_spec = spec_from_file_location("ruijing_shared_station_i18n", _shared) if _shared and _shared.exists() else None
if _spec is not None and _spec.loader is not None:
    _module = module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    for _name in dir(_module):
        if not _name.startswith("_"):
            globals()[_name] = getattr(_module, _name)
else:
    # Frozen auto-line EXEs intentionally do not depend on the manual-line
    # directory being present on the target PC. Keep the UI usable when the
    # shared source file is not available beside the bundled executable.
    import tkinter as tk

    def translated(original, language):
        return str(original)

    class TrilingualController:
        def __init__(self, root, header, use_place=True, on_change=None, show_buttons=True):
            self.root, self.header, self.language, self.on_change = root, header, "zh", on_change
            self.frame = tk.Frame(header, bg="#0b1f35")
            if show_buttons:
                self.frame.pack(side="right", padx=(10, 0))
            self.buttons = {}
            for code, label in (("zh", "中"), ("en", "EN"), ("vi", "VI")):
                button = tk.Button(self.frame, text=label, command=lambda value=code: self.set(value),
                                   font=("Segoe UI", 9, "bold"), bg="#164e63", fg="white",
                                   relief="flat", padx=7, pady=3)
                if show_buttons:
                    button.pack(side="left", padx=2)
                self.buttons[code] = button

        def set(self, language):
            self.language = language
            if self.on_change:
                self.on_change(language)
