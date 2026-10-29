import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { askQuestion, createConversation, getConversations, getMessages } from '../../api'
import type { Citation, Conversation, Message, Source } from '../../types'
import { MarkdownContent } from '../common/MarkdownContent'
import { CitationPanel } from '../citations/CitationPanel'

const NO_CITATIONS: Citation[] = []

export function ChatPanel({ notebookId, sourceIds, selectionValid, sources, onSaveAnswer, onShowCitation }: { onShowCitation?: (citation: Citation) => void; notebookId: string; sourceIds: string[]; selectionValid: boolean; sources: Source[]; onSaveAnswer: (messageId: string) => Promise<void> }) {
  const scroll = useRef<HTMLDivElement>(null)
  const follow = useRef(true)
  const [atBottom, setAtBottom] = useState(true)
  const [copied, setCopied] = useState('')
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
    getMessages(notebookId, conversation, controller.signal).then(rows => { if (!controller.signal.aborted) setMessages(rows) }).catch(e => { if (!controller.signal.aborted) setError(e.message) })
    return () => controller.abort()
  }, [notebookId, conversation, busy])
  useEffect(() => {
    if (busy || !conversation || !messages.some(m => m.status === 'running')) return
    const timer = setTimeout(() => { getMessages(notebookId, conversation).then(rows => { if (alive.current) setMessages(rows) }).catch(() => {}) }, 1500)
    return () => clearTimeout(timer)
  }, [messages, conversation, notebookId, busy])
  useLayoutEffect(() => {
    const node = scroll.current
    if (node && follow.current && !window.getSelection()?.toString()) node.scrollTop = node.scrollHeight
  }, [messages, phase])
  useEffect(() => { follow.current = true; setAtBottom(true) }, [conversation])
  async function copy(message: Message) {
    try { await navigator.clipboard.writeText(message.content); setCopied(message.id) }
    catch { setError('复制失败，请直接选择回答文字复制。') }
  }
  useEffect(() => { if (!copied) return; const timer = setTimeout(() => setCopied(''), 2000); return () => clearTimeout(timer) }, [copied])
  async function send(event: FormEvent) {
    event.preventDefault(); if (busy || !question.trim() || !selectionValid || sourceIds.length === 0) return
    const q = question.trim(); const scope = [...sourceIds]; const key = crypto.randomUUID()
    follow.current = true; setAtBottom(true)
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
  return <section className="panel research-panel" aria-label="研究对话"><div className="chat-heading"><h2>研究对话</h2><span className="count-badge">基于所选资料</span></div>
    <div className="conversation-bar"><label>会话 <select aria-label="选择会话" value={conversation} disabled={busy} onChange={e => { setConversation(e.target.value); setError('') }}>
      <option value="">新会话（发送时创建）</option>{conversations.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label>
      <button disabled={busy} onClick={() => { setConversation(''); setMessages([]); setCitation(null) }}>新建会话</button></div>
    <p className="muted">本轮已选 {sourceIds.length} 份资料。只使用勾选且索引就绪的来源，不联网搜索。</p>
    {!selectionValid && sourceIds.length > 0 && <p className="error">所选资料的索引未就绪或不兼容，请完成索引或取消勾选。</p>}
    {error && <p role="alert" className="error">{error}</p>}
    <div className="message-list" ref={scroll} tabIndex={0} aria-label="对话记录" onScroll={() => {
      const node = scroll.current!; const near = node.scrollHeight - node.scrollTop - node.clientHeight < 60
      follow.current = near; setAtBottom(near)
    }}>{messages.length === 0 && <div className="chat-empty"><span className="assistant-avatar">知</span><h3>从一个好问题开始</h3><p>在左侧勾选已建立索引的资料，<br />让知识助手帮你比较、梳理和发现。</p></div>}
      {messages.map(m => <article className={`message ${m.role}`} key={m.id}>
        <div className="message-author"><span className={`role-avatar ${m.role}`}>{m.role === 'user' ? '你' : '知'}</span><h3>{m.role === 'user' ? '你' : '知识助手'} <small>{m.status === 'running' ? '生成中' : m.status === 'failed' ? '失败' : m.status === 'interrupted' ? '未完成' : ''}</small></h3></div>
        <p className="muted message-sources">本轮资料：{m.source_ids.map(id => sources.find(s => s.id === id)?.filename || id.slice(0, 8)).join("、")}</p><div className="answer-text">{m.role === 'assistant' ? <MarkdownContent body={m.content} citations={m.status === 'complete' ? m.citations : NO_CITATIONS} onCitation={c => { if (onShowCitation) onShowCitation(c); else setCitation(c) }} /> : m.content}</div>{m.error && <p className="error">{m.error}</p>}
        {m.warnings.map((w,i) => <p className="notice" key={i}>{w}</p>)}
        {m.role === 'assistant' && m.status === 'complete' && <div className="message-actions"><button onClick={() => void copy(m)}>{copied === m.id ? '已复制' : '复制回答'}</button><button disabled={savingNote !== null} onClick={() => void saveNote(m.id)}>{savingNote === m.id ? '正在保存笔记…' : '保存为笔记'}</button></div>}
      </article>)}</div>
    {!atBottom && <button className="jump-latest" onClick={() => { if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight; follow.current = true; setAtBottom(true) }}>↓ 回到最新消息</button>}
    <CitationPanel citation={citation} onClose={() => setCitation(null)} />
    <form className="chat-composer" onSubmit={send}><label htmlFor="research-question">研究问题</label><textarea id="research-question" maxLength={2000} value={question} disabled={busy} onChange={e => setQuestion(e.target.value)} onKeyDown={e => {
        if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) { e.preventDefault(); e.currentTarget.form?.requestSubmit() }
      }} placeholder="向资料提问…" />
      <div className="composer-actions"><span className="muted">Enter 发送 · Shift + Enter 换行</span><button className="send-button" disabled={busy || !question.trim() || !selectionValid || sourceIds.length === 0}>发送问题</button>
      {busy && <><button type="button" onClick={() => abort.current?.abort()}>停止生成</button><span role="status"> {phase}</span></>}
      </div>
    </form>
  </section>
}
