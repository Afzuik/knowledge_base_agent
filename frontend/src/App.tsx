import { useCallback, useEffect, useRef, useState } from 'react'
import { useBackendHealth } from './hooks/useBackendHealth'
import { NotebooksPage } from './pages/NotebooksPage'
import type { NavigationGuard } from './types'
import { WorkbenchPage } from './pages/WorkbenchPage'

const currentNotebook = () => /^#\/notebooks\/([a-f0-9]{32})$/.exec(window.location.hash)?.[1] || null
export default function App() {
  const [notebookId, setNotebookId] = useState(currentNotebook)
  const activeNotebook = useRef(notebookId)
  const navigationGuard = useRef<NavigationGuard>(null)
  const setNavigationGuard = useCallback((guard: NavigationGuard) => { navigationGuard.current = guard }, [])
  const health = useBackendHealth()
  useEffect(() => {
    const changed = () => {
      const next = currentNotebook()
      if (next !== activeNotebook.current && navigationGuard.current && !navigationGuard.current()) {
        const hash = activeNotebook.current ? '#/notebooks/' + activeNotebook.current : ''
        window.history.replaceState(null, '', window.location.pathname + window.location.search + hash)
        return
      }
      activeNotebook.current = next; setNotebookId(next)
    }
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const open = (id: string) => { window.location.hash = `/notebooks/${id}` }
  return <div className={`app-shell${notebookId ? ' workspace-shell' : ''}`}>
    <header className="app-header"><div><span className="brand-mark">知</span><strong>知识研究工作台</strong></div>
      <span className="stage-badge">资料研究 · 笔记与导出</span></header>
    <nav className="page-nav" aria-label="页面导航">
      <button onClick={() => { window.location.hash = '' }}>专题首页</button>
      <span role="status" className={`health ${health}`}>{health === 'online' ? '后端已连接' : health === 'checking' ? '正在检查后端' : '后端未连接'}</span>
    </nav>
    <main>{notebookId ? <WorkbenchPage key={notebookId} notebookId={notebookId} setNavigationGuard={setNavigationGuard} /> : <NotebooksPage onOpen={open} />}</main>
    <footer>仅本机单用户 · 建索引与问答使用外部模型 · 不联网搜索 · 回答请核对引用</footer>
  </div>
}
