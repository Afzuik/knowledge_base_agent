import type { Source } from '../../types'
export const sourceStatus = { queued: '等待处理', parsing: '解析中', parsed: '已解析', failed: '处理失败' }
export const indexStatus = { not_indexed: '未索引', queued: '等待索引', indexing: '索引中', ready: '可检索', failed: '索引失败' }
export function SourcesPanel({ sources, selected, onSelect, chosen, onToggle, onIndex, busy }: {
  sources: Source[]; selected: string | null; onSelect: (id: string) => void; chosen: string[]
  onToggle: (id: string) => void; onIndex: (id: string, force: boolean) => void; busy: boolean
}) {
  return <div className="source-list">{sources.length === 0 ? <p className="muted">暂无资料，上传文件开始。</p> : sources.map(s =>
    <div className="source-row" key={s.id}>
      <button className="source-card" aria-pressed={s.id === selected} onClick={() => onSelect(s.id)}>
        <strong>{s.filename}</strong><span className={`status ${s.status}`}>{sourceStatus[s.status]} · {indexStatus[s.index_status]}</span>
        <small>{(s.size_bytes / 1024).toFixed(1)} KiB · {s.kind.toUpperCase()} · {s.chunk_count} 个片段</small>
      </button>
      {s.status === 'parsed' && <div className="source-actions">
        <label><input type="checkbox" checked={chosen.includes(s.id)} disabled={!chosen.includes(s.id) && !s.index_compatible}
          onChange={() => onToggle(s.id)} />用于问答：{s.filename}</label>
        <button disabled={busy || s.index_status === 'queued' || s.index_status === 'indexing'} onClick={() => onIndex(s.id, s.index_status === 'ready')}>
          {s.index_status === 'ready' ? '重建索引' : s.index_status === 'failed' ? '重试索引' : '建立索引'}</button>
        {s.index_status === 'ready' && !s.index_compatible && <small className="error">模型配置已变化，需要重建索引。</small>}
        {s.index_error && <small className="error">{s.index_error}</small>}
      </div>}
    </div>)}</div>
}
