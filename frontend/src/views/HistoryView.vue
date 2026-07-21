<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHistoryDetail, listHistory, type ConversationDetail, type ConversationSummary } from '../api/history'

const conversations = ref<ConversationSummary[]>([])
const detail = ref<ConversationDetail | null>(null)

onMounted(refresh)

async function refresh() {
  conversations.value = await listHistory()
}

async function openDetail(id: number) {
  detail.value = await getHistoryDetail(id)
}
</script>

<template>
  <main class="history-page">
    <header>
      <div>
        <p class="eyebrow">会话历史</p>
        <h1>历史记录</h1>
      </div>
      <nav>
        <RouterLink to="/chat">游客对话</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <section class="layout">
      <aside class="panel">
        <button class="refresh" @click="refresh">刷新</button>
        <article
          v-for="item in conversations"
          :key="item.id"
          class="conversation"
          @click="openDetail(item.id)"
        >
          <strong>#{{ item.id }} {{ item.title || '未命名会话' }}</strong>
          <p>{{ item.message_count }} 条消息 · {{ item.total_latency_ms }}ms</p>
          <time>{{ new Date(item.started_at).toLocaleString() }}</time>
        </article>
        <p v-if="!conversations.length" class="empty">暂无历史记录</p>
      </aside>

      <section class="panel detail">
        <div v-if="!detail" class="empty">选择左侧会话查看详情</div>
        <template v-else>
          <h2>#{{ detail.id }} {{ detail.title || '未命名会话' }}</h2>
          <article v-for="message in detail.messages" :key="message.id" class="message" :class="message.role">
            <strong>{{ message.role === 'user' ? '游客' : '导游' }}</strong>
            <p>{{ message.content }}</p>
            <span>{{ message.latency_ms }}ms · {{ new Date(message.created_at).toLocaleString() }}</span>
          </article>
        </template>
      </section>
    </section>
  </main>
</template>

<style scoped>
.history-page {
  min-height: 100vh;
  padding: 24px;
  background: #f6f7fb;
  color: #1f2937;
}

header,
.layout {
  max-width: 1120px;
  margin: 0 auto 20px;
}

header {
  display: flex;
  justify-content: space-between;
}

.eyebrow {
  color: #8b5e34;
  font-weight: 700;
}

nav {
  display: flex;
  gap: 14px;
}

nav a {
  color: #8b5e34;
  text-decoration: none;
}

.layout {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 20px;
}

.panel {
  background: white;
  border-radius: 18px;
  padding: 18px;
  box-shadow: 0 14px 36px rgb(15 23 42 / 8%);
}

.refresh,
button {
  border: 0;
  border-radius: 10px;
  background: #8b5e34;
  color: white;
  padding: 8px 12px;
  cursor: pointer;
}

.conversation,
.message {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 12px;
  margin-top: 12px;
}

.conversation {
  cursor: pointer;
}

.conversation p,
.conversation time,
.message span,
.empty {
  color: #667085;
}

.message.user {
  background: #eff6ff;
}

.message.assistant {
  background: #fff7ed;
}

@media (max-width: 820px) {
  header,
  .layout {
    display: block;
  }

  aside {
    margin-bottom: 16px;
  }
}
</style>
