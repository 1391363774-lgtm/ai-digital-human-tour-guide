import { apiClient, unwrap } from './client'

export interface VisitorEvent {
  id: number
  user_id: number | null
  session_id: string | null
  event_type: string
  target_type: string | null
  target_id: number | null
  spot_id: number | null
  page_path: string | null
  source: string | null
  duration_seconds: number | null
  metadata: Record<string, unknown> | null
  occurred_at: string
  created_at: string
}

export interface VisitorEventImportResult {
  imported_count: number
  skipped_count: number
  errors: string[]
}

export interface VisitorEventStats {
  total: number
  event_type_counts: Record<string, number>
  source_counts: Record<string, number>
  top_spot_counts: Record<string, number>
  average_duration_seconds: number
}

export function importVisitorEvents(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return unwrap<VisitorEventImportResult>(
    apiClient.post('/api/behavior/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  )
}

export function listVisitorEvents() {
  return unwrap<VisitorEvent[]>(apiClient.get('/api/behavior/events'))
}

export function getVisitorEventStats() {
  return unwrap<VisitorEventStats>(apiClient.get('/api/behavior/stats'))
}
