from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from app.models.part_models import InventoryRecord


INVENTORY_FIELD_ALIASES = {
    "inventory_pn": ["部件号", "部件编号", "PN", "Part Number", "Material PN", "物料号", "料号"],
    "inventory_model": ["型号", "Model", "物料型号", "设备型号", "Model Name"],
    "inventory_capacity_or_spec": ["容量", "规格", "容量规格", "Capacity", "Spec", "容量/规格"],
    "inventory_vendor": ["厂商", "Vendor", "Supplier", "品牌", "Manufacturer"],
    "inventory_status": ["库存状态", "有无库存", "Availability", "Stock Status", "库存", "是否有货"],
}

AVAILABLE_VALUES = {"有", "有货", "yes", "y", "available", "in stock", "true", "1"}
UNAVAILABLE_VALUES = {"无", "无货", "no", "n", "unavailable", "out of stock", "false", "0"}


@dataclass
class InventoryMappingResult:
    records: List[InventoryRecord]
    detected_mapping: Dict[str, Optional[str]]
    warnings: List[str]


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return " ".join(text.split())


def _normalize_status(raw_status: Any) -> str:
    text = (_normalize_text(raw_status) or "").lower()
    if text in AVAILABLE_VALUES:
        return "有"
    if text in UNAVAILABLE_VALUES:
        return "无"
    raise ValueError(f"无法识别的库存状态值: {raw_status}")


def _detect_column_mapping(columns: List[str]) -> Dict[str, Optional[str]]:
    mapping: Dict[str, Optional[str]] = {
        "inventory_pn": None,
        "inventory_model": None,
        "inventory_capacity_or_spec": None,
        "inventory_vendor": None,
        "inventory_status": None,
    }
    lowered = {col.lower(): col for col in columns}
    for target_field, aliases in INVENTORY_FIELD_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            if alias_lower in lowered:
                mapping[target_field] = lowered[alias_lower]
                break
    return mapping


def _validate_required_mapping(mapping: Dict[str, Optional[str]]) -> List[str]:
    errors = []
    required_fields = ["inventory_model", "inventory_capacity_or_spec", "inventory_vendor", "inventory_status"]
    for field_name in required_fields:
        if not mapping.get(field_name):
            errors.append(f"缺少必填库存字段映射: {field_name}")
    return errors


def map_inventory_dataframe(df: pd.DataFrame) -> InventoryMappingResult:
    columns = [str(c).strip() for c in df.columns.tolist()]
    mapping = _detect_column_mapping(columns)
    errors = _validate_required_mapping(mapping)
    if errors:
        raise ValueError("；".join(errors))

    warnings: List[str] = []
    if not mapping.get("inventory_pn"):
        warnings.append("未识别到库存部件号字段，将无法执行 PN 精确匹配，只能执行型号/规格匹配。")

    records: List[InventoryRecord] = []
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        record = InventoryRecord(
            inventory_pn=_normalize_text(row_dict.get(mapping["inventory_pn"])) if mapping["inventory_pn"] else None,
            inventory_model=_normalize_text(row_dict.get(mapping["inventory_model"])) or "",
            inventory_capacity_or_spec=_normalize_text(row_dict.get(mapping["inventory_capacity_or_spec"])) or "",
            inventory_vendor=_normalize_text(row_dict.get(mapping["inventory_vendor"])) or "",
            inventory_status=_normalize_status(row_dict.get(mapping["inventory_status"])),
            raw_row={str(k): v for k, v in row_dict.items()},
        )
        records.append(record)

    return InventoryMappingResult(records=records, detected_mapping=mapping, warnings=warnings)


def map_inventory_rows(rows: Iterable[Dict[str, Any]]) -> InventoryMappingResult:
    df = pd.DataFrame(list(rows))
    return map_inventory_dataframe(df)
