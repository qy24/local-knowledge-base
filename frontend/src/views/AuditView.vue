<template>
  <div class="page-card">
    <div class="toolbar">
      <el-button size="small" @click="load">刷新</el-button>
      <span style="color: #909399; font-size: 12px">共 {{ total }} 条记录</span>
    </div>
    <el-table :data="items" border size="small">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="action" label="动作" width="180" />
      <el-table-column prop="query" label="查询内容" min-width="240" show-overflow-tooltip />
      <el-table-column prop="ip" label="IP" width="130" />
      <el-table-column label="结果摘要" width="160">
        <template #default="{ row }">{{ JSON.stringify(row.result_summary) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="180" />
    </el-table>
    <div style="margin-top: 12px; display: flex; justify-content: flex-end">
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="pageSize"
        v-model:current-page="page"
        @current-change="load"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import client from '../api/client'
import type { AuditItem } from '../api/types'

const items = ref<AuditItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

async function load() {
  const { data } = await client.get('/admin/audit', { params: { limit: pageSize, offset: (page.value - 1) * pageSize } })
  items.value = data.items
  total.value = data.total
}

onMounted(load)
</script>
