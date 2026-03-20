<template>
  <div class="testplan-table">
    <el-table :data="pagedRows" border stripe height="560" :loading="loading">
      <el-table-column prop="pn" label="PN" width="160" fixed="left" />
      <el-table-column prop="part_type" label="Type" width="100" />
      <el-table-column prop="normalized_vendor" label="Vendor" width="140" />
      <el-table-column prop="normalized_model" label="Model" min-width="220" />

      <el-table-column label="OS 结果" min-width="460">
        <template #default="{ row }">
          <div class="os-cell-list">
            <div v-for="(cell, osName) in row.os_cells" :key="osName" class="os-cell-item">
              <div class="os-name">{{ osName }}</div>
              <div class="os-detail">
                <span>FW: {{ cell.fw_result || '-' }}</span>
                <span>Driver: {{ cell.driver_result || '-' }}</span>
                <span>Selected: {{ cell.selected_for_test ? 'Y' : 'N' }}</span>
              </div>
            </div>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="$emit('edit', row)">编辑结果</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="pageNo"
        v-model:page-size="pageSize"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[10, 20, 50]"
        :total="rows.length"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TestplanPreviewRow } from '@/api/api'

const props = defineProps<{ rows: TestplanPreviewRow[]; loading?: boolean }>()
defineEmits<{ (e: 'edit', row: TestplanPreviewRow): void }>()

const pageNo = ref(1)
const pageSize = ref(10)

const pagedRows = computed(() => {
  const data = props.rows || []
  const start = (pageNo.value - 1) * pageSize.value
  const end = start + pageSize.value
  return data.slice(start, end)
})
</script>

<style scoped>
.testplan-table { width: 100%; }
.pager { display: flex; justify-content: flex-end; margin-top: 16px; }
os-cell-list { display: flex; flex-direction: column; gap: 8px; }
.os-cell-list { display: flex; flex-direction: column; gap: 8px; }
.os-cell-item { padding: 8px; border: 1px solid #ebeef5; border-radius: 6px; background: #fafafa; }
.os-name { font-weight: 600; margin-bottom: 4px; }
.os-detail { display: flex; gap: 12px; flex-wrap: wrap; color: #606266; }
</style>
