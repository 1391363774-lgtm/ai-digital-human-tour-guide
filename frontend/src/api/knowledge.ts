import { apiClient, unwrap } from './client'
import type { ChunkBuildResponse, KnowledgeDocument, ParsedDocument } from '../types/knowledge'

export function listKnowledgeDocuments() {
  return unwrap<KnowledgeDocument[]>(apiClient.get('/api/admin/knowledge'))
}

export function uploadKnowledgeDocument(file: File, sourceType = 'upload') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('source_type', sourceType)
  return unwrap<KnowledgeDocument>(
    apiClient.post('/api/admin/knowledge/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  )
}

export function parseKnowledgePreview(documentId: number) {
  return unwrap<ParsedDocument>(apiClient.get(`/api/admin/knowledge/${documentId}/parse-preview`))
}

export function buildKnowledgeChunks(documentId: number) {
  return unwrap<ChunkBuildResponse>(apiClient.post(`/api/admin/knowledge/${documentId}/chunks`))
}

export function indexKnowledgeDocument(documentId: number) {
  return unwrap<{ indexed_count: number }>(apiClient.post(`/api/admin/knowledge/${documentId}/index`))
}

export function deleteKnowledgeDocument(documentId: number) {
  return unwrap<{ deleted: boolean }>(apiClient.delete(`/api/admin/knowledge/${documentId}`))
}
