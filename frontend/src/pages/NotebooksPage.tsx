import { EmptyState } from '../components/common/EmptyState'

export function NotebooksPage() {
  return (
    <section className="home-page">
      <p className="eyebrow">SOURCE-GROUNDED WORKSPACE</p>
      <h1>从资料出发，让研究有据可循。</h1>
      <p className="intro">专题组织资料，对话帮助理解，引用支持核验，笔记沉淀成果。</p>
      <div className="section-title"><h2>我的专题</h2><button disabled>创建专题 · 待实现</button></div>
      <EmptyState title="专题功能尚未接入" description="这是工程骨架，不是已加载的空知识库。下一步将实现专题创建、资料上传与真实问答。" />
      <div className="flow-strip">导入资料 <span>→</span> 选择来源 <span>→</span> 提问与核验 <span>→</span> 保存笔记</div>
    </section>
  )
}
