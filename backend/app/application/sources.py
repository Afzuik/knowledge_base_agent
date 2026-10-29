"""Upload and retry use cases. Never trust a caller-provided owner or path."""
from pathlib import PurePosixPath
from uuid import uuid4
from app.infrastructure.storage.local_files import UploadRejected
from .errors import AppError


class Sources:
    def __init__(self, repo, files, notebooks, config):
        self.repo, self.files, self.notebooks, self.config = repo, files, notebooks, config

    def require(self, owner, notebook_id, source_id):
        self.notebooks.require(owner, notebook_id)
        row = self.repo.source(owner, notebook_id, source_id)
        if row is None:
            raise AppError(404, 'not_found', '资料不存在或不属于当前专题。')
        return row

    def list(self, owner, notebook_id):
        self.notebooks.require(owner, notebook_id)
        return self.repo.sources(owner, notebook_id)

    def upload(self, owner, notebook_id, filename, stream):
        self.notebooks.require(owner, notebook_id)
        name = PurePosixPath((filename or '').replace('\\', '/')).name
        if not name or len(name) > 240 or any(ord(c) < 32 for c in name):
            raise AppError(422, 'invalid_filename', '文件名无效或过长。')
        kind = PurePosixPath(name).suffix.lower().lstrip('.')
        if kind not in ('pdf', 'md', 'txt'):
            raise AppError(415, 'unsupported_type', '仅支持 PDF、Markdown 和 TXT。')
        try:
            temp, size, digest = self.files.stage(stream, self.config.max_upload_bytes)
        except UploadRejected as exc:
            raise AppError(422, 'upload_rejected', str(exc)) from exc
        source_id = uuid4().hex
        try:
            existing = self.repo.by_hash(owner, notebook_id, digest)
            if existing:
                return existing, True
            self.files.promote(temp, source_id)
            try:
                result, duplicate = self.repo.register(owner, notebook_id, dict(id=source_id,
                    filename=name, kind=kind, size_bytes=size, sha256=digest, storage_key=source_id))
            except Exception:
                self.files.remove(source_id)
                raise
            if duplicate:
                self.files.remove(source_id)
            return result, duplicate
        finally:
            self.files.discard(temp)

    def detail(self, owner, notebook_id, source_id):
        row = self.require(owner, notebook_id, source_id)
        return row, self.repo.jobs(owner, notebook_id, source_id)

    def chunks(self, owner, notebook_id, source_id, offset=0, limit=50):
        row = self.require(owner, notebook_id, source_id)
        if row['status'] != 'parsed':
            raise AppError(409, 'not_parsed', '资料尚未成功解析。')
        return self.repo.chunks(source_id, offset, limit), row['chunk_count']

    def retry(self, owner, notebook_id, source_id):
        row = self.require(owner, notebook_id, source_id)
        if not self.files.exists(row['storage_key']):
            raise AppError(409, 'missing_file', '原始文件缺失，恢复后才能重试。')
        if not self.repo.retry(owner, notebook_id, source_id):
            raise AppError(409, 'not_retryable', '只有失败资料可以重试，当前任务可能已在处理。')
        return self.require(owner, notebook_id, source_id)
