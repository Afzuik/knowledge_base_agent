"""Database operations, each using its own short-lived session/transaction."""
from uuid import uuid4
from sqlalchemy import select, delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from .models import Notebook, Source, Chunk, Job, now


def values(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns} if row is not None else None


class Repository:
    def __init__(self, engine):
        self.session = sessionmaker(engine, expire_on_commit=False)

    def notebook(self, owner, notebook_id):
        with self.session() as s:
            return values(s.scalar(select(Notebook).where(Notebook.id == notebook_id, Notebook.owner_id == owner)))

    def notebooks(self, owner):
        with self.session() as s:
            return [values(x) for x in s.scalars(select(Notebook).where(Notebook.owner_id == owner).order_by(Notebook.created_at.desc(), Notebook.id))]

    def create_notebook(self, owner, name):
        with self.session.begin() as s:
            row = Notebook(id=uuid4().hex, owner_id=owner, name=name)
            s.add(row); s.flush()
            return values(row)

    def source(self, owner, notebook_id, source_id):
        with self.session() as s:
            return values(s.scalar(select(Source).join(Notebook).where(
                Source.id == source_id, Source.notebook_id == notebook_id, Notebook.owner_id == owner)))

    def sources(self, owner, notebook_id):
        with self.session() as s:
            return [values(x) for x in s.scalars(select(Source).join(Notebook).where(
                Source.notebook_id == notebook_id, Notebook.owner_id == owner).order_by(Source.created_at.desc(), Source.id))]

    def by_hash(self, owner, notebook_id, digest):
        with self.session() as s:
            return values(s.scalar(select(Source).join(Notebook).where(
                Source.notebook_id == notebook_id, Source.sha256 == digest, Notebook.owner_id == owner)))

    def register(self, owner, notebook_id, data):
        try:
            with self.session.begin() as s:
                source = Source(notebook_id=notebook_id, **data)
                s.add(source); s.flush()
                s.add(Job(id=uuid4().hex, source_id=source.id, notebook_id=notebook_id, owner_id=owner))
                s.flush()
                return values(source), False
        except IntegrityError:
            existing = self.by_hash(owner, notebook_id, data['sha256'])
            if existing:
                return existing, True
            raise

    def jobs(self, owner, notebook_id, source_id):
        with self.session() as s:
            return [values(x) for x in s.scalars(select(Job).where(Job.owner_id == owner,
                Job.notebook_id == notebook_id, Job.source_id == source_id).order_by(Job.created_at.desc(), Job.id))]

    def chunks(self, source_id, offset, limit):
        with self.session() as s:
            return [values(x) for x in s.scalars(select(Chunk).where(Chunk.source_id == source_id)
                .order_by(Chunk.ordinal).offset(offset).limit(limit))]

    def retry(self, owner, notebook_id, source_id):
        with self.session.begin() as s:
            changed = s.execute(update(Source).where(Source.id == source_id, Source.notebook_id == notebook_id,
                Source.status == 'failed').values(status='queued', error_code=None, error_message=None, updated_at=now()))
            if changed.rowcount != 1:
                return False
            s.add(Job(id=uuid4().hex, source_id=source_id, notebook_id=notebook_id, owner_id=owner))
            return True

    def claim(self, kind="parse"):
        with self.session.begin() as s:
            row = s.scalar(select(Job).where(Job.status == 'queued', Job.kind == kind).order_by(Job.created_at, Job.id).limit(1))
            if not row:
                return None
            changed = s.execute(update(Job).where(Job.id == row.id, Job.status == 'queued')
                .values(status='running', stage='parsing' if kind == 'parse' else 'embedding', started_at=now()))
            if changed.rowcount != 1:
                return None
            source = s.get(Source, row.source_id)
            if kind == 'parse': source.status = 'parsing'
            else: source.index_status = 'indexing'
            source.updated_at = now()
            s.flush()
            return values(row), values(source)

    def stage(self, job_id, stage):
        with self.session.begin() as s:
            s.execute(update(Job).where(Job.id == job_id, Job.status == 'running').values(stage=stage))

    def complete(self, job_id, source_id, chunks, page_count):
        with self.session.begin() as s:
            job = s.get(Job, job_id)
            if job.status != 'running':
                raise RuntimeError('Job no longer running')
            s.execute(delete(Chunk).where(Chunk.source_id == source_id))
            s.add_all([Chunk(source_id=source_id, **chunk) for chunk in chunks])
            source = s.get(Source, source_id)
            source.index_status = 'not_indexed'; source.index_profile = None; source.index_revision = None; source.index_dimension = None; source.index_error = None
            source.status = 'parsed'; source.chunk_count = len(chunks); source.page_count = page_count
            source.error_code = None; source.error_message = None; source.updated_at = now()
            job.status = 'succeeded'; job.stage = 'done'; job.finished_at = now()

    def fail(self, job_id, source_id, code, message):
        with self.session.begin() as s:
            job = s.get(Job, job_id); source = s.get(Source, source_id)
            if job.kind == 'index':
                source.index_status = 'failed'; source.index_error = message
            else:
                source.status = 'failed'; source.error_code = code; source.error_message = message
            source.updated_at = now()
            job.status = 'failed'; job.stage = 'failed'; job.error_code = code; job.error_message = message; job.finished_at = now()

    def all_sources(self):
        with self.session() as s:
            return [values(x) for x in s.scalars(select(Source))]

    def recover(self, missing_ids):
        with self.session.begin() as s:
            for job in s.scalars(select(Job).where(Job.status == 'running')):
                job.status = 'failed'; job.stage = 'failed'; job.error_code = 'interrupted'
                job.error_message = '处理被中断，请重试。'; job.finished_at = now()
            for source in s.scalars(select(Source)):
                if source.id in missing_ids or source.status == 'parsing':
                    code = 'missing_file' if source.id in missing_ids else 'interrupted'
                    message = '原始文件缺失，请恢复原文件后重试。' if code == 'missing_file' else '处理被中断，请重试。'
                    source.status = 'failed'; source.error_code = code; source.error_message = message; source.updated_at = now()
                    for job in s.scalars(select(Job).where(Job.source_id == source.id, Job.status.in_(['queued','running']))):
                        job.status = 'failed'; job.stage = 'failed'; job.error_code = code; job.error_message = message; job.finished_at = now()
