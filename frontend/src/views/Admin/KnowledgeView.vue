<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  buildKnowledgeChunks,
  deleteKnowledgeDocument,
  indexKnowledgeDocument,
  listKnowledgeDocuments,
  parseKnowledgePreview,
  uploadKnowledgeDocument,
} from '../../api/knowledge'
import type { KnowledgeDocument, ParsedDocument } from '../../types/knowledge'

const documents = ref<KnowledgeDocument[]>([])
const selectedFile = ref<File | null>(null)
const selectedDocType = ref('upload')
const preview = ref<ParsedDocument | null>(null)
const loading = ref(false)

const docTypeOptions = [
  { value: 'upload', label: '讲解词' },
  { value: 'historical', label: '文史资料' },
  { value: 'faq', label: '常见问题' },
  { value: 'other', label: '其他' },
]

const docTypeLabelMap: Record<string, string> = {
  upload: '讲解词',
  historical: '文史资料',
  faq: '常见问题',
  other: '其他',
}

function getDocTypeLabel(sourceType: string) {
  return docTypeLabelMap[sourceType] || sourceType
}

onMounted(() => {
  refreshDocuments()
})

async function refreshDocuments() {
  documents.value = await listKnowledgeDocuments()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] || null
}

async function handleUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  loading.value = true
  try {
    await uploadKnowledgeDocument(selectedFile.value, selectedDocType.value)
    ElMessage.success('上传成功')
    selectedFile.value = null
    await refreshDocuments()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传失败')
  } finally {
    loading.value = false
  }
}

async function handlePreview(document: KnowledgeDocument) {
  loading.value = true
  try {
    preview.value = await parseKnowledgePreview(document.id)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '解析失败')
  } finally {
    loading.value = false
  }
}

async function handleChunk(document: KnowledgeDocument) {
  loading.value = true
  try {
    const result = await buildKnowledgeChunks(document.id)
    ElMessage.success(`已生成 ${result.chunk_count} 个知识块`)
    await refreshDocuments()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '分块失败')
  } finally {
    loading.value = false
  }
}

async function handleIndex(document: KnowledgeDocument) {
  loading.value = true
  try {
    const result = await indexKnowledgeDocument(document.id)
    ElMessage.success(`已索引 ${result.indexed_count} 个知识块`)
    await refreshDocuments()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '索引失败')
  } finally {
    loading.value = false
  }
}

async function handleProcessAll(document: KnowledgeDocument) {
  loading.value = true
  try {
    preview.value = await parseKnowledgePreview(document.id)
    const chunks = await buildKnowledgeChunks(document.id)
    const result = await indexKnowledgeDocument(document.id)
    ElMessage.success(`处理完成：${chunks.chunk_count} 个知识块，已索引 ${result.indexed_count} 个`)
    await refreshDocuments()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '一键处理失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(document: KnowledgeDocument) {
  loading.value = true
  try {
    await deleteKnowledgeDocument(document.id)
    if (preview.value?.title === document.title) preview.value = null
    ElMessage.success('已删除文档')
    await refreshDocuments()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  } finally {
    loading.value = false
  }
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}
</script>

<template>
  <main class="admin-page">
    <header class="header">
      <div>
        <p class="eyebrow">管理后台</p>
        <h1>知识库管理</h1>
        <p>上传景区资料，解析预览后生成知识块并构建向量索引。</p>
      </div>
      <nav>
        <RouterLink to="/chat">游客对话</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <section class="grid">
      <div class="panel upload-panel">
        <h2>上传资料</h2>
        <label class="doc-type-label">
          文档类型
          <select v-model="selectedDocType" class="doc-type-select">
            <option v-for="opt in docTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </label>
        <input
          type="file"
          accept=".txt,.md,.csv,.tsv,.docx,.xlsx,.pdf"
          @change="handleFileChange"
        />
        <p v-if="selectedFile">已选择：{{ selectedFile.name }}</p>
        <button :disabled="loading" @click="handleUpload">上传</button>
      </div>

      <div class="panel list-panel">
        <div class="panel-title">
          <h2>文档列表</h2>
          <button class="ghost" @click="refreshDocuments">刷新</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>标题</th>
              <th>类型</th>
              <th>状态</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="document in documents" :key="document.id">
              <td>{{ document.id }}</td>
              <td>{{ document.title }}</td>
              <td>{{ getDocTypeLabel(document.source_type) }}</td>
              <td>{{ document.status }}</td>
              <td>{{ formatTime(document.updated_at || document.created_at) }}</td>
              <td class="actions">
                <button class="primary-action" @click="handleProcessAll(document)">一键处理</button>
                <button @click="handlePreview(document)">预览</button>
                <button @click="handleChunk(document)">分块</button>
                <button @click="handleIndex(document)">索引</button>
                <button class="danger" @click="handleDelete(document)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!documents.length" class="empty">暂无文档</p>
      </div>
    </section>

    <section v-if="preview" class="panel preview-panel">
      <h2>解析预览：{{ preview.title }}</h2>
      <p>{{ preview.file_type }} · {{ preview.section_count }} 个章节 · {{ preview.char_count }} 字符</p>
      <article v-for="section in preview.sections" :key="section.title" class="section-card">
        <h3>{{ section.title }}</h3>
        <p>{{ section.content_preview }}</p>
      </article>
    </section>
  </main>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  padding: 24px;
  background: #f6f7fb;
  color: #1f2937;
}

.header {
  max-width: 1180px;
  margin: 0 auto 24px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #8b5e34;
  font-weight: 700;
}

h1,
h2,
h3 {
  margin-top: 0;
}

.header p {
  color: #667085;
}

nav {
  display: flex;
  gap: 14px;
}

nav a {
  color: #8b5e34;
  text-decoration: none;
}

.grid {
  max-width: 1180px;
  margin: 0 auto 20px;
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
}

.panel {
  background: #ffffff;
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 14px 36px rgb(15 23 42 / 8%);
}

.upload-panel {
  align-self: start;
  display: grid;
  gap: 14px;
}

.doc-type-label {
  display: grid;
  gap: 6px;
  font-size: 14px;
  color: #475467;
}

.doc-type-select {
  border: 1px solid #d0d5dd;
  border-radius: 10px;
  padding: 9px 10px;
  font: inherit;
}

button {
  min-height: 34px;
  border: 0;
  border-radius: 10px;
  background: #8b5e34;
  color: #ffffff;
  padding: 0 12px;
  cursor: pointer;
}

button:disabled {
  background: #cbd5e1;
}

.ghost {
  background: #f3eadf;
  color: #8b5e34;
}

.primary-action {
  background: #b45309;
}

.danger {
  background: #b42318;
}

.panel-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  border-bottom: 1px solid #e5e7eb;
  padding: 10px;
  text-align: left;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.empty {
  color: #667085;
}

.preview-panel {
  max-width: 1180px;
  margin: 0 auto;
}

.section-card {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 14px;
  margin-top: 12px;
}

.section-card p {
  color: #475467;
  line-height: 1.7;
}

@media (max-width: 900px) {
  .header,
  .grid {
    display: block;
  }

  .upload-panel {
    margin-bottom: 16px;
  }
}
</style>
