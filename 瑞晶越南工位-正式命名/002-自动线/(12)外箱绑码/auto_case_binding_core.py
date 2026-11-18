# -*- coding: utf-8 -*-
"""Auto-line domain adapter for the shared outer-box binding engine."""

import sys
from pathlib import Path

try:
    import case_binding_core as _core
except ModuleNotFoundError:
    _naming_root = Path(__file__).resolve().parents[2]
    _manual_core = next(
        folder / "(12)外箱绑码"
        for folder in _naming_root.iterdir()
        if folder.is_dir()
        and folder.name.startswith("004-")
        and (folder / "(12)外箱绑码" / "case_binding_core.py").exists()
    )
    sys.path.insert(0, str(_manual_core))
    import case_binding_core as _core

_core.STATION_CODE = "auto_case_binding"
_core.NEXT_STATION = "auto_pallet_binding"
_core.ALLOWED_CASE_CAPACITIES = (48,)

BindingError = _core.BindingError
MES_BASE = _core.MES_BASE
STATION_CODE = _core.STATION_CODE


class CaseBindingStore(_core.CaseBindingStore):
    """Auto-line store with MES work-order binding permanently enforced."""

    def __init__(self, db_path=_core.DB_PATH):
        super().__init__(db_path)
        super().set_work_order_bypass(False)

    def work_order_bypass(self):
        return False

    def set_work_order_bypass(self, enabled):
        super().set_work_order_bypass(False)
        return False
