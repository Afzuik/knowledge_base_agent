export interface HealthResponse {
  status: 'ok'; stage: 'research'; mode: 'local-single-user'; business_ready: boolean
  ingestion_ready: boolean; qa_ready: boolean; max_upload_bytes: number; model_services: { llm: { model: string; configured: boolean }; embedding: { model: string; configured: boolean }; reranker: { model: string; configured: boolean }; reranker_enabled: boolean }
}
export interface Notebook { id: string; name: string; created_at: string; updated_at: string }
export interface Source {
  id: string; notebook_id: string; filename: string; kind: string; size_bytes: number; sha256: string
  status: 'queued' | 'parsing' | 'parsed' | 'failed'; index_status: 'not_indexed' | 'queued' | 'indexing' | 'ready' | 'failed'
  index_profile: string | null; index_revision: string | null; index_dimension: number | null; index_error: string | null; index_compatible: boolean
  page_count: number; chunk_count: number; error_code: string | null; error_message: string | null
  created_at: string; updated_at: string
}
export interface Job {
  id: string; kind: string; status: string; stage: string; error_code: string | null; error_message: string | null
  created_at: string; started_at: string | null; finished_at: string | null
}
export interface Chunk {
  id: string; source_id: string; ordinal: number; text: string; page_start: number | null; page_end: number | null
  char_start: number; char_end: number
}
export interface SourceDetail { source: Source; jobs: Job[] }
export interface ChunkPage { items: Chunk[]; total: number; offset: number; limit: number }

export interface Conversation { id: string; notebook_id: string; title: string; created_at: string }
export interface Citation {
  id: string; label: string; chunk_id: string; source_id: string; filename: string; text: string
  page_start: number | null; page_end: number | null; char_start: number; char_end: number; index_revision: string
}
export interface Message {
  id: string; role: 'user' | 'assistant'; content: string; status: 'running' | 'complete' | 'failed' | 'interrupted'
  source_ids: string[]; citations: Citation[]; warnings: string[]; error: string | null; created_at: string
}
export interface StreamEvent { event: string; data: { message_id?: string; text?: string; stage?: string; message?: Message; replayed?: boolean } }
