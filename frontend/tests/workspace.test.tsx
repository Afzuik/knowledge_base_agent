import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { fitWidths, LAYOUT_KEY, ResizableWorkspace, resizePanel } from '../src/components/common/ResizableWorkspace'
import { SourcePreview } from '../src/components/sources/SourcePreview'
import { MarkdownContent } from '../src/components/common/MarkdownContent'
import { ChatPanel } from '../src/components/chat/ChatPanel'
import * as api from '../src/api'
import type { Citation, Message, Source } from '../src/types'

vi.mock('../src/api', () => ({ getChunks: vi.fn(), getSourceDetail: vi.fn(), getConversations: vi.fn(), getMessages: vi.fn(), askQuestion: vi.fn(), createConversation: vi.fn() }))
const source = { id: 'source1', filename: 'test.md', kind: 'md', status: 'parsed', index_status: 'ready', sha256: 'a'.repeat(64), chunk_count: 5, index_compatible: true } as Source
const citation = { id: 'c', label: 'S1', filename: 'test.md', text: 'evidence' } as Citation
const messages: Message[] = [
  { id: 'u', role: 'user', content: '什么是研究？', status: 'complete', citations: [], source_ids: ['source1'], warnings: [], error: null, created_at: '' },
  { id: 'a', role: 'assistant', content: '**可靠的回答** [S1]\n\n- 核对资料\n- 保留引用', status: 'complete', citations: [citation], source_ids: ['source1'], warnings: [], error: null, created_at: '' },
]
let observedResize: (entries: { contentRect: { width: number } }[]) => void
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear()
  vi.stubGlobal('ResizeObserver', class { constructor(cb: typeof observedResize) { observedResize = cb } observe() {} disconnect() {} })
  vi.mocked(api.getSourceDetail).mockResolvedValue({ source, jobs: [] })
  vi.mocked(api.getChunks).mockImplementation(async (_n, id, offset = 0) => ({ offset, limit: 1, total: 5, items: [{ id: id + offset, source_id: id, ordinal: offset, text: `原文 ${id} ${offset + 1}`, page_start: null, page_end: null, char_start: offset * 100, char_end: (offset + 1) * 100 }] }))
  vi.mocked(api.getConversations).mockResolvedValue([{ id: 'conv', notebook_id: 'n', title: '研究', created_at: '' }])
  vi.mocked(api.getMessages).mockResolvedValue(messages)
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
function layout() { return render(<ResizableWorkspace sources={<input aria-label="保留来源状态" defaultValue="draft" />} chat={<p>chat</p>} notes={<p>notes</p>} active="chat" onActive={() => {}} />) }

describe('column resizing', () => {
  it('clamps both sides and preserves a usable center', () => {
    expect(resizePanel({ left: 300, right: 330 }, 'left', -999, 1200).left).toBe(240)
    expect(resizePanel({ left: 300, right: 330 }, 'right', 999, 1200).right).toBe(540)
    const fit = fitWidths({ left: 900, right: 900 }, 980)
    expect(fit.left).toBeGreaterThanOrEqual(240); expect(fit.right).toBeGreaterThanOrEqual(280)
    expect(980 - fit.left - fit.right - 20).toBeGreaterThanOrEqual(340)
    const rounded = fitWidths({ left: 300, right: 340 }, 981)
    expect(981 - rounded.left - rounded.right - 20).toBeGreaterThanOrEqual(340)
  })
  it('supports keyboard resizing, reset and persistence', () => {
    const view = layout(); const left = screen.getByRole('separator', { name: '调整资料栏宽度' })
    fireEvent.keyDown(left, { key: 'ArrowRight' }); expect(left.getAttribute('aria-valuenow')).toBe('310')
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!).left).toBe(310)
    fireEvent.keyDown(screen.getByRole('separator', { name: '调整笔记栏宽度' }), { key: 'ArrowLeft' })
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!).right).toBe(340)
    view.unmount(); layout(); expect(screen.getByRole('separator', { name: '调整资料栏宽度' }).getAttribute('aria-valuenow')).toBe('310')
    fireEvent.doubleClick(screen.getByRole('separator', { name: '调整资料栏宽度' }))
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!)).toEqual({ left: 300, right: 330 })
  })
  it('handles pointer drag in both directions and cancellation', () => {
    vi.stubGlobal('PointerEvent', MouseEvent)
    layout()
    const left = screen.getByRole('separator', { name: '调整资料栏宽度' })
    left.setPointerCapture = vi.fn(); left.hasPointerCapture = () => false
    fireEvent.pointerDown(left, { button: 0, clientX: 300 }); fireEvent.pointerMove(left, { clientX: 350 })
    expect(left.getAttribute('aria-valuenow')).toBe('350')
    fireEvent.pointerCancel(left); fireEvent.pointerMove(left, { clientX: 400 })
    expect(left.getAttribute('aria-valuenow')).toBe('350')
    const right = screen.getByRole('separator', { name: '调整笔记栏宽度' })
    right.setPointerCapture = vi.fn(); right.hasPointerCapture = () => false
    fireEvent.pointerDown(right, { button: 0, clientX: 900 }); fireEvent.pointerMove(right, { clientX: 870 }); fireEvent.pointerUp(right)
    expect(right.getAttribute('aria-valuenow')).toBe('360')
  })
  it('ignores corrupt preferences and does not unmount hidden panes', () => {
    localStorage.setItem(LAYOUT_KEY, '{bad')
    const view = layout(); fireEvent.change(screen.getByLabelText('保留来源状态'), { target: { value: 'kept' } })
    view.rerender(<ResizableWorkspace sources={<input aria-label="保留来源状态" defaultValue="draft" />} chat={<p>chat</p>} notes={<p>notes</p>} active="sources" onActive={() => {}} />)
    expect((screen.getByLabelText('保留来源状态') as HTMLInputElement).value).toBe('kept')
  })
  it('clamps on viewport shrink without overwriting preferred widths', () => {
    layout(); fireEvent.keyDown(screen.getByRole('separator', { name: '调整资料栏宽度' }), { key: 'End' })
    const saved = localStorage.getItem(LAYOUT_KEY)
    // ResizeObserver delivery is an external event.
    fireEvent(window, new Event('resize'))
    act(() => observedResize([{ contentRect: { width: 980 } }]))
    expect(localStorage.getItem(LAYOUT_KEY)).toBe(saved)
  })
})

describe('one chunk per page', () => {
  const preview = (id = 'source1') => <SourcePreview key={id} notebookId="n" sourceId={id} revision="1" busy={false} onRetry={() => {}} />
  it('loads just one chunk and navigates next and previous', async () => {
    render(preview()); await screen.findByText('原文 source1 1')
    expect(api.getChunks).toHaveBeenLastCalledWith('n', 'source1', 0, expect.any(AbortSignal), 1)
    expect((screen.getByLabelText('上一片段') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByLabelText('下一片段')); await screen.findByText('原文 source1 2')
    expect(screen.queryByText('原文 source1 1')).toBeNull()
    fireEvent.click(screen.getByLabelText('上一片段')); await screen.findByText('原文 source1 1')
  })
  it('resets to chunk one for a different source', async () => {
    const view = render(preview()); await screen.findByText('原文 source1 1')
    fireEvent.click(screen.getByLabelText('下一片段')); await screen.findByText('原文 source1 2')
    view.rerender(preview('source2')); await screen.findByText('原文 source2 1')
    expect(screen.queryByText('原文 source1 2')).toBeNull()
  })
  it('explains a single-chunk source and disables both controls', async () => {
    vi.mocked(api.getChunks).mockResolvedValue({ items: [], offset: 0, total: 1, limit: 1 })
    render(preview()); await screen.findByText('该资料只有 1 个片段，无需翻页。')
    for (const label of ['上一片段', '下一片段']) expect((screen.getByLabelText(label) as HTMLButtonElement).disabled).toBe(true)
  })
  it('aborts stale requests when the source changes', async () => {
    let resolve!: (value: Awaited<ReturnType<typeof api.getSourceDetail>>) => void
    vi.mocked(api.getSourceDetail).mockImplementationOnce(() => new Promise(r => { resolve = r }))
    const view = render(preview()); const signal = vi.mocked(api.getSourceDetail).mock.calls[0][2]!
    view.rerender(preview('source2')); await screen.findByText('原文 source2 1'); expect(signal.aborted).toBe(true)
    await act(async () => resolve({ source, jobs: [] })); await waitFor(() => expect(screen.queryByText('原文 source1 1')).toBeNull())
  })
  it('can retry a failed preview request', async () => {
    vi.mocked(api.getSourceDetail).mockRejectedValueOnce(new Error('暂时失败'))
    render(preview()); await screen.findByRole('alert'); fireEvent.click(screen.getByRole('button', { name: '重新加载预览' }))
    await screen.findByText('原文 source1 1')
  })
})

it('renders safe Markdown and only converts evidence markers outside code into buttons', () => {
  const click = vi.fn(); const { container } = render(<MarkdownContent body={'**重点** [S1]\n\n`[S1]`\n\n<script>alert(1)</script>\n\n![x](https://example.com/x.png)'} citations={[citation]} onCitation={click} />)
  expect(container.querySelector('strong')?.textContent).toBe('重点')
  expect(container.querySelector('script')).toBeNull(); expect(container.querySelector('img')).toBeNull()
  expect(screen.getAllByRole('button')).toHaveLength(1); fireEvent.click(screen.getByRole('button')); expect(click).toHaveBeenCalledWith(citation)
})

function chat(onShowCitation = vi.fn(), onSaveAnswer = vi.fn()) {
  return render(<ChatPanel notebookId="n" sourceIds={['source1']} selectionValid={true} sources={[source]} onShowCitation={onShowCitation} onSaveAnswer={onSaveAnswer} />)
}
it('keeps user/assistant roles distinct, renders Markdown, routes citations and saves notes', async () => {
  const show = vi.fn(), save = vi.fn().mockResolvedValue(undefined); const { container } = chat(show, save)
  await screen.findByText('可靠的回答')
  expect(container.querySelector('.message.user')?.textContent).toContain('什么是研究')
  expect(container.querySelector('.message.assistant strong')?.textContent).toBe('可靠的回答')
  fireEvent.click(screen.getByRole('button', { name: /查看引用/ })); expect(show).toHaveBeenCalledWith(citation)
  fireEvent.click(screen.getByRole('button', { name: '保存为笔记' })); await waitFor(() => expect(save).toHaveBeenCalledWith('a'))
})
it('Enter sends, Shift+Enter and IME Enter do not send', async () => {
  vi.mocked(api.askQuestion).mockResolvedValue(undefined)
  chat(); await screen.findByText('可靠的回答')
  const input = screen.getByLabelText('研究问题'); fireEvent.change(input, { target: { value: '新问题' } })
  fireEvent.keyDown(input, { key: 'Enter', shiftKey: true }); expect(api.askQuestion).not.toHaveBeenCalled()
  fireEvent.keyDown(input, { key: 'Enter', isComposing: true }); expect(api.askQuestion).not.toHaveBeenCalled()
  fireEvent.keyDown(input, { key: 'Enter', keyCode: 229 }); expect(api.askQuestion).not.toHaveBeenCalled()
  fireEvent.keyDown(input, { key: 'Enter' }); await waitFor(() => expect(api.askQuestion).toHaveBeenCalledTimes(1))
})
it('does not offer clickable citations or save for a streaming partial answer', async () => {
  vi.mocked(api.getMessages).mockResolvedValue([{ ...messages[1], status: 'running' }])
  chat(); await screen.findByText('可靠的回答')
  expect(screen.queryByRole('button', { name: /查看引用/ })).toBeNull()
  expect(screen.queryByRole('button', { name: '保存为笔记' })).toBeNull()
})
it('keeps Markdown DOM nodes stable when the parent polls or callbacks change', () => {
  const citations = [citation]
  const view = render(<MarkdownContent body="**保留选择** [S1]" citations={citations} onCitation={() => {}} />)
  const text = view.container.querySelector('strong'), button = screen.getByRole('button')
  button.focus()
  view.rerender(<MarkdownContent body="**保留选择** [S1]" citations={citations} onCitation={() => {}} />)
  expect(view.container.querySelector('strong')).toBe(text); expect(document.activeElement).toBe(button)
})
it('disables next at the last of five chunks', async () => {
  render(<SourcePreview notebookId="n" sourceId="source1" revision="1" busy={false} onRetry={() => {}} />)
  await screen.findByText('原文 source1 1')
  for (let i = 2; i <= 5; i++) { fireEvent.click(screen.getByLabelText('下一片段')); await screen.findByText(`原文 source1 ${i}`) }
  expect((screen.getByLabelText('下一片段') as HTMLButtonElement).disabled).toBe(true)
  expect((screen.getByLabelText('上一片段') as HTMLButtonElement).disabled).toBe(false)
})
it('copies the original Markdown answer with confirmation feedback', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  chat(); await screen.findByText('可靠的回答'); fireEvent.click(screen.getByRole('button', { name: '复制回答' }))
  await screen.findByText('已复制'); expect(writeText).toHaveBeenCalledWith(messages[1].content)
})
it('renders streamed deltas then restores a completed answer and evidence actions', async () => {
  vi.mocked(api.askQuestion).mockImplementation(async (_n, _c, _q, _s, _key, event) => {
    event({ event: 'start', data: { message_id: 'stream' } })
    event({ event: 'delta', data: { text: '**新的回答**' } })
    const final: Message = { ...messages[1], id: 'stream', content: '**新的回答** [S1]' }
    event({ event: 'done', data: { message: final } })
    vi.mocked(api.getMessages).mockResolvedValue([...messages, { ...messages[0], id: 'u2', content: '再问一次' }, final])
  })
  chat(); await screen.findByText('可靠的回答')
  fireEvent.change(screen.getByLabelText('研究问题'), { target: { value: '再问一次' } })
  fireEvent.click(screen.getByRole('button', { name: '发送问题' }))
  await screen.findByText('新的回答')
  await waitFor(() => expect(screen.getAllByRole('button', { name: /查看引用/ })).toHaveLength(2))
})
