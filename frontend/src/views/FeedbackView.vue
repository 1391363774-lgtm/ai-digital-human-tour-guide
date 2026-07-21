<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { analyzeFeedback, getFeedbackStats, submitFeedback, type FeedbackAnalysis, type FeedbackStats } from '../api/feedback'

const form = reactive({
  rating: null as number | null,
  sentiment: '',
  content: '',
})
const analysis = ref<FeedbackAnalysis | null>(null)
const stats = ref<FeedbackStats | null>(null)
const loading = ref(false)

onMounted(refreshStats)

function sentimentLabel(sentiment: string | null | undefined) {
  const labels: Record<string, string> = {
    positive: '正向',
    neutral: '中性',
    negative: '负向',
  }
  return sentiment ? labels[sentiment] || sentiment : '自动判断'
}

async function refreshStats() {
  stats.value = await getFeedbackStats()
}

async function runAnalysis() {
  analysis.value = await analyzeFeedback({ rating: form.rating, content: form.content })
  if (!form.sentiment) {
    form.sentiment = analysis.value.sentiment
  }
}

async function submit() {
  try {
    loading.value = true
    const payload = {
      rating: form.rating,
      sentiment: form.sentiment || null,
      content: form.content,
    }
    await submitFeedback(payload)
    ElMessage.success('反馈已提交，感谢你的建议')
    form.rating = null
    form.sentiment = ''
    form.content = ''
    analysis.value = null
    await refreshStats()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '反馈提交失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="feedback-page">
    <section class="panel">
      <p class="eyebrow">游客反馈</p>
      <h1>告诉我们你的游览感受</h1>
      <label>
        满意度
        <select v-model.number="form.rating">
          <option :value="null">不选择评分，仅按文字分析</option>
          <option :value="5">5 分，非常满意</option>
          <option :value="4">4 分，比较满意</option>
          <option :value="3">3 分，一般</option>
          <option :value="2">2 分，不太满意</option>
          <option :value="1">1 分，不满意</option>
        </select>
      </label>
      <label>
        情绪倾向
        <select v-model="form.sentiment">
          <option value="">自动分析</option>
          <option value="positive">正向</option>
          <option value="neutral">中性</option>
          <option value="negative">负向</option>
        </select>
      </label>
      <label>
        具体反馈
        <textarea v-model="form.content" rows="6" placeholder="例如：讲解是否清楚，路线是否合适，哪些景点还想了解？" />
      </label>
      <section v-if="analysis" class="analysis-card" :class="analysis.sentiment">
        <strong>智能分析：{{ sentimentLabel(analysis.sentiment) }} · {{ analysis.satisfaction_score }} 分</strong>
        <p>优先级：{{ analysis.priority }}；依据：{{ analysis.reason }}</p>
      </section>
      <div class="actions">
        <button class="ghost" @click="runAnalysis">先分析</button>
        <button :disabled="loading" @click="submit">{{ loading ? '提交中...' : '提交反馈' }}</button>
        <RouterLink to="/">返回首页</RouterLink>
      </div>
    </section>

    <section class="panel stats" v-if="stats">
      <p class="eyebrow">反馈分析</p>
      <h2>满意度概览</h2>
      <div class="metric-grid">
        <article>
          <span>反馈总数</span>
          <strong>{{ stats.total }}</strong>
        </article>
        <article>
          <span>平均评分</span>
          <strong>{{ stats.average_rating }}</strong>
        </article>
        <article>
          <span>满意度分</span>
          <strong>{{ stats.average_satisfaction }}</strong>
        </article>
      </div>
      <div class="sentiments">
        <span>正向 {{ stats.sentiment_counts.positive || 0 }}</span>
        <span>中性 {{ stats.sentiment_counts.neutral || 0 }}</span>
        <span>负向 {{ stats.sentiment_counts.negative || 0 }}</span>
      </div>
      <div v-if="stats.attention_items.length" class="attention">
        <h3>需关注反馈</h3>
        <article v-for="item in stats.attention_items" :key="item.id">
          <strong>#{{ item.id }} {{ sentimentLabel(item.sentiment) }} · {{ item.satisfaction_score }} 分</strong>
          <p>{{ item.content || '未填写具体内容' }}</p>
        </article>
      </div>
    </section>
  </main>
</template>

<style scoped>
.feedback-page {
  min-height: 100vh;
  display: grid;
  place-items: start center;
  grid-template-columns: minmax(320px, 680px) minmax(320px, 420px);
  justify-content: center;
  align-items: start;
  gap: 20px;
  padding: 24px;
  background: #f6f7fb;
  color: #1f2937;
}

.panel {
  width: 100%;
  background: white;
  border-radius: 20px;
  padding: 28px;
  box-shadow: 0 14px 36px rgb(15 23 42 / 8%);
  display: grid;
  gap: 16px;
}

.eyebrow {
  color: #8b5e34;
  font-weight: 700;
  margin: 0;
}

label {
  display: grid;
  gap: 8px;
  font-weight: 700;
}

select,
textarea {
  border: 1px solid #d0d5dd;
  border-radius: 12px;
  padding: 10px;
  font: inherit;
}

.actions {
  display: flex;
  gap: 14px;
  align-items: center;
}

button {
  height: 42px;
  border: 0;
  border-radius: 12px;
  background: #8b5e34;
  color: white;
  padding: 0 16px;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ghost {
  background: #fff7ed;
  color: #8b5e34;
  border: 1px solid #fed7aa;
}

a {
  color: #8b5e34;
  text-decoration: none;
}

.analysis-card {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 14px;
  padding: 12px;
}

.analysis-card.negative {
  background: #fef2f2;
  border-color: #fecaca;
}

.analysis-card.neutral {
  background: #fffbeb;
  border-color: #fde68a;
}

.analysis-card p,
.attention p {
  color: #667085;
  margin-bottom: 0;
}

.stats {
  gap: 14px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.metric-grid article,
.attention article {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 12px;
}

.metric-grid span,
.sentiments {
  color: #667085;
}

.metric-grid strong {
  display: block;
  margin-top: 6px;
  font-size: 24px;
}

.sentiments {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.sentiments span {
  border-radius: 999px;
  background: #f3f4f6;
  padding: 6px 10px;
}

.attention {
  display: grid;
  gap: 10px;
}

@media (max-width: 960px) {
  .feedback-page {
    grid-template-columns: 1fr;
  }
}
</style>
