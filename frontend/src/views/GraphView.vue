<template>
  <div class="page-card">
    <div class="toolbar">
      <el-select v-model="kbId" placeholder="选择知识库" style="width: 220px" @change="load">
        <el-option v-for="k in kbs" :key="k.id" :label="k.name" :value="k.id" />
      </el-select>
      <el-button type="primary" :disabled="!kbId" @click="load">加载图谱</el-button>
      <el-button type="success" :disabled="!kbId" @click="addEntityDialog = true">新增实体</el-button>
      <el-button type="warning" :disabled="!kbId" @click="addRelationDialog = true">新增关系</el-button>
    </div>

    <el-row :gutter="12">
      <el-col :span="17">
        <div ref="container" style="height: calc(100vh - 180px); border: 1px solid #eee"></div>
      </el-col>
      <el-col :span="7">
        <el-card shadow="never" header="选中节点 / 详情">
          <template v-if="selected">
            <el-form label-width="70px" size="small">
              <el-form-item label="名称"><el-input v-model="selected.name" /></el-form-item>
              <el-form-item label="类型"><el-input v-model="selected.type" /></el-form-item>
              <el-form-item label="已确认">
                <el-tooltip
                  content="人工核对无误后打开：已确认的实体/关系（绿色）在检索结果中权重更高，回答优先引用；未确认的为蓝色。不影响权限范围。"
                  placement="top"
                >
                  <el-switch v-model="selected.verified" />
                </el-tooltip>
              </el-form-item>
            </el-form>
            <div v-if="relatedChunk" style="margin-top: 8px">
              <el-divider content-position="left">关联原文</el-divider>
              <div style="font-size: 12px; color: #666; max-height: 200px; overflow: auto; white-space: pre-wrap">
                {{ relatedChunk.content }}
              </div>
            </div>
            <div style="margin-top: 12px">
              <el-button type="primary" size="small" @click="saveEntity">保存</el-button>
              <el-button type="warning" size="small" @click="mergeDialog = true">合并到…</el-button>
              <el-button type="danger" size="small" @click="deleteEntity">删除实体</el-button>
            </div>
          </template>
          <el-empty v-else description="点击图上的节点查看/编辑" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="mergeDialog" title="合并实体" width="420px">
      <p style="font-size: 13px; color: #666">
        将「{{ selected?.name }}」合并到目标实体（其关系将改指目标实体，属性合并）。
      </p>
      <el-select v-model="mergeTargetId" filterable placeholder="选择目标实体" style="width: 100%">
        <el-option v-for="e in entities.filter((x) => x.id !== selected?.id)" :key="e.id"
                   :label="e.name + '（' + e.type + '）'" :value="e.id" />
      </el-select>
      <template #footer>
        <el-button @click="mergeDialog = false">取消</el-button>
        <el-button type="warning" :disabled="!mergeTargetId" @click="doMerge">合并</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addEntityDialog" title="新增实体" width="420px">
      <el-form label-width="70px">
        <el-form-item label="名称"><el-input v-model="newEntity.name" /></el-form-item>
        <el-form-item label="类型"><el-input v-model="newEntity.type" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addEntityDialog = false">取消</el-button>
        <el-button type="primary" @click="createEntity">添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addRelationDialog" title="新增关系" width="480px">
      <el-form label-width="80px">
        <el-form-item label="起点实体">
          <el-select v-model="newRelation.source_entity_id" filterable style="width: 100%">
            <el-option v-for="e in entities" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="终点实体">
          <el-select v-model="newRelation.target_entity_id" filterable style="width: 100%">
            <el-option v-for="e in entities" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关系类型"><el-input v-model="newRelation.relation_type" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addRelationDialog = false">取消</el-button>
        <el-button type="primary" @click="createRelation">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import client from '../api/client'
import type { ChunkItem, EntityItem, KB, RelationItem } from '../api/types'

const route = useRoute()
const kbs = ref<KB[]>([])
const kbId = ref<number | undefined>(route.query.kb ? Number(route.query.kb) : undefined)
const container = ref<HTMLElement>()
const entities = ref<EntityItem[]>([])
const relations = ref<RelationItem[]>([])
const selected = ref<EntityItem | null>(null)
const relatedChunk = ref<ChunkItem | null>(null)
const addEntityDialog = ref(false)
const addRelationDialog = ref(false)
const mergeDialog = ref(false)
const mergeTargetId = ref('')
const newEntity = reactive({ name: '', type: '术语' })
const newRelation = reactive({ source_entity_id: '', target_entity_id: '', relation_type: '' })

let graph: any = null

async function load() {
  if (!kbId.value) return
  const [eRes, rRes] = await Promise.all([
    client.get(`/admin/kbs/${kbId.value}/entities`, { params: { limit: 500 } }),
    client.get(`/admin/kbs/${kbId.value}/relations`, { params: { limit: 500 } }),
  ])
  entities.value = eRes.data.items
  relations.value = rRes.data.items
  renderGraph()
}

function renderGraph() {
  if (!container.value) return
  if (graph) {
    graph.destroy()
    graph = null
  }
  const nodes = entities.value.map((e) => ({
    id: e.id,
    label: e.name,
    type: e.type,
    style: { fill: e.verified ? '#67c23a' : '#409eff', stroke: '#333' },
    size: 26,
  }))
  const edges = relations.value.map((r) => ({
    source: r.source_entity_id,
    target: r.target_entity_id,
    label: r.relation_type,
    style: { endArrow: true },
  }))
  import('@antv/g6').then(({ default: G6 }: any) => {
    graph = new G6.Graph({
      container: container.value!,
      width: container.value!.clientWidth,
      height: container.value!.clientHeight,
      fitView: true,
      modes: { default: ['drag-canvas', 'zoom-canvas', 'drag-node'] },
      layout: { type: 'force', preventOverlap: true, linkDistance: 120 },
      defaultNode: { type: 'circle', labelCfg: { style: { fontSize: 11 } } },
      defaultEdge: { labelCfg: { autoRotate: true, style: { fontSize: 9 } } },
      data: { nodes, edges },
    })
    graph.on('node:click', (evt: any) => {
      const model = evt.item.getModel()
      selected.value = entities.value.find((e) => e.id === model.id) || null
      loadRelatedChunk()
    })
    graph.render()
  })
}

async function loadRelatedChunk() {
  relatedChunk.value = null
  if (!selected.value?.source_chunk_id) return
  const { data } = await client.get(`/admin/chunks/${selected.value.source_chunk_id}`)
  relatedChunk.value = data
}

async function saveEntity() {
  if (!selected.value) return
  await client.patch(`/admin/entities/${selected.value.id}`, {
    name: selected.value.name,
    type: selected.value.type,
    verified: selected.value.verified,
  })
  ElMessage.success('已保存')
  load()
}

async function deleteEntity() {
  if (!selected.value) return
  await ElMessageBox.confirm(`删除实体「${selected.value.name}」？关联关系将一并删除。`, '警告', { type: 'warning' })
  await client.delete(`/admin/entities/${selected.value.id}`)
  selected.value = null
  ElMessage.success('已删除')
  load()
}

async function doMerge() {
  if (!selected.value || !mergeTargetId.value) return
  await ElMessageBox.confirm(
    `将「${selected.value.name}」合并到目标实体？此操作不可撤销。`, '确认合并', { type: 'warning' },
  )
  await client.post('/admin/entities/merge', {
    source_id: selected.value.id, target_id: mergeTargetId.value,
  })
  ElMessage.success('已合并')
  mergeDialog.value = false
  mergeTargetId.value = ''
  selected.value = null
  load()
}

async function createEntity() {
  if (!newEntity.name) return
  await client.post(`/admin/kbs/${kbId.value}/entities`, { ...newEntity })
  ElMessage.success('已添加')
  addEntityDialog.value = false
  newEntity.name = ''
  load()
}

async function createRelation() {
  if (!newRelation.source_entity_id || !newRelation.target_entity_id || !newRelation.relation_type) return
  await client.post(`/admin/kbs/${kbId.value}/relations`, { ...newRelation })
  ElMessage.success('已添加')
  addRelationDialog.value = false
  newRelation.source_entity_id = ''
  newRelation.target_entity_id = ''
  newRelation.relation_type = ''
  load()
}

onMounted(async () => {
  const { data } = await client.get('/admin/kbs')
  kbs.value = data
  await load()
})

onBeforeUnmount(() => {
  if (graph) {
    graph.destroy()
    graph = null
  }
})
</script>
