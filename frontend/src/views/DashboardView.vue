<template>
  <div class="page-card">
    <el-row :gutter="12">
      <el-col :span="4" v-for="s in stats" :key="s.label">
        <el-card shadow="hover">
          <div style="font-size: 26px; font-weight: 700">{{ s.value }}</div>
          <div style="color: #909399; font-size: 13px">{{ s.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="12">
        <el-card shadow="never" header="文档处理状态">
          <el-table :data="statusRows" size="small">
            <el-table-column prop="status" label="状态" />
            <el-table-column prop="count" label="数量" width="120" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="最近任务">
          <el-table :data="tasks" size="small">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="type" label="类型" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'done' ? 'success' : row.status === 'error' ? 'danger' : 'warning'" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="80" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import client from '../api/client'
import type { Dashboard } from '../api/types'

const data = ref<Dashboard>({
  kb_count: 0, doc_count: 0, chunk_count: 0, vector_count: 0,
  entity_count: 0, relation_count: 0, doc_status: {}, pending_tasks: 0,
})
const tasks = ref<any[]>([])

const stats = computed(() => [
  { label: '知识库', value: data.value.kb_count },
  { label: '文档', value: data.value.doc_count },
  { label: '切分块', value: data.value.chunk_count },
  { label: '向量', value: data.value.vector_count },
  { label: '实体', value: data.value.entity_count },
  { label: '关系', value: data.value.relation_count },
])

const statusRows = computed(() =>
  Object.entries(data.value.doc_status || {}).map(([status, count]) => ({ status, count })),
)

async function load() {
  const { data: d } = await client.get('/admin/dashboard')
  data.value = d
  const { data: t } = await client.get('/admin/tasks', { params: { limit: 10 } })
  tasks.value = t
}

onMounted(() => {
  load()
  setInterval(load, 5000)
})
</script>
