<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getDashboardOverview, type DashboardOverview } from '../api/dashboard'
import { getMultimodalCapability, type MultimodalCapability } from '../api/multimodal'

const overview = ref<DashboardOverview | null>(null)
const capability = ref<MultimodalCapability | null>(null)
const loading = ref(false)
const rangeMode = ref<'today' | 'week' | 'all'>('today')
let refreshTimer = 0

onMounted(() => {
  refresh()
  refreshTimer = window.setInterval(refresh, 30000)
})

onBeforeUnmount(() => {
  window.clearInterval(refreshTimer)
})

const sentimentLabels: Record<string, string> = {
  positive: '正向',
  neutral: '中性',
  negative: '负向',
}

const eventRows = computed(() => toRows(overview.value?.event_type_counts || {}))
const sentimentRows = computed(() => toRows(overview.value?.feedback_sentiment_counts || {}, sentimentLabels))
const favoriteRows = computed(() => toRows(overview.value?.favorite_type_counts || {}))
const knowledgeRows = computed(() => toRows(overview.value?.knowledge_status_counts || {}))
const pieStyle = computed(() => {
  const positive = overview.value?.feedback_sentiment_counts.positive || 0
  const neutral = overview.value?.feedback_sentiment_counts.neutral || 0
  const negative = overview.value?.feedback_sentiment_counts.negative || 0
  const total = positive + neutral + negative || 1
  const p = (positive / total) * 100
  const n = p + (neutral / total) * 100
  return {
    background: `conic-gradient(#22c55e 0 ${p}%, #fbbf24 ${p}% ${n}%, #ef4444 ${n}% 100%)`,
  }
})
const satisfactionPoints = computed(() => toPolyline(overview.value?.daily_satisfaction || [], 'score', 5))
const trendPoints = computed(() => toPolyline(overview.value?.questions_trend || [], 'count'))
const marquee = computed(() => {
  if (!overview.value) return '正在加载景区导览服务数据...'
  return `今日已服务 ${overview.value.today_visitors} 名游客，平均满意度 ${overview.value.average_satisfaction}，平均响应 ${overview.value.average_latency_ms}ms`
})

async function refresh() {
  loading.value = true
  try {
    const [overviewData, capabilityData] = await Promise.all([
      getDashboardOverview(dateRangeParams()),
      getMultimodalCapability(),
    ])
    overview.value = overviewData
    capability.value = capabilityData
  } finally {
    loading.value = false
  }
}

function dateRangeParams() {
  const today = new Date()
  if (rangeMode.value === 'all') return undefined
  const end = formatDate(today)
  if (rangeMode.value === 'today') return { start_date: end, end_date: end }
  const start = new Date(today)
  start.setDate(today.getDate() - today.getDay() + 1)
  return { start_date: formatDate(start), end_date: end }
}

function setRange(mode: 'today' | 'week' | 'all') {
  rangeMode.value = mode
  refresh()
}

function toRows(data: Record<string, number>, labels: Record<string, string> = {}) {
  const entries = Object.entries(data)
  const max = Math.max(...entries.map(([, value]) => value), 1)
  return entries.map(([key, value]) => ({
    key,
    label: labels[key] || key,
    value,
    width: `${Math.max(8, Math.round((value / max) * 100))}%`,
  }))
}

function toPolyline<T extends Record<string, number | string>>(rows: T[], key: keyof T, maxValue = 0) {
  if (!rows.length) return ''
  const max = maxValue || Math.max(...rows.map((row) => Number(row[key]) || 0), 1)
  return rows.map((row, index) => {
    const x = rows.length === 1 ? 50 : (index / (rows.length - 1)) * 100
    const y = 90 - ((Number(row[key]) || 0) / max) * 80
    return `${x},${Math.max(8, y)}`
  }).join(' ')
}

function formatDate(date: Date) {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}
</script>

<template>
  <main class="dashboard-page">
    <header>
      <div>
        <p class="eyebrow">运营数据大屏</p>
        <h1>景区导览服务总览</h1>
      </div>
      <nav>
        <button :class="{ active: rangeMode === 'today' }" @click="setRange('today')">今日</button>
        <button :class="{ active: rangeMode === 'week' }" @click="setRange('week')">本周</button>
        <button :class="{ active: rangeMode === 'all' }" @click="setRange('all')">全部</button>
        <button :disabled="loading" @click="refresh">{{ loading ? '刷新中...' : '刷新数据' }}</button>
        <RouterLink to="/admin/behavior">感受度报告</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <div class="marquee"><span>{{ marquee }}</span></div>

    <section v-if="overview" class="metrics">
      <article>
        <span>今日服务人次</span>
        <strong>{{ overview.today_visitors }}</strong>
      </article>
      <article>
        <span>本周服务人次</span>
        <strong>{{ overview.week_visitors }}</strong>
      </article>
      <article>
        <span>平均满意度</span>
        <strong>{{ overview.average_satisfaction }}</strong>
      </article>
      <article>
        <span>平均响应延迟</span>
        <strong>{{ overview.average_latency_ms }}ms</strong>
      </article>
      <article>
        <span>多模态核心模型</span>
        <strong>{{ capability?.model || 'Qwen-VL' }}</strong>
      </article>
    </section>

    <section v-if="overview" class="grid">
      <section class="panel wide">
        <h2>热门问题 Top 10</h2>
        <article v-for="item in overview.top_questions" :key="item.question" class="bar-row">
          <div>
            <span>{{ item.question }}</span>
            <strong>{{ item.count }}</strong>
          </div>
          <i :style="{ width: `${Math.max(8, Math.min(100, item.count * 18))}%` }"></i>
        </article>
        <p v-if="!overview.top_questions.length" class="empty">暂无热门问题</p>
      </section>

      <section class="panel">
        <h2>满意度趋势</h2>
        <svg viewBox="0 0 100 100" class="line-chart">
          <polyline :points="satisfactionPoints" fill="none" stroke="#fbbf24" stroke-width="3" />
        </svg>
      </section>

      <section class="panel">
        <h2>问答服务趋势</h2>
        <svg viewBox="0 0 100 100" class="line-chart">
          <polyline :points="trendPoints" fill="none" stroke="#38bdf8" stroke-width="3" />
        </svg>
      </section>

      <section class="panel">
        <h2>情感分布</h2>
        <div class="pie" :style="pieStyle"></div>
        <div class="legend">
          <span v-for="row in sentimentRows" :key="row.key">{{ row.label }} {{ row.value }}</span>
        </div>
      </section>

      <section class="panel wide">
        <h2>游客关注点词云</h2>
        <div class="word-cloud">
          <span v-for="item in overview.word_cloud" :key="item.word" :style="{ fontSize: `${14 + Math.min(28, item.count * 3)}px` }">{{ item.word }}</span>
        </div>
      </section>

      <section class="panel">
        <h2>行为事件分布</h2>
        <article v-for="row in eventRows" :key="row.key" class="bar-row"><div><span>{{ row.label }}</span><strong>{{ row.value }}</strong></div><i :style="{ width: row.width }"></i></article>
      </section>

      <section class="panel">
        <h2>知识库状态</h2>
        <article v-for="row in knowledgeRows" :key="row.key" class="bar-row"><div><span>{{ row.label }}</span><strong>{{ row.value }}</strong></div><i :style="{ width: row.width }"></i></article>
      </section>
    </section>

    <section v-if="!overview" class="panel empty-panel">
      {{ loading ? '正在加载大屏数据...' : '暂无大屏数据' }}
    </section>
  </main>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgb(139 94 52 / 18%), transparent 32%),
    linear-gradient(135deg, #111827 0%, #1f2937 100%);
  color: #f9fafb;
}

header,
.metrics,
.grid,
.marquee,
.empty-panel {
  max-width: 1180px;
  margin: 0 auto 20px;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.eyebrow {
  color: #fbbf24;
  font-weight: 700;
}

nav {
  display: flex;
  align-items: center;
  gap: 12px;
}

nav a,
button {
  border: 1px solid rgb(251 191 36 / 45%);
  border-radius: 999px;
  background: rgb(255 255 255 / 8%);
  color: #fef3c7;
  text-decoration: none;
  padding: 9px 14px;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
}

button.active {
  background: #fbbf24;
  color: #111827;
}

.marquee {
  overflow: hidden;
  border: 1px solid rgb(251 191 36 / 28%);
  border-radius: 999px;
  background: rgb(251 191 36 / 8%);
  color: #fde68a;
  white-space: nowrap;
}

.marquee span {
  display: inline-block;
  padding: 10px 0;
  animation: marquee 18s linear infinite;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.metrics article,
.panel {
  background: rgb(255 255 255 / 10%);
  border: 1px solid rgb(255 255 255 / 12%);
  border-radius: 20px;
  box-shadow: 0 20px 48px rgb(0 0 0 / 20%);
  backdrop-filter: blur(10px);
}

.metrics article,
.panel {
  padding: 18px;
}

.metrics span,
.bar-row span,
.empty {
  color: #d1d5db;
}

.metrics strong {
  display: block;
  margin-top: 10px;
  color: #fbbf24;
  font-size: clamp(30px, 5vw, 48px);
  text-shadow: 0 0 18px rgb(251 191 36 / 28%);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}

.panel {
  padding: 20px;
}

.wide {
  grid-column: span 2;
}

.bar-row {
  margin-top: 14px;
}

.bar-row div {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.bar-row i {
  display: block;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(90deg, #f59e0b, #facc15);
}

.line-chart {
  width: 100%;
  height: 210px;
  border-radius: 16px;
  background:
    linear-gradient(rgb(255 255 255 / 6%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(255 255 255 / 6%) 1px, transparent 1px);
  background-size: 20px 20px;
}

.pie {
  width: 180px;
  height: 180px;
  margin: 16px auto;
  border-radius: 50%;
  box-shadow: inset 0 0 0 18px rgb(17 24 39 / 0.48), 0 18px 40px rgb(0 0 0 / 0.28);
}

.legend {
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
  color: #d1d5db;
}

.word-cloud {
  min-height: 160px;
  display: flex;
  align-items: center;
  align-content: center;
  justify-content: center;
  gap: 14px;
  flex-wrap: wrap;
}

.word-cloud span {
  color: #fde68a;
  text-shadow: 0 0 14px rgb(251 191 36 / 0.24);
}

.empty-panel {
  padding: 30px;
  text-align: center;
}

@media (max-width: 920px) {
  header,
  .metrics,
  .grid {
    display: block;
  }

  .metrics article,
  .panel {
    margin-bottom: 14px;
  }
}

@keyframes marquee {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(-100%);
  }
}
</style>
