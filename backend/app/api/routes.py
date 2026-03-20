from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.config_loader import get_compiled_pn_pattern, load_rule_config
from app.services.change_list_parser import compare_release_note_with_ddlist
from app.services.ddlist_normalizer import DDlistNormalizer
from app.services.excel_parser import ParsedWorkbook, parse_workbook
from app.services.exporter import TestPlanExporter
from app.services.inventory_mapper import map_inventory_dataframe
from app.services.os_rule_engine import OSRuleEngine, TestPlanRowState
from app.services.selection_engine import SelectionEngine

router = APIRouter()

BASE_DIR = Path('.')
UPLOAD_DIR = BASE_DIR / 'uploads'
OUTPUT_DIR = BASE_DIR / 'output'
CONFIG_PATH = BASE_DIR / 'config' / 'rules.yaml'

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class InMemoryStore:
    def __init__(self) -> None:
        self.ddlist_uploads: Dict[str, Dict[str, Any]] = {}
        self.inventory_uploads: Dict[str, Dict[str, Any]] = {}
        self.jobs: Dict[str, Dict[str, Any]] = {}


STORE = InMemoryStore()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _save_upload_file(file: UploadFile, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open('wb') as f:
        shutil.copyfileobj(file.file, f)


def _read_inventory_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == '.csv':
        return pd.read_csv(file_path)
    if suffix == '.xlsx':
        return pd.read_excel(file_path, engine='openpyxl')
    raise ValueError('仅支持 .csv / .xlsx 库存文件')


def _serialize_os_cell(cell) -> Dict[str, Any]:
    return {
        'os_name': cell.os_name,
        'original_value': cell.original_value,
        'selected_for_test': cell.selected_for_test,
        'fw_result': cell.fw_result,
        'driver_result': cell.driver_result,
        'bios_bmc_fpga_ddlist_version': cell.bios_bmc_fpga_ddlist_version,
        'decision_reason': cell.decision_reason,
    }


def _serialize_testplan_row_state(row_state: TestPlanRowState) -> Dict[str, Any]:
    return {
        'pn': row_state.part.pn,
        'part_type': row_state.part.part_type,
        'normalized_model': row_state.features.normalized_model,
        'normalized_vendor': row_state.features.normalized_vendor,
        'os_cells': {k: _serialize_os_cell(v) for k, v in row_state.os_cells.items()},
    }


def _serialize_no_inventory_item(item) -> Dict[str, Any]:
    return {
        'pn': item.part.pn,
        'type': item.part.part_type,
        'model': item.features.normalized_model,
        'vendor': item.features.normalized_vendor,
        'reason': item.reason,
        'suggestion': item.suggestion,
    }


def _serialize_change_list_item(item) -> Dict[str, Any]:
    return {
        'pn': item.extracted_pn,
        'release_version': item.release_version,
        'exists_in_ddlist': item.exists_in_ddlist,
        'status': item.status,
        'message': item.message,
    }


@router.get('/health')
def health_check() -> Dict[str, str]:
    return {'status': 'ok'}


@router.post('/upload/ddlist')
async def upload_ddlist(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(status_code=400, detail='DDlist 文件仅支持 .xlsx')
    file_id = _new_id('ddlist')
    save_path = UPLOAD_DIR / f'{file_id}_{file.filename}'
    _save_upload_file(file, save_path)
    try:
        parsed = parse_workbook(save_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'DDlist 解析失败: {e}')
    STORE.ddlist_uploads[file_id] = {'file_id': file_id, 'filename': file.filename, 'path': str(save_path), 'parsed': parsed}
    return {
        'file_id': file_id,
        'filename': file.filename,
        'sheet_names': parsed.metadata.get('sheet_names', []),
        'ddlist_meta': parsed.metadata.get('ddlist', {}),
        'release_note_meta': parsed.metadata.get('release_note', {}),
        'preview_parts': [part.model_dump() for part in parsed.normalized_parts[:10]],
        'preview_release_note': [row.model_dump() for row in parsed.release_note_rows[:10]],
    }


@router.post('/upload/inventory')
async def upload_inventory(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not (file.filename.lower().endswith('.csv') or file.filename.lower().endswith('.xlsx')):
        raise HTTPException(status_code=400, detail='库存文件仅支持 .csv / .xlsx')
    file_id = _new_id('inventory')
    save_path = UPLOAD_DIR / f'{file_id}_{file.filename}'
    _save_upload_file(file, save_path)
    try:
        df = _read_inventory_dataframe(save_path)
        mapping_result = map_inventory_dataframe(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'库存文件解析失败: {e}')
    STORE.inventory_uploads[file_id] = {'file_id': file_id, 'filename': file.filename, 'path': str(save_path), 'mapping_result': mapping_result}
    return {
        'file_id': file_id,
        'filename': file.filename,
        'detected_mapping': mapping_result.detected_mapping,
        'warnings': mapping_result.warnings,
        'preview_records': [item.model_dump() for item in mapping_result.records[:10]],
        'total_records': len(mapping_result.records),
    }


@router.post('/plan/generate')
def generate_testplan(ddlist_file_id: str = Form(...), project_name: str = Form(...), inventory_file_id: Optional[str] = Form(None), date_str: Optional[str] = Form(None)) -> Dict[str, Any]:
    ddlist_entry = STORE.ddlist_uploads.get(ddlist_file_id)
    if not ddlist_entry:
        raise HTTPException(status_code=404, detail='未找到 DDlist 上传记录')
    parsed: ParsedWorkbook = ddlist_entry['parsed']
    inventory_records = []
    inventory_info: Dict[str, Any] = {'inventory_used': False, 'inventory_file_id': None}
    if inventory_file_id:
        inventory_entry = STORE.inventory_uploads.get(inventory_file_id)
        if not inventory_entry:
            raise HTTPException(status_code=404, detail='未找到库存上传记录')
        inventory_records = inventory_entry['mapping_result'].records
        inventory_info = {
            'inventory_used': True,
            'inventory_file_id': inventory_file_id,
            'inventory_filename': inventory_entry['filename'],
            'inventory_record_count': len(inventory_records),
        }
    try:
        config = load_rule_config(CONFIG_PATH)
        normalizer = DDlistNormalizer(config)
        features_list = normalizer.normalize_parts(parsed.normalized_parts)
        selection_engine = SelectionEngine(inventory_records=inventory_records)
        selection_result = selection_engine.select_parts(parsed.normalized_parts, features_list)
        os_engine = OSRuleEngine()
        row_states = os_engine.apply(selection_result.selected_candidates)
        pn_pattern = get_compiled_pn_pattern(config)
        change_matches = compare_release_note_with_ddlist(parsed.release_note_rows, parsed.normalized_parts, pn_pattern)
        exporter = TestPlanExporter(output_dir=OUTPUT_DIR)
        excel_path = exporter.export_testplan_excel(
            project_name=project_name,
            row_states=row_states,
            no_inventory_parts=selection_result.no_inventory_parts,
            release_rows=parsed.release_note_rows,
            system_fw_rows=parsed.system_fw_rows,
            version_note_lines=parsed.version_note_lines,
            date_str=date_str,
        )
        change_paths = exporter.export_change_list_reports(project_name=project_name, matches=change_matches, date_str=date_str)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'生成 Testplan 失败: {e}')
    job_id = _new_id('job')
    STORE.jobs[job_id] = {
        'job_id': job_id,
        'project_name': project_name,
        'ddlist_file_id': ddlist_file_id,
        'inventory_file_id': inventory_file_id,
        'parsed': parsed,
        'row_states': row_states,
        'no_inventory_parts': selection_result.no_inventory_parts,
        'change_matches': change_matches,
        'excel_path': str(excel_path),
        'change_csv_path': str(change_paths['csv']),
        'change_txt_path': str(change_paths['txt']),
        'date_str': date_str,
    }
    return {
        'job_id': job_id,
        'project_name': project_name,
        'inventory_info': inventory_info,
        'selected_count': len(selection_result.selected_candidates),
        'no_inventory_count': len(selection_result.no_inventory_parts),
        'change_match_count': len(change_matches),
        'excel_file': Path(excel_path).name,
        'change_list_csv': Path(change_paths['csv']).name,
        'change_list_txt': Path(change_paths['txt']).name,
        'preview_rows': [_serialize_testplan_row_state(row) for row in row_states[:10]],
    }


@router.get('/download/testplan/{job_id}')
def download_testplan_excel(job_id: str):
    job = STORE.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='未找到生成任务')
    path = Path(job['excel_path'])
    if not path.exists():
        raise HTTPException(status_code=404, detail='Testplan 文件不存在')
    return FileResponse(path=path, filename=path.name, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@router.get('/download/change-list/{job_id}/{fmt}')
def download_change_list(job_id: str, fmt: str):
    job = STORE.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='未找到生成任务')
    fmt = fmt.lower()
    if fmt == 'csv':
        path = Path(job['change_csv_path'])
        media_type = 'text/csv'
    elif fmt == 'txt':
        path = Path(job['change_txt_path'])
        media_type = 'text/plain'
    else:
        raise HTTPException(status_code=400, detail='仅支持 csv / txt')
    if not path.exists():
        raise HTTPException(status_code=404, detail='Change List 报告不存在')
    return FileResponse(path=path, filename=path.name, media_type=media_type)


@router.post('/plan/edit-row')
def edit_testplan_row(payload: Dict[str, Any]) -> Dict[str, Any]:
    job_id = payload.get('job_id')
    pn = payload.get('pn')
    os_name = payload.get('os_name')
    fw_result = payload.get('fw_result')
    driver_result = payload.get('driver_result')
    if not job_id or not pn or not os_name:
        raise HTTPException(status_code=400, detail='job_id / pn / os_name 为必填')
    job = STORE.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='未找到生成任务')
    row_states: List[TestPlanRowState] = job['row_states']
    target_row = next((row for row in row_states if row.part.pn == pn), None)
    if not target_row:
        raise HTTPException(status_code=404, detail=f'未找到 PN={pn} 的测试行')
    target_cell = target_row.os_cells.get(os_name)
    if not target_cell:
        raise HTTPException(status_code=404, detail=f'未找到 OS={os_name} 的结果列')
    if fw_result is not None:
        target_cell.fw_result = fw_result
    if driver_result is not None:
        target_cell.driver_result = driver_result
    exporter = TestPlanExporter(output_dir=OUTPUT_DIR)
    excel_path = exporter.export_testplan_excel(
        project_name=job['project_name'],
        row_states=row_states,
        no_inventory_parts=job['no_inventory_parts'],
        release_rows=job['parsed'].release_note_rows,
        system_fw_rows=job['parsed'].system_fw_rows,
        version_note_lines=job['parsed'].version_note_lines,
        date_str=job.get('date_str'),
    )
    job['excel_path'] = str(excel_path)
    return {
        'job_id': job_id,
        'pn': pn,
        'os_name': os_name,
        'updated_cell': _serialize_os_cell(target_cell),
        'excel_file': Path(excel_path).name,
        'message': '编辑成功，已重新导出 Testplan Excel',
    }


@router.get('/plan/preview/{job_id}')
def preview_generated_plan(job_id: str) -> Dict[str, Any]:
    job = STORE.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='未找到生成任务')
    row_states: List[TestPlanRowState] = job['row_states']
    return {
        'job_id': job_id,
        'project_name': job['project_name'],
        'row_count': len(row_states),
        'rows': [_serialize_testplan_row_state(row) for row in row_states[:100]],
        'no_inventory_count': len(job['no_inventory_parts']),
        'change_match_count': len(job['change_matches']),
    }


@router.get('/plan/no-inventory/{job_id}')
def get_no_inventory_detail(job_id: str) -> Dict[str, Any]:
    job = STORE.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='未找到生成任务')
    no_inventory_parts = job.get('no_inventory_parts', [])
    return {'job_id': job_id, 'count': len(no_inventory_parts), 'rows': [_serialize_no_inventory_item(item) for item in no_inventory_parts]}


@router.get('/plan/change-list/{job_id}')
def get_change_list_detail(job_id: str) -> Dict[str, Any]:
    job = STORE.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='未找到生成任务')
    change_matches = job.get('change_matches', [])
    return {'job_id': job_id, 'count': len(change_matches), 'rows': [_serialize_change_list_item(item) for item in change_matches]}
