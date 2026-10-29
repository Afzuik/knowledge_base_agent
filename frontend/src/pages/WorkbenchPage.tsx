import { SourcesPanel } from '../components/sources/SourcesPanel'
import { ChatPanel } from '../components/chat/ChatPanel'
import { NotesPanel } from '../components/notes/NotesPanel'

export function WorkbenchPage() {
  return (
    <section aria-label="工作台布局预览">
      <p className="preview-notice">布局占位：未选择真实专题，所有业务操作尚未实现。</p>
      <div className="workbench-grid"><SourcesPanel /><ChatPanel /><NotesPanel /></div>
    </section>
  )
}
