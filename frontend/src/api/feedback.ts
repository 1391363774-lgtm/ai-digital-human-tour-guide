import { apiClient, unwrap } from './client'

export interface FeedbackPayload {
  conversation_id?: number | null
  rating?: number | null
  sentiment?: string | null
  content?: string | null
}

export interface Feedback {
  id: number
  user_id: number | null
  conversation_id: number | null
  rating: number | null
  sentiment: string | null
  content: string | null
  created_at: string
}

export interface FeedbackAnalysis {
  sentiment: string
  satisfaction_score: number
  priority: string
  reason: string
}

export interface FeedbackAttentionItem {
  id: number
  rating: number | null
  sentiment: string
  satisfaction_score: number
  priority: string
  content: string | null
  created_at: string
}

export interface FeedbackStats {
  total: number
  average_rating: number
  average_satisfaction: number
  sentiment_counts: Record<string, number>
  priority_counts: Record<string, number>
  latest_at: string | null
  attention_items: FeedbackAttentionItem[]
}

export function submitFeedback(payload: FeedbackPayload) {
  return unwrap<Feedback>(apiClient.post('/api/feedback', payload))
}

export function listFeedback() {
  return unwrap<Feedback[]>(apiClient.get('/api/feedback'))
}

export function analyzeFeedback(payload: Pick<FeedbackPayload, 'rating' | 'content'>) {
  return unwrap<FeedbackAnalysis>(apiClient.post('/api/feedback/analyze', payload))
}

export function getFeedbackStats() {
  return unwrap<FeedbackStats>(apiClient.get('/api/feedback/stats'))
}
