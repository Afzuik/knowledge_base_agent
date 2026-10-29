"""Research persistence. Short transactions; snapshots preserve historical citations."""
import json
from uuid import uuid4
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .repositories import Repository, values
from .models import Source, Chunk, Job, Conversation, Message, Citation, Notebook, now


class RagRepository(Repository):
    def enqueue_index(self, source_id, owner, profile, force=False):
        try:
            with self.session.begin() as s:
                source = s.get(Source, source_id)
                if source.status != 'parsed': return False
                if s.scalar(select(Job.id).where(Job.source_id == source_id, Job.status.in_(['queued','running']))): return False
                if not force and source.index_status == 'ready' and source.index_profile == profile: return False
                previous = s.scalar(select(Job).where(Job.source_id == source_id, Job.kind == 'index').order_by(Job.created_at.desc()).limit(1))
                revision = previous.target_revision if previous and previous.status == 'failed' and previous.target_profile == profile else uuid4().hex
                source.index_status = 'queued'; source.index_error = None; source.updated_at = now()
                s.add(Job(id=uuid4().hex, source_id=source.id, notebook_id=source.notebook_id, owner_id=owner,
                    kind='index', target_profile=profile, target_revision=revision))
                return True
        except IntegrityError:
            return False

    def complete_index(self, job_id, source_id, profile, revision, dimension):
        with self.session.begin() as s:
            job = s.get(Job, job_id); source = s.get(Source, source_id)
            if job.status != 'running' or source.status != 'parsed': raise RuntimeError('Index job changed')
            source.index_status = 'ready'; source.index_profile = profile; source.index_revision = revision
            source.index_dimension = dimension; source.index_error = None; source.updated_at = now()
            job.status = 'succeeded'; job.stage = 'done'; job.finished_at = now()

    def recover_research(self):
        with self.session.begin() as s:
            for job in s.scalars(select(Job).where(Job.kind == 'index', Job.status == 'running')):
                source = s.get(Source, job.source_id)
                source.index_status = 'failed'; source.index_error = '索引被中断，请重试。'; source.updated_at = now()
                job.status = 'failed'; job.stage = 'failed'; job.error_code = 'interrupted'; job.error_message = source.index_error; job.finished_at = now()
            for m in s.scalars(select(Message).where(Message.status == 'running')):
                m.status = 'interrupted'; m.error = '服务中断，保留部分内容；请重新提问。'; m.updated_at = now()

    def selected_chunks(self, source_ids):
        with self.session() as s:
            return [{**values(chunk), 'filename': filename, 'index_revision': revision} for chunk, filename, revision in
                s.execute(select(Chunk, Source.filename, Source.index_revision).join(Source).where(Chunk.source_id.in_(source_ids)).order_by(Chunk.source_id, Chunk.ordinal))]

    def conversation(self, owner, notebook_id, conversation_id):
        with self.session() as s:
            return values(s.scalar(select(Conversation).join(Notebook).where(Conversation.id == conversation_id,
                Conversation.notebook_id == notebook_id, Notebook.owner_id == owner)))

    def conversations(self, owner, notebook_id):
        with self.session() as s:
            return [values(x) for x in s.scalars(select(Conversation).join(Notebook).where(Conversation.notebook_id == notebook_id,
                Notebook.owner_id == owner).order_by(Conversation.created_at.desc()))]

    def create_conversation(self, notebook_id, title):
        with self.session.begin() as s:
            row = Conversation(id=uuid4().hex, notebook_id=notebook_id, title=title)
            s.add(row); s.flush(); return values(row)

    def _message(self, s, m):
        row = values(m)
        row['source_ids'] = json.loads(row.pop('source_ids_json'))
        row['warnings'] = json.loads(row.pop('warnings_json'))
        row['citations'] = [values(c) for c in s.scalars(select(Citation).where(Citation.message_id == m.id).order_by(Citation.label))]
        return row

    def message(self, message_id):
        with self.session() as s:
            m = s.get(Message, message_id)
            return self._message(s, m) if m else None

    def messages(self, conversation_id):
        with self.session() as s:
            return [self._message(s, m) for m in s.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at, Message.id))]

    def request_message(self, conversation_id, request_key):
        with self.session() as s:
            row = s.scalar(select(Message).where(Message.conversation_id == conversation_id, Message.request_key == request_key, Message.role == 'assistant'))
            return self._message(s, row) if row else None

    def reserve_message(self, conversation_id, request_key, fingerprint, question, source_ids):
        existing = self.request_message(conversation_id, request_key)
        if existing: return existing, 'replay' if existing['request_fingerprint'] == fingerprint else 'conflict'
        try:
            with self.session.begin() as s:
                user = Message(id=uuid4().hex, conversation_id=conversation_id, role='user', content=question,
                    status='complete', request_key=request_key, request_fingerprint=fingerprint, source_ids_json=json.dumps(source_ids))
                s.add(user); s.flush()
                assistant = Message(id=uuid4().hex, conversation_id=conversation_id, role='assistant', content='',
                    status='running', request_key=request_key, request_fingerprint=fingerprint, source_ids_json=json.dumps(source_ids))
                s.add(assistant); s.flush(); result = self._message(s, assistant)
            return result, 'new'
        except IntegrityError:
            existing = self.request_message(conversation_id, request_key)
            if existing: return existing, 'replay' if existing['request_fingerprint'] == fingerprint else 'conflict'
            return None, 'busy'

    def checkpoint(self, message_id, content):
        with self.session.begin() as s:
            s.execute(update(Message).where(Message.id == message_id, Message.status == 'running').values(content=content, updated_at=now()))

    def finish_message(self, message_id, content, citations, warnings):
        with self.session.begin() as s:
            m = s.get(Message, message_id)
            if m.status != 'running': raise RuntimeError('Message no longer running')
            m.content = content; m.status = 'complete'; m.warnings_json = json.dumps(warnings, ensure_ascii=False); m.updated_at = now()
            for citation in citations:
                s.add(Citation(id=uuid4().hex, message_id=message_id, **citation))

    def fail_message(self, message_id, status='interrupted', error='回答未完成。', content=None):
        with self.session.begin() as s:
            m = s.get(Message, message_id)
            if m and m.status == 'running':
                m.status = status; m.error = error; m.updated_at = now()
                if content is not None: m.content = content
