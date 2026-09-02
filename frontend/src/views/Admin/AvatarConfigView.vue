<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAvatarConfig,
  getAvatarModels,
  updateAvatarConfig,
  type AvatarConfigPayload,
  type AvatarModelOption,
} from '../../api/avatarConfig'

const loading = ref(false)
const config = ref<AvatarConfigPayload | null>(null)
const models = ref<AvatarModelOption[]>([])

onMounted(() => {
  void loadModels()
  void loadConfig()
})

const avatar = computed(() => config.value?.avatar)
const accessoriesText = computed({
  get: () => avatar.value?.appearance.accessories.join(', ') || '',
  set: (value: string) => {
    if (!avatar.value) return
    avatar.value.appearance.accessories = value.split(',').map((item) => item.trim()).filter(Boolean)
  },
})
const expressionsText = computed({
  get: () => avatar.value?.live2d?.expressions.join(', ') || '',
  set: (value: string) => {
    if (!avatar.value) return
    ensureLive2dConfig()
    avatar.value.live2d!.expressions = value.split(',').map((item) => item.trim()).filter(Boolean)
  },
})
const selectedLive2dModel = computed({
  get: () => {
    const current = avatar.value
    if (!current) return ''
    return current.live2d?.modelMap?.[current.appearance.outfitStyle] || current.live2d?.modelUrl || ''
  },
  set: (url: string) => {
    setLive2dModel(url)
  },
})

async function loadConfig() {
  loading.value = true
  try {
    config.value = await getAvatarConfig()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '读取数字人配置失败')
  } finally {
    loading.value = false
  }
}

async function loadModels() {
  try {
    models.value = await getAvatarModels()
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '读取 Live2D 模型列表失败')
  }
}

async function saveConfig() {
  if (!config.value) return
  loading.value = true
  try {
    if (config.value.avatar.engine === 'live2d') {
      ensureLive2dConfig()
    }
    config.value = await updateAvatarConfig(config.value)
    ElMessage.success('数字人配置已保存，刷新数字人页面后生效')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    loading.value = false
  }
}

function ensureLive2dConfig() {
  if (!avatar.value) return
  const fallbackUrl = models.value[0]?.url || '/models/haru/Haru.model3.json'
  avatar.value.live2d = {
    modelUrl: avatar.value.live2d?.modelUrl || fallbackUrl,
    idleMotionGroup: avatar.value.live2d?.idleMotionGroup || 'Idle',
    expressions: avatar.value.live2d?.expressions?.length ? avatar.value.live2d.expressions : ['F01', 'F03', 'F06'],
    modelMap: avatar.value.live2d?.modelMap || {},
  }
  const style = avatar.value.appearance.outfitStyle
  if (!avatar.value.live2d.modelMap?.[style]) {
    avatar.value.live2d.modelMap = {
      ...avatar.value.live2d.modelMap,
      [style]: avatar.value.live2d.modelUrl,
    }
  }
}

function setLive2dModel(url: string) {
  if (!avatar.value || !url) return
  ensureLive2dConfig()
  avatar.value.live2d!.modelUrl = url
  avatar.value.live2d!.modelMap = {
    ...(avatar.value.live2d!.modelMap || {}),
    [avatar.value.appearance.outfitStyle]: url,
  }
}

const isPlaying = ref(false)

function handleVoicePreview() {
  if (!avatar.value) return
  if (isPlaying.value) {
    window.speechSynthesis.cancel()
    isPlaying.value = false
    return
  }

  const text = '您好，我是灵山胜境AI数字人导游，很高兴为您服务'
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = avatar.value.voice.rate || 1

  const voiceName = avatar.value.voice.voiceName
  const voices = window.speechSynthesis.getVoices()
  const matchedVoice = voices.find((v) => v.name === voiceName)
  if (matchedVoice) {
    utterance.voice = matchedVoice
  }

  utterance.onend = () => {
    isPlaying.value = false
  }
  utterance.onerror = () => {
    isPlaying.value = false
  }

  isPlaying.value = true
  window.speechSynthesis.speak(utterance)
}

// 确保语音列表已加载（部分浏览器需要异步加载）
onMounted(() => {
  if (window.speechSynthesis.getVoices().length === 0) {
    window.speechSynthesis.addEventListener('voiceschanged', () => {}, { once: true })
  }
})
</script>

<template>
  <main class="admin-page">
    <header>
      <div>
        <p class="eyebrow">管理后台</p>
        <h1>数字人形象管理</h1>
        <p>配置数字人的 Live2D 模型、服装风格和声音，使其更贴合景区文化特色。</p>
      </div>
      <nav>
        <RouterLink to="/avatar">预览数字人</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>

    <section v-if="avatar" class="layout">
      <form class="panel form" @submit.prevent="saveConfig">
        <h2>基础形象</h2>
        <label>名称 <input v-model="avatar.name" /></label>
        <label>
          渲染引擎
          <select v-model="avatar.engine">
            <option value="live2d">Live2D 模型</option>
            <option value="svg">SVG 后备形象</option>
          </select>
        </label>
        <label>问候语 <textarea v-model="avatar.greeting" rows="3"></textarea></label>

        <template v-if="avatar.engine === 'live2d'">
          <h2>Live2D 模型</h2>
          <label>
            当前模型
            <select v-model="selectedLive2dModel">
              <option disabled value="">请选择模型</option>
              <option v-for="model in models" :key="model.url" :value="model.url">
                {{ model.name }} · {{ model.label }}
              </option>
            </select>
          </label>
          <label>待机动作组 <input v-model="avatar.live2d!.idleMotionGroup" @focus="ensureLive2dConfig" /></label>
          <label>表情编号 <input v-model="expressionsText" placeholder="F01, F03, F06" /></label>
        </template>

        <h2>外观与服装</h2>
        <label>发色 <input v-model="avatar.appearance.hairColor" type="color" /></label>
        <label>发型 <input v-model="avatar.appearance.hairStyle" /></label>
        <label>瞳色 <input v-model="avatar.appearance.eyeColor" type="color" /></label>
        <label>肤色 <input v-model="avatar.appearance.skinColor" type="color" /></label>
        <label>服装款式 <input v-model="avatar.appearance.outfitStyle" /></label>
        <label>服装主色 <input v-model="avatar.appearance.outfitPrimary" type="color" /></label>
        <label>点缀色 <input v-model="avatar.appearance.outfitAccent" type="color" /></label>
        <label>配饰 <input v-model="accessoriesText" placeholder="golden-hairpin, lotus-brooch" /></label>

        <h2>声音</h2>
        <label>
          声线
          <div class="voice-row">
            <select v-model="avatar.voice.voiceName">
              <option value="zh-CN-XiaoxiaoNeural">晓晓自然女声</option>
              <option value="zh-CN-XiaoyiNeural">晓伊温柔女声</option>
              <option value="zh-CN-YunxiNeural">云希男声</option>
              <option value="zh-CN-YunjianNeural">云健男声</option>
            </select>
            <button type="button" class="preview-btn" :disabled="isPlaying" @click="handleVoicePreview">
              {{ isPlaying ? '停止' : '试听' }}
            </button>
          </div>
        </label>
        <label>语速 {{ avatar.voice.rate.toFixed(1) }}x <input v-model.number="avatar.voice.rate" type="range" min="0.8" max="1.2" step="0.1" /></label>

        <button :disabled="loading" type="submit">{{ loading ? '保存中...' : '保存配置' }}</button>
      </form>

    </section>

    <section v-else class="panel empty">{{ loading ? '正在加载配置...' : '暂无配置' }}</section>
  </main>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  padding: 24px;
  background: #f6f7fb;
  color: #1f2937;
}

header,
.layout,
.empty {
  max-width: 1180px;
  margin: 0 auto 20px;
}

header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
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
  max-width: 860px;
}

.panel {
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 14px 36px rgb(15 23 42 / 8%);
  padding: 20px;
}

.form {
  display: grid;
  gap: 12px;
}

label {
  display: grid;
  gap: 6px;
  color: #475467;
  font-size: 14px;
}

input,
select,
textarea {
  border: 1px solid #d0d5dd;
  border-radius: 10px;
  padding: 9px 10px;
  font: inherit;
}


button {
  height: 42px;
  border: 0;
  border-radius: 12px;
  background: #8b5e34;
  color: #ffffff;
  font-weight: 800;
  cursor: pointer;
}

.voice-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.voice-row select {
  flex: 1;
}

.preview-btn {
  height: auto;
  min-height: 38px;
  padding: 8px 16px;
  background: #b45309;
  font-weight: 600;
  font-size: 14px;
  white-space: nowrap;
}

.preview-btn:hover {
  background: #92400e;
}

.preview-btn:disabled {
  background: #cbd5e1;
}

  .layout {
    display: block;
  }

  .preview {
}
</style>
