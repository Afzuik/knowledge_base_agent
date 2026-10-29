// Contract will be connected to real server-side citations; never invent source text.
export function CitationPanel({ title, excerpt, page }: { title: string; excerpt: string; page?: number }) {
  return <aside aria-label="引用原文" className="panel"><h2>{title}</h2>{page !== undefined && <p>第 {page} 页</p>}<blockquote className="whitespace-pre-wrap">{excerpt}</blockquote></aside>
}
