"""Scope, idempotency, research orchestration and message durability."""
import hashlib
import json
import logging
import time
from .errors import AppError
from app.intelligence.generation import history_pairs, query_for, messages_for
from app.intelligence.retrieval import retrieve
from app.intelligence.citations import finalize
from app.infrastructure.models.transport import ModelError

log = logging.getLogger(__name__)


class Chat:
    def __init__(self, repo, notebooks, sources, providers, vectors):
        self.repo, self.notebooks, self.sources = repo, notebooks, sources
        self.providers, self.vectors = providers, vectors

    def require_conversation(self, owner, notebook_id, conversation_id):
        row = self.repo.conversation(owner, notebook_id, conversation_id)
        if not row: raise AppError(404,'not_found','会话不存在或不属于当前专题。')
        return row

    def create(self, owner, notebook_id, title):
        self.notebooks.require(owner, notebook_id)
        return self.repo.create_conversation(notebook_id, title.strip() or '研究对话')

    def conversations(self, owner, notebook_id):
        self.notebooks.require(owner, notebook_id)
        return self.repo.conversations(owner, notebook_id)

    def messages(self, owner, notebook_id, conversation_id):
        self.require_conversation(owner, notebook_id, conversation_id)
        return self.repo.messages(conversation_id)

    def scope(self, owner, notebook_id, source_ids):
        rows = [self.sources.require(owner, notebook_id, sid) for sid in source_ids]
        if not rows: raise AppError(422,'empty_scope','请至少选择一份资料。')
        if any(s['status'] != 'parsed' or s['index_status'] != 'ready' or s['index_profile'] != self.providers.embedding.profile for s in rows):
            raise AppError(409,'index_not_ready','所选资料尚未就绪或模型配置已变化，请重新建立索引。')
        return rows

    def prepare(self, owner, notebook_id, conversation_id, question, source_ids, request_key):
        self.require_conversation(owner, notebook_id, conversation_id)
        ids = sorted(set(source_ids))
        fingerprint = hashlib.sha256(json.dumps([question,ids],ensure_ascii=False).encode()).hexdigest()
        # Replay does not re-query or charge models, even if indexing state has since changed.
        existing = self.repo.request_message(conversation_id, request_key)
        if existing:
            if existing['request_fingerprint'] != fingerprint: raise AppError(409,'request_key_conflict','同一请求标识不能用于不同问题或资料。')
            if existing['status'] == 'running': raise AppError(409,'already_running','本问题正在生成，请勿重复提交。')
            return existing, None, True
        selected = self.scope(owner, notebook_id, ids)
        if not self.providers.settings.llm.configured or not self.providers.settings.embedding.configured:
            raise AppError(503,'model_unconfigured','请先配置 LLM 与 Embedding 服务。')
        history = history_pairs(self.repo.messages(conversation_id), ids)
        row, outcome = self.repo.reserve_message(conversation_id, request_key, fingerprint, question, ids)
        if outcome in ('conflict','busy'): raise AppError(409,'conversation_busy','会话正在生成或请求标识冲突。')
        if outcome == 'replay' and row['status'] == 'running': raise AppError(409,'already_running','问题正在生成。')
        return row, (selected,history), outcome == 'replay'

    def events(self, row, prepared, replay, owner, notebook_id, question):
        if replay:
            yield {'event':'done' if row['status']=='complete' else 'error','data':{'message':row,'replayed':True}}
            return
        content = ''; finished = False; last_save = time.monotonic()
        try:
            yield {'event':'start','data':{'message_id':row['id']}}
            selected, history = prepared
            yield {'event':'status','data':{'stage':'retrieving'}}
            # Recheck immediately before retrieval in case indexing changed after reservation.
            current = self.scope(owner, notebook_id, row['source_ids'])
            if [(s['id'],s['index_revision']) for s in selected] != [(s['id'],s['index_revision']) for s in current]:
                raise ModelError('索引版本已变化，请重新提问。')
            query = query_for(question, history, self.providers.llm)
            refreshed = self.scope(owner, notebook_id, row['source_ids'])
            if [(s['id'],s['index_revision']) for s in current] != [(s['id'],s['index_revision']) for s in refreshed]:
                raise ModelError('检索准备期间索引版本发生变化，请重新提问。')
            chunks = self.repo.selected_chunks(row['source_ids'])
            evidence, warnings = retrieve(query, notebook_id, current, chunks, self.providers, self.vectors)
            yield {'event':'status','data':{'stage':'generating'}}
            if not evidence:
                content = '根据所选资料无法回答：未找到可用证据。'
                yield {'event':'delta','data':{'text':content}}
            else:
                for delta in self.providers.llm.stream(messages_for(question,history,evidence)):
                    if not isinstance(delta,str): raise ModelError('模型返回的文本格式无效。')
                    content += delta
                    if len(content)>20000: raise ModelError('生成内容超过长度限制。')
                    if time.monotonic()-last_save>0.5:
                        self.repo.checkpoint(row['id'],content); last_save=time.monotonic()
                    yield {'event':'delta','data':{'text':delta}}
            if not content.strip(): raise ModelError('模型返回空回答。')
            content, citations, citation_warnings = finalize(content,evidence)
            self.repo.finish_message(row['id'],content,citations,warnings+citation_warnings)
            finished = True
            yield {'event':'done','data':{'message':self.repo.message(row['id'])}}
        except Exception as exc:
            log.warning('Chat failed: %s',type(exc).__name__)
            message = str(exc) if isinstance(exc,(ModelError,AppError)) else '问答执行或保存失败，请检查配置和本地存储。'
            self.repo.fail_message(row['id'],'failed',message,content)
            finished = True
            yield {'event':'error','data':{'message':self.repo.message(row['id'])}}
        finally:
            if not finished:
                self.repo.fail_message(row['id'],'interrupted','连接中断，回答未完成。',content)
