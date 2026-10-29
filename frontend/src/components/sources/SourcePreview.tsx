import { useEffect, useState } from 'react'
import { getChunks, getSourceDetail } from '../../api'
import type { ChunkPage, SourceDetail } from '../../types'
import { sourceStatus, indexStatus } from './SourcesPanel'

// The parent keys this component by source id so a different source always starts at chunk 1.
export function SourcePreview({ notebookId, sourceId, revision, busy, onRetry }: {
  notebookId: string; sourceId: string; revision: string; busy: boolean; onRetry: () => void
}) {
  const [detail, setDetail] = useState<SourceDetail | null>(null)
  const [chunks, setChunks] = useState<ChunkPage | null>(null)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let active = true; const controller = new AbortController()
    setLoading(true); setError('')
    getSourceDetail(notebookId, sourceId, controller.signal).then(async d => {
      if (!active) return
      const page = d.source.status === 'parsed' ? await getChunks(notebookId, sourceId, offset, controller.signal, 1) : null
      if (!active) return
      setDetail(d)
      if (page && page.total > 0 && offset >= page.total) { setOffset(page.total - 1); return }
      setChunks(page); setLoading(false)
    }).catch(e => { if (active) { setError(e.message); setLoading(false) } })
    return () => { active = false; controller.abort() }
  }, [notebookId, sourceId, revision, offset, retry])
  const src = detail?.source
  return <div className="source-preview-content" aria-busy={loading}>
    {error && <div className="error" role="alert">{error} <button onClick={() => setRetry(x => x + 1)}>重新加载预览</button></div>}
    {loading && <p role="status" className="muted">正在加载片段…</p>}
    {src && <>
      <h3>{src.filename}</h3><p className={`status ${src.status}`}>{sourceStatus[src.status]} · {indexStatus[src.index_status]}</p>
      {src.error_message && <p className="error">{src.error_message}（{src.error_code}）</p>}
      {src.status === 'failed' && <button disabled={busy} onClick={onRetry}>重试解析</button>}
      {(src.status === 'queued' || src.status === 'parsing') && <p role="status">后台处理中，页面会自动更新。</p>}
      {chunks && <>
        <div className="pagination">
          <span role="status">片段 {chunks.total ? chunks.offset + 1 : 0} / {chunks.total}</span>
          <button aria-label="上一片段" disabled={loading || offset === 0} onClick={() => setOffset(x => x - 1)}>← 上一片</button>
          <button aria-label="下一片段" disabled={loading || offset + 1 >= chunks.total} onClick={() => setOffset(x => x + 1)}>下一片 →</button>
        </div>
        {chunks.total === 1 && <p className="muted">该资料只有 1 个片段，无需翻页。</p>}
        {chunks.total === 0 && <p className="muted">暂无可预览的片段。</p>}
        <div className="chunk-reader">{chunks.items.map(c => <article className="chunk" key={c.id}>
          <h4>片段 {c.ordinal + 1} · {c.page_start ? `PDF 第 ${c.page_start} 页` : '文本'} · 字符 [{c.char_start}, {c.char_end})</h4><pre>{c.text}</pre>
        </article>)}</div>
      </>}
      <details className="job-history"><summary>资料详情与处理记录（{detail.jobs.length}）</summary>
        <p>{src.kind.toUpperCase()} · {src.chunk_count} 个片段 · SHA256: {src.sha256}</p>
        {detail.jobs.map(j => <p key={j.id}>{new Date(j.created_at).toLocaleString()} · {j.kind} · {j.status} / {j.stage}{j.error_message ? ` · ${j.error_message}` : ''}</p>)}
      </details>
    </>}
  </div>
}
