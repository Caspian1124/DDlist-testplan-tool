<template>
  <div class="page-container">
    <el-card class="mb-16">
      <template #header>
        <div class="header-line">
          <span>Testplan 结果预览</span>
          <div class="toolbar">
            <el-button type="primary" @click="handleDownloadExcel">下载 Testplan Excel</el-button>
            <el-button @click="handleDownloadChangeList('csv')">下载 Change List CSV</el-button>
            <el-button @click="handleDownloadChangeList('txt')">下载 Change List TXT</el-button>
            <el-button @click="loadPreview">刷新预览</el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="4" border>
        <el-descriptions-item label="Job ID">{{ store.jobId }}</el-descriptions-item>
        <el-descriptions-item label="项目名">{{ store.projectName }}</el-descriptions-item>
        <el-descriptions-item label="主表行数">{{ store.previewData?.row_count || 0 }}</el-descriptions-item>
        <el-descriptions-item label="无库存数量">{{ noInventoryData?.count || 0 }}</el-descriptions-item>
        <el-descriptions-item label="Change List 数量">{{ changeListData?.count || 0 }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-tabs v-model="activeTab" type="border-card" @tab-change="handleTabChange">
      <el-tab-pane label="主表" name="main">
        <TestplanTable :rows="store.previewData?.rows || []" :loading="store.loadingPreview" @edit="openEditDialog" />
      </el-tab-pane>

      <el-tab-pane label="无库存" name="noInventory">
        <el-table :data="noInventoryData?.rows || []" border stripe height="520" v-loading="loadingNoInventory">
          <el-table-column prop="pn" label="PN" width="160" />
          <el-table-column prop="type" label="Type" width="100" />
          <el-table-column prop="model" label="Model" min-width="220" />
          <el-table-column prop="vendor" label="Vendor" width="140" />
          <el-table-column prop="reason" label="Reason" min-width="220" />
          <el-table-column prop="suggestion" label="Suggestion" min-width="220" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="Change List" name="changeList">
        <el-table :data="changeListData?.rows || []" border stripe height="520" v-loading="loadingChangeList">
          <el-table-column prop="pn" label="PN" width="160" />
          <el-table-column prop="release_version" label="Release Version" width="160" />
          <el-table-column prop="exists_in_ddlist" label="Exists in DDList" width="150">
            <template #default="{ row }">
              <el-tag :type="row.exists_in_ddlist ? 'success' : 'danger'">{{ row.exists_in_ddlist ? 'Yes' : 'No' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="Status" width="140" />
          <el-table-column prop="message" label="Message" min-width="260" />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <EditResultDialog v-model:visible="editDialogVisible" :row="editingRow" :loading="store.editing" @submit="handleSubmitEdit" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import TestplanTable from '@/components/TestplanTable.vue'
import EditResultDialog from '@/components/EditResultDialog.vue'
import { useTestplanStore } from '@/stores/testplan'
import type { TestplanPreviewRow, NoInventoryResponse, ChangeListDetailResponse } from '@/api/api'
import { getNoInventoryDetail, getChangeListDetail } from '@/api/api'
import { getErrorMessage } from '@/utils/error'

const store = useTestplanStore()

const activeTab = ref('main')
const editDialogVisible = ref(false)
const editingRow = ref<TestplanPreviewRow | null>(null)

const noInventoryData = ref<NoInventoryResponse | null>(null)
const changeListData = ref<ChangeListDetailResponse | null>(null)
const loadingNoInventory = ref(false)
const loadingChangeList = ref(false)

const loadPreview = async () => {
  if (!store.jobId) {
    ElMessage.warning('当前没有可预览的任务，请先在上传页生成 Testplan')
    return
  }
  try {
    await store.fetchPreview()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

const loadNoInventory = async () => {
  if (!store.jobId) return
  try {
    loadingNoInventory.value = true
    noInventoryData.value = await getNoInventoryDetail(store.jobId)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loadingNoInventory.value = false
  }
}

const loadChangeList = async () => {
  if (!store.jobId) return
  try {
    loadingChangeList.value = true
    changeListData.value = await getChangeListDetail(store.jobId)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loadingChangeList.value = false
  }
}

const handleTabChange = async (tabName: string | number) => {
  if (tabName === 'noInventory' && !noInventoryData.value) {
    await loadNoInventory()
  }
  if (tabName === 'changeList' && !changeListData.value) {
    await loadChangeList()
  }
}

const handleDownloadExcel = async () => {
  try {
    await store.downloadExcel()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

const handleDownloadChangeList = async (fmt: 'csv' | 'txt') => {
  try {
    await store.downloadChangeListReport(fmt)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

const openEditDialog = (row: TestplanPreviewRow) => {
  editingRow.value = row
  editDialogVisible.value = true
}

const handleSubmitEdit = async (payload: { pn: string; os_name: string; fw_result?: string; driver_result?: string }) => {
  try {
    await store.editRow({
      job_id: store.jobId,
      pn: payload.pn,
      os_name: payload.os_name,
      fw_result: payload.fw_result,
      driver_result: payload.driver_result,
    })
    ElMessage.success('保存成功')
    editDialogVisible.value = false
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

onMounted(async () => {
  if (!store.previewData && store.jobId) {
    await loadPreview()
  }
})
</script>

<style scoped>
.mb-16 { margin-bottom: 16px; }
.header-line { display: flex; align-items: center; justify-content: space-between; }
</style>
