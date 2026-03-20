import axios, { type AxiosInstance, type AxiosProgressEvent } from 'axios'

const request: AxiosInstance = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 1000 * 60 * 5,
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error?.response?.data?.detail || error?.message || '请求失败，请稍后重试'
    return Promise.reject(new Error(message))
  }
)

export interface UploadDdlistResponse {
  file_id: string
  filename: string
  sheet_names: string[]
  ddlist_meta: Record<string, any>
  release_note_meta: Record<string, any>
  preview_parts: any[]
  preview_release_note: any[]
}

export interface UploadInventoryResponse {
  file_id: string
  filename: string
  detected_mapping: Record<string, string | null>
  warnings: string[]
  preview_records: any[]
  total_records: number
}

export interface GeneratePlanParams {
  ddlist_file_id: string
  project_name: string
  inventory_file_id?: string
  date_str?: string
}

export interface TestplanPreviewRow {
  pn: string
  part_type: string
  normalized_model: string
  normalized_vendor: string
  os_cells: Record<
    string,
    {
      os_name: string
      original_value: string | null
      selected_for_test: boolean
      fw_result: string | null
      driver_result: string | null
      bios_bmc_fpga_ddlist_version: string | null
      decision_reason: string
    }
  >
}

export interface GeneratePlanResponse {
  job_id: string
  project_name: string
  inventory_info: {
    inventory_used: boolean
    inventory_file_id: string | null
    inventory_filename?: string
    inventory_record_count?: number
  }
  selected_count: number
  no_inventory_count: number
  change_match_count: number
  excel_file: string
  change_list_csv: string
  change_list_txt: string
  preview_rows: TestplanPreviewRow[]
}

export interface PreviewPlanResponse {
  job_id: string
  project_name: string
  row_count: number
  rows: TestplanPreviewRow[]
  no_inventory_count: number
  change_match_count: number
}

export interface EditPlanRowParams {
  job_id: string
  pn: string
  os_name: string
  fw_result?: string
  driver_result?: string
}

export interface EditPlanRowResponse {
  job_id: string
  pn: string
  os_name: string
  updated_cell: {
    os_name: string
    original_value: string | null
    selected_for_test: boolean
    fw_result: string | null
    driver_result: string | null
    bios_bmc_fpga_ddlist_version: string | null
    decision_reason: string
  }
  excel_file: string
  message: string
}

export interface NoInventoryRow {
  pn: string
  type: string
  model: string
  vendor: string
  reason: string
  suggestion: string | null
}

export interface NoInventoryResponse {
  job_id: string
  count: number
  rows: NoInventoryRow[]
}

export interface ChangeListRow {
  pn: string
  release_version: string | null
  exists_in_ddlist: boolean
  status: string
  message: string | null
}

export interface ChangeListDetailResponse {
  job_id: string
  count: number
  rows: ChangeListRow[]
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

export async function uploadDdlistFile(file: File, onUploadProgress?: (progressEvent: AxiosProgressEvent) => void): Promise<UploadDdlistResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await request.post('/api/upload/ddlist', formData, { headers: { 'Content-Type': 'multipart/form-data' }, onUploadProgress })
  return data
}

export async function uploadInventoryFile(file: File, onUploadProgress?: (progressEvent: AxiosProgressEvent) => void): Promise<UploadInventoryResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await request.post('/api/upload/inventory', formData, { headers: { 'Content-Type': 'multipart/form-data' }, onUploadProgress })
  return data
}

export async function generateTestplan(params: GeneratePlanParams): Promise<GeneratePlanResponse> {
  const formData = new FormData()
  formData.append('ddlist_file_id', params.ddlist_file_id)
  formData.append('project_name', params.project_name)
  if (params.inventory_file_id) formData.append('inventory_file_id', params.inventory_file_id)
  if (params.date_str) formData.append('date_str', params.date_str)
  const { data } = await request.post('/api/plan/generate', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
  return data
}

export async function previewPlan(jobId: string): Promise<PreviewPlanResponse> {
  const { data } = await request.get(`/api/plan/preview/${jobId}`)
  return data
}

export async function editPlanRow(params: EditPlanRowParams): Promise<EditPlanRowResponse> {
  const { data } = await request.post('/api/plan/edit-row', params, { headers: { 'Content-Type': 'application/json' } })
  return data
}

export async function downloadTestplanExcel(jobId: string, filename?: string) {
  const response = await request.get(`/api/download/testplan/${jobId}`, { responseType: 'blob' })
  downloadBlob(response.data, filename || `TestPlan_${jobId}.xlsx`)
}

export async function downloadChangeList(jobId: string, fmt: 'csv' | 'txt', filename?: string) {
  const response = await request.get(`/api/download/change-list/${jobId}/${fmt}`, { responseType: 'blob' })
  downloadBlob(response.data, filename || `ChangeList_${jobId}.${fmt}`)
}

export async function getNoInventoryDetail(jobId: string): Promise<NoInventoryResponse> {
  const { data } = await request.get(`/api/plan/no-inventory/${jobId}`)
  return data
}

export async function getChangeListDetail(jobId: string): Promise<ChangeListDetailResponse> {
  const { data } = await request.get(`/api/plan/change-list/${jobId}`)
  return data
}
