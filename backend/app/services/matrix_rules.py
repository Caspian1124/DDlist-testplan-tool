from __future__ import annotations

from typing import Dict, Tuple


VERSION_NOTE_COLUMNS = {
    "BIOS/BMC/FPGA/DDlist版本",
    "BIOS/BMC/FPGA/Config/DDlist",
    "BIOS/BMC/FPGA/DDlist 版本",
    "BIOS/BMC/FPGA/Config/DDlist版本",
}


HDD_SSD_TYPES = {"HDD", "SSD"}
DRIVER_RELEVANT_TYPES = {"NIC", "RAID", "GPU", "HBA", "NVME SWITCH", "NVME_SWITCH", "SWITCH"}


def is_supported(value: str) -> bool:
    """
    判断该 OS 列是否有测试意义。
    常见无效值：空、N/A、NA
    其余如 inbox / 版本号 / 包名 / 链接等都视为“支持”。
    """
    text = str(value or "").strip().lower()
    return text not in {"", "n/a", "na"}


def build_result_marks(part_type: str, os_cell_value: str) -> Tuple[str, str, str]:
    """
    返回：(fw_result, driver_result, version_note)

    规则：
    1. HDD/SSD：只打 FW，Driver 空，版本备注空
    2. NIC/RAID/GPU/HBA/SWITCH：FW/Driver 都可打，版本备注空
    3. 其他类型：默认只打 FW，Driver 空，版本备注空
    """
    normalized_type = str(part_type or "").strip().upper()
    supported = is_supported(os_cell_value)

    if not supported:
        return "", "", ""

    if normalized_type in HDD_SSD_TYPES:
        return "Y", "", ""

    if normalized_type in DRIVER_RELEVANT_TYPES:
        return "Y", "Y", ""

    return "Y", "", ""


def force_blank_version_note(_: str = "") -> str:
    """
    所有版本备注列统一留空，供测试人员手工填写。
    """
    return ""