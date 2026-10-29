"""Persistent manual indexing; ready only after all vectors verify successfully."""
import logging
from .errors import AppError
from app.infrastructure.models.transport import ModelError

log = logging.getLogger(__name__)


class Indexing:
    def __init__(self, repo, sources, providers, vectors):
        self.repo, self.sources, self.providers, self.vectors = repo, sources, providers, vectors
        self.profile = providers.embedding.profile

    def decorate(self, row):
        return {**row, 'index_compatible': row['index_profile'] == self.profile and row['index_status'] == 'ready'}

    def request(self, owner, notebook_id, source_id, force=False):
        source = self.sources.require(owner, notebook_id, source_id)
        if not self.providers.settings.embedding.configured:
            raise AppError(503, 'embedding_unconfigured', '请先配置 Embedding 服务。')
        if source['status'] != 'parsed':
            raise AppError(409, 'not_parsed', '请先完成资料解析。')
        if not self.repo.enqueue_index(source_id, owner, self.profile, force):
            raise AppError(409, 'index_conflict', '资料已有活动任务或索引已就绪。需要时可选择重建。')
        return self.decorate(self.sources.require(owner, notebook_id, source_id))

    def run_once(self):
        claim = self.repo.claim('index')
        if not claim: return False
        job, source = claim
        try:
            if job['target_profile'] != self.profile:
                raise ModelError('Embedding 配置已改变，请重新建立索引。')
            if not self.repo.source(job['owner_id'], job['notebook_id'], source['id']) or source['status'] != 'parsed':
                raise ModelError('资料范围或解析状态已改变。')
            chunks = self.repo.selected_chunks([source['id']])
            if not chunks: raise ModelError('没有可索引片段。')
            dimension = None
            for start in range(0, len(chunks), 16):
                batch = chunks[start:start+16]
                self.repo.stage(job['id'], 'embedding')
                embeddings = self.providers.embedding.embed([c['text'] for c in batch])
                if len(embeddings) != len(batch): raise ModelError('Embedding 数量不匹配。')
                current = len(embeddings[0])
                if not current or any(len(x) != current for x in embeddings) or dimension not in (None,current):
                    raise ModelError('Embedding 维度变化，拒绝混合索引。')
                dimension = current
                self.repo.stage(job['id'], 'writing_vectors')
                self.vectors.upsert(source['notebook_id'], self.profile, dimension, source['id'], job['target_revision'], batch, embeddings)
            self.repo.stage(job['id'], 'verifying_vectors')
            if not self.vectors.verify(source['notebook_id'], self.profile, dimension, source['id'], job['target_revision'], [c['id'] for c in chunks]):
                raise ModelError('向量索引数量校验失败。')
            self.repo.complete_index(job['id'], source['id'], self.profile, job['target_revision'], dimension)
        except Exception as exc:
            # Do not log provider exception bodies, credentials, source text or remote headers.
            log.warning('Index failed: %s', type(exc).__name__)
            message = str(exc) if isinstance(exc,ModelError) else '索引保存失败，请检查本地存储后重试。'
            self.repo.fail(job['id'], source['id'], 'index_failed', message)
        return True
