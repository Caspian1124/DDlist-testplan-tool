from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

import yaml

from app.models.config_models import NICModelGenerationDefaults, NICModelGenerationRule, RuleConfig


def _load_raw_config(config_path: str | Path) -> Dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    if path.suffix.lower() in {".yaml", ".yml"}:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    raise ValueError(f"不支持的配置文件格式: {path.suffix}")


def _parse_nic_model_generation(raw: Dict[str, Any]) -> tuple[dict, NICModelGenerationDefaults]:
    nic_section = raw.get("nic_model_generation", {}) or {}
    defaults_raw = nic_section.get("defaults", {}) if isinstance(nic_section, dict) else {}
    defaults = NICModelGenerationDefaults(**defaults_raw)

    parsed: Dict[str, list[NICModelGenerationRule]] = {}
    for vendor, rules in nic_section.items():
        if vendor == "defaults":
            continue
        if not isinstance(rules, list):
            raise ValueError(f"nic_model_generation.{vendor} 必须是列表")
        parsed[vendor] = [NICModelGenerationRule(**item) for item in rules]

    return parsed, defaults


def load_rule_config(config_path: str | Path) -> RuleConfig:
    raw = _load_raw_config(config_path)
    nic_model_generation, nic_defaults = _parse_nic_model_generation(raw)

    config = RuleConfig(
        nic_model_generation=nic_model_generation,
        nic_model_generation_defaults=nic_defaults,
        os_generation_map=raw.get("os_generation_map", {}) or {},
        capacity_priority=raw.get("capacity_priority", {}) or {},
        pn_regex=raw.get("pn_regex", r"\b[A-Z]{2,4}\d[A-Z0-9]{5,}\b"),
    )
    return config


def get_compiled_pn_pattern(config: RuleConfig) -> re.Pattern:
    return re.compile(config.pn_regex, re.IGNORECASE)


def get_nic_generation_rank(config: RuleConfig, vendor: str, search_text: str) -> tuple[int, str | None]:
    rules = config.nic_model_generation.get(vendor, [])
    if not rules:
        return config.nic_model_generation_defaults.unknown_vendor_rank, None

    normalized_text = (search_text or "").strip().lower()
    matched_rank = config.nic_model_generation_defaults.unknown_model_rank
    matched_family = None

    for rule in rules:
        if rule.keyword.lower() in normalized_text:
            if rule.rank > matched_rank:
                matched_rank = rule.rank
                matched_family = rule.family or rule.keyword

    return matched_rank, matched_family
