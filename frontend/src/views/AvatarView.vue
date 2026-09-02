<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { streamChatMessage } from '../api/chat'
import { synthesizeSpeech, streamSynthesizeSpeech, base64ToBlob, transcribeAudio } from '../api/speech'

type AvatarStatus = 'idle' | 'thinking' | 'speaking'
type AvatarExpression = 'smile' | 'focus' | 'surprised'
type AvatarRenderMode = 'image3d' | 'live2d' | 'svg'
type VoiceMode = 'edge' | 'browser' | 'text'
type SpeechRecognitionConstructor = new () => SpeechRecognition

interface SpeechRecognition extends EventTarget {
  lang: string
  interimResults: boolean
  continuous: boolean
  start: () => void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
}

interface SpeechRecognitionEvent extends Event {
  results: ArrayLike<ArrayLike<{ transcript: string }>>
}

declare global {
  interface Window {
    PIXI?: any
  }
}

const LIVE2D_MODEL_PATH = '/models/haru/Haru.model3.json'
const LIVE2D_MODEL_MAP: Record<string, string> = {
  'guide-hanfu': '/models/haru/Haru.model3.json',
  ceremonial: '/models/hiyori/Hiyori.model3.json',
  modern: '/models/natori/Natori.model3.json',
}
const LIVE2D_EXPRESSION_MAP: Record<AvatarExpression, string> = {
  smile: 'F01',
  focus: 'F03',
  surprised: 'F06',
}

interface Image3dLandmarks {
  faceLeft: number
  faceTop: number
  faceWidth: number
  faceHeight: number
  leftEyeX: number
  leftEyeY: number
  rightEyeX: number
  rightEyeY: number
  eyeWidth: number
  eyeHeight: number
  mouthX: number
  mouthY: number
  mouthWidth: number
  mouthHeight: number
}

interface AvatarAppearance {
  renderMode: AvatarRenderMode
  name: string
  avatarImage: string
  hair: {
    color: string
    shade: string
    style: 'long' | 'short' | 'side-tail'
  }
  eyes: {
    color: string
    highlight: string
  }
  skin: {
    base: string
    shadow: string
    blush: string
  }
  outfit: {
    style: 'guide-hanfu' | 'ceremonial' | 'modern'
    primary: string
    secondary: string
    accent: string
    trim: string
  }
  accessories: {
    hat: boolean
    glasses: boolean
    hairpin: boolean
    haloPin: boolean
  }
  voice: {
    provider: 'edge-tts' | 'browser'
    voiceName: string
    label: string
    rate: number
  }
  image3d: {
    landmarks: Image3dLandmarks
  }
  live2d?: {
    modelUrl: string
    idleMotionGroup: string
    expressions: string[]
    modelMap?: Record<string, string>
  }
}

const avatarConfig = ref<AvatarAppearance>({
  renderMode: 'live2d',
  name: '灵山导游·灵汐',
  avatarImage: '',
  hair: {
    color: '#2d1b4f',
    shade: '#111827',
    style: 'long',
  },
  eyes: {
    color: '#55d6ff',
    highlight: '#ffffff',
  },
  skin: {
    base: '#ffd9bf',
    shadow: '#f0b997',
    blush: '#ff8fb3',
  },
  outfit: {
    style: 'guide-hanfu',
    primary: '#6d28d9',
    secondary: '#312e81',
    accent: '#f59e0b',
    trim: '#fde68a',
  },
  accessories: {
    hat: false,
    glasses: false,
    hairpin: true,
    haloPin: true,
  },
  voice: {
    provider: 'edge-tts',
    voiceName: 'zh-CN-XiaoxiaoNeural',
    label: '晓晓自然女声',
    rate: 1,
  },
  image3d: {
    landmarks: {
      faceLeft: 25,
      faceTop: 16,
      faceWidth: 50,
      faceHeight: 38,
      leftEyeX: 38,
      leftEyeY: 31,
      rightEyeX: 62,
      rightEyeY: 31,
      eyeWidth: 10,
      eyeHeight: 4.8,
      mouthX: 50.5,
      mouthY: 41.2,
      mouthWidth: 7.8,
      mouthHeight: 4.2,
    },
  },
  live2d: {
    modelUrl: LIVE2D_MODEL_PATH,
    idleMotionGroup: 'Idle',
    expressions: ['F01', 'F03', 'F06'],
    modelMap: LIVE2D_MODEL_MAP,
  },
})

const question = ref('请介绍一下灵山大佛')
const subtitle = ref('你好，我是灵山胜境 AI 数字人导游。我可以讲景点故事、推荐路线，也可以用语音为你讲解。')
const status = ref<AvatarStatus>('idle')
const expression = ref<AvatarExpression>('smile')
const mouthOpen = ref(0)
const voiceMode = ref<VoiceMode>('edge')
const conversationId = ref<number | null>(null)
const live2dCanvas = ref<HTMLCanvasElement | null>(null)
const live2dReady = ref(false)
const recording = ref(false)
const recognizing = ref(false)
const mediaRecorder = ref<MediaRecorder | null>(null)
const audioChunks = ref<Blob[]>([])

let audioEl: HTMLAudioElement | null = null
let currentAudioUrl = ''
let live2dApp: any = null
let live2dModel: any = null
let currentLive2DModelPath = ''
let live2dMouthParamIds: string[] = ['ParamMouthOpenY', 'PARAM_MOUTH_OPEN_Y', 'ParamMouthOpen']
let currentTtsAbort: AbortController | null = null
// Live2D 嘴型覆盖：模型的动作系统每帧会覆盖参数，必须在模型 update 之后强制写入
let live2dMouthOverride = 0
let live2dMouthActive = false

const avatarVars = computed(() => ({
  '--face-left': `${avatarConfig.value.image3d.landmarks.faceLeft}%`,
  '--face-top': `${avatarConfig.value.image3d.landmarks.faceTop}%`,
  '--face-width': `${avatarConfig.value.image3d.landmarks.faceWidth}%`,
  '--face-height': `${avatarConfig.value.image3d.landmarks.faceHeight}%`,
  '--left-eye-x': `${avatarConfig.value.image3d.landmarks.leftEyeX}%`,
  '--left-eye-y': `${avatarConfig.value.image3d.landmarks.leftEyeY}%`,
  '--left-eye-left': `${avatarConfig.value.image3d.landmarks.leftEyeX - avatarConfig.value.image3d.landmarks.eyeWidth / 2}%`,
  '--left-eye-top': `${avatarConfig.value.image3d.landmarks.leftEyeY - avatarConfig.value.image3d.landmarks.eyeHeight / 2}%`,
  '--right-eye-x': `${avatarConfig.value.image3d.landmarks.rightEyeX}%`,
  '--right-eye-y': `${avatarConfig.value.image3d.landmarks.rightEyeY}%`,
  '--right-eye-left': `${avatarConfig.value.image3d.landmarks.rightEyeX - avatarConfig.value.image3d.landmarks.eyeWidth / 2}%`,
  '--right-eye-top': `${avatarConfig.value.image3d.landmarks.rightEyeY - avatarConfig.value.image3d.landmarks.eyeHeight / 2}%`,
  '--eye-width': `${avatarConfig.value.image3d.landmarks.eyeWidth}%`,
  '--eye-height': `${avatarConfig.value.image3d.landmarks.eyeHeight}%`,
  '--mouth-x': `${avatarConfig.value.image3d.landmarks.mouthX}%`,
  '--mouth-y': `${avatarConfig.value.image3d.landmarks.mouthY}%`,
  '--mouth-left': `${avatarConfig.value.image3d.landmarks.mouthX - avatarConfig.value.image3d.landmarks.mouthWidth / 2}%`,
  '--mouth-top': `${avatarConfig.value.image3d.landmarks.mouthY - avatarConfig.value.image3d.landmarks.mouthHeight / 2}%`,
  '--smile-left': `${avatarConfig.value.image3d.landmarks.mouthX - avatarConfig.value.image3d.landmarks.mouthWidth * 0.56}%`,
  '--smile-top': `${avatarConfig.value.image3d.landmarks.mouthY - avatarConfig.value.image3d.landmarks.mouthHeight * 0.62}%`,
  '--mouth-width': `${avatarConfig.value.image3d.landmarks.mouthWidth}%`,
  '--mouth-height': `${avatarConfig.value.image3d.landmarks.mouthHeight}%`,
  '--hair': avatarConfig.value.hair.color,
  '--hair-shade': avatarConfig.value.hair.shade,
  '--eye': avatarConfig.value.eyes.color,
  '--eye-highlight': avatarConfig.value.eyes.highlight,
  '--skin': avatarConfig.value.skin.base,
  '--skin-shadow': avatarConfig.value.skin.shadow,
  '--blush': avatarConfig.value.skin.blush,
  '--cloth-primary': avatarConfig.value.outfit.primary,
  '--cloth-secondary': avatarConfig.value.outfit.secondary,
  '--cloth-accent': avatarConfig.value.outfit.accent,
  '--cloth-trim': avatarConfig.value.outfit.trim,
  '--mouth-scale': `${0.15 + mouthOpen.value * 1.4}`,
}))

onMounted(() => {
  void loadAvatarConfig()
})

watch(
  () => avatarConfig.value.outfit.style,
  async () => {
    if (avatarConfig.value.renderMode === 'live2d' && live2dCanvas.value) {
      await initLive2D()
    }
  },
)

async function loadAvatarConfig() {
  try {
    const response = await fetch('/avatar-config.json', { cache: 'no-store' })
    if (!response.ok) return
    const data = await response.json()
    const remote = data.avatar || data
    avatarConfig.value = mergeAvatarConfig(avatarConfig.value, remote)
    if (avatarConfig.value.renderMode === 'live2d') {
      await initLive2D()
    } else {
      await ensureAvatarImage()
    }
  } catch {
    avatarConfig.value.renderMode = 'svg'
  }
}

function mergeAvatarConfig(base: AvatarAppearance, remote: Record<string, unknown>): AvatarAppearance {
  const appearance = (remote.appearance || {}) as Record<string, unknown>
  const image3d = (remote.image3d || {}) as { landmarks?: Partial<Image3dLandmarks> }
  const voice = (remote.voice || {}) as Partial<AvatarAppearance['voice']>
  const remoteMode = remote.engine as AvatarRenderMode | undefined
  return {
    ...base,
    name: String(remote.name || base.name),
    renderMode: remoteMode === 'svg' ? 'svg' : 'live2d',
    avatarImage: String(remote.avatarImage || base.avatarImage),
    hair: {
      ...base.hair,
      color: String(appearance.hairColor || base.hair.color),
      style: (appearance.hairStyle as AvatarAppearance['hair']['style']) || base.hair.style,
    },
    eyes: {
      ...base.eyes,
      color: String(appearance.eyeColor || base.eyes.color),
    },
    skin: {
      ...base.skin,
      base: String(appearance.skinColor || base.skin.base),
    },
    outfit: {
      ...base.outfit,
      style: (appearance.outfitStyle as AvatarAppearance['outfit']['style']) || base.outfit.style,
      primary: String(appearance.outfitPrimary || base.outfit.primary),
      accent: String(appearance.outfitAccent || base.outfit.accent),
    },
    voice: {
      ...base.voice,
      ...voice,
      rate: Number(voice.rate ?? base.voice.rate),
    },
    image3d: {
      landmarks: {
        ...base.image3d.landmarks,
        ...(image3d.landmarks || {}),
      },
    },
    live2d: {
      modelUrl: String((remote.live2d as { modelUrl?: string } | undefined)?.modelUrl || base.live2d?.modelUrl || LIVE2D_MODEL_PATH),
      idleMotionGroup: String((remote.live2d as { idleMotionGroup?: string } | undefined)?.idleMotionGroup || base.live2d?.idleMotionGroup || 'Idle'),
      expressions: ((remote.live2d as { expressions?: string[] } | undefined)?.expressions || base.live2d?.expressions || ['F01', 'F03', 'F06']),
      modelMap: {
        ...LIVE2D_MODEL_MAP,
        ...(base.live2d?.modelMap || {}),
        ...(((remote.live2d as { modelMap?: Record<string, string> } | undefined)?.modelMap) || {}),
      },
    },
  }
}

function getLive2DModelPath() {
  const style = avatarConfig.value.outfit.style
  return avatarConfig.value.live2d?.modelMap?.[style] || avatarConfig.value.live2d?.modelUrl || LIVE2D_MODEL_PATH
}

async function initLive2D() {
  const canvas = live2dCanvas.value
  if (!canvas || !window.PIXI?.live2d?.Live2DModel) {
    avatarConfig.value.renderMode = 'svg'
    return
  }
  try {
    live2dReady.value = false
    destroyLive2D()
    const modelPath = getLive2DModelPath()
    currentLive2DModelPath = modelPath
    live2dApp = new window.PIXI.Application({
      view: canvas,
      backgroundAlpha: 0,
      width: 600,
      height: 650,
      antialias: true,
    })
    live2dModel = await window.PIXI.live2d.Live2DModel.from(modelPath, {
      autoInteract: false,
      idleMotionGroup: avatarConfig.value.live2d?.idleMotionGroup || 'Idle',
    })
    live2dModel.anchor.set(0.5, 0.4)
    live2dModel.x = live2dApp.screen.width / 2
    live2dModel.y = live2dApp.screen.height / 2
    const scale = Math.min(
      live2dApp.screen.width / live2dModel.width,
      live2dApp.screen.height / live2dModel.height,
    ) * 0.82
    live2dModel.scale.set(scale)
    live2dApp.stage.addChild(live2dModel)
    live2dMouthParamIds = await resolveLive2DMouthParams(modelPath)
    live2dReady.value = true

    // 关键修复：用 PIXI ticker 的 postrender 在模型更新后、渲染前覆盖嘴型参数
    // idle 动画每帧会把 ParamMouthOpenY 重置为 0，必须在渲染前最后一刻强制写入
    live2dApp.ticker.add(() => {
      if (!live2dMouthActive || live2dMouthParamIds.length === 0) return
      const core = live2dModel?.internalModel?.coreModel
      if (!core) return
      const value = Math.max(0, Math.min(1, live2dMouthOverride))
      for (const paramName of live2dMouthParamIds) {
        try {
          const idx = core.getParameterIndex?.(paramName)
          if (typeof idx === 'number' && idx >= 0 && core.setParameterValueByIndex) {
            core.setParameterValueByIndex(idx, value)
          } else {
            core.setParameterValueById?.(paramName, value)
          }
        } catch {
          // 忽略不匹配的参数名
        }
      }
    })

    console.log('Live2D loaded:', modelPath)
    const parameterIds = live2dModel.internalModel.coreModel.getParameterIds?.() || live2dMouthParamIds
    console.log('Live2D parameters:', parameterIds)
    console.log(
      'Live2D mouth parameters:',
      parameterIds.filter((id: string) => id.toLowerCase().includes('mouth')),
    )
    console.log('Expressions:', live2dModel.internalModel.motionManager.expressionManager?.definitions)
    setLive2DMouth(0.01)
    window.setTimeout(() => setLive2DMouth(0), 180)
  } catch (error) {
    console.warn('Live2D 加载失败，降级到 SVG:', error)
    avatarConfig.value.renderMode = 'svg'
    live2dReady.value = false
    destroyLive2D()
  }
}

async function resolveLive2DMouthParams(modelPath: string) {
  const fallback = ['ParamMouthOpenY', 'PARAM_MOUTH_OPEN_Y', 'ParamMouthOpen']
  try {
    const cdiPath = modelPath.replace(/[^/]+\.model3\.json$/, (file) => file.replace('.model3.json', '.cdi3.json'))
    const response = await fetch(cdiPath, { cache: 'no-store' })
    if (!response.ok) return fallback
    const data = await response.json()
    const params = Array.isArray(data.Parameters) ? data.Parameters : []
    const mouthIds = params
      .filter((item: { Id?: string; GroupId?: string; Name?: string }) => {
        const text = `${item.Id || ''} ${item.GroupId || ''} ${item.Name || ''}`.toLowerCase()
        return text.includes('mouth') || text.includes('口')
      })
      .map((item: { Id: string }) => item.Id)
      .filter(Boolean)
    return mouthIds.length ? mouthIds : fallback
  } catch {
    return fallback
  }
}

function destroyLive2D() {
  live2dModel = null
  live2dApp?.destroy?.(true)
  live2dApp = null
  currentLive2DModelPath = ''
  live2dMouthOverride = 0
  live2dMouthActive = false
}

function ensureAvatarImage() {
  return new Promise<void>((resolve) => {
    if (avatarConfig.value.renderMode !== 'image3d') {
      resolve()
      return
    }
    if (!avatarConfig.value.avatarImage) {
      avatarConfig.value.renderMode = 'svg'
      resolve()
      return
    }
    const image = new Image()
    image.onload = () => resolve()
    image.onerror = () => {
      avatarConfig.value.renderMode = 'svg'
      resolve()
    }
    image.src = avatarConfig.value.avatarImage
  })
}

const modeLabel = computed(() => {
  if (avatarConfig.value.renderMode === 'live2d') return live2dReady.value ? 'Live2D 数字人' : 'Live2D 加载中'
  if (avatarConfig.value.renderMode === 'image3d') return '3D 数字人'
  return 'SVG 后备模式'
})

async function askAvatar() {
  const content = question.value.trim()
  if (!content || status.value !== 'idle') return
  status.value = 'thinking'
  expression.value = 'focus'
  subtitle.value = '...'
  try {
    const stream = streamChatMessage({ message: content, conversation_id: conversationId.value, top_k: 6, fast: true })
    let fullText = ''
    let firstTtsText = ''
    let ttsPromise: Promise<void> | null = null

    /** 从已累积文本中提取第一个完整句子（以。！？\n结尾），用于提前启动 TTS */
    const extractFirstSentence = (text: string): string => {
      const match = text.match(/^[^。！？\n]*[。！？\n]/)
      if (match) return match[0]
      // 没有完整句子但文本已足够长，截取前 20 字作为首段
      if (text.length >= 20) return text.slice(0, 20)
      return ''
    }

    for await (const event of stream) {
      if (event.type === 'conversation_id') { conversationId.value = event.id; continue }
      if (event.type === 'text') {
        fullText += event.text
        subtitle.value = fullText

        // 首句就绪时立即启动 TTS（不 await，与 Chat 剩余文本生成并行）
        if (!ttsPromise && fullText.length >= 8) {
          const firstSentence = extractFirstSentence(fullText)
          if (firstSentence && firstSentence.length >= 6) {
            firstTtsText = firstSentence
            status.value = 'speaking'
            expression.value = 'smile'
            ttsPromise = speak(firstTtsText)
          }
        }
      }
      if (event.type === 'refused') {
        fullText = event.text
        subtitle.value = event.text
        continue
      }
      if (event.type === 'error') {
        fullText = event.text || '抱歉，服务暂时不可用。我是灵山胜境 AI 导游，可以为您介绍灵山大佛、九龙灌浴、灵山梵宫等景点，也可以推荐游览路线哦！'
        subtitle.value = fullText
        continue
      }
      if (event.type === 'done') { conversationId.value = event.conversation_id; continue }
    }

    // Chat 流结束后的处理
    if (!ttsPromise) {
      // 没有触发首句 TTS（拒答/短文本/错误），直接播放全部
      if (fullText) {
        status.value = 'speaking'
        expression.value = 'smile'
        await speak(fullText)
      } else {
        status.value = 'idle'
        expression.value = 'smile'
      }
    } else {
      // 等待首段 TTS 播完，然后播放剩余文本
      await ttsPromise
      const remaining = fullText.slice(firstTtsText.length).trim()
      if (remaining) {
        status.value = 'speaking'
        expression.value = 'smile'
        await speak(remaining)
      }
    }
  } catch {
    // 连接失败或异常时显示引导语，绕回景区话题
    subtitle.value = '这个问题我暂时无法回答，可能是网络波动。我是灵山胜境 AI 导游，可以为您介绍灵山大佛、九龙灌浴、灵山梵宫等景点，也可以推荐游览路线哦！'
    expression.value = 'focus'
    status.value = 'idle'
    mouthOpen.value = 0
  }
}

async function speak(text: string) {
  status.value = 'speaking'
  const cleanText = stripMarkdown(text)
  const onEnd = () => {
    status.value = 'idle'
    expression.value = 'smile'
    mouthOpen.value = 0
    setLive2DMouth(0)
    stopLipSyncTimer()
  }

  // 中止上一次的 TTS 流
  currentTtsAbort?.abort()
  const abortController = new AbortController()
  currentTtsAbort = abortController

  // 异步队列：流式到达的音频段按顺序排队播放
  const segmentQueue: Array<{ text: string; audio_base64: string }> = []
  let streamDone = false
  let streamFailed = false
  let waitingResolve: ((value: boolean) => void) | null = null

  /** 等待下一段音频就绪，返回 false 表示流已结束且队列空 */
  const waitForNextSegment = (): Promise<boolean> => {
    if (segmentQueue.length > 0) return Promise.resolve(true)
    if (streamDone || streamFailed) return Promise.resolve(false)
    return new Promise((resolve) => { waitingResolve = resolve })
  }

  const onSegmentReady = (seg: { text: string; audio_base64: string }) => {
    segmentQueue.push(seg)
    waitingResolve?.(true)
    waitingResolve = null
  }

  /** 流结束或失败时唤醒等待者 */
  const wakeWaiter = (failed: boolean) => {
    if (failed) streamFailed = true
    else streamDone = true
    waitingResolve?.(false)
    waitingResolve = null
  }

  try {
    voiceMode.value = 'edge'

    // 启动流式请求（后台运行，不阻塞播放循环）
    const streamPromise = streamSynthesizeSpeech(
      cleanText,
      avatarConfig.value.voice.voiceName,
      avatarConfig.value.voice.rate,
      onSegmentReady,
      undefined,
      abortController.signal,
    ).then(() => {
      wakeWaiter(false)
    }).catch(() => {
      wakeWaiter(true)
    })

    // 逐段播放：拿到一段播一段，播完等下一段
    while (true) {
      if (status.value !== 'speaking') {
        stopLipSyncTimer()
        onEnd()
        return
      }

      const hasMore = await waitForNextSegment()
      if (!hasMore && segmentQueue.length === 0) {
        // 流失败且没有拿到任何段 → 跳到 catch 走回退逻辑
        if (streamFailed) throw new Error('stream_failed')
        break
      }

      const seg = segmentQueue.shift()!
      await playOneSegmentWithLipSync(seg)
    }

    stopLipSyncTimer()
    onEnd()
    await streamPromise
  } catch {
    // 流式接口失败时回退到单段模式
    try {
      const audioBlob = await synthesizeSpeech(
        cleanText,
        avatarConfig.value.voice.voiceName,
        avatarConfig.value.voice.rate,
      )
      voiceMode.value = 'edge'
      await playAudioWithSyncedLip(audioBlob, cleanText, onEnd)
    } catch {
      speakBrowser(cleanText, onEnd)
    }
  }
}

// ---- 文本预处理：去除 Markdown ----
function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`{1,3}[^`]*`{1,3}/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/[-*]\s+/g, '')
    .trim()
}

// ---- 核心：基于音频真实播放进度的口型同步 ----
function precomputeMouthFrames(text: string, totalFrames: number): number[] {
  const frames: number[] = []
  const chars = text.replace(/\s/g, '').split('')
  if (chars.length === 0) return new Array(totalFrames).fill(0)

  const charsPerFrame = Math.max(1, chars.length / totalFrames)

  for (let f = 0; f < totalFrames; f++) {
    const startIdx = Math.floor(f * charsPerFrame)
    const endIdx = Math.floor((f + 1) * charsPerFrame)
    let maxOpen = 0.06
    for (let i = startIdx; i < Math.min(endIdx, chars.length); i++) {
      const ch = chars[i]
      // 标点 → 闭嘴
      if (/[，。！？、；：,.!?；：\n]/.test(ch)) { maxOpen = Math.max(maxOpen, 0.01); continue }
      // 大口元音 → 张大嘴（夸张）
      if (/[啊阿哇凹噢哦喔饿哦俄恶诶哎哀爱奥澳傲熬袄嗷坳拗]/.test(ch)) { maxOpen = Math.max(maxOpen, 0.98); continue }
      // 中口元音（张大）
      if (/[呀牙鸭雅压崖涯哑亚讶轧娅蚜氩砑伢]/i.test(ch)) { maxOpen = Math.max(maxOpen, 0.85); continue }
      // 一般开口（大幅提升）
      if (/[大那拿哪纳钠娜呐捺衲镎塔他她它踏塌榻獭挞蹋遢嗒闼哈蛤铪虾瞎匣侠峡狭暇霞辖下吓夏厦唬懗]/.test(ch)) { maxOpen = Math.max(maxOpen, 0.75); continue }
      if (/[吧把八拔坝霸罢爸扒叭巴芭疤笆粑捌茇岜灞钯魃]/.test(ch)) { maxOpen = Math.max(maxOpen, 0.70); continue }
      if (/[吗妈马骂麻码蚂玛嘛蟆杩犸嬷]/.test(ch)) { maxOpen = Math.max(maxOpen, 0.70); continue }
      if (/[啦拉辣腊蜡喇垃剌藜邋旯砬瘌]/.test(ch)) { maxOpen = Math.max(maxOpen, 0.70); continue }
      // 闭口辅音 → 适度张开
      if (/[不布步部补捕卜簿哺怖埠埔卟逋瓿晡钚醭]/.test(ch)) { maxOpen = Math.max(maxOpen, 0.30); continue }
      if (/[目木母亩幕牧墓慕穆暮牟拇募沐牡睦姆姥幂苜仫坶苜]/.test(ch)) { maxOpen = Math.max(maxOpen, 0.30); continue }
      // 默认中等偏大开口
      maxOpen = Math.max(maxOpen, 0.50)
    }
    frames.push(Math.min(1, maxOpen + (Math.random() - 0.5) * 0.08))
  }
  return frames
}

let lipSyncTimer: ReturnType<typeof setInterval> | null = null

function stopLipSyncTimer() {
  if (lipSyncTimer) { clearInterval(lipSyncTimer); lipSyncTimer = null }
  mouthOpen.value = 0
  live2dMouthOverride = 0
  live2dMouthActive = false
}

async function playAudioWithSyncedLip(audioBlob: Blob, text: string, onEnd: () => void) {
  stopSpeaking(false)
  stopLipSyncTimer()

  const url = URL.createObjectURL(audioBlob)
  const audio = new Audio(url)

  // 使用估算时长，不等 metadata
  const estimatedDuration = estimateSpeechDuration(text)
  const fps = 60
  const totalFrames = Math.max(1, Math.round(estimatedDuration * fps))
  const mouthFrames = precomputeMouthFrames(text, totalFrames)

  const onAudioEnd = () => {
    stopLipSyncTimer()
    URL.revokeObjectURL(url)
    onEnd()
  }
  audio.onended = onAudioEnd
  audio.onerror = () => {
    stopLipSyncTimer()
    URL.revokeObjectURL(url)
    speakBrowser(text, onEnd)
  }

  // 立即启动口型同步，优先使用实际时长
  lipSyncTimer = setInterval(() => {
    if (!audio || audio.paused || audio.ended) {
      if (audio?.ended) stopLipSyncTimer()
      return
    }
    const playbackTime = audio.currentTime
    const dur = (audio.duration && isFinite(audio.duration) && audio.duration > 0)
      ? audio.duration
      : estimatedDuration
    const progress = dur > 0 ? playbackTime / dur : 0
    const frameIdx = Math.min(totalFrames - 1, Math.floor(progress * totalFrames))
    const value = mouthFrames[frameIdx] || 0.15
    mouthOpen.value = value
    setLive2DMouth(value)
  }, 1000 / fps)

  audioEl = audio
  try { await audio.play() } catch { audio.onerror?.(new Event('error')) }
}

/** 播放单段音频并驱动口型同步 — 优化版：跳过 metadata 等待，立即播放 */
function playOneSegmentWithLipSync(seg: { text: string; audio_base64: string }): Promise<void> {
  const segText = seg.text
  const audioBlob = base64ToBlob(seg.audio_base64, 'audio/mpeg')
  const url = URL.createObjectURL(audioBlob)
  const audio = new Audio(url)

  // 预计算口型帧，不等 metadata
  const estimatedDuration = estimateSpeechDuration(segText)
  const fps = 60
  const totalFrames = Math.max(1, Math.round(estimatedDuration * fps))
  const mouthFrames = precomputeMouthFrames(segText, totalFrames)

  return new Promise<void>((resolve) => {
    let resolved = false
    const cleanup = () => {
      if (resolved) return
      resolved = true
      stopLipSyncTimer()
      URL.revokeObjectURL(url)
      resolve()
    }

    audio.onended = cleanup
    audio.onerror = cleanup

    // 立即启动口型同步定时器，使用估算时长
    lipSyncTimer = setInterval(() => {
      if (!audio || audio.paused || audio.ended) {
        if (audio?.ended) cleanup()
        return
      }
      const playbackTime = audio.currentTime
      // 优先使用实际时长，未知时回退到估算值
      const dur = (audio.duration && isFinite(audio.duration) && audio.duration > 0)
        ? audio.duration
        : estimatedDuration
      const progress = dur > 0 ? playbackTime / dur : 0
      const frameIdx = Math.min(totalFrames - 1, Math.floor(progress * totalFrames))
      const value = mouthFrames[frameIdx] || 0.15
      mouthOpen.value = value
      setLive2DMouth(value)
    }, 1000 / fps)

    audioEl = audio
    // 立即播放，不等 metadata — 浏览器会自动缓冲并尽快开始播放
    audio.play().catch(() => {
      // 立即播放失败（浏览器尚未准备好），等待 canplay 后再试
      audio.addEventListener('canplay', () => {
        audio.play().catch(cleanup)
      }, { once: true })
      // 超时保护：2s 后仍未播放则放弃
      setTimeout(cleanup, 2000)
    })
  })
}

function estimateSpeechDuration(text: string): number {
  const chars = text.replace(/\s/g, '').length
  return Math.max(2, chars * 0.22 + 1.5)
}

function speakBrowser(text: string, cb: () => void, showWarning = true) {
  stopSpeaking(false)
  stopLipSyncTimer()
  if (!window.speechSynthesis) {
    voiceMode.value = 'text'
    ElMessage.warning('后端语音不可用，当前浏览器也不支持语音合成，已保留文字展示')
    cb()
    return
  }
  voiceMode.value = 'browser'
  if (showWarning) {
    ElMessage.warning('后端 Edge TTS 不可用，已临时回退浏览器语音')
  }
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1
  utterance.pitch = 1.08

  // 用文本预计算口型帧，估算时长
  const duration = estimateSpeechDuration(text)
  const totalFrames = Math.max(1, Math.round(duration * 60))
  const mouthFrames = precomputeMouthFrames(text, totalFrames)

  const startedAt = performance.now()
  lipSyncTimer = setInterval(() => {
    if (status.value !== 'speaking') { stopLipSyncTimer(); return }
    const elapsed = (performance.now() - startedAt) / 1000
    const progress = Math.min(1, elapsed / duration)
    const frameIdx = Math.min(totalFrames - 1, Math.floor(progress * totalFrames))
    const value = mouthFrames[frameIdx] || 0.15
    mouthOpen.value = value
    setLive2DMouth(value)
  }, 1000 / 60) // 60fps

  utterance.onstart = () => { /* 已通过定时器驱动 */ }
  utterance.onend = () => { stopLipSyncTimer(); cb() }
  utterance.onerror = () => { stopLipSyncTimer(); cb() }
  window.speechSynthesis.speak(utterance)
}

function stopSpeaking(resetStatus = true) {
  currentTtsAbort?.abort()
  currentTtsAbort = null
  window.speechSynthesis?.cancel()
  stopLipSyncTimer()
  audioEl?.pause()
  audioEl = null
  releaseAudioUrl()
  mouthOpen.value = 0
  setLive2DMouth(0)
  if (resetStatus) {
    status.value = 'idle'
    expression.value = 'smile'
  }
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
      await recognizeRecording()
    }
    mediaRecorder.value = recorder
    recorder.start()
    recording.value = true
  } catch {
    await recognizeWithBrowserSpeech()
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
    if (result.text?.trim()) {
      question.value = result.text.trim()
      await askAvatar()
    } else {
      ElMessage.warning('没有识别到有效语音')
    }
  } catch {
    await recognizeWithBrowserSpeech()
  } finally {
    recognizing.value = false
    audioChunks.value = []
  }
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
    recognition.onresult = async (event) => {
      const text = event.results?.[0]?.[0]?.transcript || ''
      if (text.trim()) {
        question.value = text.trim()
        await askAvatar()
      }
      resolve()
    }
    recognition.onerror = () => resolve()
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

function pickMimeType() {
  if (!window.MediaRecorder) return ''
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus'
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm'
  if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4'
  if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) return 'audio/ogg;codecs=opus'
  return ''
}

function switchExpression(next: AvatarExpression) {
  expression.value = next
  const expressionName = LIVE2D_EXPRESSION_MAP[next]
  live2dModel?.internalModel?.motionManager?.expressionManager?.setExpression?.(expressionName)
}

function releaseAudioUrl() {
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl)
    currentAudioUrl = ''
  }
}

function setLive2DMouth(value: number) {
  // 不直接设置参数 — 模型 update 会覆盖
  // 改为写入覆盖变量，由 internalModel.update 拦截器在模型更新后强制写入
  live2dMouthOverride = value
  live2dMouthActive = value > 0.001
}

onBeforeUnmount(() => {
  stopSpeaking()
  destroyLive2D()
})
</script>

<template>
  <main class="page">
    <section class="top">
      <div>
        <p class="badge">Live · 景区导览</p>
        <h1>灵山胜境 · AI 数字人导游</h1>
      </div>
      <nav>
        <RouterLink to="/chat">文本对话</RouterLink>
        <RouterLink to="/routes">路线推荐</RouterLink>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </section>

    <section class="stage">
      <div class="card avatar-card" :class="[status, expression]" :style="avatarVars">
        <div class="golden-aura"></div>
        <div class="golden-aura inner"></div>
        <div class="soft-orb purple"></div>
        <div class="soft-orb amber"></div>

        <div v-if="avatarConfig.renderMode === 'live2d'" class="avatar-shell live2d-shell" aria-label="Live2D AI 数字人导游">
          <div class="canvas-wrap">
            <canvas ref="live2dCanvas" class="live2d-canvas"></canvas>
            <div v-if="!live2dReady" class="live2d-loading">Live2D 加载中...</div>
          </div>
          <div class="avatar-name">{{ avatarConfig.name }} · Live2D 导游</div>
        </div>

        <div
          v-else-if="avatarConfig.renderMode === 'image3d'"
          class="avatar-shell image3d-shell"
          aria-label="AI 数字人导游"
        >
          <div class="portrait-wrap">
            <span class="portrait-glow"></span>
            <span class="breath-highlight"></span>
            <span class="hair-flow left"></span>
            <span class="hair-flow right"></span>
            <span class="eye-cover left"></span>
            <span class="eye-cover right"></span>
            <span class="iris-shine left"></span>
            <span class="iris-shine right"></span>
            <span class="mouth-overlay"></span>
            <span class="smile-overlay"></span>
            <span class="expression-aura"></span>
            <span v-if="avatarConfig.accessories.haloPin" class="lotus-pin">✦</span>
            <span v-if="avatarConfig.accessories.glasses" class="glasses-overlay"></span>
          </div>
          <div class="avatar-name">{{ avatarConfig.name }} · AI 导游</div>
        </div>
        <div v-else class="avatar-shell svg-fallback" aria-label="AI 数字人导游后备形象">
          <div class="fallback-head">
            <span class="fallback-eye left"></span>
            <span class="fallback-eye right"></span>
            <span class="fallback-mouth"></span>
          </div>
          <div class="fallback-body"></div>
          <div class="avatar-name">{{ avatarConfig.name }} · AI 导游</div>
        </div>

        <div class="expression-switcher">
          <button :class="{ active: expression === 'smile' }" @click="switchExpression('smile')">微笑</button>
          <button :class="{ active: expression === 'focus' }" @click="switchExpression('focus')">专注</button>
          <button :class="{ active: expression === 'surprised' }" @click="switchExpression('surprised')">惊喜</button>
        </div>

        <div class="status-bar">
          <span>{{ status === 'thinking' ? '检索中...' : status === 'speaking' ? '讲解中 ♪' : '待命中' }}</span>
          <small>{{ modeLabel }} · {{ voiceMode === 'edge' ? '晓晓自然女声' : voiceMode === 'browser' ? '浏览器兜底声线' : '仅文字' }}</small>
        </div>
      </div>

      <div class="card ctrl">
        <h2>向数字人提问</h2>
        <div class="bubble">{{ subtitle }}</div>
        <textarea v-model="question" rows="3" placeholder="比如：灵山大佛有多高？拈花湾适合亲子游吗？" />
        <div class="btns">
          <button :disabled="status !== 'idle'" @click="askAvatar">
            {{ status === 'idle' ? '提问并播报' : status === 'thinking' ? '思考中...' : '回答中...' }}
          </button>
          <button class="voice" :disabled="status !== 'idle' || recognizing" @click="toggleRecording">
            {{ recording ? '停止录音' : recognizing ? '识别中...' : '语音提问' }}
          </button>
          <button class="ghost" @click="stopSpeaking()">停止</button>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24px;
  color: #fff;
  background:
    radial-gradient(ellipse at 30% 20%, rgb(251 191 36 / 10%) 0%, transparent 55%),
    linear-gradient(160deg, #0f172a 0%, #1c1917 100%);
}

.top {
  max-width: 1120px;
  margin: 0 auto 28px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}

.badge {
  margin: 0 0 6px;
  color: #f4c27a;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 2px;
}

h1 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
}

nav {
  display: flex;
  gap: 16px;
}

nav a {
  color: #fde68a;
  text-decoration: none;
  font-size: 14px;
}

.stage {
  max-width: 1120px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 24px;
  align-items: start;
}

.card {
  border: 1px solid rgb(255 255 255 / 12%);
  border-radius: 24px;
  background: rgb(255 255 255 / 6%);
  backdrop-filter: blur(20px);
  box-shadow: 0 20px 60px rgb(0 0 0 / 30%);
}

.avatar-card {
  position: relative;
  min-height: 620px;
  perspective: 1200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.golden-aura {
  position: absolute;
  width: 430px;
  height: 430px;
  top: 34px;
  border-radius: 50%;
  background:
    radial-gradient(circle, transparent 46%, rgb(251 191 36 / 36%) 47% 49%, transparent 50%),
    radial-gradient(circle, rgb(251 191 36 / 22%), transparent 64%);
  animation: auraPulse 4.8s ease-in-out infinite;
}

.golden-aura.inner {
  width: 300px;
  height: 300px;
  top: 98px;
  opacity: 0.75;
  animation-delay: -1.4s;
}

.soft-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(1px);
}

.soft-orb.purple {
  width: 220px;
  height: 220px;
  right: 42px;
  bottom: 80px;
  background: radial-gradient(circle, rgb(192 132 252 / 16%), transparent 64%);
}

.soft-orb.amber {
  width: 180px;
  height: 180px;
  left: 52px;
  bottom: 52px;
  background: radial-gradient(circle, rgb(245 158 11 / 16%), transparent 66%);
}

.avatar-shell {
  position: relative;
  z-index: 2;
  width: min(500px, 94%);
  transform-style: preserve-3d;
  animation: avatarFloat3d 4s ease-in-out infinite;
}

.live2d-shell {
  width: min(560px, 96%);
}

.canvas-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 12 / 13;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 28px;
  background:
    radial-gradient(circle at 50% 20%, rgb(253 230 138 / 0.16), transparent 45%),
    linear-gradient(180deg, rgb(15 23 42 / 0.24), rgb(15 23 42 / 0.08));
  box-shadow:
    0 30px 80px rgb(0 0 0 / 0.34),
    inset 0 0 0 1px rgb(253 230 138 / 0.18);
}

.live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.live2d-loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fde68a;
  background: rgb(15 23 42 / 0.32);
  font-weight: 800;
}

.portrait-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 28px;
  transform-origin: 50% 65%;
  transform: rotateX(2deg) rotateY(-4deg);
  animation: breathe 3.2s ease-in-out infinite;
  box-shadow:
    0 30px 80px rgb(0 0 0 / 0.36),
    inset 0 0 0 1px rgb(253 230 138 / 0.16);
}

.portrait-wrap::before {
  content: '';
  position: absolute;
  z-index: 0;
  left: 16%;
  right: 16%;
  bottom: 2%;
  height: 13%;
  border-radius: 50%;
  background: radial-gradient(ellipse, rgb(251 191 36 / 0.28), rgb(0 0 0 / 0.24) 60%, transparent 72%);
  filter: blur(8px);
  transform: translateZ(-30px);
}

.portrait-wrap::after {
  content: '';
  position: absolute;
  z-index: 5;
  right: 0;
  bottom: 0;
  width: 90px;
  height: 34px;
  background: linear-gradient(135deg, transparent, #1b2544 40%, #141c35);
  opacity: 0.92;
  border-top-left-radius: 28px;
}

.avatar-portrait {
  position: relative;
  z-index: 2;
  width: 106%;
  height: 106%;
  object-fit: cover;
  object-position: center center;
  transform: translateY(-1%) translateZ(36px);
  filter:
    drop-shadow(0 28px 36px rgb(0 0 0 / 0.34))
    saturate(1.08)
    contrast(1.03);
  user-select: none;
  pointer-events: none;
}

.portrait-glow,
.breath-highlight,
.expression-aura,
.hair-flow,
.eye-cover,
.iris-shine,
.mouth-overlay,
.smile-overlay,
.lotus-pin,
.glasses-overlay {
  position: absolute;
  z-index: 3;
  pointer-events: none;
}

.portrait-glow {
  inset: 7% 10% 2%;
  z-index: 1;
  border-radius: 44% 44% 36% 36%;
  background: radial-gradient(circle at 52% 22%, rgb(253 230 138 / 0.22), transparent 44%);
  filter: blur(18px);
}

.breath-highlight {
  left: 23%;
  top: 38%;
  width: 54%;
  height: 37%;
  border-radius: 45%;
  background: linear-gradient(100deg, transparent, rgb(255 255 255 / 0.08), transparent);
  mix-blend-mode: screen;
  animation: clothShimmer 4.6s ease-in-out infinite;
}

.hair-flow {
  top: 20%;
  width: 27%;
  height: 45%;
  border-radius: 50%;
  border-top: 2px solid rgb(255 255 255 / 0.16);
  filter: blur(0.4px);
  animation: hairFloat 3.8s ease-in-out infinite;
}

.hair-flow.left {
  left: 10%;
  rotate: 17deg;
}

.hair-flow.right {
  right: 10%;
  rotate: -17deg;
  animation-delay: -1.2s;
}

.eye-cover {
  left: var(--left-eye-left);
  top: var(--left-eye-top);
  width: var(--eye-width);
  height: 0%;
  border-radius: 999px;
  background: linear-gradient(180deg, #27151b 0 18%, #f7c8b5 42%, #ffd8c8 100%);
  opacity: 0.98;
  transform-origin: 50% 0;
  animation: blink3d 4.8s ease-in-out infinite;
  box-shadow: inset 0 -2px 3px rgb(0 0 0 / 0.12);
}

.eye-cover.left {
  left: var(--left-eye-left);
}

.eye-cover.right {
  left: var(--right-eye-left);
}

.focus .eye-cover {
  top: var(--left-eye-top);
}

.surprised .eye-cover {
  opacity: 0;
}

.iris-shine {
  top: calc(var(--left-eye-y) - 0.2%);
  width: 2.1%;
  height: 2.1%;
  border-radius: 50%;
  background: rgb(255 255 255 / 0.82);
  box-shadow: 0 0 8px rgb(255 255 255 / 0.65);
  animation: eyeSpark 2.8s ease-in-out infinite;
}

.iris-shine.left {
  left: calc(var(--left-eye-x) + 1.6%);
}

.iris-shine.right {
  left: calc(var(--right-eye-x) + 1.6%);
}

.mouth-overlay {
  left: var(--mouth-left);
  top: var(--mouth-top);
  width: var(--mouth-width);
  height: calc(0.35% + var(--mouth-scale) * var(--mouth-height));
  border-radius: 46% 46% 50% 50%;
  background: radial-gradient(circle at 50% 24%, #ff9ead, #b31945 55%, #4d071a);
  transform: scaleY(var(--mouth-scale));
  transform-origin: 50% 45%;
  opacity: 0;
  transition: height 40ms linear, opacity 50ms ease;
  box-shadow: inset 0 -2px 3px rgb(0 0 0 / 0.35);
}

.speaking .mouth-overlay {
  opacity: 0.96;
}

.smile-overlay {
  left: var(--smile-left);
  top: var(--smile-top);
  width: calc(var(--mouth-width) * 1.12);
  height: 2.8%;
  border-bottom: 2px solid rgb(157 45 67 / 0.55);
  border-radius: 0 0 999px 999px;
  opacity: 0.75;
}

.speaking .smile-overlay {
  opacity: 0;
}

.expression-aura {
  inset: 8% 20% 48%;
  z-index: 1;
  border-radius: 50%;
  background: radial-gradient(circle, rgb(253 230 138 / 0.16), transparent 62%);
  opacity: 0;
  transition: opacity 180ms ease;
}

.smile .expression-aura {
  opacity: 0.55;
}

.focus .expression-aura {
  background: radial-gradient(circle, rgb(96 165 250 / 0.22), transparent 62%);
  opacity: 0.75;
}

.surprised .expression-aura {
  background: radial-gradient(circle, rgb(244 114 182 / 0.26), transparent 62%);
  opacity: 0.9;
}

.lotus-pin {
  right: 19%;
  top: 19%;
  color: var(--cloth-accent);
  font-size: 28px;
  text-shadow: 0 0 10px rgb(253 230 138 / 0.75);
  animation: accessorySwing 4.2s ease-in-out infinite;
}

.glasses-overlay {
  left: 31.8%;
  top: 29.2%;
  width: 36%;
  height: 8.4%;
  border: 2px solid rgb(253 230 138 / 0.82);
  border-left-width: 0;
  border-right-width: 0;
  border-radius: 999px;
  box-shadow:
    inset 14px 0 0 -12px rgb(253 230 138 / 0.92),
    inset -14px 0 0 -12px rgb(253 230 138 / 0.92);
}

.svg-fallback {
  width: 320px;
  height: 430px;
  display: grid;
  place-items: center;
}

.fallback-head {
  position: relative;
  width: 190px;
  height: 190px;
  border-radius: 48% 48% 46% 46%;
  background: radial-gradient(circle at 50% 34%, #ffd9bf, #e8ad8f);
  box-shadow: 0 26px 48px rgb(0 0 0 / 0.26);
}

.fallback-head::before {
  content: '';
  position: absolute;
  inset: -28px -22px 92px;
  border-radius: 52% 52% 28% 28%;
  background: linear-gradient(135deg, var(--hair), var(--hair-shade));
}

.fallback-eye {
  position: absolute;
  top: 76px;
  width: 28px;
  height: 32px;
  border-radius: 50%;
  background: var(--eye);
  animation: blink3d 4.8s ease-in-out infinite;
}

.fallback-eye.left {
  left: 48px;
}

.fallback-eye.right {
  right: 48px;
}

.fallback-mouth {
  position: absolute;
  left: 50%;
  top: 128px;
  width: 26px;
  height: calc(6px + var(--mouth-scale) * 22px);
  border-radius: 50%;
  background: #9f1239;
  transform: translateX(-50%) scaleY(var(--mouth-scale));
  opacity: 0.85;
}

.fallback-body {
  width: 220px;
  height: 210px;
  margin-top: -40px;
  border-radius: 34px 34px 22px 22px;
  background: linear-gradient(135deg, var(--cloth-primary), var(--cloth-secondary));
  box-shadow: inset 0 0 0 6px rgb(253 230 138 / 0.18);
}

.avatar-name {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  padding: 7px 18px;
  border: 1px solid rgb(253 230 138 / 45%);
  border-radius: 999px;
  color: #713f12;
  background: linear-gradient(180deg, #fde68a, #f59e0b);
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
  box-shadow: 0 12px 28px rgb(0 0 0 / 24%);
}

.expression-switcher {
  position: absolute;
  z-index: 3;
  left: 24px;
  bottom: 58px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.expression-switcher button {
  height: 30px;
  padding: 0 10px;
  border: 1px solid rgb(253 230 138 / 28%);
  border-radius: 999px;
  color: #fde68a;
  background: rgb(255 255 255 / 8%);
  font-size: 12px;
}

.expression-switcher button.active {
  color: #111827;
  background: #fde68a;
}

.status-bar {
  position: absolute;
  z-index: 3;
  right: 24px;
  bottom: 24px;
  display: grid;
  gap: 4px;
  justify-items: end;
  color: #fde68a;
  font-size: 13px;
}

.status-bar small {
  color: rgb(255 255 255 / 58%);
}

.ctrl {
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ctrl h2 {
  margin: 0;
  font-size: 1.1rem;
}

.bubble {
  min-height: 160px;
  max-height: 300px;
  padding: 14px;
  border-radius: 16px;
  background: rgb(0 0 0 / 25%);
  line-height: 1.75;
  font-size: 14px;
  white-space: pre-wrap;
  overflow-y: auto;
}

textarea {
  width: 100%;
  resize: none;
  box-sizing: border-box;
  border: 1px solid rgb(255 255 255 / 18%);
  border-radius: 14px;
  padding: 12px;
  color: #fff;
  background: rgb(255 255 255 / 8%);
  font: inherit;
  font-size: 14px;
}

.btns {
  display: grid;
  grid-template-columns: 1fr 80px;
  gap: 10px;
}

button {
  height: 42px;
  border: 0;
  border-radius: 12px;
  color: #111827;
  background: #f59e0b;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

button:disabled {
  background: #64748b;
  cursor: not-allowed;
}

.ghost {
  color: #fff;
  background: rgb(255 255 255 / 14%);
}

@keyframes avatarFloat3d {
  0%,
  100% {
    transform: translateY(0) rotateX(0deg) rotateY(0deg);
  }
  50% {
    transform: translateY(-12px) rotateX(1.5deg) rotateY(-2deg);
  }
}

@keyframes breathe {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.018);
  }
}

@keyframes blink {
  0%,
  92%,
  100% {
    transform: scaleY(1);
  }
  95% {
    transform: scaleY(0.08);
  }
}

@keyframes blink3d {
  0%,
  91%,
  100% {
    height: 0%;
  }
  94%,
  96% {
    height: 4.5%;
  }
}

@keyframes hairFloat {
  0%,
  100% {
    transform: translateY(0) rotate(0deg);
    opacity: 0.55;
  }
  50% {
    transform: translateY(-8px) rotate(2deg);
    opacity: 0.85;
  }
}

@keyframes clothShimmer {
  0%,
  100% {
    opacity: 0.2;
    transform: translateX(-12px);
  }
  50% {
    opacity: 0.7;
    transform: translateX(12px);
  }
}

@keyframes eyeSpark {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.14);
  }
}

@keyframes driftLeft {
  0%,
  100% {
    transform: rotate(0deg);
  }
  50% {
    transform: rotate(-2.5deg);
  }
}

@keyframes driftRight {
  0%,
  100% {
    transform: rotate(0deg);
  }
  50% {
    transform: rotate(2.5deg);
  }
}

@keyframes accessorySwing {
  0%,
  100% {
    transform: rotate(0deg);
  }
  50% {
    transform: rotate(4deg);
  }
}

@keyframes auraPulse {
  0%,
  100% {
    opacity: 0.72;
    transform: scale(0.98);
  }
  50% {
    opacity: 1;
    transform: scale(1.04);
  }
}

@media (max-width: 860px) {
  .stage {
    grid-template-columns: 1fr;
  }

  .avatar-card {
    min-height: 540px;
  }
}
</style>
