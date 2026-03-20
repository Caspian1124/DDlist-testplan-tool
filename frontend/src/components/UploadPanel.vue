<template>
  <div class="upload-panel">
    <el-upload
      drag
      :auto-upload="false"
      :show-file-list="true"
      :limit="1"
      :accept="accept"
      :on-change="handleFileChange"
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">拖拽文件到这里，或 <em>点击选择文件</em></div>
      <template #tip>
        <div class="el-upload__tip">{{ tipText }}</div>
      </template>
    </el-upload>

    <div class="action-line">
      <el-button type="primary" :loading="uploading" :disabled="!selectedFile" @click="handleUpload">
        {{ buttonText }}
      </el-button>
      <span v-if="progress > 0">上传进度：{{ progress }}%</span>
    </div>

    <el-alert v-if="uploadSuccessText" type="success" :closable="false" show-icon class="mt-12">
      <template #default>
        <div>{{ uploadSuccessText }}</div>
      </template>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useTestplanStore } from '@/stores/testplan'
import type { UploadMode } from '@/types/testplan-ui'
import { getErrorMessage } from '@/utils/error'

const props = defineProps<{ mode: UploadMode; title: string; tip?: string }>()
const emit = defineEmits<{ (e: 'uploaded'): void }>()

const store = useTestplanStore()
const selectedFile = ref<File | null>(null)
const progress = ref(0)

const uploading = computed(() => (props.mode === 'ddlist' ? store.ddlistUploading : store.inventoryUploading))
const accept = computed(() => (props.mode === 'ddlist' ? '.xlsx' : '.xlsx,.csv'))
const buttonText = computed(() => (props.mode === 'ddlist' ? '上传 DDlist' : '上传库存'))
const tipText = computed(() => props.tip || (props.mode === 'ddlist' ? '仅支持 .xlsx，建议上传 WR5215 G5_DDlist_ V1.0 .xlsx' : '支持 .xlsx / .csv'))
const uploadSuccessText = computed(() => {
  if (props.mode === 'ddlist' && store.ddlistUploadResult) return `DDlist 上传成功，file_id：${store.ddlistUploadResult.file_id}`
  if (props.mode === 'inventory' && store.inventoryUploadResult) return `库存文件上传成功，file_id：${store.inventoryUploadResult.file_id}`
  return ''
})

const handleFileChange = (file: UploadFile) => {
  selectedFile.value = file.raw || null
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  try {
    progress.value = 0
    if (props.mode === 'ddlist') {
      await store.uploadDdlist(selectedFile.value, (evt) => {
        if (!evt.total) return
        progress.value = Math.round((evt.loaded / evt.total) * 100)
      })
      ElMessage.success('DDlist 上传成功')
    } else {
      await store.uploadInventory(selectedFile.value, (evt) => {
        if (!evt.total) return
        progress.value = Math.round((evt.loaded / evt.total) * 100)
      })
      ElMessage.success('库存文件上传成功')
    }
    emit('uploaded')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}
</script>

<style scoped>
.upload-panel { width: 100%; }
.action-line { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
.mt-12 { margin-top: 12px; }
</style>
