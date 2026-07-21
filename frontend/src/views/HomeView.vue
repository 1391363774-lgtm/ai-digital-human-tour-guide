<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { transcribeAudio } from '../api/speech'

type SpeechRecognitionConstructor = new () => SpeechRecognition
interface SpeechRecognition extends EventTarget {
  lang: string
  interimResults: boolean
  continuous: boolean
  start: () => void
  stop: () => void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: Event) => void) | null
  onend: (() => void) | null
}
interface SpeechRecognitionEvent extends Event {
  results: ArrayLike<ArrayLike<{ transcript: string }>>
}

const router = useRouter()
const recording = ref(false)
const recognizing = ref(false)
const mediaRecorder = ref<MediaRecorder | null>(null)
const audioChunks = ref<Blob[]>([])

async function toggleHomeRecording() {
  if (recording.value) {
    stopHomeRecording()
    return
  }
  await startHomeRecording()
}

async function startHomeRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    await recognizeWithBrowserSpeech()
    return
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeType = pickMimeType()
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
    audioChunks.value = []
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) audioChunks.value.push(event.data)
    }
    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop())
      await recognizeHomeRecording()
    }
    mediaRecorder.value = recorder
    recorder.start()
    recording.value = true
  } catch {
    await recognizeWithBrowserSpeech()
  }
}

function stopHomeRecording() {
  if (!mediaRecorder.value || mediaRecorder.value.state === 'inactive') {
    recording.value = false
    return
  }
  mediaRecorder.value.stop()
  recording.value = false
}

async function recognizeHomeRecording() {
  if (!audioChunks.value.length) return
  recognizing.value = true
  try {
    const mimeType = pickMimeType()
    const blob = new Blob(audioChunks.value, mimeType ? { type: mimeType } : undefined)
    const result = await transcribeAudio(blob)
    await goChatWithQuestion(result.text)
  } catch (error) {
    const message = error instanceof Error ? error.message : '后端语音识别失败'
    ElMessage.warning(`${message}，正在尝试浏览器语音识别`)
    await recognizeWithBrowserSpeech()
  } finally {
    recognizing.value = false
    audioChunks.value = []
  }
}

async function recognizeWithBrowserSpeech() {
  const SpeechRecognitionClass = getSpeechRecognition()
  if (!SpeechRecognitionClass) {
    ElMessage.error('当前浏览器不支持语音识别，请进入对话页手动输入')
    return
  }
  recognizing.value = true
  await new Promise<void>((resolve) => {
    const recognition = new SpeechRecognitionClass()
    recognition.lang = 'zh-CN'
    recognition.interimResults = false
    recognition.continuous = false
    recognition.onresult = async (event) => {
      const text = event.results?.[0]?.[0]?.transcript || ''
      await goChatWithQuestion(text)
      resolve()
    }
    recognition.onerror = () => {
      ElMessage.error('浏览器语音识别失败，请使用文本输入')
      resolve()
    }
    recognition.onend = () => {
      recognizing.value = false
      resolve()
    }
    recognition.start()
  })
}

async function goChatWithQuestion(text: string) {
  const question = text.trim()
  if (!question) {
    ElMessage.warning('没有识别到有效语音')
    return
  }
  await router.push({ path: '/chat', query: { question } })
}

function pickMimeType() {
  if (!window.MediaRecorder) return ''
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus'
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm'
  if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4'
  if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) return 'audio/ogg;codecs=opus'
  return ''
}

function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  const win = window as Window & {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
  return win.SpeechRecognition || win.webkitSpeechRecognition || null
}
</script>

<template>
  <main class="home">
    <h1>景区导览服务 AI 数字人</h1>
    <p>用语音、文字或景区照片询问景点历史、路线推荐、演出信息和游客服务。</p>
    <p class="model-note">核心 AI：DeepSeek/Qwen 文本问答 + Qwen-VL 图文多模态识别 + 本地景区知识库 RAG。</p>
    <button class="mic-button" :class="{ recording }" :disabled="recognizing" @click="toggleHomeRecording">
      {{ recording ? '停止录音并识别' : recognizing ? '识别中...' : '按下开始语音提问' }}
    </button>
    <div class="actions">
      <RouterLink class="primary-link" to="/chat">进入游客对话</RouterLink>
      <RouterLink class="secondary-link" to="/avatar">数字人讲解</RouterLink>
      <RouterLink class="secondary-link" to="/vision">拍照问导游</RouterLink>
      <RouterLink class="secondary-link" to="/routes">生成游览路线</RouterLink>
      <RouterLink class="secondary-link" to="/map">景区地图</RouterLink>
      <RouterLink class="secondary-link" to="/favorites">我的收藏</RouterLink>
      <RouterLink class="secondary-link" to="/history">历史记录</RouterLink>
      <RouterLink class="secondary-link" to="/feedback">游客反馈</RouterLink>
      <RouterLink class="secondary-link" to="/dashboard">数据大屏</RouterLink>
      <RouterLink class="secondary-link" to="/admin/knowledge">知识库后台</RouterLink>
      <RouterLink class="secondary-link" to="/admin/spots">景点后台</RouterLink>
      <RouterLink class="secondary-link" to="/admin/behavior">感受度报告</RouterLink>
      <RouterLink class="secondary-link" to="/admin/avatar">形象管理</RouterLink>
    </div>
  </main>
</template>

<style scoped>
.home {
  min-height: 100vh;
  display: grid;
  place-content: center;
  gap: 12px;
  text-align: center;
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.model-note {
  max-width: 720px;
  color: #667085;
  font-weight: 700;
}

.mic-button {
  width: min(420px, 92vw);
  height: 64px;
  margin: 8px auto 12px;
  border: 0;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(135deg, #8b5e34, #d97706);
  box-shadow: 0 16px 38px rgb(139 94 52 / 25%);
  font-size: 18px;
  font-weight: 800;
  cursor: pointer;
}

.mic-button.recording {
  background: linear-gradient(135deg, #b42318, #f97316);
  animation: pulse 1s ease-in-out infinite;
}

.mic-button:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.03);
  }
}

.primary-link {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  min-width: 140px;
  height: 44px;
  padding: 0 18px;
  border-radius: 999px;
  background: #8b5e34;
  color: #ffffff;
  text-decoration: none;
  font-weight: 700;
}

.secondary-link {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  min-width: 140px;
  height: 44px;
  padding: 0 18px;
  border-radius: 999px;
  border: 1px solid #8b5e34;
  color: #8b5e34;
  text-decoration: none;
  font-weight: 700;
}
</style>
