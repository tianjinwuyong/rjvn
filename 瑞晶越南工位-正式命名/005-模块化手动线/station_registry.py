from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from modular_contract import StationDefinition, merge_policy


class StationRegistry:
    def __init__(self, config_path=None):
        path = Path(config_path or Path(__file__).with_name("stations.json"))
        self.raw = json.loads(path.read_text(encoding="utf-8"))
        defaults = self.raw["repairDefaults"]
        policy_rows = self.raw["repairPolicies"]
        self._stations: Dict[str, StationDefinition] = {}
        for row in self.raw["stations"]:
            policy_key = row["ngPolicy"]
            station = StationDefinition(
                sequence=int(row["sequence"]), code=row["code"],
                name_zh=row["nameZh"], name_en=row["nameEn"], adapter=row["adapter"],
                inputs=list(row["inputs"]), normal_next=row["normalNext"],
                ng_policy=merge_policy(policy_key, policy_rows[policy_key], defaults),
            )
            if station.code in self._stations:
                raise ValueError("Duplicate station code: " + station.code)
            self._stations[station.code] = station

    def all(self) -> List[StationDefinition]:
        return sorted(self._stations.values(), key=lambda row: row.sequence)

    def get(self, code: str) -> StationDefinition:
        return self._stations[code]
