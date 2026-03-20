from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.core.config_loader import get_nic_generation_rank
from app.models.config_models import RuleConfig
from app.models.part_models import DerivedPartFeatures, NormalizedPart

_CAPACITY_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>TB|T|GB|G)\b", re.IGNORECASE)
_PORT_PATTERNS = [
    re.compile(r"(?P<count>\d+)\s*[- ]?port\b", re.IGNORECASE),
    re.compile(r"\b(?P<count>\d+)P\b", re.IGNORECASE),
    re.compile(r"\bSingle[- ]port\b", re.IGNORECASE),
]
_SPEED_PATTERNS = [
    re.compile(r"(?P<speed>\d+)\s*GbE\b", re.IGNORECASE),
    re.compile(r"(?P<speed>\d+)\s*Gb/s\b", re.IGNORECASE),
]
_RAID_SERIES_PATTERNS = [
    re.compile(r"\bRAID\s*(?P<series>B?\d{3,4})\b", re.IGNORECASE),
    re.compile(r"\b(?P<series>B?\d{3,4})-(?P<spec>\d+i)\b", re.IGNORECASE),
    re.compile(r"\b(?P<series>3S\d{3,4})\b", re.IGNORECASE),
]
_RAID_SPEC_PATTERN = re.compile(r"\b(?P<spec>\d+i)\b", re.IGNORECASE)
_FW_PACKAGE_PATTERN = re.compile(r"(?P<pkg>(?:[A-Za-z0-9]+[-_])+[A-Za-z0-9.]+(?:_linux|_windows|_vmware|_anyos|_noarch)[A-Za-z0-9._-]*)", re.IGNORECASE)
_VERSION_PATTERNS = [
    re.compile(r"Version\s*[：:]\s*(?P<version>[^\n#]+)", re.IGNORECASE),
    re.compile(r"NX1\s+Version\s*[：:]\s*(?P<version>[^\n#]+)", re.IGNORECASE),
    re.compile(r"NXE\s+Version\s*[：:]\s*(?P<version>[^\n#]+)", re.IGNORECASE),
    re.compile(r"NIC\s+FW\s+Version\s*[：:]\s*(?P<version>[^\n#]+)", re.IGNORECASE),
]
_NO_DRIVER_VALUES = {"no required", "n/a", "na"}
_INBOX_VALUES = {"inbox"}
_VENDOR_CANONICAL_MAP = {
    "mellanox": "Mellanox",
    "nvidia": "NVIDIA",
    "broadcom": "Broadcom",
    "intel": "Intel",
    "samsung": "Samsung",
    "toshiba": "Toshiba",
    "seagate": "Seagate",
    "wdc": "WDC",
    "solidigm": "Solidigm",
    "lenovo": "Lenovo",
    "sstc": "SSSTC",
    "unionmemory": "UnionMemory",
    "3snic": "3SNIC",
}


class DDlistNormalizer:
    def __init__(self, config: RuleConfig):
        self.config = config

    @staticmethod
    def _clean_text(value: Optional[str]) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())

    @staticmethod
    def _clean_multiline(value: Optional[str]) -> str:
        if value is None:
            return ""
        return "\n".join(line.strip() for line in str(value).splitlines())

    def normalize_vendor(self, part: NormalizedPart) -> str:
        base = self._clean_text(part.supplier).lower()
        if base in _VENDOR_CANONICAL_MAP:
            return _VENDOR_CANONICAL_MAP[base]
        search_text = f"{part.supplier or ''} {part.supplier_pn or ''} {part.l2_description or ''}".lower()
        for keyword, vendor in _VENDOR_CANONICAL_MAP.items():
            if keyword in search_text:
                return vendor
        return (part.supplier or "Unknown").strip() or "Unknown"

    def parse_capacity(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        match = _CAPACITY_PATTERN.search(text)
        if not match:
            return None, None
        value = float(match.group("value"))
        unit = match.group("unit").upper()
        if unit == "T":
            unit = "TB"
        elif unit == "G":
            unit = "GB"
        return value, unit

    def parse_port_count(self, text: str) -> Optional[int]:
        for pattern in _PORT_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            if "single-port" in match.group(0).lower():
                return 1
            count = match.groupdict().get("count")
            if count:
                return int(count)
        return None

    def parse_speed_gbps(self, text: str) -> Optional[int]:
        speeds: List[int] = []
        for pattern in _SPEED_PATTERNS:
            for match in pattern.finditer(text):
                try:
                    speeds.append(int(match.group("speed")))
                except (TypeError, ValueError):
                    continue
        return max(speeds) if speeds else None

    def parse_raid_series_and_spec(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        series = None
        spec = None
        for pattern in _RAID_SERIES_PATTERNS:
            match = pattern.search(text)
            if match:
                series = match.groupdict().get("series")
                spec = match.groupdict().get("spec") or spec
                break
        if spec is None:
            match = _RAID_SPEC_PATTERN.search(text)
            if match:
                spec = match.group("spec")
        if series:
            series = series.upper().replace("RAID", "").strip()
        if spec:
            spec = spec.lower()
        return series, spec

    def extract_fw_package_key(self, fw_raw: Optional[str]) -> Optional[str]:
        text = self._clean_multiline(fw_raw)
        if not text:
            return None
        matches = _FW_PACKAGE_PATTERN.findall(text)
        if not matches:
            return None
        pkg = matches[0].strip().replace("\\", "_")
        pkg = re.sub(r"__+", "_", pkg)
        return pkg

    def parse_os_driver_version(self, raw_value: Optional[str]) -> Optional[str]:
        text = self._clean_multiline(raw_value)
        if not text:
            return None
        lowered = text.strip().lower()
        if lowered in _INBOX_VALUES:
            return "inbox"
        if lowered in _NO_DRIVER_VALUES:
            return None
        for pattern in _VERSION_PATTERNS:
            match = pattern.search(text)
            if match:
                version = match.group("version").strip()
                version = version.split("FormID")[0].strip()
                version = version.split("#SPAR")[0].strip()
                return version
        first_line = text.split("\n", 1)[0].strip()
        return first_line or None

    def build_os_driver_version_map(self, part: NormalizedPart) -> Dict[str, Optional[str]]:
        return {os_name: self.parse_os_driver_version(raw_value) for os_name, raw_value in part.os_raw_map.items()}

    def build_os_generation_map(self, part: NormalizedPart) -> Dict[str, str]:
        return {os_name: self.config.os_generation_map.get(os_name, os_name) for os_name in part.os_raw_map.keys()}

    def infer_model(self, part: NormalizedPart, normalized_vendor: str) -> str:
        desc = self._clean_text(part.l2_description)
        supplier_pn = self._clean_text(part.supplier_pn)
        part_type = part.part_type.upper()
        if part_type in {"HDD", "SSD"}:
            model_patterns = [
                r"\b(PM9A3|PM893a|PM893|P5520|S4520|S4620|MG09|MG10|MG11|ESS5610|UH812a|UH832a|UM311b|ER3)\b",
                r"\b(ConnectX-\d(?:\s+[A-Za-z]+)?|BlueField-\d|E810|X710|I350)\b",
            ]
            for pat in model_patterns:
                m = re.search(pat, desc, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            return supplier_pn or desc
        if part_type == "NIC":
            nic_patterns = [
                r"\b(ConnectX-\d\s*[A-Za-z]*\b)",
                r"\b(BlueField-\d)\b",
                r"\b(E810)\b",
                r"\b(X710)\b",
                r"\b(I350)\b",
                r"\b(57508|57504|57414|5719)\b",
                r"\b(3SC10|82599ES)\b",
            ]
            for pat in nic_patterns:
                m = re.search(pat, desc, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            return supplier_pn or desc
        if part_type == "RAID":
            series, _ = self.parse_raid_series_and_spec(desc)
            if series:
                return f"RAID {series}"
            return supplier_pn or desc
        return supplier_pn or desc

    def normalize_part(self, part: NormalizedPart) -> DerivedPartFeatures:
        desc = self._clean_text(part.l2_description)
        normalized_vendor = self.normalize_vendor(part)
        normalized_model = self.infer_model(part, normalized_vendor)
        capacity_value, capacity_unit = self.parse_capacity(desc)
        port_count = self.parse_port_count(desc) if part.part_type.upper() == "NIC" else None
        speed_gbps = self.parse_speed_gbps(desc) if part.part_type.upper() == "NIC" else None
        raid_series, raid_spec = self.parse_raid_series_and_spec(desc) if part.part_type.upper() == "RAID" else (None, None)
        fw_package_key = self.extract_fw_package_key(part.fw_raw) if part.part_type.upper() == "NIC" else None
        search_text = f"{part.supplier_pn or ''} {part.l2_description or ''}"
        nic_generation_rank, nic_model_family = (None, None)
        if part.part_type.upper() == "NIC":
            rank, family = get_nic_generation_rank(self.config, normalized_vendor, search_text)
            nic_generation_rank, nic_model_family = rank, family
        spec_value = None
        if part.part_type.upper() == "RAID":
            spec_value = raid_spec
        elif part.part_type.upper() == "NIC" and port_count:
            spec_value = f"{port_count}-port"
        return DerivedPartFeatures(
            normalized_vendor=normalized_vendor,
            normalized_model=normalized_model,
            capacity_value=capacity_value,
            capacity_unit=capacity_unit,
            spec_value=spec_value,
            nic_fw_package_key=fw_package_key,
            nic_port_count=port_count,
            nic_speed_gbps=speed_gbps,
            nic_model_family=nic_model_family,
            nic_generation_rank=nic_generation_rank,
            raid_series=raid_series,
            raid_spec=raid_spec,
            os_driver_version_map=self.build_os_driver_version_map(part),
            os_generation_map=self.build_os_generation_map(part),
        )

    def normalize_parts(self, parts: List[NormalizedPart]) -> List[DerivedPartFeatures]:
        return [self.normalize_part(part) for part in parts]
