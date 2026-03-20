import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AxiosProgressEvent } from 'axios'
import {
  uploadDdlistFile,
  uploadInventoryFile,
  generateTestplan,
  previewPlan,
  editPlanRow,
  downloadTestplanExcel,
  downloadChangeList,
  type UploadDdlistResponse,
  type UploadInventoryResponse,
  type GeneratePlanResponse,
  type PreviewPlanResponse,
  type EditPlanRowParams,
} from '@/api/api'

export const useTestplanStore = defineStore('testplan', () => {
  const projectName = ref('WR5215G5')
  const ddlistUploadResult = ref<UploadDdlistResponse | null>(null)
  const inventoryUploadResult = ref<UploadInventoryResponse | null>(null)
  const generateResult = ref<GeneratePlanResponse | null>(null)
  const previewData = ref<PreviewPlanResponse | null>(null)

  const ddlistFileId = computed(() => ddlistUploadResult.value?.file_id || '')
  const inventoryFileId = computed(() => inventoryUploadResult.value?.file_id || '')
  const jobId = computed(() => generateResult.value?.job_id || previewData.value?.job_id || '')

  const ddlistUploading = ref(false)
  const inventoryUploading = ref(false)
  const generating = ref(false)
  const loadingPreview = ref(false)
  const editing = ref(false)

  const canGenerate = computed(() => !!ddlistFileId.value && !!projectName.value)

  function setProjectName(name: string) {
    projectName.value = name
  }

  async function uploadDdlist(file: File, onUploadProgress?: (progressEvent: AxiosProgressEvent) => void) {
    ddlistUploading.value = true
    try {
      const result = await uploadDdlistFile(file, onUploadProgress)
      ddlistUploadResult.value = result
      return result
    } finally {
      ddlistUploading.value = false
    }
  }

  async function uploadInventory(file: File, onUploadProgress?: (progressEvent: AxiosProgressEvent) => void) {
    inventoryUploading.value = true
    try {
      const result = await uploadInventoryFile(file, onUploadProgress)
      inventoryUploadResult.value = result
      return result
    } finally {
      inventoryUploading.value = false
    }
  }

  async function generate(dateStr?: string) {
    if (!ddlistFileId.value) throw new Error('请先上传 DDlist 文件')
    generating.value = true
    try {
      const result = await generateTestplan({
        ddlist_file_id: ddlistFileId.value,
        inventory_file_id: inventoryFileId.value || undefined,
        project_name: projectName.value,
        date_str: dateStr,
      })
      generateResult.value = result
      previewData.value = {
        job_id: result.job_id,
        project_name: result.project_name,
        row_count: result.selected_count,
        rows: result.preview_rows,
        no_inventory_count: result.no_inventory_count,
        change_match_count: result.change_match_count,
      }
      return result
    } finally {
      generating.value = false
    }
  }

  async function fetchPreview() {
    if (!jobId.value) throw new Error('当前没有可预览的 jobId')
    loadingPreview.value = true
    try {
      const data = await previewPlan(jobId.value)
      previewData.value = data
      return data
    } finally {
      loadingPreview.value = false
    }
  }

  async function editRow(params: EditPlanRowParams) {
    editing.value = true
    try {
      const result = await editPlanRow(params)
      const row = previewData.value?.rows.find((item) => item.pn === params.pn)
      if (row && row.os_cells[params.os_name]) {
        row.os_cells[params.os_name].fw_result = result.updated_cell.fw_result
        row.os_cells[params.os_name].driver_result = result.updated_cell.driver_result
        row.os_cells[params.os_name].bios_bmc_fpga_ddlist_version = result.updated_cell.bios_bmc_fpga_ddlist_version
      }
      return result
    } finally {
      editing.value = false
    }
  }

  async function downloadExcel() {
    if (!jobId.value) throw new Error('当前没有可下载的 jobId')
    await downloadTestplanExcel(jobId.value, `TestPlan1_${projectName.value || jobId.value}.xlsx`)
  }

  async function downloadChangeListReport(fmt: 'csv' | 'txt') {
    if (!jobId.value) throw new Error('当前没有可下载的 jobId')
    await downloadChangeList(jobId.value, fmt, `ChangeList_${projectName.value || jobId.value}.${fmt}`)
  }

  function resetGenerateState() {
    generateResult.value = null
    previewData.value = null
  }

  function clearAll() {
    projectName.value = 'WR5215G5'
    ddlistUploadResult.value = null
    inventoryUploadResult.value = null
    generateResult.value = null
    previewData.value = null
  }

  return {
    projectName,
    ddlistUploadResult,
    inventoryUploadResult,
    generateResult,
    previewData,
    ddlistFileId,
    inventoryFileId,
    jobId,
    ddlistUploading,
    inventoryUploading,
    generating,
    loadingPreview,
    editing,
    canGenerate,
    setProjectName,
    uploadDdlist,
    uploadInventory,
    generate,
    fetchPreview,
    editRow,
    downloadExcel,
    downloadChangeListReport,
    resetGenerateState,
    clearAll,
  }
})
