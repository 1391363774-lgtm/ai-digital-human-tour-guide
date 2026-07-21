export interface RouteSpot {
  spot_id: number
  name: string
  category: string | null
  stay_minutes: number
  explanation: string
  highlights: string | null
}

export interface RouteRecommendResponse {
  recommendation_id: number | null
  interest: string
  duration_hours: number
  group_type: string
  reason: string
  spots: RouteSpot[]
}
