# -*- coding: utf-8 -*-
"""Equipment adapter contract shared by legacy and modular station UIs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass
class LegacyStationAdapter:
    module_name: str
    equipment: str
    version: str = "legacy-adapter-1.0"

    def on_register(self, common_agent: Any) -> None:
        self.common_agent = common_agent

    def health(self) -> Mapping[str, str]:
        return {"module": self.module_name, "equipment": self.equipment, "version": self.version}

    def normalize_result(self, result: Mapping[str, Any]) -> dict:
        payload = dict(result)
        payload.setdefault("stationModule", self.module_name)
        payload.setdefault("equipmentAdapter", self.equipment)
        return payload


def build_adapter(module_name: str, equipment: Optional[str] = None) -> LegacyStationAdapter:
    fallback = module_name[len("module_"):] if module_name.startswith("module_") else module_name
    return LegacyStationAdapter(module_name, equipment or fallback)


__all__ = ["LegacyStationAdapter", "build_adapter"]
