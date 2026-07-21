<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listFavorites, removeFavorite, type Favorite } from '../api/favorite'

const favorites = ref<Favorite[]>([])

onMounted(refresh)

async function refresh() {
  favorites.value = await listFavorites()
}

async function remove(id: number) {
  try {
    await removeFavorite(id)
    ElMessage.success('已取消收藏')
    await refresh()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '取消收藏失败')
  }
}

function label(type: string) {
  const map: Record<string, string> = {
    spot: '景点',
    route: '路线',
    message: '消息',
    qa: '问答',
  }
  return map[type] || type
}
</script>

<template>
  <main class="favorite-page">
    <header>
      <div>
        <p class="eyebrow">游客收藏</p>
        <h1>我的收藏</h1>
      </div>
      <nav>
        <RouterLink to="/chat">游客对话</RouterLink>
        <RouterLink to="/routes">路线推荐</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <section class="panel">
      <div v-if="!favorites.length" class="empty">暂无收藏。后续页面会逐步加入一键收藏按钮。</div>
      <article v-for="item in favorites" :key="item.id" class="favorite-card">
        <div>
          <strong>{{ label(item.target_type) }} #{{ item.target_id }}</strong>
          <p>{{ new Date(item.created_at).toLocaleString() }}</p>
        </div>
        <button @click="remove(item.id)">取消收藏</button>
      </article>
    </section>
  </main>
</template>

<style scoped>
.favorite-page {
  min-height: 100vh;
  padding: 24px;
  background: #f6f7fb;
  color: #1f2937;
}

header,
.panel {
  max-width: 960px;
  margin: 0 auto 20px;
}

header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
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

.panel {
  background: #ffffff;
  border-radius: 18px;
  padding: 20px;
  box-shadow: 0 14px 36px rgb(15 23 42 / 8%);
}

.favorite-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  margin-bottom: 12px;
}

.favorite-card p,
.empty {
  color: #667085;
}

button {
  border: 0;
  border-radius: 10px;
  background: #b42318;
  color: #ffffff;
  padding: 0 12px;
  cursor: pointer;
}
</style>
