import { EmptyState } from '../common/EmptyState'

export function NotesPanel() {
  return <section className="panel"><h2>笔记与成果</h2><EmptyState title="保存有价值的回答" description="待支持笔记保存、Markdown 编辑与导出。笔记不会自动进入检索。" /></section>
}
