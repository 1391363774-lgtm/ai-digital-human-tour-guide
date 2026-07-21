import { apiClient, unwrap } from './client'
import type { RouteRecommendResponse } from '../types/route'

export interface RouteRecommendPayload {
  interest: string
  duration_hours: number
  group_type: string
}

export function recommendRoute(payload: RouteRecommendPayload) {
  return unwrap<RouteRecommendResponse>(apiClient.post('/api/routes/recommend', payload))
}
