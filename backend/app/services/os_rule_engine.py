from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from app.models.part_models import DerivedPartFeatures, NormalizedPart
from app.services.selection_engine import PartCandidate


@dataclass
class OSResultCell:
    os_name: str
    original_value: Optional[str]
    selected_for_test: bool
    fw_result: Optional[str]
    driver_result: Optional[str]
    bios_bmc_fpga_ddlist_version: Optional[str]
    decision_reason: str


@dataclass
class TestPlanRowState:
    part: NormalizedPart
    features: DerivedPartFeatures
    os_cells: Dict[str, OSResultCell]


class OSRuleEngine:
    def apply(self, selected_candidates: Sequence[PartCandidate]) -> List[TestPlanRowState]:
        return [self._build_testplan_row_state(candidate) for candidate in selected_candidates]

    def _build_testplan_row_state(self, candidate: PartCandidate) -> TestPlanRowState:
        part = candidate.part
        features = candidate.features
        generation_groups: Dict[str, List[str]] = {}
        for os_name in part.os_raw_map.keys():
            generation = features.os_generation_map.get(os_name, os_name)
            generation_groups.setdefault(generation, []).append(os_name)
        selected_os_names: List[str] = []
        for _, os_list in generation_groups.items():
            selected_os_names.extend(self._select_within_generation(os_list, features))
        os_cells: Dict[str, OSResultCell] = {}
        for os_name, original_value in part.os_raw_map.items():
            is_selected = os_name in selected_os_names
            os_cells[os_name] = OSResultCell(
                os_name=os_name,
                original_value=original_value,
                selected_for_test=is_selected,
                fw_result="Y" if is_selected else None,
                driver_result="Y" if is_selected else None,
                bios_bmc_fpga_ddlist_version="Y" if is_selected else None,
                decision_reason=self._build_decision_reason(os_name, is_selected, features),
            )
        return TestPlanRowState(part=part, features=features, os_cells=os_cells)

    def _select_within_generation(self, os_list: Sequence[str], features: DerivedPartFeatures) -> List[str]:
        driver_versions = {os_name: features.os_driver_version_map.get(os_name) for os_name in os_list}
        normalized_versions = {os_name: self._normalize_driver_value(version) for os_name, version in driver_versions.items()}
        unique_versions = {v for v in normalized_versions.values() if v is not None}
        if len(os_list) <= 1:
            return list(os_list)
        if len(unique_versions) <= 1:
            return [self._pick_highest_os_version(os_list)]
        return list(os_list)

    @staticmethod
    def _normalize_driver_value(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().lower()
        return text or None

    def _pick_highest_os_version(self, os_list: Sequence[str]) -> str:
        return sorted(os_list, key=self._os_version_sort_key, reverse=True)[0]

    @staticmethod
    def _os_version_sort_key(os_name: str) -> Tuple[int, ...]:
        nums = re.findall(r"\d+(?:\.\d+)?", os_name or "")
        result: List[int] = []
        for item in nums:
            if "." in item:
                result.extend(int(x) for x in item.split("."))
            else:
                result.append(int(item))
        return tuple(result) if result else (0,)

    def _build_decision_reason(self, os_name: str, is_selected: bool, features: DerivedPartFeatures) -> str:
        generation = features.os_generation_map.get(os_name, os_name)
        driver_version = features.os_driver_version_map.get(os_name)
        if is_selected:
            if driver_version:
                return f"OS 入选，代际={generation}，驱动版本={driver_version}"
            return f"OS 入选，代际={generation}"
        return f"OS 被覆盖，代际={generation}"
