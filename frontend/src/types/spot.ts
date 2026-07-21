export interface ScenicSpot {
  id: number
  code: string
  name: string
  scenic_area: string
  location: string | null
  category: string | null
  parameters: string | null
  core_function: string | null
  cultural_meaning: string | null
  description: string | null
  highlights: string | null
  open_info: string | null
  remarks: string | null
  recommended_duration_minutes: number | null
  latitude: number | null
  longitude: number | null
}

export type ScenicSpotPayload = Omit<ScenicSpot, 'id'>
