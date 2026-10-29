import { useEffect, useState, type FormEvent } from 'react'
import { createNotebook, getNotebooks } from '../api'
import type { Notebook } from '../types'
import { EmptyState } from '../components/common/EmptyState'

export function NotebooksPage({ onOpen }: { onOpen: (id: string) => void }) {
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [name, setName] = useState(''); const [error, setError] = useState('')
  const [loading, setLoading] = useState(true); const [creating, setCreating] = useState(false)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    const controller = new AbortController(); let active = true
    setLoading(true); setError('')
    getNotebooks(controller.signal).then(rows => { if (active) setNotebooks(rows) })
      .catch(e => { if (active) setError(e.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false; controller.abort() }
  }, [refresh])
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!name.trim() || creating) return
    setCreating(true); setError('')
    try { const row = await createNotebook(name.trim()); onOpen(row.id) }
    catch (e) { setError((e as Error).message) }
    finally { setCreating(false) }
  }
  return <section className="home-page">
    <p className="eyebrow">SOURCE-GROUNDED WORKSPACE</p><h1>从资料出发，让研究有据可循。</h1>
    <p className="intro">创建专题、导入资料、建立索引，再围绕所选来源提问、核对引用，并保存笔记导出。</p>
    <form onSubmit={submit} className="create-form"><label htmlFor="notebook-name">专题名称</label>
      <input id="notebook-name" value={name} onChange={e => setName(e.target.value)} maxLength={100} required placeholder="例如：Agent 技术学习" />
      <button disabled={creating || !name.trim()}>{creating ? '创建中…' : '创建专题'}</button></form>
    {error && <div role="alert" className="error">{error} <button onClick={() => setRefresh(x => x + 1)}>刷新列表</button></div>}
    <div className="section-title"><h2>我的专题</h2><span>{notebooks.length} 个专题</span></div>
    {loading ? <p role="status">正在加载专题…</p> : !error && notebooks.length === 0 ?
      <EmptyState title="还没有专题" description="创建专题后即可上传 PDF、Markdown 或 TXT。" /> :
      <div className="notebook-grid">{notebooks.map(n => <button className="notebook-card" key={n.id} onClick={() => onOpen(n.id)}>
        <h3>{n.name}</h3><p>创建于 {new Date(n.created_at).toLocaleString()}</p><span>打开专题 →</span></button>)}</div>}
  </section>
}
