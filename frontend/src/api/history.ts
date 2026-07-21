import { apiClient, unwrap } from './client'

export interface HistoryMessage {
  id: number
  role: string
  content: string
  latency_ms: number
  created_at: string
}

export interface ConversationSummary {
  id: number
  title: string | null
  channel: string
  total_latency_ms: number
  started_at: string
  message_count: number
}

export interface ConversationDetail extends Omit<ConversationSummary, 'message_count'> {
  messages: HistoryMessage[]
}

export function listHistory() {
  return unwrap<ConversationSummary[]>(apiClient.get('/api/history'))
}

export function getHistoryDetail(id: number) {
  return unwrap<ConversationDetail>(apiClient.get(`/api/history/${id}`))
}
