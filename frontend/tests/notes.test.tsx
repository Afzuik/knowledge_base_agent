import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, act, waitFor } from '@testing-library/react'
import { NoteDraft } from '../src/components/notes/noteDraft'
import { MarkdownPreview } from '../src/components/notes/MarkdownPreview'
import { NoteEditor, NotesPanel } from '../src/components/notes/NotesPanel'
import { noteLabels } from '../src/components/notes/markdown'
import type { Note } from '../src/types'
import * as api from '../src/api'

function note(): Note {
  return { id: 'n', notebook_id: 'book', origin_message_id: 'answer', title: '标题', body_markdown: '预算 [S1]', revision: 1, created_at: 'time', updated_at: 'time',
    citations: [{ id: 'c', label: 'S1', chunk_id: 'chunk', source_id: 'source', filename: '资料.md', text: '预算120元', page_start: null, page_end: null, char_start: 0, char_end: 6, index_revision: 'v1' }], used_labels: ['S1'], invalid_labels: [] }
}
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void; const promise = new Promise<T>((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

describe('serialized note saves', () => {
  it('preserves edits made during an in-flight save and sends a new revision', async () => {
    const one = deferred<Note>(); const two = deferred<Note>()
    const writer = vi.fn().mockReturnValueOnce(one.promise).mockReturnValueOnce(two.promise)
    const draft = new NoteDraft(note(), writer)
    draft.edit({ body: 'first [S1]' }); const saving = draft.flush()
    draft.edit({ body: 'newest [S1]' }); const concurrent = draft.flush()
    expect(writer).toHaveBeenCalledTimes(1)
    one.resolve({ ...note(), body_markdown: 'first [S1]', revision: 2 })
    await vi.waitFor(() => expect(writer).toHaveBeenCalledTimes(2))
    expect(draft.snapshot().body).toBe('newest [S1]')
    expect(writer.mock.calls[1]).toEqual([2, '标题', 'newest [S1]'])
    two.resolve({ ...note(), body_markdown: 'newest [S1]', revision: 3 })
    await Promise.all([saving, concurrent])
    expect(draft.snapshot().saved.revision).toBe(3)
    expect(draft.needsGuard).toBe(false)
  })
  it('preserves input after failure and supports explicit retry', async () => {
    const writer = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ ...note(), body_markdown: 'draft', revision: 2 })
    const draft = new NoteDraft(note(), writer); draft.edit({ body: 'draft' })
    expect(await draft.flush()).toBeNull()
    expect(draft.snapshot().body).toBe('draft'); expect(draft.snapshot().error).toBe('offline')
    expect(draft.needsGuard).toBe(true)
    await draft.flush(); expect(draft.snapshot().saved.revision).toBe(2)
  })
  it('does not auto-overwrite after version conflict', async () => {
    const writer = vi.fn().mockRejectedValue(new api.ApiError('conflict', 409, 'revision_conflict'))
    const draft = new NoteDraft(note(), writer); draft.edit({ title: 'local change' }); await draft.flush()
    expect(draft.snapshot().conflict).toBe(true)
    draft.edit({ body: 'more input' }); await draft.flush()
    expect(writer).toHaveBeenCalledTimes(1); expect(draft.snapshot().body).toBe('more input')
  })
  it('does not overwrite or notify another note after dispose', async () => {
    const result = deferred<Note>(); const callback = vi.fn(); const draft = new NoteDraft(note(), () => result.promise, callback)
    draft.edit({ body: 'draft' }); const saving = draft.flush(); draft.dispose()
    result.resolve({ ...note(), body_markdown: 'draft', revision: 2 }); await saving
    expect(callback).not.toHaveBeenCalled()
  })
  it('normalizes server title without repeatedly saving unchanged whitespace', async () => {
    const writer = vi.fn().mockResolvedValue({ ...note(), title: 'trimmed', revision: 2 })
    const draft = new NoteDraft(note(), writer); draft.edit({ title: ' trimmed ' }); await draft.flush()
    expect(draft.snapshot().title).toBe('trimmed'); expect(draft.needsGuard).toBe(false); expect(writer).toHaveBeenCalledTimes(1)
  })
})

describe('Markdown reference and safety handling', () => {
  it('ignores code and links when collecting references', () => {
    expect(noteLabels('**[S1]** [S2] `literal [S99]`\n\n```\n[S98]\n```')).toEqual(['S1', 'S2'])
    expect(noteLabels('[link [S8]](https://example.com) ![image [S9]](x)\n\n<script>[S7]</script>')).toEqual([])
  })
  it('renders formatting and citations without HTML execution, external images or unsafe links', () => {
    const selected = vi.fn()
    const { container } = render(<MarkdownPreview body={'## 概览\n\n**预算** [S1]\n\n<script>window.pwned=1</script>\n\n![remote](https://example.com/private.png)\n\n[bad](javascript:alert(1))\n\n`[S1]`'} citations={note().citations} onCitation={selected} />)
    expect(container.querySelector('h2')?.textContent).toBe('概览')
    expect(container.querySelector('strong')?.textContent).toBe('预算')
    expect(container.querySelector('script')).toBeNull(); expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('a[href^="javascript"]')).toBeNull()
    expect(screen.getAllByRole('button', { name: '笔记引用 S1：资料.md' })).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: '笔记引用 S1：资料.md' })); expect(selected).toHaveBeenCalledWith(note().citations[0])
  })
  it('does not turn unknown labels into links', () => {
    render(<MarkdownPreview body={'未验证 [S99]'} citations={note().citations} onCitation={() => {}} />)
    expect(screen.queryByRole('button')).toBeNull()
  })
})

describe('editor behavior', () => {
  it('autosaves after one second and displays acknowledged status', async () => {
    vi.useFakeTimers()
    const writer = vi.fn().mockImplementation(async (revision: number, title: string, body: string) => ({ ...note(), title, body_markdown: body, revision: revision + 1 }))
    const draft = new NoteDraft(note(), writer)
    render(<NoteEditor draft={draft} notebookId="book" locked={false} onReload={() => {}} />)
    fireEvent.change(screen.getByLabelText('笔记正文（Markdown）'), { target: { value: '新的正文 [S1]' } })
    expect(screen.getByRole('status').textContent).toContain('未保存')
    await act(async () => { await vi.advanceTimersByTimeAsync(999) }); expect(writer).not.toHaveBeenCalled()
    await act(async () => { await vi.advanceTimersByTimeAsync(1) }); expect(writer).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status').textContent).toContain('已保存'); expect(screen.getByRole('status').textContent).toContain('版本 2')
  })
  it('blocks export when unknown reference exists', () => {
    const draft = new NoteDraft(note(), vi.fn())
    render(<NoteEditor draft={draft} notebookId="book" locked={false} onReload={() => {}} />)
    fireEvent.change(screen.getByLabelText('笔记正文（Markdown）'), { target: { value: 'wrong [S99]' } })
    expect((screen.getByRole('button', { name: '导出 Markdown' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByRole('alert').textContent).toContain('S99')
  })
  it('waits for latest save before exporting its revision', async () => {
    const result = deferred<Note>(); const writer = vi.fn().mockReturnValue(result.promise)
    const exporter = vi.spyOn(api, 'exportNote').mockResolvedValue({ blob: new Blob(['markdown']), filename: '笔记.md' })
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:test') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const draft = new NoteDraft(note(), writer)
    render(<NoteEditor draft={draft} notebookId="book" locked={false} onReload={() => {}} />)
    fireEvent.change(screen.getByLabelText('笔记正文（Markdown）'), { target: { value: 'latest [S1]' } })
    fireEvent.click(screen.getByRole('button', { name: '导出 Markdown' }))
    expect(exporter).not.toHaveBeenCalled()
    await act(async () => { result.resolve({ ...note(), body_markdown: 'latest [S1]', revision: 2 }) })
    await waitFor(() => expect(exporter).toHaveBeenCalledWith('book', 'n', 2))
  })
  it('does not export when saving fails', async () => {
    const exporter = vi.spyOn(api, 'exportNote')
    const draft = new NoteDraft(note(), vi.fn().mockRejectedValue(new Error('offline')))
    render(<NoteEditor draft={draft} notebookId="book" locked={false} onReload={() => {}} />)
    fireEvent.change(screen.getByLabelText('笔记正文（Markdown）'), { target: { value: 'unsaved [S1]' } })
    fireEvent.click(screen.getByRole('button', { name: '导出 Markdown' }))
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('保存失败'))
    expect(exporter).not.toHaveBeenCalled()
    expect((screen.getByLabelText('笔记正文（Markdown）') as HTMLTextAreaElement).value).toBe('unsaved [S1]')
  })
})


describe('unsaved navigation guard', () => {
  it('prompts before switching and prevents unload when edits remain', async () => {
    const current = note(); const other = { ...note(), id: 'other', title: '第二笔记' }
    vi.spyOn(api, 'getNotes').mockResolvedValue([current, other])
    const detail = vi.spyOn(api, 'getNote').mockResolvedValue(current)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const guard = vi.fn()
    render(<NotesPanel notebookId="book" setNavigationGuard={guard} />)
    fireEvent.click(await screen.findByRole('button', { name: /^标题/ }))
    fireEvent.change(await screen.findByLabelText('笔记正文（Markdown）'), { target: { value: 'unsaved [S1]' } })
    fireEvent.click(screen.getByRole('button', { name: /^第二笔记/ }))
    expect(confirm).toHaveBeenCalledTimes(1); expect(detail).toHaveBeenCalledTimes(1)
    expect((screen.getByLabelText('笔记正文（Markdown）') as HTMLTextAreaElement).value).toBe('unsaved [S1]')
    expect(guard.mock.calls[0][0]()).toBe(false)
    const event = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true)
  })
  it('ignores markers inside autolinks', () => {
    expect(noteLabels('https://example.com/[S99]')).toEqual([])
  })
})
