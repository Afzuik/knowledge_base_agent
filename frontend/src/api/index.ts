import type { HealthResponse, Notebook, Source, SourceDetail, ChunkPage } from '../types'

export async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.message || (typeof body?.detail === 'string' ? body.detail : body?.detail?.[0]?.msg)
    throw new Error(detail || `请求失败（HTTP ${response.status}）`)
  }
  return response.json() as Promise<T>
}
export function getHealth(signal?: AbortSignal) { return requestJson<HealthResponse>('/health', { signal }) }
export function getNotebooks(signal?: AbortSignal) { return requestJson<Notebook[]>('/notebooks', { signal }) }
export function createNotebook(name: string) {
  return requestJson<Notebook>('/notebooks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) })
}
export const sourcePath = (notebookId: string, sourceId?: string) => `/notebooks/${encodeURIComponent(notebookId)}/sources${sourceId ? '/' + encodeURIComponent(sourceId) : ''}`
export function getNotebook(id: string, signal?: AbortSignal) { return requestJson<Notebook>(`/notebooks/${encodeURIComponent(id)}`, { signal }) }
export function getSources(id: string, signal?: AbortSignal) { return requestJson<Source[]>(sourcePath(id), { signal }) }
export function uploadSource(id: string, file: File) {
  const body = new FormData(); body.append('file', file)
  return requestJson<{ source: Source; duplicate: boolean }>(sourcePath(id), { method: 'POST', body })
}
export function getSourceDetail(id: string, sourceId: string, signal?: AbortSignal) { return requestJson<SourceDetail>(sourcePath(id, sourceId), { signal }) }
export function getChunks(id: string, sourceId: string, offset = 0, signal?: AbortSignal) {
  return requestJson<ChunkPage>(sourcePath(id, sourceId) + `/chunks?offset=${offset}&limit=20`, { signal })
}
export function retrySource(id: string, sourceId: string) { return requestJson<Source>(sourcePath(id, sourceId) + '/retry', { method: 'POST' }) }
