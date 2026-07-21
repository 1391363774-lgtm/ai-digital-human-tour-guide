import { apiClient, unwrap } from './client'

export interface Favorite {
  id: number
  user_id: number
  target_type: string
  target_id: number
  created_at: string
}

export function addFavorite(target_type: string, target_id: number) {
  return unwrap<Favorite>(apiClient.post('/api/favorites', { target_type, target_id }))
}

export function listFavorites() {
  return unwrap<Favorite[]>(apiClient.get('/api/favorites'))
}

export function removeFavorite(id: number) {
  return unwrap<{ deleted: boolean }>(apiClient.delete(`/api/favorites/${id}`))
}
