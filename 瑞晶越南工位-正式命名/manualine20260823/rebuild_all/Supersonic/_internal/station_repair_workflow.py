# -*- coding: utf-8 -*-
"""Auto-line adapter for the shared MES repair workflow component."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import os
import sys

if getattr(sys, "frozen", False):
    # PyInstaller one-file uses _MEIPASS directly, while recent onedir
    # builds place data below <exe>/_internal.  Check both layouts.
    _frozen_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    _frozen_roots = [
        _frozen_root,
        _frozen_root / "_internal",
        Path(sys.executable).resolve().parent,
        Path(sys.executable).resolve().parent / "_internal",
    ]
    _shared = None
    for _root in _frozen_roots:
        _bundle_root = _root / "manual_repair"
        for _candidate in (
            _bundle_root / "shared_station_repair_workflow.py" / "station_repair_workflow.py",
            _bundle_root / "shared_station_repair_workflow.py",
            _bundle_root / "station_repair_workflow.py",
        ):
            if _candidate.is_file():
                _shared = _candidate
                break
        if _shared is not None:
            break
    if _shared is None:
        raise ImportError("No bundled manual_repair/station_repair_workflow.py was found")
else:
    _naming_root = Path(__file__).resolve().parents[1]
    _manual_candidates = [
        path / "station_repair_workflow.py"
        for path in _naming_root.iterdir()
        if path.is_dir() and path.name.startswith("004-")
    ]
    _manual_candidates.extend(_naming_root.glob("002-自动线/*/dist/manual_repair/station_repair_workflow.py"))
    _shared = next((path for path in _manual_candidates if path.exists()), None)
    if _shared is None:
        raise ImportError("No shared station_repair_workflow.py was found")
    _manual_line = _shared.parent
    if str(_manual_line) not in sys.path:
        sys.path.insert(0, str(_manual_line))
    for _manual_root in _naming_root.glob("004-*"):
        if _manual_root.is_dir() and str(_manual_root) not in sys.path:
            sys.path.insert(0, str(_manual_root))
# Frozen station bundles keep the shared workflow under manual_repair;
# make sibling bundled modules importable before executing it.
if str(_shared.parent) not in sys.path:
    sys.path.insert(0, str(_shared.parent))
_spec = spec_from_file_location("ruijing_shared_station_repair_workflow", _shared)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load shared repair workflow: {_shared}")
_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

RepairWorkflowPanel = _module.RepairWorkflowPanel
def install_repair_workflow(*args, **kwargs):
    if os.environ.get("STATION_MINIMAL_UI", "0") == "1":
        return None
    return _module.install_repair_workflow(*args, **kwargs)
render_streamlit_repair_workflow = _module.render_streamlit_repair_workflow

__all__ = ["RepairWorkflowPanel", "install_repair_workflow", "render_streamlit_repair_workflow"]
