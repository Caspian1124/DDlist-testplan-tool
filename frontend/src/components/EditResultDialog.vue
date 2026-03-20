<template>
  <el-dialog :model-value="visible" title="编辑 FW/Driver Result" width="520px" @update:model-value="handleVisibleChange">
    <el-form label-width="120px">
      <el-form-item label="PN"><el-input :model-value="row?.pn || ''" disabled /></el-form-item>
      <el-form-item label="OS">
        <el-select v-model="form.os_name" placeholder="请选择 OS">
          <el-option v-for="osName in osOptions" :key="osName" :label="osName" :value="osName" />
        </el-select>
      </el-form-item>
      <el-form-item label="FW Result">
        <el-select v-model="form.fw_result" placeholder="请选择 FW Result">
          <el-option label="Y" value="Y" />
          <el-option label="PASS" value="PASS" />
          <el-option label="FAIL" value="FAIL" />
          <el-option label="BLOCK" value="BLOCK" />
        </el-select>
      </el-form-item>
      <el-form-item label="Driver Result">
        <el-select v-model="form.driver_result" placeholder="请选择 Driver Result">
          <el-option label="Y" value="Y" />
          <el-option label="PASS" value="PASS" />
          <el-option label="FAIL" value="FAIL" />
          <el-option label="BLOCK" value="BLOCK" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleVisibleChange(false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import type { TestplanPreviewRow } from '@/api/api'
import type { EditDialogSubmitPayload } from '@/types/testplan-ui'

const props = defineProps<{ visible: boolean; row: TestplanPreviewRow | null; loading?: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void
  (e: 'submit', payload: EditDialogSubmitPayload): void
}>()

const form = reactive({ os_name: '', fw_result: 'Y', driver_result: 'Y' })

const osOptions = computed(() => (props.row ? Object.keys(props.row.os_cells || {}) : []))

watch(
  () => props.row,
  (row) => {
    if (!row) return
    const firstOs = Object.keys(row.os_cells || {})[0] || ''
    form.os_name = firstOs
    form.fw_result = row.os_cells?.[firstOs]?.fw_result || 'Y'
    form.driver_result = row.os_cells?.[firstOs]?.driver_result || 'Y'
  },
  { immediate: true }
)

watch(
  () => form.os_name,
  (osName) => {
    if (!props.row || !osName) return
    form.fw_result = props.row.os_cells?.[osName]?.fw_result || 'Y'
    form.driver_result = props.row.os_cells?.[osName]?.driver_result || 'Y'
  }
)

const handleVisibleChange = (visible: boolean) => emit('update:visible', visible)

const handleSubmit = () => {
  if (!props.row) return
  emit('submit', {
    pn: props.row.pn,
    os_name: form.os_name,
    fw_result: form.fw_result,
    driver_result: form.driver_result,
  })
}
</script>
