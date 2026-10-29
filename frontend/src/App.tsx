import { useEffect, useState } from 'react'
import { useBackendHealth } from './hooks/useBackendHealth'
import { NotebooksPage } from './pages/NotebooksPage'
import { WorkbenchPage } from './pages/WorkbenchPage'

const currentNotebook = () => /^#\/notebooks\/([a-f0-9]{32})$/.exec(window.location.hash)?.[1] || null
export default function App() {
  const [notebookId, setNotebookId] = useState(currentNotebook)
  const health = useBackendHealth()
  useEffect(() => {
    const changed = () => setNotebookId(currentNotebook())
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const open = (id: string) => { window.location.hash = `/notebooks/${id}` }
  return <div className="app-shell">
    <header className="app-header"><div><span className="brand-mark">知</span><strong>知识研究工作台</strong></div>
      <span className="stage-badge">资料入库版 · 问答尚未接入</span></header>
    <nav className="page-nav" aria-label="页面导航">
      <button onClick={() => { window.location.hash = '' }}>专题首页</button>
      <span role="status" className={`health ${health}`}>{health === 'online' ? '后端已连接' : health === 'checking' ? '正在检查后端' : '后端未连接'}</span>
    </nav>
    <main>{notebookId ? <WorkbenchPage key={notebookId} notebookId={notebookId} /> : <NotebooksPage onOpen={open} />}</main>
    <footer>仅本机单用户 · 原始资料与处理结果本地保存 · 不调用模型、不生成向量 · 不具备多用户隔离</footer>
  </div>
}
