from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class NormalizedPart(BaseModel):
    part_type: str = Field(..., description="部件大类，如 NIC / SSD / HDD / RAID / GPU")
    pn: str = Field(..., description="部件号，对应原始 DDlist 的 PN 列")
    source_tag: Optional[str] = Field(None, description="来源标签，对应 GP/CFC/HS")
    supplier_pn: Optional[str] = Field(None, description="厂商料号 / 型号编码")
    l2_description: str = Field(..., description="L2 Description 完整描述")
    supplier: Optional[str] = Field(None, description="厂商")
    fw_raw: Optional[str] = Field(None, description="FW 列原始多行文本")
    os_raw_map: Dict[str, Optional[str]] = Field(default_factory=dict, description="各 OS 列原始值映射")
    tool: Optional[str] = Field(None, description="Tool 列内容")
    remark: Optional[str] = Field(None, description="Remark 列内容")
    change_date: Optional[str] = Field(None, description="change date 列内容（建议 ISO 格式）")


class DerivedPartFeatures(BaseModel):
    normalized_vendor: str = Field(..., description="标准化后的厂商名")
    normalized_model: str = Field(..., description="标准化后的型号/系列名")

    capacity_value: Optional[float] = Field(None, description="容量数值，如 1.92 / 20 / 960")
    capacity_unit: Optional[str] = Field(None, description="容量单位，如 GB / TB")
    spec_value: Optional[str] = Field(None, description="规格值，如 8i / 16i / 2-port")

    nic_fw_package_key: Optional[str] = Field(None, description="NIC FW 包分组 key")
    nic_port_count: Optional[int] = Field(None, description="NIC 端口数")
    nic_speed_gbps: Optional[int] = Field(None, description="NIC 速率（Gbps）")
    nic_model_family: Optional[str] = Field(None, description="NIC 型号家族名")
    nic_generation_rank: Optional[int] = Field(None, description="NIC 型号新旧优先级")

    raid_series: Optional[str] = Field(None, description="RAID 系列，如 940 / 540 / 440")
    raid_spec: Optional[str] = Field(None, description="RAID 规格，如 8i / 16i / 2i")

    os_driver_version_map: Dict[str, Optional[str]] = Field(default_factory=dict, description="各 OS 列解析出的驱动版本映射")
    os_generation_map: Dict[str, str] = Field(default_factory=dict, description="OS 列名 -> 代际名映射")


class InventoryRecord(BaseModel):
    inventory_pn: Optional[str] = Field(None, description="库存中的部件号")
    inventory_model: str = Field(..., description="库存中的型号")
    inventory_capacity_or_spec: str = Field(..., description="库存中的容量/规格")
    inventory_vendor: str = Field(..., description="库存中的厂商")
    inventory_status: str = Field(..., description="库存状态，标准化为 有 / 无")
    raw_row: Dict[str, Any] = Field(default_factory=dict, description="原始库存行字典")


class ReleaseNoteRow(BaseModel):
    release_date: Optional[str] = Field(None, description="版本日期")
    release_version: Optional[str] = Field(None, description="版本号")
    content: str = Field(..., description="Release note 文本内容")
    done_by: Optional[str] = Field(None, description="责任人")


class ChangeListMatch(BaseModel):
    release_date: Optional[str] = None
    release_version: Optional[str] = None
    extracted_pn: str
    exists_in_ddlist: bool
    matched_ddlist_row_count: int = 0
    status: str
    message: Optional[str] = None
