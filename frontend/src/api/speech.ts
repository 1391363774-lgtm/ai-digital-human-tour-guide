import { apiClient, unwrap } from './client'

export interface AsrResponse {
  text: string
  language: string | null
  duration: number | null
  segments: Array<{ start: number; end: number; text: string }>
}

export function transcribeAudio(file: Blob) {
  const formData = new FormData()
  formData.append('file', file, `recording.${audioExtension(file.type)}`)
  return unwrap<AsrResponse>(
    apiClient.post('/api/speech/asr', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
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
}

export async function synthesizeSpeech(text: string, voice = 'zh-CN-XiaoxiaoNeural', rate = 1) {
  const response = await apiClient.post<Blob>(
    '/api/speech/tts',
    { text, voice, rate } satisfies TtsPayload,
    {
      responseType: 'blob',
      timeout: 120000,
    },
  )
  const contentType = String(response.headers['content-type'] || '')
  if (!contentType.includes('audio/')) {
    throw new Error('后端未返回有效音频')
  }
  return response.data
}
