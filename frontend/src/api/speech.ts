import { apiClient, unwrap } from './client'
import { readLines } from './stream'

export interface AsrResponse {
  text: string
  language: string | null
  duration: number | null
  segments: Array<{ start: number; end: number; text: string }>
}

export function transcribeAudio(file: Blob, signal?: AbortSignal) {
  const formData = new FormData()
  formData.append('file', file, `recording.${audioExtension(file.type)}`)
  return unwrap<AsrResponse>(
    apiClient.post('/api/speech/asr', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
      signal,
    }),
  )
}

function audioExtension(mimeType: string) {
  if (mimeType.includes('mp4')) return 'mp4'
  if (mimeType.includes('ogg')) return 'ogg'
  if (mimeType.includes('mpeg')) return 'mp3'
  if (mimeType.includes('wav')) return 'wav'
  return 'webm'
}

export interface TtsPayload {
  text: string
  voice?: string
  rate?: number
  request_id?: string
  segment_id?: string
}

export async function synthesizeSpeech(
  text: string, voice = 'zh-CN-XiaoxiaoNeural', rate = 1,
  signal?: AbortSignal, ids?: { request_id: string; segment_id: string },
) {
  const response = await apiClient.post<Blob>(
    '/api/speech/tts',
    { text, voice, rate, ...ids } satisfies TtsPayload,
    {
      responseType: 'blob',
      timeout: 30000,
      signal,
    },
  )
  const contentType = String(response.headers['content-type'] || '')
  if (!contentType.includes('audio/')) {
    throw new Error('后端未返回有效音频')
  }
  if (!response.data.size || response.data.size > 4 * 1024 * 1024) throw new Error('音频为空或超出单段限制')
  return response.data
}

export interface TtsSegment {
  text: string
  audio_base64: string
  size: number
}

export interface TtsSegmentResult {
  segments: TtsSegment[]
  total_segments: number
}

/** 分段 TTS：后端将文本切分后并行合成，返回每段的 base64 MP3 */
export async function synthesizeSpeechSegments(
  text: string,
  voice = 'zh-CN-XiaoxiaoNeural',
  rate = 1,
): Promise<TtsSegmentResult> {
  const data = await unwrap<TtsSegmentResult>(
    apiClient.post(
      '/api/speech/tts/segments',
      { text, voice, rate } satisfies TtsPayload,
      { timeout: 120000 },
    ),
  )
  return data
}

/**
 * 流式分段 TTS：通过 NDJSON 流逐段返回音频。
 * 第一段合成后立即返回，前端可立即播放；后续段并行合成后按顺序返回。
 *
 * onSegment 回调在每段音频就绪时被调用。
 * onMeta 回调在收到元信息（总段数）时被调用。
 */
export async function streamSynthesizeSpeech(
  text: string,
  voice: string,
  rate: number,
  onSegment: (seg: TtsSegment, index: number) => void,
  onMeta?: (totalSegments: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const response = await fetch(`${baseURL}/api/speech/tts/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice, rate }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`流式 TTS 请求失败: ${response.status}`)
  }

  let total: number | null = null
  let next = 0
  for await (const line of readLines(response, signal)) {
    if (!line.trim()) continue
    const msg = JSON.parse(line)
    if (msg.type === 'meta') {
      if (total !== null || !Number.isInteger(msg.total_segments) || msg.total_segments < 1 || msg.total_segments > 3000) throw new Error('无效语音段总数')
      total = msg.total_segments
      onMeta?.(total!)
    } else if (msg.type === 'segment') {
      if (total === null || msg.index !== next || next >= total || typeof msg.text !== 'string' ||
        !msg.text.trim() || typeof msg.audio_base64 !== 'string' || !msg.audio_base64 || msg.audio_base64.length > 5_600_000) {
        throw new Error('语音段重复、乱序或格式错误')
      }
      onSegment({ text: msg.text, audio_base64: msg.audio_base64, size: msg.size }, next++)
    } else if (msg.type === 'error') throw new Error('语音合成未完成，已保留文字')
    else if (msg.type === 'done') {
      if (total === null || next !== total || msg.total_segments !== total) throw new Error('语音段缺失')
      return
    } else throw new Error('未知语音流事件')
  }
  throw new Error('语音连接提前关闭：缺少 done')
}

/** base64 转 Blob */
export function base64ToBlob(b64: string, mimeType = 'audio/mpeg'): Blob {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return new Blob([bytes], { type: mimeType })
}
