<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header"><span>DDlist 测试编排工具 - 文件上传</span></div>
      </template>

      <el-form label-width="120px" class="upload-form">
        <el-form-item label="项目名称">
          <el-input v-model="projectName" placeholder="例如：WR5215G5" clearable />
        </el-form-item>

        <el-form-item label="DDlist 文件">
          <UploadPanel mode="ddlist" title="DDlist 文件" />
        </el-form-item>

        <el-form-item label="库存文件（可选）">
          <UploadPanel mode="inventory" title="库存文件" />
        </el-form-item>

        <el-form-item label="生成 Testplan">
          <el-button type="success" :loading="store.generating" :disabled="!store.canGenerate" @click="handleGenerate">生成 Testplan</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="store.ddlistUploadResult" class="mt-16">
      <template #header><span>DDlist 预览（前 10 行）</span></template>
      <el-table :data="store.ddlistUploadResult.preview_parts" border stripe height="300">
        <el-table-column prop="part_type" label="Type" width="100" />
        <el-table-column prop="pn" label="PN" width="140" />
        <el-table-column prop="supplier_pn" label="Supplier PN" width="200" />
        <el-table-column prop="l2_description" label="L2 Description" min-width="320" />
        <el-table-column prop="supplier" label="Supplier" width="120" />
        <el-table-column prop="remark" label="Remark" width="120" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import UploadPanel from '@/components/UploadPanel.vue'
import { useTestplanStore } from '@/stores/testplan'
import { getErrorMessage } from '@/utils/error'

const router = useRouter()
const store = useTestplanStore()

const projectName = computed({
  get: () => store.projectName,
  set: (val: string) => store.setProjectName(val),
})

const handleGenerate = async () => {
  try {
    await store.generate('20260320')
    ElMessage.success('Testplan 生成成功')
    router.push('/testplan')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

const handleReset = () => {
  store.clearAll()
  ElMessage.success('已重置状态')
}
</script>

<style scoped>
.card-header { display: flex; align-items: center; justify-content: space-between; }
.upload-form { max-width: 1000px; }
.mt-16 { margin-top: 16px; }
</style>
