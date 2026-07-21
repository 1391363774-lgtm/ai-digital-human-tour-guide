import { apiClient, unwrap } from './client'

export interface DashboardMetric {
  label: string
  value: number
  unit: string | null
}

export interface DashboardOverview {
  metrics: DashboardMetric[]
  event_type_counts: Record<string, number>
  feedback_sentiment_counts: Record<string, number>
  favorite_type_counts: Record<string, number>
  knowledge_status_counts: Record<string, number>
  top_spot_counts: Record<string, number>
  average_rating: number
  average_satisfaction: number
  average_latency_ms: number
  average_duration_seconds: number
  today_visitors: number
  week_visitors: number
  questions_trend: Array<{ date: string; count: number }>
  top_questions: Array<{ question: string; count: number }>
  daily_satisfaction: Array<{ date: string; score: number }>
  word_cloud: Array<{ word: string; count: number }>
}

export function getDashboardOverview(params?: { start_date?: string; end_date?: string }) {
  return unwrap<DashboardOverview>(apiClient.get('/api/dashboard/overview', { params }))
}
