import { useEffect, useRef, useState } from 'react'
import { getHealth, indexSource, getNotebook, getSources, retrySource, uploadSource } from '../api'
import type { Citation, Notebook, Source } from '../types'
import { NotesPanel, type NotesHandle } from '../components/notes/NotesPanel'
import type { NavigationGuard } from '../types'
import { ChatPanel } from '../components/chat/ChatPanel'
import { SourcesPanel } from '../components/sources/SourcesPanel'

import { SourcePreview } from '../components/sources/SourcePreview'
import { CitationPanel } from '../components/citations/CitationPanel'
import { ResizableWorkspace, type WorkspacePane } from '../components/common/ResizableWorkspace'

export function WorkbenchPage({ notebookId, setNavigationGuard }: { notebookId: string; setNavigationGuard: (guard: NavigationGuard) => void }) {
  const notesRef = useRef<NotesHandle>(null)
  const [models, setModels] = useState('正在读取服务配置…')
  const [chosen, setChosen] = useState<string[]>([])
  const [notebook, setNotebook] = useState<Notebook | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [active, setActive] = useState<WorkspacePane>('chat')
  const [citation, setCitation] = useState<Citation | null>(null)
  const [pollError, setPollError] = useState('')
  const [tick, setTick] = useState(0)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(''); const [busy, setBusy] = useState(false)
  const [limit, setLimit] = useState(20 * 1024 * 1024)
  const input = useRef<HTMLInputElement>(null)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    let active = true; const controller = new AbortController()
    getNotebook(notebookId, controller.signal).then(n => { if (active) setNotebook(n) }).catch(e => { if (active) setError(e.message) })
    getHealth(controller.signal).then(h => { if (active) { setLimit(h.max_upload_bytes); setModels(`LLM：${h.model_services.llm.model} · Embedding：${h.model_services.embedding.model}（仅表示已配置，不代表实时可用）`) } }).catch(() => {})
    return () => { active = false; controller.abort() }
  }, [notebookId])
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>; const controller = new AbortController()
    async function poll() {
      try { const rows = await getSources(notebookId, controller.signal); if (active) { setSources(rows); setPollError(''); setSelected(id => id || rows[0]?.id || null) } }
      catch (e) { if (active) setPollError((e as Error).message) }
      if (active) timer = setTimeout(poll, 1500)
    }
    void poll()
    return () => { active = false; clearTimeout(timer); controller.abort() }
  }, [notebookId, tick])
  const previewSource = sources.find(s => s.id === selected)
  async function upload(file?: File) {
    if (!file || busy) return
    setNotice(''); setError('')
    if (file.size > limit || file.size === 0) { setError('文件为空或超过大小限制。'); if (input.current) input.current.value = ''; return }
    setBusy(true)
    try {
      const result = await uploadSource(notebookId, file)
      if (!alive.current) return
      setSelected(result.source.id); setCitation(null); setActive('sources'); setTick(x => x + 1)
      setNotice(result.duplicate ? '相同内容已存在，已定位到原资料。失败资料可点击重试。' : '文件已接收，后台将解析；这不表示已可问答。')
    } catch (e) { if (alive.current) setError((e as Error).message) }
    finally { if (alive.current) { setBusy(false); if (input.current) input.current.value = '' } }
  }
  async function retry() {
    if (!selected || busy) return
    setBusy(true); setError('')
    try { await retrySource(notebookId, selected); if (alive.current) { setTick(x => x + 1); setNotice('已创建重试任务。') } }
    catch (e) { if (alive.current) setError((e as Error).message) }
    finally { if (alive.current) setBusy(false) }
  }
  async function establishIndex(id: string, force: boolean) {
    if (busy) return
    setBusy(true); setError('')
    try { await indexSource(notebookId, id, force); if (alive.current) { setTick(x => x + 1); setNotice('索引任务已创建，将调用已配置的 Embedding 服务。') } }
    catch (e) { if (alive.current) setError((e as Error).message) }
    finally { if (alive.current) setBusy(false) }
  }
  return <section className="workbench">
    <div className="workbench-heading"><div><span className="eyebrow">RESEARCH NOTEBOOK</span><h1>{notebook?.name || '正在加载专题…'}</h1></div>
      <details className="service-details"><summary>使用说明与模型配置</summary><p>上传 → 解析 → 建立索引 → 勾选来源 → 提问。建索引与提问会调用外部模型。</p><p>{models}</p><p>拖动栏间边框调整宽度，双击边框恢复默认。</p></details>
    </div>
    <div className="workbench-feedback">{(error || pollError) && <p className="error" role="alert">{error || pollError}</p>}{notice && <p role="status" className="notice">{notice}<button onClick={() => setNotice('')} aria-label="关闭通知">×</button></p>}</div>
    <ResizableWorkspace active={active} onActive={setActive}
      sources={<>
        <aside className="panel source-library"><h2>资料来源 <span className="count-badge">{sources.length}</span></h2>
          <label className="upload-label" htmlFor="source-file">＋ 上传 PDF / Markdown / TXT</label>
          <input id="source-file" ref={input} type="file" accept=".pdf,.md,.txt" disabled={busy || !notebook} onChange={e => void upload(e.target.files?.[0])} />
          <details className="upload-help"><summary>上传说明 · 上限 {(limit / 1024 / 1024).toFixed(0)} MiB</summary><p>不支持 OCR 或加密 PDF。文本请使用 UTF-8。勾选已建立索引的资料用于问答。</p></details>
          {busy && <p role="status" className="muted">正在提交，请稍候…</p>}
          <div className="source-list-scroll"><SourcesPanel sources={sources} selected={selected} onSelect={id => { setSelected(id); setCitation(null) }} chosen={chosen}
            onToggle={id => setChosen(ids => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id])} onIndex={(id, force) => void establishIndex(id, force)} busy={busy} /></div>
        </aside>
        <section className="panel preview-panel"><h2>资料与片段预览</h2>
          {citation && <div className="citation-preview"><p className="muted">回答生成时的证据快照，不随原资料变化。</p><CitationPanel citation={citation} onClose={() => setCitation(null)} /></div>}
          <div className="source-preview-slot" hidden={!!citation}>
            {selected ? <SourcePreview key={selected} notebookId={notebookId} sourceId={selected} revision={`${previewSource?.updated_at || ''}:${tick}`} busy={busy} onRetry={() => void retry()} /> : <p className="muted">选择一份资料，逐片查看原文。</p>}
          </div>
        </section>
      </>}
      chat={<ChatPanel onShowCitation={c => { setCitation(c); setActive('sources') }} onSaveAnswer={async id => { await notesRef.current?.saveAnswer(id) }} notebookId={notebookId} sources={sources} sourceIds={chosen} selectionValid={chosen.length <= 10 && chosen.every(id => sources.some(s => s.id === id && s.index_compatible && s.status === 'parsed'))} />}
      notes={<NotesPanel ref={notesRef} onOpen={() => setActive('notes')} notebookId={notebookId} setNavigationGuard={setNavigationGuard} />}
    />
  </section>
}
