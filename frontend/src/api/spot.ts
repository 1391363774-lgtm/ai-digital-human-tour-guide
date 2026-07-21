import { apiClient, unwrap } from './client'
import type { ScenicSpot, ScenicSpotPayload } from '../types/spot'

export function listSpots(keyword = '') {
  return unwrap<ScenicSpot[]>(apiClient.get('/api/spots', { params: { keyword } }))
}

export function createSpot(payload: ScenicSpotPayload) {
  return unwrap<ScenicSpot>(apiClient.post('/api/admin/spots', payload))
}

export function updateSpot(id: number, payload: Partial<ScenicSpotPayload>) {
  return unwrap<ScenicSpot>(apiClient.put(`/api/admin/spots/${id}`, payload))
}

export function deleteSpot(id: number) {
  return unwrap<{ deleted: boolean }>(apiClient.delete(`/api/admin/spots/${id}`))
}
