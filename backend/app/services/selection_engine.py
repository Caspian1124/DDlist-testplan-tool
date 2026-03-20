from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from app.models.part_models import DerivedPartFeatures, InventoryRecord, NormalizedPart


@dataclass
class PartCandidate:
    part: NormalizedPart
    features: DerivedPartFeatures
    inventory_status: str
    inventory_match_reason: str
    matched_inventory: Optional[InventoryRecord] = None


@dataclass
class NoInventoryPart:
    part: NormalizedPart
    features: DerivedPartFeatures
    reason: str
    suggestion: Optional[str] = None


@dataclass
class SelectionResult:
    selected_candidates: List[PartCandidate]
    no_inventory_parts: List[NoInventoryPart]
    rejected_candidates: List[PartCandidate]


class SelectionEngine:
    """
    修正后的选型逻辑：
    1. 不依赖手工基准 TestPlan PN
    2. 不使用 GP/CFC/HS 作为优先级
    3. 无库存表时仍然生成基础 TestPlan
    4. 按“代表组”归并选型，减少冗余条目
    """

    def __init__(self, inventory_records: Optional[Sequence[InventoryRecord]] = None):
        self.inventory_records = list(inventory_records or [])

    @property
    def inventory_enabled(self) -> bool:
        return len(self.inventory_records) > 0

    def select_parts(
        self,
        parts: Sequence[NormalizedPart],
        features_list: Sequence[DerivedPartFeatures],
    ) -> SelectionResult:
        if len(parts) != len(features_list):
            raise ValueError("parts 与 features_list 长度不一致，无法进行选择")

        candidates = [
            self._build_candidate(part, features)
            for part, features in zip(parts, features_list)
        ]

        grouped: Dict[str, List[PartCandidate]] = {}
        for candidate in candidates:
            key = self._build_group_key(candidate)
            grouped.setdefault(key, []).append(candidate)

        selected: List[PartCandidate] = []
        rejected: List[PartCandidate] = []
        no_inventory: List[NoInventoryPart] = []

        for _, group in grouped.items():
            # 如果启用了库存，则优先从“有库存”中挑代表件
            if self.inventory_enabled:
                available = [c for c in group if c.inventory_status == "有"]
                if available:
                    winner = sorted(available, key=self._sort_key, reverse=True)[0]
                    selected.append(winner)
                    for c in group:
                        if c is not winner:
                            rejected.append(c)
                    continue

                # 有库存模式下，如果整组都没有库存，则进入无库存明细
                representative = sorted(group, key=self._sort_key, reverse=True)[0]
                no_inventory.append(
                    NoInventoryPart(
                        part=representative.part,
                        features=representative.features,
                        reason="代表组内无库存",
                        suggestion=self._build_group_key(representative),
                    )
                )
                rejected.extend(group)
                continue

            # 没有库存文件时，直接在组内选一个代表件，保证生成基础 TestPlan
            winner = sorted(group, key=self._sort_key, reverse=True)[0]
            selected.append(winner)
            for c in group:
                if c is not winner:
                    rejected.append(c)

        return SelectionResult(
            selected_candidates=selected,
            no_inventory_parts=no_inventory,
            rejected_candidates=rejected,
        )

    def _build_candidate(
        self,
        part: NormalizedPart,
        features: DerivedPartFeatures,
    ) -> PartCandidate:
        matched_inventory, reason = self._match_inventory(part, features)

        if not self.inventory_enabled:
            status = "未知"
        else:
            status = matched_inventory.inventory_status if matched_inventory else "无"

        return PartCandidate(
            part=part,
            features=features,
            inventory_status=status,
            inventory_match_reason=reason,
            matched_inventory=matched_inventory,
        )

    def _match_inventory(
        self,
        part: NormalizedPart,
        features: DerivedPartFeatures,
    ) -> Tuple[Optional[InventoryRecord], str]:
        if not self.inventory_enabled:
            return None, "未提供库存文件，按 DDlist 基础规则选型"

        pn = self._safe_upper(getattr(part, "pn", ""))
        vendor = self._safe_lower(self._get_attr(features, "normalized_vendor", ""))
        model = self._safe_lower(self._get_attr(features, "normalized_model", ""))
        spec = self._safe_lower(self._build_capacity_or_spec(features))

        # 1) PN 精确匹配
        pn_matches = [
            item for item in self.inventory_records
            if self._safe_upper(getattr(item, "inventory_pn", "")) == pn
        ]
        if pn_matches:
            return self._pick_best_inventory_record(pn_matches), "PN 精确匹配"

        # 2) 厂商 + 型号 + 规格
        vmc_matches = [
            item for item in self.inventory_records
            if self._safe_lower(getattr(item, "inventory_vendor", "")) == vendor
            and self._safe_lower(getattr(item, "inventory_model", "")) == model
            and self._safe_lower(getattr(item, "inventory_capacity_or_spec", "")) == spec
        ]
        if vmc_matches:
            return self._pick_best_inventory_record(vmc_matches), "厂商+型号+规格匹配"

        # 3) 型号 + 规格
        mc_matches = [
            item for item in self.inventory_records
            if self._safe_lower(getattr(item, "inventory_model", "")) == model
            and self._safe_lower(getattr(item, "inventory_capacity_or_spec", "")) == spec
        ]
        if mc_matches:
            return self._pick_best_inventory_record(mc_matches), "型号+规格匹配"

        # 4) 仅型号
        m_matches = [
            item for item in self.inventory_records
            if self._safe_lower(getattr(item, "inventory_model", "")) == model
        ]
        if m_matches:
            return self._pick_best_inventory_record(m_matches), "仅型号匹配"

        return None, "库存未匹配"

    def _build_group_key(self, candidate: PartCandidate) -> str:
        """
        代表组构建逻辑（不依赖手工基准 PN，不使用 GP/CFC/HS）：
        - HDD/SSD：协议 + 形态 + 容量档 + 类型
        - NIC：厂商 + 芯片族/型号 + 口数 + 速率 + 形态
        - RAID/HBA/SWITCH：系列 + 规格
        - GPU：型号族 + 形态
        - 其他：Type + 规范化型号
        """
        part = candidate.part
        f = candidate.features

        part_type = self._safe_upper(getattr(part, "part_type", "UNKNOWN"))

        protocol = self._guess_protocol(candidate)
        form_factor = self._guess_form_factor(candidate)
        capacity_bucket = self._guess_capacity_bucket(candidate)
        vendor = self._safe_upper(self._get_attr(f, "normalized_vendor", "UNKNOWN"))
        model = self._safe_upper(self._get_attr(f, "normalized_model", "") or getattr(part, "supplier_pn", "") or getattr(part, "pn", ""))
        raid_series = self._safe_upper(self._get_attr(f, "raid_series", ""))
        raid_spec = self._safe_upper(self._get_attr(f, "raid_spec", ""))
        nic_ports = str(self._get_attr(f, "nic_port_count", "") or "")
        nic_speed = str(self._get_attr(f, "nic_speed_gbps", "") or "")
        nic_shape = form_factor

        if part_type in {"HDD", "SSD"}:
            return f"{part_type}|{protocol}|{form_factor}|{capacity_bucket}"

        if part_type == "NIC":
            return f"{part_type}|{vendor}|{model}|{nic_ports}|{nic_speed}|{nic_shape}"

        if part_type in {"RAID", "HBA", "NVME SWITCH", "NVME_SWITCH", "SWITCH"}:
            return f"{part_type}|{raid_series or model}|{raid_spec or form_factor}"

        if part_type == "GPU":
            return f"{part_type}|{vendor}|{model}|{form_factor}"

        return f"{part_type}|{model}"

    def _sort_key(self, candidate: PartCandidate) -> Tuple[int, int, int, int, int]:
        """
        修正后的组内优先级：
        1. 库存（仅启用库存时）
        2. 覆盖价值（支持矩阵更完整）
        3. 规格完整度
        4. 代表性规格
        5. 时间/PN 稳定兜底

        注意：
        - 不依赖手工基准 TestPlan PN
        - 不使用 GP/CFC/HS
        """
        inventory_score = self._inventory_score(candidate.inventory_status)
        coverage_score = self._coverage_score(candidate)
        completeness_score = self._completeness_score(candidate)
        representative_score = self._representative_score(candidate)
        recency_score = self._recency_score(candidate)
        pn_score = self._pn_score(getattr(candidate.part, "pn", ""))

        return (
            inventory_score,
            coverage_score,
            completeness_score,
            representative_score,
            recency_score,
            pn_score,
        )

    @staticmethod
    def _inventory_score(status: str) -> int:
        if status == "有":
            return 2
        if status == "未知":
            return 1
        return 0

    def _coverage_score(self, candidate: PartCandidate) -> int:
        """
        覆盖价值：统计该部件支持多少个 OS 项。
        """
        part = candidate.part
        fields = [
            "windows_server_2019",
            "windows_server_2022",
            "windows_server_2025",
            "vmware_esxi_7_0_u3",
            "vmware_esxi_8_0",
            "vmware_esxi_8_0_u3",
            "rhel_8_6",
            "rhel_8_9",
            "rhel_8_10",
            "rhel_9_0",
            "rhel_9_3",
            "rhel_9_4",
            "rhel_9_5",
            "sles_15_sp4",
            "sles_15_sp5",
            "sles_15_sp6",
            "ubuntu_20_04_2",
            "ubuntu_22_04_4",
            "ubuntu_22_04_5",
            "ubuntu_24_04",
        ]
        score = 0
        for name in fields:
            val = getattr(part, name, None)
            if isinstance(val, str) and val.strip().lower() not in {"", "n/a", "na"}:
                score += 1
        return score

    def _completeness_score(self, candidate: PartCandidate) -> int:
        """
        规格完整度：能否解析出协议、形态、容量、型号、RAID规格、NIC口数/速率等。
        """
        score = 0
        f = candidate.features

        if self._guess_protocol(candidate) != "UNKNOWN":
            score += 1
        if self._guess_form_factor(candidate) != "UNKNOWN":
            score += 1
        if self._guess_capacity_bucket(candidate) != "UNKNOWN":
            score += 1
        if self._get_attr(f, "normalized_model", ""):
            score += 1
        if self._get_attr(f, "raid_spec", ""):
            score += 1
        if self._get_attr(f, "nic_port_count", None):
            score += 1
        if self._get_attr(f, "nic_speed_gbps", None):
            score += 1

        return score

    def _representative_score(self, candidate: PartCandidate) -> int:
        """
        代表性规格：倾向选择更主流、更典型的代表件，而不是极端规格。
        """
        part_type = self._safe_upper(getattr(candidate.part, "part_type", "UNKNOWN"))
        protocol = self._guess_protocol(candidate)
        form_factor = self._guess_form_factor(candidate)
        bucket = self._guess_capacity_bucket(candidate)

        score = 0

        if part_type in {"HDD", "SSD"}:
            # 中容量档优先，小/大次之
            if bucket == "MID":
                score += 3
            elif bucket in {"SMALL", "LARGE"}:
                score += 2

            # 常见形态优先
            if form_factor in {"2.5", "U.2", "M.2"}:
                score += 2
            elif form_factor in {"3.5", "U.3"}:
                score += 1

            # 协议代表性
            if protocol in {"SATA", "SAS", "NVME"}:
                score += 2

        elif part_type == "NIC":
            ports = self._get_attr(candidate.features, "nic_port_count", 0) or 0
            speed = self._get_attr(candidate.features, "nic_speed_gbps", 0) or 0

            # 2-port/4-port、10/25/100G 更典型
            if ports in {2, 4}:
                score += 2
            if speed in {10, 25, 100}:
                score += 2

        elif part_type in {"RAID", "HBA", "NVME SWITCH", "NVME_SWITCH", "SWITCH"}:
            spec = self._safe_upper(self._get_attr(candidate.features, "raid_spec", ""))
            if spec in {"8I", "16I", "8E", "16E"}:
                score += 3

        return score

    def _recency_score(self, candidate: PartCandidate) -> int:
        raw = getattr(candidate.part, "change_date", None) or getattr(candidate.part, "change_date_raw", None)
        if not raw:
            return 0

        if isinstance(raw, datetime):
            return int(raw.timestamp())

        text = str(raw).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
            try:
                return int(datetime.strptime(text, fmt).timestamp())
            except Exception:
                continue
        return 0

    @staticmethod
    def _pn_score(pn: str) -> int:
        text = str(pn or "")
        return sum(ord(ch) for ch in text)

    @staticmethod
    def _pick_best_inventory_record(records: Sequence[InventoryRecord]) -> InventoryRecord:
        return sorted(
            records,
            key=lambda r: 1 if getattr(r, "inventory_status", "") == "有" else 0,
            reverse=True,
        )[0]

    @staticmethod
    def _safe_upper(value: str) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _safe_lower(value: str) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _get_attr(obj, name: str, default=None):
        return getattr(obj, name, default)

    def _build_capacity_or_spec(self, features: DerivedPartFeatures) -> str:
        cap_val = self._get_attr(features, "capacity_value", None)
        cap_unit = self._get_attr(features, "capacity_unit", "")
        if cap_val is not None and cap_unit:
            value = int(cap_val) if float(cap_val).is_integer() else cap_val
            return f"{value}{cap_unit}"

        raid_spec = self._get_attr(features, "raid_spec", "")
        if raid_spec:
            return str(raid_spec)

        nic_port_count = self._get_attr(features, "nic_port_count", None)
        nic_speed_gbps = self._get_attr(features, "nic_speed_gbps", None)
        if nic_port_count and nic_speed_gbps:
            return f"{nic_port_count}-port {nic_speed_gbps}GbE"

        spec_value = self._get_attr(features, "spec_value", "")
        return str(spec_value or "")

    def _guess_protocol(self, candidate: PartCandidate) -> str:
        text = " ".join([
            str(getattr(candidate.part, "l2_description", "") or ""),
            str(getattr(candidate.part, "supplier_pn", "") or ""),
            str(getattr(candidate.part, "pn", "") or ""),
        ]).upper()

        if "NVME" in text:
            return "NVME"
        if "SAS" in text:
            return "SAS"
        if "SATA" in text:
            return "SATA"
        return "UNKNOWN"

    def _guess_form_factor(self, candidate: PartCandidate) -> str:
        text = " ".join([
            str(getattr(candidate.part, "l2_description", "") or ""),
            str(getattr(candidate.part, "supplier_pn", "") or ""),
        ]).upper()

        if '2.5"' in text or "2.5" in text:
            return "2.5"
        if '3.5"' in text or "3.5" in text:
            return "3.5"
        if "M.2" in text:
            return "M.2"
        if "U.2" in text:
            return "U.2"
        if "U.3" in text:
            return "U.3"
        if "OCP" in text:
            return "OCP"
        if "PCIE" in text or "PCIe" in text:
            return "PCIe"
        return "UNKNOWN"

    def _guess_capacity_bucket(self, candidate: PartCandidate) -> str:
        cap = self._get_attr(candidate.features, "capacity_value", None)
        unit = self._safe_upper(self._get_attr(candidate.features, "capacity_unit", ""))

        if cap is None:
            return "UNKNOWN"

        value_tb = float(cap)
        if unit == "GB":
            value_tb = value_tb / 1024.0
        elif unit == "TB":
            value_tb = value_tb
        else:
            return "UNKNOWN"

        part_type = self._safe_upper(getattr(candidate.part, "part_type", ""))

        if part_type == "HDD":
            if value_tb <= 2:
                return "SMALL"
            if value_tb <= 8:
                return "MID"
            return "LARGE"

        if part_type == "SSD":
            if value_tb <= 0.96:
                return "SMALL"
            if value_tb <= 3.84:
                return "MID"
            return "LARGE"

        return "UNKNOWN"