"""Orchestrates parsing and transactional persistence; no embedding or model calls."""
import logging
from app.intelligence.parsing import parse_document, ParseError
from app.intelligence.chunking import chunk_document
from app.infrastructure.storage.local_files import FileIntegrityError

log = logging.getLogger(__name__)


class Ingestion:
    def __init__(self, repo, files, config):
        self.repo, self.files, self.config = repo, files, config

    def recover(self):
        sources = self.repo.all_sources()
        missing = {x['id'] for x in sources if not self.files.exists(x['storage_key'])}
        self.repo.recover(missing)
        self.files.cleanup({x['storage_key'] for x in sources})

    def run_once(self):
        claimed = self.repo.claim()
        if not claimed:
            return False
        job, source = claimed
        try:
            # Confirm persisted identity/scope before handing data to processing.
            if not self.repo.source(job['owner_id'], job['notebook_id'], source['id']):
                raise ParseError('invalid_scope', '任务与资料归属不一致。')
            content = self.files.read_verified(source['storage_key'], source['size_bytes'],
                source['sha256'], self.config.max_upload_bytes)
            document = parse_document(content, source['kind'], self.config.max_text_chars, self.config.max_pdf_pages)
            self.repo.stage(job['id'], 'chunking')
            chunks = chunk_document(source['id'], document, self.config.chunk_size, self.config.chunk_overlap)
            self.repo.complete(job['id'], source['id'], chunks, document.page_count)
        except FileNotFoundError:
            self.repo.fail(job['id'], source['id'], 'missing_file', '原始文件缺失，请恢复后重试。')
        except FileIntegrityError as exc:
            self.repo.fail(job['id'], source['id'], 'file_changed', str(exc))
        except ParseError as exc:
            self.repo.fail(job['id'], source['id'], exc.code, str(exc))
        except Exception:
            log.exception('Ingestion failed for job %s', job['id'])
            self.repo.fail(job['id'], source['id'], 'processing_error', '处理或保存失败，请重试并检查本地日志。')
        return True
