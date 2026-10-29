import type { HealthResponse, Notebook, Source, SourceDetail, ChunkPage, Conversation, Message, StreamEvent, Note, NoteSummary } from '../types'

export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string) { super(message) }
}

export async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.message || (typeof body?.detail === 'string' ? body.detail : body?.detail?.[0]?.msg)
    throw new ApiError(detail || `请求失败（HTTP ${response.status}）`, response.status, body?.code || "request_failed")
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
export function getChunks(id: string, sourceId: string, offset = 0, signal?: AbortSignal, limit = 20) {
  return requestJson<ChunkPage>(sourcePath(id, sourceId) + `/chunks?offset=${offset}&limit=${limit}`, { signal })
}
export function retrySource(id: string, sourceId: string) { return requestJson<Source>(sourcePath(id, sourceId) + '/retry', { method: 'POST' }) }

export function indexSource(nid: string, sid: string, force = false) {
  return requestJson<Source>(sourcePath(nid, sid) + '/index', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ force }) })
}
const conversationPath = (nid: string) => `/notebooks/${encodeURIComponent(nid)}/conversations`
export function getConversations(nid: string, signal?: AbortSignal) { return requestJson<Conversation[]>(conversationPath(nid), { signal }) }
export function createConversation(nid: string, title: string) { return requestJson<Conversation>(conversationPath(nid), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) }) }
export function getMessages(nid: string, cid: string, signal?: AbortSignal) { return requestJson<Message[]>(conversationPath(nid) + `/${encodeURIComponent(cid)}/messages`, { signal }) }
export async function askQuestion(nid: string, cid: string, question: string, sourceIds: string[], requestKey: string, onEvent: (event: StreamEvent) => void, signal: AbortSignal) {
  const response = await fetch('/api' + conversationPath(nid) + `/${encodeURIComponent(cid)}/messages`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, signal,
    body: JSON.stringify({ question, source_ids: sourceIds, request_key: requestKey })
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.message || body?.detail?.[0]?.msg || `请求失败（HTTP ${response.status}）`)
  }
  if (!response.body) throw new Error('浏览器不支持流式响应。')
  const reader = response.body.getReader(); const decoder = new TextDecoder()
  let buffer = ''; let terminal = false
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2)
        const lines = block.split('\n')
        const event = lines.find(x => x.startsWith('event:'))?.slice(6).trim()
        const raw = lines.filter(x => x.startsWith('data:')).map(x => x.slice(5).trim()).join('\n')
        if (event && raw) { const data = JSON.parse(raw); onEvent({ event, data }); if (event === 'done' || event === 'error') terminal = true }
      }
      if (done) break
    }
    if (!terminal) throw new Error('回答连接中断，未确认完成；可刷新查看保存状态。')
  } finally { reader.releaseLock() }
}

const notesPath = (nid: string, noteId?: string) => `/notebooks/${encodeURIComponent(nid)}/notes${noteId ? '/' + encodeURIComponent(noteId) : ''}`
export function saveAnswerAsNote(nid: string, messageId: string) {
  return requestJson<{ note: Note; created: boolean }>(notesPath(nid), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ origin_message_id: messageId }) })
}
export function getNotes(nid: string, signal?: AbortSignal) { return requestJson<NoteSummary[]>(notesPath(nid), { signal, cache: 'no-store' }) }
export function getNote(nid: string, noteId: string, signal?: AbortSignal) { return requestJson<Note>(notesPath(nid, noteId), { signal, cache: 'no-store' }) }
export function updateNote(nid: string, noteId: string, revision: number, title: string, body: string) {
  return requestJson<Note>(notesPath(nid, noteId), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, signal: AbortSignal.timeout(15000), body: JSON.stringify({ revision, title, body_markdown: body }) })
}
export async function exportNote(nid: string, noteId: string, revision: number): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch('/api' + notesPath(nid, noteId) + `/export?revision=${revision}`, { signal: AbortSignal.timeout(15000) })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(body?.message || '导出失败', response.status, body?.code || 'export_failed')
  }
  if (response.headers.get('X-Note-Revision') !== String(revision)) throw new Error('导出版本与请求不一致。')
  const match = /filename\*=UTF-8''([^;]+)/i.exec(response.headers.get('Content-Disposition') || '')
  return { blob: await response.blob(), filename: match ? decodeURIComponent(match[1]) : '研究笔记.md' }
}
