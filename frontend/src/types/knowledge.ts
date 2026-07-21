export interface KnowledgeDocument {
  id: number
  title: string
  source_type: string
  file_path: string | null
  status: string
  version: number
  created_at?: string | null
  updated_at?: string | null
}

export interface ParsedSection {
  title: string
  content_preview: string
  metadata: Record<string, string>
}

export interface ParsedDocument {
  title: string
  file_type: string
  section_count: number
  char_count: number
  sections: ParsedSection[]
}

export interface ChunkBuildResponse {
  chunk_count: number
  chunks: Array<{
    id: number
    document_id: number
    spot_id: number | null
    chunk_index: number
    content_preview: string
    token_count: number
  }>
}
