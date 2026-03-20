from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NICModelGenerationRule(BaseModel):
    keyword: str = Field(..., description="用于匹配 NIC 型号家族的关键字")
    family: Optional[str] = Field(None, description="匹配后的家族名")
    rank: int = Field(..., description="型号新旧优先级，越大越新")


class NICModelGenerationDefaults(BaseModel):
    unknown_vendor_rank: int = 0
    unknown_model_rank: int = 0


class CapacityPriorityDefaults(BaseModel):
    unit_order: Dict[str, int] = Field(default_factory=lambda: {"TB": 2, "GB": 1})
    prefer_larger_capacity: bool = True


class CapacityPrioritySection(BaseModel):
    order: List[str] = Field(default_factory=list)


class CapacityPriorityConfig(BaseModel):
    defaults: CapacityPriorityDefaults = Field(default_factory=CapacityPriorityDefaults)
    SSD: Optional[CapacityPrioritySection] = None
    HDD: Optional[CapacityPrioritySection] = None


class RuleConfig(BaseModel):
    nic_model_generation: Dict[str, List[NICModelGenerationRule]] = Field(default_factory=dict)
    nic_model_generation_defaults: NICModelGenerationDefaults = Field(default_factory=NICModelGenerationDefaults)
    os_generation_map: Dict[str, str] = Field(default_factory=dict)
    capacity_priority: CapacityPriorityConfig = Field(default_factory=CapacityPriorityConfig)
    pn_regex: str = Field(default=r"\b[A-Z]{2,4}\d[A-Z0-9]{5,}\b", description="用于从 Release note 文本中提取 PN 的正则表达式")
