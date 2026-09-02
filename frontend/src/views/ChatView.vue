<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { sendChatMessage } from '../api/chat'
import { synthesizeSpeech, transcribeAudio } from '../api/speech'
import type { ChatMessage } from '../types/chat'

type SpeechRecognitionConstructor = new () => SpeechRecognition
interface SpeechRecognition extends EventTarget {
  lang: string
  interimResults: boolean
  continuous: boolean
  start: () => void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: Event) => void) | null
  onend: (() => void) | null
}
interface SpeechRecognitionEvent extends Event {
  results: ArrayLike<ArrayLike<{ transcript: string }>>
}

const route = useRoute()
const input = ref(typeof route.query.question === 'string' ? route.query.question : '')
const loading = ref(false)
const recording = ref(false)
const recognizing = ref(false)
const mediaRecorder = ref<MediaRecorder | null>(null)
const audioChunks = ref<Blob[]>([])
const conversationId = ref<number | null>(null)
const autoSpeak = ref(true)
const fastMode = ref(false)
const lastLatencyMs = ref<number | null>(null)
const messages = ref<ChatMessage[]>([
  {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '你好，我是灵山胜境 AI 数字人导游。你可以问我景点历史、演出时间、游玩亮点或路线建议。',
  },
])

const canSend = computed(() => input.value.trim().length > 0 && !loading.value)
const canRecord = computed(() => !loading.value && !recognizing.value)

onMounted(() => {
  if (input.value.trim()) {
    void handleSend()
  }
})

async function handleSend() {
  const content = input.value.trim()
  if (!content || loading.value) return

  messages.value.push({
    id: crypto.randomUUID(),
    role: 'user',
    content,
  })
  input.value = ''
  loading.value = true
  const startedAt = performance.now()

  try {
    const response = await sendChatMessage({
      message: content,
      conversation_id: conversationId.value,
      top_k: 5,
      fast: fastMode.value,
    })
    conversationId.value = response.conversation_id
    lastLatencyMs.value = Math.round(performance.now() - startedAt)
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: response.answer,
      sources: response.sources,
      provider: response.provider,
      model: response.model,
      refused: response.refused,
    })
    if (autoSpeak.value && !response.refused) {
      await speakMessage(response.answer)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '发送失败'
    ElMessage.error(message)
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `请求失败：${message}`,
      refused: true,
    })
  } finally {
    loading.value = false
  }
}

function sourceTitle(source: NonNullable<ChatMessage['sources']>[number], index: number) {
  const metadata = source.metadata || {}
  return String(metadata.section_title || metadata.document_title || `来源 ${index + 1}`)
}

async function toggleRecording() {
  if (recording.value) {
    stopRecording()
    return
  }
  await startRecording()
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    ElMessage.error('当前浏览器不支持录音，请使用文本输入')
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
      await recognizeRecording()
    }
    mediaRecorder.value = recorder
    recorder.start()
    recording.value = true
  } catch (error) {
    const message = error instanceof Error ? error.message : '无法打开麦克风'
    ElMessage.error(`录音失败：${message}`)
  }
}

function stopRecording() {
  if (!mediaRecorder.value || mediaRecorder.value.state === 'inactive') {
    recording.value = false
    return
  }
  mediaRecorder.value.stop()
  recording.value = false
}

async function recognizeRecording() {
  if (!audioChunks.value.length) return
  recognizing.value = true
  try {
    const mimeType = pickMimeType()
    const blob = new Blob(audioChunks.value, mimeType ? { type: mimeType } : undefined)
    const result = await transcribeAudio(blob)
    if (!result.text) {
      ElMessage.warning('没有识别到有效语音，请重试或直接输入文字')
      return
    }
    input.value = result.text
    ElMessage.success('语音识别完成，已填入输入框')
  } catch (error) {
    const message = error instanceof Error ? error.message : '语音识别失败'
    ElMessage.warning(`${message}，正在尝试浏览器语音识别`)
    await recognizeWithBrowserSpeech()
  } finally {
    recognizing.value = false
    audioChunks.value = []
  }
}

function pickMimeType() {
  if (!window.MediaRecorder) return ''
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus'
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm'
  if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4'
  if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) return 'audio/ogg;codecs=opus'
  return ''
}

async function recognizeWithBrowserSpeech() {
  const SpeechRecognitionClass = getSpeechRecognition()
  if (!SpeechRecognitionClass) {
    ElMessage.error('当前浏览器不支持语音识别，请使用文本输入')
    return
  }
  recognizing.value = true
  await new Promise<void>((resolve) => {
    const recognition = new SpeechRecognitionClass()
    recognition.lang = 'zh-CN'
    recognition.interimResults = false
    recognition.continuous = false
    recognition.onresult = (event) => {
      const text = event.results?.[0]?.[0]?.transcript || ''
      if (text.trim()) {
        input.value = text.trim()
        ElMessage.success('浏览器语音识别完成，已填入输入框')
      } else {
        ElMessage.warning('没有识别到有效语音，请重试或直接输入文字')
      }
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

function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  const win = window as Window & {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
  return win.SpeechRecognition || win.webkitSpeechRecognition || null
}

async function speakMessage(content: string) {
  try {
    const audioBlob = await synthesizeSpeech(content)
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)
    audio.onended = () => URL.revokeObjectURL(audioUrl)
    audio.onerror = () => {
      URL.revokeObjectURL(audioUrl)
      speakWithBrowser(content)
    }
    await audio.play()
  } catch (error) {
    speakWithBrowser(content)
  }
}

function speakWithBrowser(text: string) {
  if (!window.speechSynthesis) {
    ElMessage.warning('当前浏览器不支持语音合成')
    return
  }
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1
  window.speechSynthesis.speak(utterance)
}
</script>

<template>
  <main class="chat-page">
    <section class="hero">
      <div>
        <p class="eyebrow">游客对话端</p>
        <h1>灵山胜境 AI 数字人导游</h1>
        <p>支持语音输入、文本输入、知识库问答和自动语音播报，回答会显示资料来源。</p>
      </div>
      <RouterLink class="home-link" to="/">返回首页</RouterLink>
    </section>

    <section class="chat-panel">
      <div class="messages">
        <article
          v-for="message in messages"
          :key="message.id"
          class="message"
          :class="message.role"
        >
          <div class="avatar">{{ message.role === 'user' ? '游客' : '导游' }}</div>
          <div class="bubble">
            <p class="content">{{ message.content }}</p>
            <p v-if="message.provider" class="meta">
              {{ message.provider }} / {{ message.model }}
              <span v-if="lastLatencyMs && message.role === 'assistant'"> · {{ lastLatencyMs }}ms</span>
              <span v-if="message.refused"> · 已拒答</span>
            </p>
            <button
              v-if="message.role === 'assistant'"
              class="speak-button"
              type="button"
              @click="speakMessage(message.content)"
            >
              朗读答案
            </button>
            <details v-if="message.sources?.length" class="sources">
              <summary>查看资料来源（{{ message.sources.length }}）</summary>
              <div v-for="(source, index) in message.sources" :key="index" class="source-item">
                <strong>{{ sourceTitle(source, index) }}</strong>
                <span>匹配分：{{ source.score.toFixed(2) }}</span>
                <p>{{ source.content }}</p>
              </div>
            </details>
          </div>
        </article>
        <article v-if="loading" class="message assistant">
          <div class="avatar">导游</div>
          <div class="bubble loading">正在检索景区资料并组织回答...</div>
        </article>
      </div>

      <form class="composer" @submit.prevent="handleSend">
        <label class="auto-speak">
          <input v-model="autoSpeak" type="checkbox" />
          自动语音播报
        </label>
        <label class="auto-speak">
          <input v-model="fastMode" type="checkbox" />
          快速回答
        </label>
        <textarea
          v-model="input"
          placeholder="例如：灵山大佛有多高？九龙灌浴什么时候表演？"
          rows="3"
          @keydown.ctrl.enter.prevent="handleSend"
        />
        <button class="record-button" type="button" :disabled="!canRecord" @click="toggleRecording">
          {{ recording ? '停止录音' : recognizing ? '识别中' : '语音输入' }}
        </button>
        <button type="submit" :disabled="!canSend">
          {{ loading ? '发送中' : '发送' }}
        </button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.chat-page {
  min-height: 100vh;
  background: #f5f7fb;
  color: #1f2937;
  padding: 24px;
}

.hero {
  max-width: 1100px;
  margin: 0 auto 20px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
}

.eyebrow {
  color: #8b5e34;
  margin: 0 0 8px;
  font-weight: 700;
}

.hero h1 {
  margin: 0 0 8px;
  font-size: 32px;
}

.hero p {
  margin: 0;
  color: #667085;
}

.home-link {
  color: #8b5e34;
  text-decoration: none;
  white-space: nowrap;
}

.chat-panel {
  max-width: 1100px;
  height: calc(100vh - 170px);
  margin: 0 auto;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 16px 50px rgb(15 23 42 / 8%);
  display: grid;
  grid-template-rows: 1fr auto;
  overflow: hidden;
}

.messages {
  padding: 24px;
  overflow-y: auto;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #ede1d2;
  color: #7a4d24;
  font-size: 13px;
  flex: 0 0 auto;
}

.user .avatar {
  background: #dbeafe;
  color: #1d4ed8;
}

.bubble {
  max-width: min(760px, 78%);
  border-radius: 18px;
  padding: 14px 16px;
  background: #f8fafc;
  line-height: 1.7;
}

.user .bubble {
  background: #2563eb;
  color: #ffffff;
}

.content {
  white-space: pre-wrap;
  margin: 0;
}

.meta {
  margin: 8px 0 0;
  font-size: 12px;
  color: #98a2b3;
}

.speak-button {
  margin-top: 10px;
  height: 30px;
  padding: 0 12px;
  border: 1px solid #d6bbfb;
  border-radius: 999px;
  background: #f4ebff;
  color: #6941c6;
  cursor: pointer;
}

.sources {
  margin-top: 12px;
  font-size: 13px;
}

.source-item {
  margin-top: 10px;
  padding: 10px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
}

.source-item span {
  margin-left: 10px;
  color: #667085;
}

.source-item p {
  margin: 6px 0 0;
  color: #475467;
}

.composer {
  border-top: 1px solid #e5e7eb;
  padding: 16px;
  display: grid;
  grid-template-columns: 140px 1fr 108px 108px;
  gap: 12px;
}

.auto-speak {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #475467;
  font-size: 14px;
}

.composer textarea {
  resize: none;
  border: 1px solid #d0d5dd;
  border-radius: 14px;
  padding: 12px;
  font: inherit;
  outline: none;
}

.composer textarea:focus {
  border-color: #8b5e34;
}

.composer button {
  border: 0;
  border-radius: 14px;
  background: #8b5e34;
  color: #ffffff;
  font-weight: 700;
  cursor: pointer;
}

.record-button {
  background: #2563eb !important;
}

.record-button:disabled {
  background: #cbd5e1 !important;
}

.composer button:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.loading {
  color: #667085;
}

@media (max-width: 720px) {
  .chat-page {
    padding: 12px;
  }

  .hero {
    display: block;
  }

  .chat-panel {
    height: calc(100vh - 190px);
    border-radius: 16px;
  }

  .bubble {
    max-width: 86%;
  }

  .composer {
    grid-template-columns: 1fr;
  }

  .composer button {
    height: 44px;
  }
}
</style>
