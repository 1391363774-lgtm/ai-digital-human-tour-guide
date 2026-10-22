<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { setAdminKey } from './api/access'
const route = useRoute()
const input = ref('')
const configured = ref(false)
function applyKey() { setAdminKey(input.value); configured.value = !!input.value.trim(); input.value = '' }
</script>

<template>
  <details v-if="route.path.startsWith('/admin') || route.path === '/dashboard' || route.path === '/feedback'" class="admin-access">
    <summary>管理员访问{{ configured ? '（本页已设置）' : '（需配置）' }}</summary>
    <form @submit.prevent="applyKey">
      <label>管理密钥 <input v-model="input" type="password" autocomplete="off" /></label>
      <button type="submit">应用 / 清除</button>
      <small>仅保存在当前页内存；刷新后重新输入，然后刷新数据。不将密钥放入地址或源码。</small>
    </form>
  </details>
  <router-view />
</template>

<style scoped>
.admin-access { padding: 12px; background: #fff7df; color: #241b00; }
form { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
</style>
