<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getFeedbackStats, type FeedbackStats } from '../../api/feedback'
import {
  getVisitorEventStats,
  importVisitorEvents,
  listVisitorEvents,
  type VisitorEvent,
  type VisitorEventImportResult,
  type VisitorEventStats,
} from '../../api/behavior'

const events = ref<VisitorEvent[]>([])
const stats = ref<VisitorEventStats | null>(null)
const feedbackStats = ref<FeedbackStats | null>(null)
const importResult = ref<VisitorEventImportResult | null>(null)
const loading = ref(false)

onMounted(refresh)

async function refresh() {
  const [eventItems, statData, feedbackData] = await Promise.all([listVisitorEvents(), getVisitorEventStats(), getFeedbackStats()])
  events.value = eventItems
  stats.value = statData
  feedbackStats.value = feedbackData
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    loading.value = true
    importResult.value = await importVisitorEvents(file)
    ElMessage.success(`已导入 ${importResult.value.imported_count} 条行为数据`)
    await refresh()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '行为数据导入失败')
  } finally {
    loading.value = false
    input.value = ''
  }
}

const serviceSuggestions = computed(() => {
  const items: string[] = []
  const negative = feedbackStats.value?.sentiment_counts.negative || 0
  const total = feedbackStats.value?.total || 0
  const avg = feedbackStats.value?.average_satisfaction || 0
  if (total === 0) {
    items.push('暂无反馈数据，建议在游客端引导游客完成满意度反馈。')
  }
  if (negative > 0) {
    items.push('存在负向反馈，建议优先查看“需关注反馈”，定位讲解、路线或服务体验问题。')
  }
  if (avg && avg < 70) {
    items.push('满意度偏低，建议补充常见问题答案并优化热门景点讲解词。')
  }
  if ((stats.value?.average_duration_seconds || 0) < 30 && (stats.value?.total || 0) > 0) {
    items.push('平均停留较短，建议在首页和地图页加强路线入口与推荐提示。')
  }
  if (!items.length) {
    items.push('整体反馈稳定，可继续关注热门问题并定期更新知识库。')
  }
  return items
})
</script>

<template>
  <main class="behavior-page">
    <header>
      <div>
        <p class="eyebrow">游客感受度报告</p>
        <h1>游客关注点、情感趋势与服务建议</h1>
      </div>
      <nav>
        <RouterLink to="/dashboard">数据大屏</RouterLink>
        <RouterLink to="/admin/knowledge">知识库后台</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <section class="layout">
      <section class="panel">
        <h2>上传 CSV</h2>
        <p class="hint">
          支持表头：event_type、session_id、spot_id、page_path、source、duration_seconds、occurred_at，也兼容中文表头。
        </p>
        <label class="upload">
          <input type="file" accept=".csv" :disabled="loading" @change="handleFileChange" />
          <span>{{ loading ? '导入中...' : '选择 CSV 文件导入' }}</span>
        </label>

        <article v-if="importResult" class="result">
          <strong>导入 {{ importResult.imported_count }} 条，跳过 {{ importResult.skipped_count }} 条</strong>
          <p v-for="error in importResult.errors" :key="error">{{ error }}</p>
        </article>
      </section>

      <section class="panel stats" v-if="feedbackStats">
        <h2>感受度概览</h2>
        <div class="metric-grid">
          <article>
            <span>反馈总数</span>
            <strong>{{ feedbackStats.total }}</strong>
          </article>
          <article>
            <span>满意度分</span>
            <strong>{{ feedbackStats.average_satisfaction }}</strong>
          </article>
        </div>
        <h3>情感趋势</h3>
        <p class="tag-line">
          <span>正向 {{ feedbackStats.sentiment_counts.positive || 0 }}</span>
          <span>中性 {{ feedbackStats.sentiment_counts.neutral || 0 }}</span>
          <span>负向 {{ feedbackStats.sentiment_counts.negative || 0 }}</span>
        </p>
        <h3>服务建议</h3>
        <ul class="suggestions">
          <li v-for="item in serviceSuggestions" :key="item">{{ item }}</li>
        </ul>
      </section>

      <section class="panel stats" v-if="stats">
        <h2>数据概览</h2>
        <div class="metric-grid">
          <article>
            <span>事件总数</span>
            <strong>{{ stats.total }}</strong>
          </article>
          <article>
            <span>平均停留</span>
            <strong>{{ stats.average_duration_seconds }}s</strong>
          </article>
        </div>
        <h3>事件类型</h3>
        <p class="tag-line">
          <span v-for="(count, type) in stats.event_type_counts" :key="type">{{ type }} {{ count }}</span>
        </p>
        <h3>来源渠道</h3>
        <p class="tag-line">
          <span v-for="(count, source) in stats.source_counts" :key="source">{{ source }} {{ count }}</span>
        </p>
      </section>
    </section>

    <section class="panel events" v-if="feedbackStats?.attention_items.length">
      <div class="section-title">
        <h2>需关注反馈</h2>
        <RouterLink to="/feedback">查看游客反馈页</RouterLink>
      </div>
      <article v-for="item in feedbackStats.attention_items" :key="item.id" class="event-card">
        <strong>#{{ item.id }} · {{ item.sentiment }} · {{ item.satisfaction_score }} 分</strong>
        <p>{{ item.content || '未填写具体内容' }}</p>
        <time>{{ new Date(item.created_at).toLocaleString() }}</time>
      </article>
    </section>

    <section class="panel events">
      <div class="section-title">
        <h2>最近事件</h2>
        <button @click="refresh">刷新</button>
      </div>
      <article v-for="item in events" :key="item.id" class="event-card">
        <strong>{{ item.event_type }} · {{ item.source || 'unknown' }}</strong>
        <p>
          session: {{ item.session_id || '-' }} · spot: {{ item.spot_id || '-' }} · 页面:
          {{ item.page_path || '-' }}
        </p>
        <time>{{ new Date(item.occurred_at).toLocaleString() }}</time>
      </article>
      <p v-if="!events.length" class="hint">暂无行为数据</p>
    </section>
  </main>
</template>

<style scoped>
.behavior-page {
  min-height: 100vh;
  padding: 24px;
  background: #f6f7fb;
  color: #1f2937;
}

header,
.layout,
.events {
  max-width: 1120px;
  margin: 0 auto 20px;
}

header,
.section-title {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.eyebrow,
nav a {
  color: #8b5e34;
  font-weight: 700;
}

nav {
  display: flex;
  gap: 14px;
}

nav a {
  text-decoration: none;
}

.layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.panel {
  background: white;
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 14px 36px rgb(15 23 42 / 8%);
}

.hint,
.event-card p,
.event-card time,
.result p {
  color: #667085;
}

.upload {
  display: inline-flex;
  margin-top: 12px;
  cursor: pointer;
}

.upload input {
  display: none;
}

.upload span,
button {
  border: 0;
  border-radius: 12px;
  background: #8b5e34;
  color: white;
  padding: 10px 14px;
  cursor: pointer;
}

.result,
.event-card,
.metric-grid article {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 12px;
  margin-top: 12px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.metric-grid strong {
  display: block;
  font-size: 28px;
  margin-top: 6px;
}

.tag-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-line span {
  background: #f3f4f6;
  border-radius: 999px;
  padding: 6px 10px;
}

.suggestions {
  margin: 0;
  padding-left: 18px;
  color: #475467;
  line-height: 1.7;
}

@media (max-width: 820px) {
  header,
  .layout {
    display: block;
  }
}
</style>
