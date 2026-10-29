import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'

interface Node { type: string; value?: string; children?: Node[] }
const parser = unified().use(remarkParse).use(remarkGfm)
export function noteLabels(body: string): string[] {
  const labels = new Set<string>()
  function visit(node: Node) {
    if (['code', 'inlineCode', 'html', 'link', 'linkReference', 'image', 'imageReference'].includes(node.type)) return
    if (node.type === 'text') for (const match of (node.value || '').matchAll(/\[(S\d+)\]/g)) labels.add(match[1])
    node.children?.forEach(visit)
  }
  visit(parser.parse(body) as Node)
  return [...labels]
}
