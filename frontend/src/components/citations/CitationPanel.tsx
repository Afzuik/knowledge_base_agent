import type { Citation } from '../../types'
export function CitationPanel({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  if (!citation) return null
  return <aside className="citation-detail" aria-label="引用原文">
    <button onClick={onClose}>关闭引用</button><h3>[{citation.label}] {citation.filename}</h3>
    <p className="muted">{citation.page_start ? `PDF 第 ${citation.page_start} 页` : '文本资料'} · 字符 [{citation.char_start}, {citation.char_end})</p>
    <pre>{citation.text}</pre><p className="muted">这是该次回答保存的证据快照。引用存在不代表结论已被自动核验。</p>
  </aside>
}
