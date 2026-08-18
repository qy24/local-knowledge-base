<template>
  <div class="page-card" style="max-width: 1000px">
    <el-card shadow="never" header="云端大模型（OpenAI 兼容）">
      <el-form label-width="200px">
        <el-form-item label="Embedding 模式">
          <el-select v-model="form.embedding_mode">
            <el-option label="openai（云端兼容 API）" value="openai" />
            <el-option label="dummy（离线开发占位）" value="dummy" />
          </el-select>
        </el-form-item>
        <el-form-item label="Embedding Base URL">
          <el-input v-model="form.embedding_base_url" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="Embedding 模型">
          <el-input v-model="form.embedding_model" placeholder="text-embedding-3-small" />
        </el-form-item>
        <el-form-item label="Embedding API Key">
          <el-input v-model="form.embedding_api_key" type="password" show-password
                    :placeholder="masked.embedding_api_key_masked || 'sk-...'" />
        </el-form-item>
        <el-divider />
        <el-form-item label="大模型 Base URL">
          <el-input v-model="form.llm_base_url" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="大模型名称">
          <el-input v-model="form.llm_model" placeholder="gpt-4o-mini / deepseek-chat" />
        </el-form-item>
        <el-form-item label="大模型 API Key">
          <el-input v-model="form.llm_api_key" type="password" show-password
                    :placeholder="masked.llm_api_key_masked || 'sk-...'" />
        </el-form-item>
        <el-form-item label="图谱抽取">
          <el-switch v-model="form.graph_extraction_enabled" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save">保存设置</el-button>
          <span style="color: #909399; font-size: 12px; margin-left: 12px">
            密钥留空则保持原值；知识库也可单独配置自己的大模型
          </span>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const form = reactive({
  embedding_mode: 'openai', embedding_base_url: '', embedding_model: '',
  embedding_api_key: '', llm_base_url: '', llm_model: '', llm_api_key: '',
  graph_extraction_enabled: true,
})
const masked = ref<any>({})

async function load() {
  const { data } = await client.get('/admin/settings')
  masked.value = data
  form.embedding_mode = data.embedding_mode
  form.embedding_base_url = data.embedding_base_url
  form.embedding_model = data.embedding_model
  form.llm_base_url = data.llm_base_url
  form.llm_model = data.llm_model
  form.graph_extraction_enabled = data.graph_extraction_enabled
  form.embedding_api_key = ''
  form.llm_api_key = ''
}

async function save() {
  const body: any = { ...form }
  if (!body.embedding_api_key) delete body.embedding_api_key
  if (!body.llm_api_key) delete body.llm_api_key
  await client.put('/admin/settings', body)
  ElMessage.success('已保存')
  load()
}

onMounted(load)
</script>
