<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { addFavorite } from '../api/favorite'
import { recommendRoute } from '../api/route'
import type { RouteRecommendResponse } from '../types/route'

const interest = ref('历史文化')
const durationHours = ref(3)
const groupType = ref('普通游客')
const loading = ref(false)
const result = ref<RouteRecommendResponse | null>(null)

const interests = ['历史文化', '自然风光', '亲子家庭', '轻松慢游', '祈福朝圣']
const groupTypes = ['普通游客', '亲子家庭', '老人同行', '朋友结伴', '摄影打卡']

async function handleRecommend() {
  loading.value = true
  try {
    result.value = await recommendRoute({
      interest: interest.value,
      duration_hours: durationHours.value,
      group_type: groupType.value,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : '路线推荐失败'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

async function favoriteRoute() {
  if (!result.value?.recommendation_id) return
  await addFavorite('route', result.value.recommendation_id)
  ElMessage.success('路线已收藏')
}

async function favoriteSpot(spotId: number) {
  await addFavorite('spot', spotId)
  ElMessage.success('景点已收藏')
}
</script>

<template>
  <main class="route-page">
    <section class="hero">
      <div>
        <p class="eyebrow">路线推荐</p>
        <h1>按兴趣生成灵山胜境游览路线</h1>
        <p>根据兴趣、游玩时长和同行类型，自动推荐景点顺序和停留时间。</p>
      </div>
      <div class="links">
        <RouterLink to="/chat">游客对话</RouterLink>
        <RouterLink to="/">返回首页</RouterLink>
      </div>
    </section>

    <section class="layout">
      <form class="panel form-panel" @submit.prevent="handleRecommend">
        <label>
          兴趣偏好
          <select v-model="interest">
            <option v-for="item in interests" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <label>
          游玩时长
          <input v-model.number="durationHours" type="number" min="1" max="10" />
        </label>
        <label>
          同行类型
          <select v-model="groupType">
            <option v-for="item in groupTypes" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
        <button type="submit" :disabled="loading">
          {{ loading ? '生成中' : '生成路线' }}
        </button>
      </form>

      <section class="panel result-panel">
        <div v-if="!result" class="empty">
          选择偏好后生成路线。请先在后端导入官方景点数据，否则会提示景点库为空。
        </div>
        <template v-else>
          <h2>{{ result.interest }} · {{ result.duration_hours }} 小时</h2>
          <p class="reason">{{ result.reason }}</p>
          <button
            v-if="result.recommendation_id"
            class="favorite-route"
            type="button"
            @click="favoriteRoute"
          >
            收藏整条路线
          </button>
          <ol class="route-list">
            <li v-for="(spot, index) in result.spots" :key="spot.spot_id">
              <div class="order">{{ index + 1 }}</div>
              <div class="spot-card">
                <div class="spot-header">
                  <h3>{{ spot.name }}</h3>
                  <span>{{ spot.stay_minutes }} 分钟</span>
                </div>
                <p class="category">{{ spot.category || '综合景点' }}</p>
                <p>{{ spot.explanation }}</p>
                <p v-if="spot.highlights" class="highlights">{{ spot.highlights }}</p>
                <button class="favorite-spot" type="button" @click="favoriteSpot(spot.spot_id)">
                  收藏景点
                </button>
              </div>
            </li>
          </ol>
        </template>
      </section>
    </section>
  </main>
</template>

<style scoped>
.route-page {
  min-height: 100vh;
  padding: 24px;
  background: linear-gradient(135deg, #f8fafc, #f3eadf);
  color: #1f2937;
}

.hero {
  max-width: 1120px;
  margin: 0 auto 24px;
  display: flex;
  justify-content: space-between;
  gap: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #8b5e34;
  font-weight: 700;
}

h1 {
  margin: 0 0 8px;
  font-size: 32px;
}

.hero p {
  margin: 0;
  color: #667085;
}

.links {
  display: flex;
  gap: 12px;
}

.links a {
  color: #8b5e34;
  text-decoration: none;
}

.layout {
  max-width: 1120px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
}

.panel {
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 16px 40px rgb(15 23 42 / 8%);
  padding: 20px;
}

.form-panel {
  display: grid;
  gap: 16px;
  align-self: start;
}

label {
  display: grid;
  gap: 8px;
  color: #344054;
  font-weight: 700;
}

select,
input {
  height: 42px;
  border-radius: 12px;
  border: 1px solid #d0d5dd;
  padding: 0 12px;
  font: inherit;
}

button {
  height: 44px;
  border: 0;
  border-radius: 12px;
  background: #8b5e34;
  color: white;
  font-weight: 700;
  cursor: pointer;
}

button:disabled {
  background: #cbd5e1;
}

.empty {
  min-height: 280px;
  display: grid;
  place-items: center;
  text-align: center;
  color: #667085;
}

h2 {
  margin: 0 0 8px;
}

.reason {
  color: #667085;
}

.route-list {
  list-style: none;
  padding: 0;
  margin: 20px 0 0;
  display: grid;
  gap: 16px;
}

.route-list li {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 12px;
}

.order {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #8b5e34;
  color: #ffffff;
  display: grid;
  place-items: center;
  font-weight: 700;
}

.spot-card {
  border: 1px solid #eadfd2;
  border-radius: 16px;
  padding: 14px;
}

.spot-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.spot-header h3 {
  margin: 0;
}

.spot-header span,
.category {
  color: #8b5e34;
  font-weight: 700;
}

.highlights {
  color: #475467;
}

.favorite-route,
.favorite-spot {
  margin-top: 8px;
  background: #2563eb;
  color: #ffffff;
}

@media (max-width: 820px) {
  .hero,
  .layout {
    display: block;
  }

  .form-panel {
    margin-bottom: 16px;
  }
}
</style>
