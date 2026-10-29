import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'

export type WorkspacePane = 'sources' | 'chat' | 'notes'
export interface PanelWidths { left: number; right: number }
export const LAYOUT_KEY = 'knowledge-workbench:columns:v1'
const DEFAULTS: PanelWidths = { left: 300, right: 330 }
const LEFT_MIN = 240, RIGHT_MIN = 280, CENTER_MIN = 340, GUTTERS = 20
const clamp = (n: number, min: number, max: number) => Math.min(Math.max(n, min), Math.max(min, max))

// Keep the center usable even after a window resize or an oversized saved preference.
export function fitWidths(value: PanelWidths, total: number): PanelWidths {
  const left = Math.max(LEFT_MIN, value.left), right = Math.max(RIGHT_MIN, value.right)
  const extra = Math.floor(Math.max(0, total - GUTTERS - CENTER_MIN - LEFT_MIN - RIGHT_MIN))
  const desired = left - LEFT_MIN + right - RIGHT_MIN
  const scale = desired > extra ? extra / desired : 1
  const leftExtra = Math.round((left - LEFT_MIN) * scale)
  const rightExtra = Math.min(Math.round((right - RIGHT_MIN) * scale), extra - leftExtra)
  return { left: LEFT_MIN + leftExtra, right: RIGHT_MIN + rightExtra }
}
export function resizePanel(value: PanelWidths, side: 'left' | 'right', delta: number, total: number): PanelWidths {
  const min = side === 'left' ? LEFT_MIN : RIGHT_MIN
  const other = side === 'left' ? value.right : value.left
  return { ...value, [side]: clamp(value[side] + delta, min, total - other - CENTER_MIN - GUTTERS) }
}
function readWidths(): PanelWidths {
  try {
    const v = JSON.parse(localStorage.getItem(LAYOUT_KEY) || 'null')
    if (v && Number.isFinite(v.left) && Number.isFinite(v.right) && v.left > 0 && v.right > 0) return v
  } catch { /* Storage can be disabled; the layout must still work. */ }
  return DEFAULTS
}

export function ResizableWorkspace({ sources, chat, notes, active, onActive }: {
  sources: ReactNode; chat: ReactNode; notes: ReactNode; active: WorkspacePane; onActive: (pane: WorkspacePane) => void
}) {
  const root = useRef<HTMLDivElement>(null)
  const drag = useRef<{ side: 'left' | 'right'; x: number; widths: PanelWidths; total: number } | null>(null)
  const [preferred, setPreferred] = useState(readWidths)
  const [total, setTotal] = useState(1200)
  const [dragging, setDragging] = useState(false)
  const widths = fitWidths(preferred, total)
  useEffect(() => {
    const node = root.current!
    const observer = new ResizeObserver(entries => { setTotal(entries[0].contentRect.width); drag.current = null; setDragging(false) })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])
  useEffect(() => { try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(preferred)) } catch { /* optional preference */ } }, [preferred])
  function separator(side: 'left' | 'right') {
    const min = side === 'left' ? LEFT_MIN : RIGHT_MIN
    const max = Math.max(min, total - (side === 'left' ? widths.right : widths.left) - CENTER_MIN - GUTTERS)
    return <div className="column-resizer" role="separator" tabIndex={0} aria-orientation="vertical"
      aria-label={side === 'left' ? '调整资料栏宽度' : '调整笔记栏宽度'} aria-controls={side === 'left' ? 'workspace-sources' : 'workspace-notes'}
      aria-valuemin={min} aria-valuemax={Math.round(max)} aria-valuenow={widths[side]} aria-valuetext={`${widths[side]} 像素`}
      title="拖动调整栏宽 · 方向键微调 · 双击恢复默认"
      onDoubleClick={() => setPreferred(DEFAULTS)}
      onPointerDown={e => {
        if (e.button !== 0) return
        e.preventDefault(); e.currentTarget.focus(); e.currentTarget.setPointerCapture(e.pointerId)
        drag.current = { side, x: e.clientX, widths, total }; setDragging(true)
      }}
      onPointerMove={e => {
        const start = drag.current
        if (start?.side !== side) return
        const delta = (e.clientX - start.x) * (side === 'left' ? 1 : -1)
        setPreferred(resizePanel(start.widths, side, delta, start.total))
      }}
      onPointerUp={e => { drag.current = null; setDragging(false); if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId) }}
      onPointerCancel={() => { drag.current = null; setDragging(false) }} onLostPointerCapture={() => { drag.current = null; setDragging(false) }}
      onKeyDown={e => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
        e.preventDefault()
        const delta = e.key === 'Home' ? -Infinity : e.key === 'End' ? Infinity : (e.key === 'ArrowRight' ? 1 : -1) * (side === 'left' ? 1 : -1) * (e.shiftKey ? 40 : 10)
        setPreferred(resizePanel(widths, side, delta, total))
      }}><span /></div>
  }
  const names: Record<WorkspacePane, string> = { sources: '资料与预览', chat: '研究对话', notes: '笔记与成果' }
  return <>
    <div className="workspace-tabs" aria-label="工作区切换">{(['sources', 'chat', 'notes'] as const).map(p =>
      <button key={p} aria-pressed={active === p} aria-controls={`workspace-${p}`} onClick={() => onActive(p)}>{names[p]}</button>)}</div>
    <div className={`resizable-workspace${dragging ? ' is-resizing' : ''}`} ref={root} style={{ '--left-width': `${widths.left}px`, '--right-width': `${widths.right}px` } as CSSProperties}>
      <div id="workspace-sources" className={`workspace-pane sources-pane${active === 'sources' ? ' is-active' : ''}`}>{sources}</div>
      {separator('left')}
      <div id="workspace-chat" className={`workspace-pane chat-pane${active === 'chat' ? ' is-active' : ''}`}>{chat}</div>
      {separator('right')}
      <div id="workspace-notes" className={`workspace-pane notes-pane${active === 'notes' ? ' is-active' : ''}`}>{notes}</div>
    </div>
  </>
}
