import type { Citation } from '../../types'
import { MarkdownContent } from '../common/MarkdownContent'

export function MarkdownPreview(props: { body: string; citations: Citation[]; onCitation: (c: Citation) => void }) {
  return <div className="markdown-preview"><MarkdownContent {...props} citationLabel="笔记引用" /></div>
}
