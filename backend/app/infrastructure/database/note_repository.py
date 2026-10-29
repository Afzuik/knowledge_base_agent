"""Independent snapshots and compare-and-swap persistence; no model calls."""
import json
from uuid import uuid4
from sqlalchemy import select, update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from .models import Note, Notebook, Message, Conversation, Citation, now
from .repositories import values


class NoteRepository:
    def __init__(self, engine):
        self.session = sessionmaker(engine, expire_on_commit=False)

    def _query(self, owner, notebook_id):
        return select(Note).join(Notebook).where(Note.notebook_id == notebook_id, Notebook.owner_id == owner)

    def notebook_exists(self, owner, notebook_id):
        with self.session() as s:
            return s.scalar(select(Notebook.id).where(Notebook.id == notebook_id, Notebook.owner_id == owner)) is not None

    def get(self, owner, notebook_id, note_id):
        with self.session() as s:
            return values(s.scalar(self._query(owner,notebook_id).where(Note.id == note_id)))

    def list(self, owner, notebook_id):
        with self.session() as s:
            return [values(n) for n in s.scalars(self._query(owner,notebook_id).order_by(Note.updated_at.desc(),Note.id))]

    def by_origin(self, owner, notebook_id, message_id):
        with self.session() as s:
            return values(s.scalar(self._query(owner,notebook_id).where(Note.origin_message_id == message_id)))

    def create_snapshot(self, owner, notebook_id, message_id, requested_title):
        try:
            with self.session.begin() as s:
                # sqlite3 legacy mode does not start read transactions automatically.
                # Take the writer lock before reading message + citations for a consistent snapshot.
                s.execute(text('BEGIN IMMEDIATE'))
                message = s.scalar(select(Message).join(Conversation).join(Notebook).where(
                    Message.id == message_id, Conversation.notebook_id == notebook_id, Notebook.owner_id == owner))
                if message is None: return None, 'not_found'
                if message.role != 'assistant' or message.status != 'complete': return None, 'not_complete'
                existing = s.scalar(self._query(owner,notebook_id).where(Note.origin_message_id == message_id))
                if existing: return values(existing), 'existing'
                question = s.scalar(select(Message.content).where(Message.conversation_id == message.conversation_id,
                    Message.request_key == message.request_key, Message.role == 'user'))
                default_title = ''.join(c for c in ' '.join((question or '研究笔记').split()) if ord(c) >= 32 and ord(c) != 127)[:80]
                title = requested_title if requested_title is not None else default_title
                citations = [values(c) for c in s.scalars(select(Citation).where(Citation.message_id == message_id).order_by(Citation.label))]
                # Copy evidence; no FK to mutable source/chunk/message objects is needed afterwards.
                allowed = ('id','label','chunk_id','source_id','filename','text','page_start','page_end','char_start','char_end','index_revision')
                snapshot = [{k:c[k] for k in allowed} for c in citations]
                row = Note(id=uuid4().hex, notebook_id=notebook_id, origin_message_id=message_id,
                    title=title or '研究笔记', body_markdown=message.content,
                    citations_snapshot_json=json.dumps(snapshot,ensure_ascii=False), revision=1)
                s.add(row);s.flush()
                return values(row), 'created'
        except IntegrityError:
            # Concurrent double click: only reuse a note visible in this exact scope.
            existing = self.by_origin(owner,notebook_id,message_id)
            if existing: return existing, 'existing'
            raise

    def update(self, owner, notebook_id, note_id, revision, title, body):
        with self.session.begin() as s:
            row = s.scalar(self._query(owner,notebook_id).where(Note.id == note_id))
            if row is None: return None, 'not_found'
            changed = s.execute(update(Note).where(Note.id == note_id, Note.revision == revision, Note.notebook_id == notebook_id,
                Note.notebook_id.in_(select(Notebook.id).where(Notebook.owner_id == owner))).values(
                title=title, body_markdown=body, revision=Note.revision+1, updated_at=now()))
            if changed.rowcount != 1: return None, 'conflict'
            s.refresh(row)
            return values(row), 'updated'
