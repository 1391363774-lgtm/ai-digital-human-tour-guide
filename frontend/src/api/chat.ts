import { apiClient, unwrap } from './client'
import type { ChatResponse } from '../types/chat'

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
export async function* streamChatMessage(payload: SendChatMessagePayload) {
  const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  const response = await fetch(`${baseURL}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: payload.message,
      conversation_id: payload.conversation_id ?? null,
      top_k: payload.top_k ?? 5,
      ...(payload.fast !== undefined && { fast: payload.fast }),
    }),
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`流式请求失败：${response.status} ${err}`)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed.startsWith('data: ')) {
        try {
          yield JSON.parse(trimmed.slice(6))
        } catch { /* skip parse errors */ }
      }
    }
  }
}
