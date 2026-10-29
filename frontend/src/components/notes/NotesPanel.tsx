import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState, useSyncExternalStore } from 'react'
import { exportNote, getNote, getNotes, saveAnswerAsNote, updateNote } from '../../api'
import type { Citation, NavigationGuard, Note, NoteSummary } from '../../types'
import { NoteDraft } from './noteDraft'
import { noteLabels } from './markdown'
import { MarkdownPreview } from './MarkdownPreview'
import { CitationPanel } from '../citations/CitationPanel'

export interface NotesHandle { saveAnswer: (messageId: string) => Promise<void> }
interface Props { onOpen?: () => void; notebookId: string; setNavigationGuard: (guard: NavigationGuard) => void }

export const NotesPanel = forwardRef<NotesHandle, Props>(function NotesPanel({ notebookId, setNavigationGuard, onOpen }, ref) {
  const [notes, setNotes] = useState<NoteSummary[]>([])
  const [draft, setDraft] = useState<NoteDraft | null>(null)
  const [error, setError] = useState(''); const [notice, setNotice] = useState('')
  const [opening, setOpening] = useState(false)
  const current = useRef<NoteDraft | null>(null); const loading = useRef(false); const mounted = useRef(true)
  const panel = useRef<HTMLElement>(null)
  const guard = useCallback(() => !current.current?.needsGuard || window.confirm('笔记有未保存修改或仍在保存。离开可能丢失未保存内容，正在提交的请求可能已生效。仍要离开吗？'), [])
  useEffect(() => {
    mounted.current = true; const controller = new AbortController()
    getNotes(notebookId, controller.signal).then(rows => { if (mounted.current) setNotes(existing => { const all = new Map(rows.map(n => [n.id, n])); for (const n of existing) if (!all.has(n.id) || all.get(n.id)!.revision <= n.revision) all.set(n.id, n); return [...all.values()].sort((a, b) => b.updated_at.localeCompare(a.updated_at)) }) }).catch(e => { if (!controller.signal.aborted) setError(e.message) })
    setNavigationGuard(guard)
    const beforeUnload = (event: BeforeUnloadEvent) => { if (current.current?.needsGuard) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', beforeUnload)
    return () => { mounted.current = false; controller.abort(); current.current?.dispose(); setNavigationGuard(null); window.removeEventListener('beforeunload', beforeUnload) }
  }, [notebookId, guard, setNavigationGuard])
  function updated(note: Note) {
    if (!mounted.current) return
    setNotes(rows => [note, ...rows.filter(n => n.id !== note.id)].sort((a, b) => b.updated_at.localeCompare(a.updated_at)))
  }
  function open(note: Note) {
    current.current?.dispose()
    const controller = new NoteDraft(note, (revision, title, body) => updateNote(notebookId, note.id, revision, title, body), updated)
    current.current = controller; setDraft(controller); updated(note)
    if (onOpen) onOpen()
    else panel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  async function load(id: string) {
    if (loading.current || !guard()) return
    loading.current = true; setOpening(true); setError(''); setNotice('')
    try { const note = await getNote(notebookId, id); if (mounted.current) open(note) }
    catch (e) { if (mounted.current) setError((e as Error).message) }
    finally { loading.current = false; if (mounted.current) setOpening(false) }
  }
  useImperativeHandle(ref, () => ({ saveAnswer: async (messageId: string) => {
    if (loading.current || !guard()) return
    loading.current = true; setOpening(true); setError('')
    try {
      const result = await saveAnswerAsNote(notebookId, messageId)
      if (mounted.current) { open(result.note); setNotice(result.created ? '已保存为独立笔记，可在下方修改。' : '已打开已有笔记，没有覆盖编辑内容。') }
    } catch (e) { if (mounted.current) setError((e as Error).message); throw e }
    finally { loading.current = false; if (mounted.current) setOpening(false) }
  } }))
  return <section className="panel notes-panel" ref={panel} aria-label="笔记与成果">
    <h2>笔记与成果</h2><p className="muted">在完整回答下点击“保存为笔记”。笔记不会自动进入知识库检索，也不会修改原回答。</p>
    {notice && <p className="notice" role="status">{notice}</p>}{error && <p className="error" role="alert">{error}</p>}
    <div className="notes-layout"><aside className="notes-list">
      {notes.length === 0 && <p className="muted">暂无笔记。</p>}
      {notes.map(note => <button key={note.id} disabled={opening} aria-pressed={note.id === draft?.snapshot().saved.id} onClick={() => void load(note.id)}>
        <strong>{note.title}</strong><small>版本 {note.revision} · {new Date(note.updated_at).toLocaleString()}</small></button>)}
    </aside><div>{opening && <p role="status">正在打开笔记…</p>}
      {draft ? <NoteEditor key={draft.snapshot().saved.id} draft={draft} notebookId={notebookId} locked={opening} onReload={() => void load(draft.snapshot().saved.id)} /> : <p className="muted">保存或选择一篇笔记开始编辑。</p>}
    </div></div>
  </section>
})

export function NoteEditor({ draft, notebookId, locked, onReload }: { draft: NoteDraft; notebookId: string; locked: boolean; onReload: () => void }) {
  const state = useSyncExternalStore(draft.subscribe, draft.snapshot)
  const [preview, setPreview] = useState(false); const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(''); const [citation, setCitation] = useState<Citation | null>(null)
  useEffect(() => { setExportError(''); setCitation(null) }, [draft])
  const labels = noteLabels(state.body); const known = new Set(state.saved.citations.map(c => c.label))
  const invalid = labels.filter(label => !known.has(label))
  useEffect(() => {
    if (!state.dirty || state.saving || state.error || locked || exporting) return
    const timer = setTimeout(() => { void draft.flush() }, 1000)
    return () => clearTimeout(timer)
  }, [draft, state.dirty, state.saving, state.error, state.title, state.body, locked, exporting])
  async function download() {
    setExporting(true); setExportError('')
    try {
      const saved = await draft.flush()
      if (!saved) return
      const file = await exportNote(notebookId, saved.id, saved.revision)
      const url = URL.createObjectURL(file.blob); const anchor = document.createElement('a')
      anchor.href = url; anchor.download = file.filename; document.body.appendChild(anchor); anchor.click(); anchor.remove()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch (e) { setExportError((e as Error).message) }
    finally { setExporting(false) }
  }
  return <div className="note-editor">
    <div className="note-toolbar"><span role="status">{state.conflict ? '版本冲突 · 输入已保留' : state.error ? '保存失败 · 输入已保留' : state.saving ? '保存中…' : state.dirty ? '有未保存修改' : '已保存'} · 版本 {state.saved.revision}</span>
      <button disabled={locked || exporting} onClick={() => setPreview(x => !x)}>{preview ? '编辑 Markdown' : '预览 Markdown'}</button>
      <button disabled={locked || exporting || state.saving || state.conflict || !state.dirty} onClick={() => void draft.flush()}>立即保存</button>
      <button disabled={locked || exporting || state.conflict || invalid.length > 0} onClick={() => void download()}>{exporting ? '正在导出…' : '导出 Markdown'}</button>
    </div>
    <label htmlFor="note-title">笔记标题</label><input id="note-title" maxLength={120} value={state.title} disabled={locked || exporting} onChange={e => draft.edit({ title: e.target.value })} />
    <p className="notice">引用保留自原回答，编辑后请重新核对。证据快照只读，不随正文修改。</p>
    {state.error && <div role="alert" className="error">{state.error}<button disabled={locked || state.saving} onClick={onReload}>重新加载服务端版本</button><p>重新加载会询问是否放弃本地输入，请先复制需要保留的内容。</p></div>}
    {invalid.length > 0 && <p className="error" role="alert">无效引用：{invalid.join('、')}。请修正后导出（代码块和链接内的标记不算引用）。</p>}
    {exportError && <div role="alert" className="error">{exportError}<button disabled={locked || exporting} onClick={onReload}>重新加载服务端版本</button></div>}
    {preview ? <><p className="muted">预览当前编辑内容，可能尚未保存。图片不自动加载，原始 HTML 不执行。</p><MarkdownPreview body={state.body} citations={state.saved.citations} onCitation={setCitation} /></> :
      <><label htmlFor="note-body">笔记正文（Markdown）</label><textarea id="note-body" maxLength={100000} value={state.body} disabled={locked || exporting} onChange={e => draft.edit({ body: e.target.value })} /></>}
    <p className="muted">正文使用 {labels.filter(x => known.has(x)).length} 个引用 / 保存 {state.saved.citations.length} 个证据快照。</p>
    <CitationPanel citation={citation} onClose={() => setCitation(null)} />
  </div>
}
