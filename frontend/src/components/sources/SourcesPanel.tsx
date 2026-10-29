import type { Source } from '../../types'
export const sourceStatus = { queued: '等待处理', parsing: '解析中', parsed: '已解析', failed: '处理失败' }
export function SourcesPanel({ sources, selected, onSelect }: { sources: Source[]; selected: string | null; onSelect: (id: string) => void }) {
  return <div className="source-list">{sources.length === 0 ? <p className="muted">暂无资料，上传文件开始。</p> : sources.map(s =>
    <button key={s.id} className="source-card" aria-pressed={s.id === selected} onClick={() => onSelect(s.id)}>
      <strong>{s.filename}</strong><span className={`status ${s.status}`}>{sourceStatus[s.status]}</span>
      <small>{(s.size_bytes / 1024).toFixed(1)} KiB · {s.kind.toUpperCase()}{s.status === 'parsed' ? ` · ${s.chunk_count} 个片段` : ''}</small>
    </button>)}</div>
}
