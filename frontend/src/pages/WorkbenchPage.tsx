import { useEffect, useRef, useState } from 'react'
import { getChunks, getHealth, getNotebook, getSourceDetail, getSources, retrySource, uploadSource } from '../api'
import type { ChunkPage, Notebook, Source, SourceDetail } from '../types'
import { SourcesPanel, sourceStatus } from '../components/sources/SourcesPanel'

export function WorkbenchPage({ notebookId }: { notebookId: string }) {
  const [notebook, setNotebook] = useState<Notebook | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [detail, setDetail] = useState<SourceDetail | null>(null)
  const [chunks, setChunks] = useState<ChunkPage | null>(null)
  const [offset, setOffset] = useState(0); const [tick, setTick] = useState(0)
  const [error, setError] = useState(''); const [detailError, setDetailError] = useState('')
  const [notice, setNotice] = useState(''); const [busy, setBusy] = useState(false)
  const [limit, setLimit] = useState(20 * 1024 * 1024)
  const input = useRef<HTMLInputElement>(null)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    let active = true; const controller = new AbortController()
    getNotebook(notebookId, controller.signal).then(n => { if (active) setNotebook(n) }).catch(e => { if (active) setError(e.message) })
    getHealth(controller.signal).then(h => { if (active) setLimit(h.max_upload_bytes) }).catch(() => {})
    return () => { active = false; controller.abort() }
  }, [notebookId])
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>; const controller = new AbortController()
    async function poll() {
      try { const rows = await getSources(notebookId, controller.signal); if (active) { setSources(rows); setError('') } }
      catch (e) { if (active) setError((e as Error).message) }
      if (active) timer = setTimeout(poll, 1500)
    }
    void poll()
    return () => { active = false; clearTimeout(timer); controller.abort() }
  }, [notebookId, tick])
  const chosen = sources.find(s => s.id === selected)
  useEffect(() => {
    setDetail(null); setChunks(null); setDetailError('')
    if (!selected) return
    let active = true; const controller = new AbortController()
    getSourceDetail(notebookId, selected, controller.signal).then(async d => {
      if (!active) return
      setDetail(d)
      if (d.source.status === 'parsed') { const page = await getChunks(notebookId, selected, offset, controller.signal); if (active) setChunks(page) }
    }).catch(e => { if (active) setDetailError(e.message) })
    return () => { active = false; controller.abort() }
  }, [notebookId, selected, chosen?.updated_at, offset, tick])
  async function upload(file?: File) {
    if (!file || busy) return
    setNotice(''); setError('')
    if (file.size > limit || file.size === 0) { setError('文件为空或超过大小限制。'); if (input.current) input.current.value = ''; return }
    setBusy(true)
    try {
      const result = await uploadSource(notebookId, file)
      if (!alive.current) return
      setSelected(result.source.id); setOffset(0); setTick(x => x + 1)
      setNotice(result.duplicate ? '相同内容已存在，已定位到原资料。失败资料可点击重试。' : '文件已接收，后台将解析；这不表示已可问答。')
    } catch (e) { if (alive.current) setError((e as Error).message) }
    finally { if (alive.current) { setBusy(false); if (input.current) input.current.value = '' } }
  }
  async function retry() {
    if (!selected || busy) return
    setBusy(true); setDetailError('')
    try { await retrySource(notebookId, selected); if (alive.current) { setTick(x => x + 1); setNotice('已创建重试任务。') } }
    catch (e) { if (alive.current) setDetailError((e as Error).message) }
    finally { if (alive.current) setBusy(false) }
  }
  const src = detail?.source
  return <section>
    <h1>{notebook?.name || '正在加载专题…'}</h1><p className="intro">上传 → 解析 → 核对片段。已解析不等于可问答，本轮不建立向量索引。</p>
    {error && <p className="error" role="alert">{error}</p>}{notice && <p role="status" className="notice">{notice}</p>}
    <div className="ingestion-grid"><aside className="panel"><h2>资料来源 · {sources.length}</h2>
      <label className="upload-label" htmlFor="source-file">上传 PDF / Markdown / TXT</label>
      <input id="source-file" ref={input} type="file" accept=".pdf,.md,.txt" disabled={busy || !notebook} onChange={e => void upload(e.target.files?.[0])} />
      <p className="muted">单文件上限 {(limit / 1024 / 1024).toFixed(0)} MiB；不支持 OCR 或加密 PDF。文本请使用 UTF-8。</p>
      {busy && <p role="status">正在提交，请稍候…</p>}
      <SourcesPanel sources={sources} selected={selected} onSelect={id => { setSelected(id); setOffset(0) }} />
    </aside><div className="panel preview-panel"><h2>资料与片段预览</h2>
      {!selected && <p className="muted">从左侧选择资料，查看处理结果。</p>}
      {detailError && <p className="error" role="alert">{detailError}</p>}
      {selected && !detail && !detailError && <p role="status">正在加载资料…</p>}
      {src && <><h3>{src.filename}</h3><p className={`status ${src.status}`}>{sourceStatus[src.status]} · 未索引</p>
        <p className="muted">{src.kind === 'pdf' ? `${src.page_count} 页 · ` : ''}{src.chunk_count} 个片段 · SHA256: {src.sha256.slice(0, 12)}…</p>
        {src.error_message && <p className="error">{src.error_message}（{src.error_code}）</p>}
        {src.status === 'failed' && <button disabled={busy} onClick={() => void retry()}>重试解析</button>}
        {(src.status === 'queued' || src.status === 'parsing') && <p role="status">后台处理中，页面会自动更新。</p>}
        {chunks && <><div className="pagination"><span>片段 {chunks.total ? offset + 1 : 0}–{Math.min(offset + 20, chunks.total)} / {chunks.total}</span>
          <button disabled={offset === 0} onClick={() => setOffset(x => Math.max(0, x - 20))}>上一页</button>
          <button disabled={offset + 20 >= chunks.total} onClick={() => setOffset(x => x + 20)}>下一页</button></div>
          {chunks.items.map(c => <article className="chunk" key={c.id}><h4>片段 {c.ordinal + 1} · {c.page_start ? `PDF 第 ${c.page_start} 页` : '文本'} · 字符 [{c.char_start}, {c.char_end})</h4><pre>{c.text}</pre></article>)}</>}
        <details className="job-history"><summary>处理记录（{detail.jobs.length}）</summary>{detail.jobs.map(j => <p key={j.id}>{new Date(j.created_at).toLocaleString()} · {j.status} / {j.stage}{j.error_message ? ` · ${j.error_message}` : ''}</p>)}</details>
      </>}
    </div></div>
  </section>
}
