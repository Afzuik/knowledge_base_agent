import { EmptyState } from '../common/EmptyState'

export function ChatPanel() {
  return <section className="panel chat-panel"><h2>研究对话</h2><EmptyState title="围绕所选资料提问" description="待接入真实检索、流式回答与片段级引用。当前没有模拟回答。" /><label htmlFor="question">你的问题</label><textarea id="question" disabled placeholder="问答接口尚未实现" /><button disabled>发送 · 待实现</button></section>
}
