import { apiClient, unwrap } from './client'
import type { ChatResponse } from '../types/chat'
import { readSseData } from './stream'
import { visitorHeaders } from './access'
import type { ChatSource } from '../types/chat'

type Outcome = 'completed' | 'partial' | 'failed' | 'refused' | 'cancelled'
export type ChatEvent = (
  | { type: 'conversation_id'; id: number }
  | { type: 'text' | 'refused'; text: string }
  | { type: 'source'; sources: ChatSource[] }
  | { type: 'error'; text: string; code?: string; partial?: boolean; retryable?: boolean }
  | { type: 'done'; conversation_id: number; status?: Outcome; first_text_ms?: number | null; total_ms?: number; provider?: string | null; model?: string | null; fallback_from?: string[] }
) & { request_id?: string }

function parseEvent(value: unknown): ChatEvent {
  if (!value || typeof value !== 'object') throw new Error('无效 SSE 事件')
  const event = value as Record<string, unknown>
  const valid = ['text', 'refused', 'error'].includes(String(event.type)) ? typeof event.text === 'string'
    : event.type === 'conversation_id' ? Number.isInteger(event.id)
    : event.type === 'source' ? Array.isArray(event.sources) && event.sources.every(s => s && typeof s.content === 'string' && typeof s.score === 'number' && typeof s.metadata === 'object')
    : event.type === 'done' ? Number.isInteger(event.conversation_id)
    : false
  if (!valid || (event.request_id !== undefined && typeof event.request_id !== 'string')) throw new Error('无效 SSE 事件字段')
  return event as ChatEvent
}

export interface SendChatMessagePayload {
  message: string
  conversation_id?: number | null
  top_k?: number
  fast?: boolean
}

export function sendChatMessage(payload: SendChatMessagePayload) {
  return unwrap<ChatResponse>(apiClient.post('/api/chat/messages', payload))
}

/** 流式 SSE 聊天，返回 AsyncGenerator，每次 yield { type, text, id, ... } */
export async function* streamChatMessage(payload: SendChatMessagePayload, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const response = await fetch(`${baseURL}/api/chat/stream`, {
    method: 'POST',
    signal,
    headers: { 'Content-Type': 'application/json', ...visitorHeaders() },
    body: JSON.stringify({
      message: payload.message,
      conversation_id: payload.conversation_id ?? null,
      top_k: payload.top_k ?? 5,
      ...(payload.fast !== undefined && { fast: payload.fast }),
    }),
  })

  if (!response.ok) {
    await response.body?.cancel()
    throw new Error(`流式请求失败：${response.status}`)
  }

  let requestId: string | undefined
  for await (const value of readSseData(response, signal)) {
    const event = parseEvent(value)
    if (requestId && event.request_id !== requestId) throw new Error('SSE request_id 不一致')
    requestId ??= event.request_id
    yield event
    if (event.type === 'done') return
  }
  throw new Error('连接提前关闭：未收到 done，回答可能不完整')
}
