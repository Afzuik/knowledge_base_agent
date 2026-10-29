import { useState } from 'react'
import { useBackendHealth } from './hooks/useBackendHealth'
import { NotebooksPage } from './pages/NotebooksPage'
import { WorkbenchPage } from './pages/WorkbenchPage'

export default function App() {
  const [page, setPage] = useState<'home' | 'workbench'>('home')
  const health = useBackendHealth()
  const statusText = { checking: '正在检查后端', online: '后端进程已连接', offline: '后端未连接，请检查启动状态' }
  return (
    <div className="app-shell">
      <header className="app-header">
        <div><span className="brand-mark">知</span><strong>知识研究工作台</strong></div>
        <span className="stage-badge">工程骨架 · 非功能演示版</span>
      </header>
      <nav aria-label="页面导航" className="page-nav">
        <button aria-pressed={page === 'home'} onClick={() => setPage('home')}>专题首页</button>
        <button aria-pressed={page === 'workbench'} onClick={() => setPage('workbench')}>工作台布局预览</button>
        <span role="status" className={`health ${health}`}>{statusText[health]}</span>
      </nav>
      <main>{page === 'home' ? <NotebooksPage /> : <WorkbenchPage />}</main>
      <footer>仅本机单用户。当前不读取旧知识库、不调用模型、不具备多用户隔离。</footer>
    </div>
  )
}
