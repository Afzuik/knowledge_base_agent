import { EmptyState } from '../common/EmptyState'

export function SourcesPanel() {
  return <section className="panel"><h2>资料来源</h2><button disabled>上传资料 · 待实现</button><EmptyState title="来源列表" description="将支持文本 PDF、Markdown、TXT，展示解析状态并勾选问答范围。" /></section>
}
