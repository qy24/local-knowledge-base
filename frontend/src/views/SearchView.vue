<template>
  <div class="page-card">
    <div class="toolbar">
      <el-select v-model="kbId" placeholder="选择知识库" style="width: 200px">
        <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
      </el-select>
      <el-input v-model="query" placeholder="输入查询，验证向量+图谱混合检索" style="width: 360px" @keyup.enter="run" />
      <el-input-number v-model="topK" :min="1" :max="50" />
      <el-switch v-model="enableGraph" active-text="图谱检索" />
      <el-button type="primary" :disabled="!kbId || !query" @click="run">检 索</el-button>
    </div>

    <el-alert v-if="result" type="info" :closable="false" style="margin-bottom: 12px"
              :title="`实际生效范围: 知识库 #${result.permission_scope.kb_ids.join(', ')}；图谱命中实体 ${result.graph.entities.length} 个 / 关系 ${result.graph.relations.length} 条`" />

    <el-table v-if="result" :data="result.chunks" border size="small">
      <el-table-column prop="source" label="来源" width="90">
        <template #default="{ row }">
          <el-tag :type="row.source === 'graph' ? 'success' : 'primary'" size="small">{{ row.source }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="score" label="分数" width="80" />
      <el-table-column label="来源文档" width="140">
        <template #default="{ row }">{{ result.kb_names?.[row.kb_id] }} / {{ row.metadata?.page ?? '' }}</template>
      </el-table-column>
      <el-table-column prop="content" label="内容" min-width="400" show-overflow-tooltip />
    </el-table>
    <el-empty v-else description="输入问题开始检索调试" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import client from '../api/client'
import type { KB, SearchResult } from '../api/types'

const kbs = ref<KB[]>([])
const kbId = ref<number>()
const query = ref('')
const topK = ref(8)
const enableGraph = ref(true)
const result = ref<SearchResult | null>(null)

async function run() {
  if (!kbId.value || !query.value) return
  const { data } = await client.post(`/admin/kbs/${kbId.value}/debug-search`, {
    query: query.value, top_k: topK.value, graph_depth: 1, enable_graph: enableGraph.value,
  })
  result.value = data
}

onMounted(async () => {
  const { data } = await client.get('/admin/kbs')
  kbs.value = data
  if (kbs.value.length) kbId.value = kbs.value[0].id
})
</script>
