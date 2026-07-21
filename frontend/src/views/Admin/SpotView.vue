<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createSpot, deleteSpot, listSpots, updateSpot } from '../../api/spot'
import type { ScenicSpot, ScenicSpotPayload } from '../../types/spot'

const spots = ref<ScenicSpot[]>([])
const keyword = ref('')
const editingId = ref<number | null>(null)
const form = reactive<ScenicSpotPayload>({
  code: '',
  name: '',
  scenic_area: '灵山胜境',
  location: '',
  category: '',
  parameters: '',
  core_function: '',
  cultural_meaning: '',
  description: '',
  highlights: '',
  open_info: '',
  remarks: '',
  recommended_duration_minutes: 30,
  latitude: null,
  longitude: null,
})

onMounted(refresh)

async function refresh() {
  spots.value = await listSpots(keyword.value)
}

function edit(spot: ScenicSpot) {
  editingId.value = spot.id
  Object.assign(form, {
    code: spot.code,
    name: spot.name,
    scenic_area: spot.scenic_area,
    location: spot.location || '',
    category: spot.category || '',
    parameters: spot.parameters || '',
    core_function: spot.core_function || '',
    cultural_meaning: spot.cultural_meaning || '',
    description: spot.description || '',
    highlights: spot.highlights || '',
    open_info: spot.open_info || '',
    remarks: spot.remarks || '',
    recommended_duration_minutes: spot.recommended_duration_minutes || 30,
    latitude: spot.latitude,
    longitude: spot.longitude,
  })
}

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    code: '',
    name: '',
    scenic_area: '灵山胜境',
    location: '',
    category: '',
    parameters: '',
    core_function: '',
    cultural_meaning: '',
    description: '',
    highlights: '',
    open_info: '',
    remarks: '',
    recommended_duration_minutes: 30,
    latitude: null,
    longitude: null,
  })
}

async function submit() {
  if (!form.code || !form.name) {
    ElMessage.warning('景点 ID 和名称必填')
    return
  }
  try {
    if (editingId.value) {
      await updateSpot(editingId.value, form)
      ElMessage.success('景点已更新')
    } else {
      await createSpot(form)
      ElMessage.success('景点已创建')
    }
    resetForm()
    await refresh()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  }
}

async function remove(spot: ScenicSpot) {
  try {
    await deleteSpot(spot.id)
    ElMessage.success('景点已删除')
    await refresh()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '删除失败')
  }
}
</script>

<template>
  <main class="admin-page">
    <header class="header">
      <div>
        <p class="eyebrow">管理后台</p>
        <h1>景点管理</h1>
        <p>维护景点结构化信息，支撑问答、路线推荐和知识库关联。</p>
      </div>
      <nav>
        <RouterLink to="/admin/knowledge">知识库</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <section class="grid">
      <form class="panel form" @submit.prevent="submit">
        <h2>{{ editingId ? '编辑景点' : '新增景点' }}</h2>
        <input v-model="form.code" placeholder="景点ID，如 LS-001" :disabled="Boolean(editingId)" />
        <input v-model="form.name" placeholder="景点名称" />
        <input v-model="form.category" placeholder="分类，如 佛教文化" />
        <input v-model.number="form.recommended_duration_minutes" type="number" placeholder="建议停留分钟" />
        <input v-model.number="form.latitude" type="number" step="0.000001" placeholder="纬度，可选" />
        <input v-model.number="form.longitude" type="number" step="0.000001" placeholder="经度，可选" />
        <textarea v-model="form.location" rows="2" placeholder="具体位置" />
        <textarea v-model="form.description" rows="4" placeholder="详细介绍" />
        <textarea v-model="form.highlights" rows="3" placeholder="游玩亮点" />
        <textarea v-model="form.open_info" rows="2" placeholder="开放/演艺信息" />
        <div class="actions">
          <button type="submit">{{ editingId ? '保存修改' : '新增景点' }}</button>
          <button class="ghost" type="button" @click="resetForm">重置</button>
        </div>
      </form>

      <section class="panel">
        <div class="toolbar">
          <input v-model="keyword" placeholder="搜索景点名称或ID" @keyup.enter="refresh" />
          <button @click="refresh">搜索</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>景点</th>
              <th>分类</th>
              <th>停留</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="spot in spots" :key="spot.id">
              <td>{{ spot.code }}</td>
              <td>{{ spot.name }}</td>
              <td>{{ spot.category || '-' }}</td>
              <td>{{ spot.recommended_duration_minutes || '-' }} 分钟</td>
              <td class="row-actions">
                <button @click="edit(spot)">编辑</button>
                <button class="danger" @click="remove(spot)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
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

.header,
.grid {
  max-width: 1180px;
  margin: 0 auto 24px;
}

.header {
  display: flex;
  justify-content: space-between;
}

.eyebrow {
  color: #8b5e34;
  font-weight: 700;
  margin: 0 0 8px;
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
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 20px;
}

.panel {
  background: #ffffff;
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 14px 36px rgb(15 23 42 / 8%);
}

.form {
  display: grid;
  gap: 10px;
  align-self: start;
}

input,
textarea {
  border: 1px solid #d0d5dd;
  border-radius: 10px;
  padding: 10px;
  font: inherit;
}

.actions,
.toolbar,
.row-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.toolbar {
  margin-bottom: 14px;
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

.ghost {
  background: #f3eadf;
  color: #8b5e34;
}

.danger {
  background: #b42318;
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

@media (max-width: 960px) {
  .header,
  .grid {
    display: block;
  }

  .form {
    margin-bottom: 16px;
  }
}
</style>
