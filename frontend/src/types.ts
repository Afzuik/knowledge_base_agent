export interface HealthResponse {
  status: 'ok'; stage: 'ingestion'; mode: 'local-single-user'; business_ready: boolean
  ingestion_ready: boolean; qa_ready: boolean; max_upload_bytes: number
}
export interface Notebook { id: string; name: string; created_at: string; updated_at: string }
export interface Source {
  id: string; notebook_id: string; filename: string; kind: string; size_bytes: number; sha256: string
  status: 'queued' | 'parsing' | 'parsed' | 'failed'; index_status: 'not_indexed'
  page_count: number; chunk_count: number; error_code: string | null; error_message: string | null
  created_at: string; updated_at: string
}
export interface Job {
  id: string; status: string; stage: string; error_code: string | null; error_message: string | null
  created_at: string; started_at: string | null; finished_at: string | null
}
export interface Chunk {
  id: string; source_id: string; ordinal: number; text: string; page_start: number | null; page_end: number | null
  char_start: number; char_end: number
}
export interface SourceDetail { source: Source; jobs: Job[] }
export interface ChunkPage { items: Chunk[]; total: number; offset: number; limit: number }
