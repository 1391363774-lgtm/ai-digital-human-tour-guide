export interface ChatSource {
  content: string
  score: number
  metadata: Record<string, unknown>
}

export interface ChatResponse {
  answer: string
  provider: string
  model: string
  conversation_id: number | null
  sources: ChatSource[]
  refused: boolean
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: ChatSource[]
  provider?: string
  model?: string
  refused?: boolean
}
