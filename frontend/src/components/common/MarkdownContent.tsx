import { Children, useEffect, useMemo, useRef, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Citation } from '../../types'

export function MarkdownContent({ body, citations, onCitation, citationLabel = '查看引用' }: { body: string; citations: Citation[]; onCitation: (c: Citation) => void; citationLabel?: string }) {
  const handler = useRef(onCitation)
  useEffect(() => { handler.current = onCitation }, [onCitation])
  const components = useMemo<Components>(() => {
    const mapping = new Map(citations.map(c => [c.label, c]))
    function decorate(children: ReactNode): ReactNode {
      return Children.map(children, child => typeof child !== 'string' ? child : child.split(/(\[S\d+\])/g).map((part, i) => {
        const c = mapping.get(part.slice(1, -1))
        return c ? <button key={i} type="button" className="citation-chip" onClick={() => handler.current(c)} aria-label={`${citationLabel} ${c.label}：${c.filename}`}>{part}</button> : <span key={i}>{part}</span>
      }))
    }
    return {
      p: ({ children }) => <p>{decorate(children)}</p>,
      li: ({ children }) => <li>{decorate(children)}</li>,
      strong: ({ children }) => <strong>{decorate(children)}</strong>,
      em: ({ children }) => <em>{decorate(children)}</em>,
      del: ({ children }) => <del>{decorate(children)}</del>,
      h1: ({ children }) => <h1>{decorate(children)}</h1>,
      h2: ({ children }) => <h2>{decorate(children)}</h2>,
      h3: ({ children }) => <h3>{decorate(children)}</h3>,
      h4: ({ children }) => <h4>{decorate(children)}</h4>,
      h5: ({ children }) => <h5>{decorate(children)}</h5>,
      h6: ({ children }) => <h6>{decorate(children)}</h6>,
      td: ({ children }) => <td>{decorate(children)}</td>,
      th: ({ children }) => <th>{decorate(children)}</th>,
      a: ({ href, children }) => href && /^https?:\/\//i.test(href) ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>,
      img: ({ alt }) => <span className="muted">[图片不自动加载：{alt || '图片'}]</span>,
    }
  }, [citations, citationLabel])
  return <div className="markdown-content"><ReactMarkdown skipHtml remarkPlugins={[remarkGfm]} components={components}>{body}</ReactMarkdown></div>
}
