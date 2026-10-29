import type { Note } from '../../types'

export type NoteWriter = (revision: number, title: string, body: string) => Promise<Note>
export interface DraftState {
  saved: Note; title: string; body: string; dirty: boolean; saving: boolean; error: string; conflict: boolean
}

/** Serializes writes and coalesces newer edits. An acknowledgement never overwrites newer input. */
export class NoteDraft {
  private listeners = new Set<() => void>()
  private pending: Promise<Note | null> | null = null
  private disposed = false
  private state: DraftState
  constructor(note: Note, private writer: NoteWriter, private onSaved: (note: Note) => void = () => {}) {
    this.state = { saved: note, title: note.title, body: note.body_markdown, dirty: false, saving: false, error: '', conflict: false }
  }
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  snapshot = () => this.state
  private change(fields: Partial<DraftState>) {
    this.state = { ...this.state, ...fields }
    this.state.dirty = this.state.title !== this.state.saved.title || this.state.body !== this.state.saved.body_markdown
    if (!this.disposed) for (const listener of this.listeners) listener()
  }
  edit(fields: { title?: string; body?: string }) {
    this.change({ ...fields, error: this.state.conflict ? this.state.error : '' })
  }
  get needsGuard() { return this.state.dirty || this.state.saving }
  dispose() { this.disposed = true; this.listeners.clear() }
  async flush(): Promise<Note | null> {
    if (this.disposed || this.state.conflict) return null
    if (this.pending) {
      const result = await this.pending
      return result && !this.disposed ? this.flush() : null
    }
    if (!this.state.dirty) return this.state.saved
    const sent = { title: this.state.title, body: this.state.body, revision: this.state.saved.revision }
    this.change({ saving: true, error: '' })
    const run = async (): Promise<Note | null> => {
      try {
        const note = await this.writer(sent.revision, sent.title, sent.body)
        const unchanged = this.state.title === sent.title && this.state.body === sent.body
        this.change({ saved: note, ...(unchanged ? { title: note.title, body: note.body_markdown } : {}), error: '', conflict: false })
        if (!this.disposed) this.onSaved(note)
        return note
      } catch (error) {
        const e = error as Error & { code?: string }
        this.change({ error: e.message || '保存失败，输入已保留。', conflict: e.code === 'revision_conflict' })
        return null
      } finally { this.change({ saving: false }) }
    }
    this.pending = run()
    const result = await this.pending
    this.pending = null
    // Continue with the newest input using the freshly acknowledged revision.
    return result && this.state.dirty && !this.disposed ? this.flush() : result
  }
}
