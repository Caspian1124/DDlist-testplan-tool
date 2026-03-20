from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from app.models.part_models import ReleaseNoteRow
from app.services.os_rule_engine import TestPlanRowState
from app.services.selection_engine import NoInventoryPart

BASE_COLUMNS = ["Type", "PN", "GP/CFC/HS", "Supplier PN", "L2 Description", "Supplier", "FW"]
RESULT_COLUMNS = ["FW Result", "Driver Result", "BIOS/BMC/FPGA/DDlist版本"]
TAIL_COLUMNS = ["Tool", "Remark", "change date"]
NO_INVENTORY_HEADERS = ["PN", "型号", "原因", "建议"]
RELEASE_NOTE_HEADERS = ["Edit history:", "Version", "Content", "Done by"]
SYSTEM_FW_HEADERS = ["Name", "Value"]
VERSION_NOTE_HEADERS = ["内容"]


def infer_os_order(row_states: Sequence[TestPlanRowState]) -> List[str]:
    if not row_states:
        return []
    return list(row_states[0].part.os_raw_map.keys())


def build_testplan_headers(os_order: Sequence[str]) -> List[str]:
    headers: List[str] = []
    headers.extend(BASE_COLUMNS)
    for os_name in os_order:
        headers.append(os_name)
        headers.extend(RESULT_COLUMNS)
    headers.extend(TAIL_COLUMNS)
    return headers


def build_testplan_rows(row_states: Sequence[TestPlanRowState], os_order: Optional[Sequence[str]] = None) -> Tuple[List[str], List[List[object]]]:
    os_order = list(os_order) if os_order is not None else infer_os_order(row_states)
    headers = build_testplan_headers(os_order)
    rows: List[List[object]] = []
    for row_state in row_states:
        part = row_state.part
        row: List[object] = [part.part_type, part.pn, part.source_tag, part.supplier_pn, part.l2_description, part.supplier, part.fw_raw]
        for os_name in os_order:
            cell = row_state.os_cells.get(os_name)
            row.append(part.os_raw_map.get(os_name))
            row.append(cell.fw_result if cell else None)
            row.append(cell.driver_result if cell else None)
            row.append(cell.bios_bmc_fpga_ddlist_version if cell else None)
        row.extend([part.tool, part.remark, part.change_date])
        rows.append(row)
    return headers, rows


def build_no_inventory_table(no_inventory_parts: Sequence[NoInventoryPart]) -> Tuple[List[str], List[List[object]]]:
    return NO_INVENTORY_HEADERS, [[item.part.pn, item.features.normalized_model, item.reason, item.suggestion] for item in no_inventory_parts]


def build_release_note_table(release_rows: Sequence[ReleaseNoteRow]) -> Tuple[List[str], List[List[object]]]:
    return RELEASE_NOTE_HEADERS, [[row.release_date, row.release_version, row.content, row.done_by] for row in release_rows]


def build_system_fw_table(system_fw_rows: Sequence[Dict[str, object]]) -> Tuple[List[str], List[List[object]]]:
    return SYSTEM_FW_HEADERS, [[row.get("name"), row.get("value")] for row in system_fw_rows]


def build_version_note_table(version_note_lines: Sequence[str]) -> Tuple[List[str], List[List[object]]]:
    return VERSION_NOTE_HEADERS, [[line] for line in version_note_lines]
