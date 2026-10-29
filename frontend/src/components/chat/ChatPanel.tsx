import { useEffect, useRef, useState, type FormEvent } from 'react'
import { askQuestion, createConversation, getConversations, getMessages } from '../../api'
import type { Citation, Conversation, Message, Source } from '../../types'
import { CitationPanel } from '../citations/CitationPanel'

export function ChatPanel({ notebookId, sourceIds, selectionValid, sources, onSaveAnswer }: { notebookId: string; sourceIds: string[]; selectionValid: boolean; sources: Source[]; onSaveAnswer: (messageId: string) => Promise<void> }) {
  const [savingNote, setSavingNote] = useState<string | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversation, setConversation] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState(''); const [busy, setBusy] = useState(false)
  const [error, setError] = useState(''); const [phase, setPhase] = useState('')
  const [citation, setCitation] = useState<Citation | null>(null)
  const abort = useRef<AbortController | null>(null); const alive = useRef(true)
  useEffect(() => {
    alive.current = true; const controller = new AbortController()
    getConversations(notebookId, controller.signal).then(rows => { if (alive.current) { setConversations(rows); setConversation(rows[0]?.id || '') } }).catch(e => { if (alive.current && !controller.signal.aborted) setError(e.message) })
    return () => { alive.current = false; controller.abort(); abort.current?.abort() }
  }, [notebookId])
  useEffect(() => {
    if (busy) return
    setCitation(null)
    if (!conversation) { setMessages([]); return }
    const controller = new AbortController()
    getMessages(notebookId, conversation, controller.signal).then(setMessages).catch(e => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [notebookId, conversation, busy])
  useEffect(() => {
    if (busy || !conversation || !messages.some(m => m.status === 'running')) return
    const timer = setTimeout(() => { getMessages(notebookId, conversation).then(rows => { if (alive.current) setMessages(rows) }).catch(() => {}) }, 1500)
    return () => clearTimeout(timer)
  }, [messages, conversation, notebookId, busy])
  async function send(event: FormEvent) {
    event.preventDefault(); if (busy || !question.trim() || !selectionValid || sourceIds.length === 0) return
    const q = question.trim(); const scope = [...sourceIds]; const key = crypto.randomUUID()
    setBusy(true); setError(''); setCitation(null); setPhase('准备中')
    const controller = new AbortController(); abort.current = controller
    let cid = conversation; let assistantId = ''
    try {
      if (!cid) {
        const created = await createConversation(notebookId, q.slice(0, 30))
        cid = created.id; setConversations(rows => [created, ...rows]); setConversation(cid)
      }
      await askQuestion(notebookId, cid, q, scope, key, item => {
        if (!alive.current) return
        if (item.event === 'start') {
          assistantId = item.data.message_id!
          const base = { source_ids: scope, citations: [], warnings: [], error: null, created_at: new Date().toISOString() }
          setMessages(rows => [...rows.filter(m => m.id !== assistantId), { ...base, id: 'local-' + key, role: 'user', content: q, status: 'complete' }, { ...base, id: assistantId, role: 'assistant', content: '', status: 'running' }])
          setQuestion('')
        }
        if (item.event === 'status') setPhase(item.data.stage === 'retrieving' ? '检索证据中' : '生成回答中')
        if (item.event === 'delta') setMessages(rows => rows.map(m => m.id === assistantId ? { ...m, content: m.content + (item.data.text || '') } : m))
        if ((item.event === 'done' || item.event === 'error') && item.data.message) {
          const final = item.data.message
          setMessages(rows => rows.some(m => m.id === final.id) ? rows.map(m => m.id === final.id ? final : m) : [...rows, final])
          if (item.event === 'error') setError(final.error || '回答失败')
        }
      }, controller.signal)
    } catch (e) { if (alive.current) setError(controller.signal.aborted ? '已停止接收；正在保存中断状态，可稍后刷新查看。' : (e as Error).message) }
    finally {
      if (alive.current) {
        if (cid) { try { setMessages(await getMessages(notebookId, cid)) } catch { /* preserve visible partial output */ } }
        setBusy(false); setPhase('')
      }
    }
  }
  async function saveNote(messageId: string) {
    setSavingNote(messageId); setError('')
    try { await onSaveAnswer(messageId) } catch (e) { setError((e as Error).message) }
    finally { setSavingNote(null) }
  }
  function answer(message: Message) {
    const mapping = new Map(message.citations.map(c => [c.label, c]))
    return message.content.split(/(\[S\d+\])/g).map((part, i) => {
      const label = part.slice(1, -1); const c = mapping.get(label)
      return c && message.status === 'complete' ? <button key={i} className="citation-chip" onClick={() => setCitation(c)} aria-label={`查看引用 ${label}：${c.filename}`}>{part}</button> : <span key={i}>{part}</span>
    })
  }
  return <section className="panel research-panel"><h2>研究对话</h2>
    <div className="conversation-bar"><label>会话 <select aria-label="选择会话" value={conversation} disabled={busy} onChange={e => { setConversation(e.target.value); setError('') }}>
      <option value="">新会话（发送时创建）</option>{conversations.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label>
      <button disabled={busy} onClick={() => { setConversation(''); setMessages([]); setCitation(null) }}>新建会话</button></div>
    <p className="muted">本轮已选 {sourceIds.length} 份资料。只使用勾选且索引就绪的来源，不联网搜索。</p>
    {!selectionValid && sourceIds.length > 0 && <p className="error">所选资料的索引未就绪或不兼容，请完成索引或取消勾选。</p>}
    {error && <p role="alert" className="error">{error}</p>}
    <div className="message-list">{messages.length === 0 && <p className="muted">先为资料建立索引并勾选，再输入问题。</p>}
      {messages.map(m => <article className={`message ${m.role}`} key={m.id}>
        <h3>{m.role === 'user' ? '你' : '知识助手'} <small>{m.status === 'running' ? '生成中' : m.status === 'failed' ? '失败' : m.status === 'interrupted' ? '未完成' : ''}</small></h3>
        <p className="muted">本轮资料：{m.source_ids.map(id => sources.find(s => s.id === id)?.filename || id.slice(0, 8)).join("、")}</p><div className="answer-text">{answer(m)}</div>{m.error && <p className="error">{m.error}</p>}
        {m.warnings.map((w,i) => <p className="notice" key={i}>{w}</p>)}
        {m.role === 'assistant' && m.status === 'complete' && <button disabled={savingNote !== null} onClick={() => void saveNote(m.id)}>{savingNote === m.id ? '正在保存笔记…' : '保存为笔记'}</button>}
      </article>)}</div>
    <CitationPanel citation={citation} onClose={() => setCitation(null)} />
    <form onSubmit={send}><label htmlFor="research-question">研究问题</label><textarea id="research-question" maxLength={2000} value={question} disabled={busy} onChange={e => setQuestion(e.target.value)} placeholder="例如：这些资料记录的预算有什么不同？" />
      <button disabled={busy || !question.trim() || !selectionValid || sourceIds.length === 0}>发送问题</button>
      {busy && <><button type="button" onClick={() => abort.current?.abort()}>停止生成</button><span role="status"> {phase}</span></>}
    </form>
  </section>
}
