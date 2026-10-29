"""Explicit local config import. Secrets stay in memory, never in repr/metadata."""
from dataclasses import dataclass, field
from pathlib import Path
from hashlib import sha256
from urllib.parse import urlsplit
import json
import os
from dotenv import dotenv_values


@dataclass(frozen=True)
class Endpoint:
    base_url: str
    model: str
    api_key: str = field(default='', repr=False)
    dimensions: int | None = None

    @property
    def configured(self):
        return bool(self.api_key and self.model and self.base_url)

    @property
    def profile(self):
        return sha256(json.dumps([self.base_url.rstrip('/'), self.model, self.dimensions, 'cosine-v1'], ensure_ascii=False).encode()).hexdigest()[:24]


@dataclass(frozen=True)
class ModelSettings:
    llm: Endpoint
    embedding: Endpoint
    reranker: Endpoint
    reranker_enabled: bool = True
    trust_env: bool = False
    timeout: float = 60
    enable_thinking: bool | None = None

    def public(self):
        def info(e): return {'host': urlsplit(e.base_url).hostname, 'model': e.model, 'configured': e.configured, 'dimensions': e.dimensions}
        return {'llm': info(self.llm), 'embedding': info(self.embedding), 'reranker': info(self.reranker),
                'reranker_enabled': self.reranker_enabled, 'embedding_profile': self.embedding.profile}


def load_settings(project_root):
    local = dotenv_values(Path(project_root) / 'backend/.env')
    reference = os.getenv('WORKBENCH_MODEL_ENV') or local.get('WORKBENCH_MODEL_ENV')
    imported = dotenv_values(Path(reference).expanduser()) if reference else {}
    e = {**imported, **local, **os.environ}
    provider = (e.get('LLM_PROVIDER') or 'openai').lower()
    if provider not in ('openai','siliconflow','deepseek'):
        raise ValueError('Unsupported LLM provider')
    prefix, default_url, default_model = {
        'siliconflow': ('SILICONFLOW', 'https://api.siliconflow.cn/v1', 'deepseek-ai/DeepSeek-V3.2'),
        'deepseek': ('DEEPSEEK', 'https://api.deepseek.com', 'deepseek-flash'),
        'openai': ('OPENAI', 'https://api.openai.com/v1', 'gpt-4o-mini'),
    }.get(provider, ('OPENAI', 'https://api.openai.com/v1', 'gpt-4o-mini'))
    def key_for(url, explicit, inherited_url, inherited_key):
        if explicit: return explicit
        # Never forward one vendor's secret to a different service endpoint.
        return inherited_key if url.rstrip('/') == inherited_url.rstrip('/') else ''

    key = e.get(prefix + '_API_KEY') or ''
    base = e.get(prefix + '_BASE_URL') or default_url
    model_key = 'SILICONFLOW_LLM_MODEL' if provider == 'siliconflow' else prefix + '_MODEL'
    llm = Endpoint(e.get('LLM_BASE_URL') or base, e.get('LLM_MODEL') or e.get(model_key) or default_model, key_for(e.get('LLM_BASE_URL') or base, e.get('LLM_API_KEY'), base, key))
    if provider == 'siliconflow':
        embedding = Endpoint(e.get('EMBEDDING_BASE_URL') or base,
            e.get('EMBEDDING_MODEL') or e.get('SILICONFLOW_EMBEDDING_MODEL') or 'BAAI/bge-large-zh-v1.5', key_for(e.get('EMBEDDING_BASE_URL') or base, e.get('EMBEDDING_API_KEY'), base, key))
    else:
        embedding = Endpoint(e.get('EMBEDDING_BASE_URL') or e.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1',
            e.get('EMBEDDING_MODEL') or 'text-embedding-3-small', key_for(e.get('EMBEDDING_BASE_URL') or e.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1',
                e.get('EMBEDDING_API_KEY'), e.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1', e.get('OPENAI_API_KEY') or ''))
    reranker = Endpoint(e.get('RERANKER_BASE_URL') or base, e.get('RERANKER_MODEL') or 'BAAI/bge-reranker-v2-m3', key_for(e.get('RERANKER_BASE_URL') or base, e.get('RERANKER_API_KEY'), base, key))
    for endpoint in [llm, embedding, reranker]:
        parsed = urlsplit(endpoint.base_url)
        if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Model endpoint must be an HTTP(S) base URL without embedded credentials/query')
    if e.get('EMBEDDING_DIMENSIONS'):
        dimension = int(e['EMBEDDING_DIMENSIONS'])
        if dimension <= 0: raise ValueError('Embedding dimensions must be positive')
        embedding = Endpoint(embedding.base_url, embedding.model, embedding.api_key, dimension)
    thinking = e.get('LLM_ENABLE_THINKING')
    return ModelSettings(llm, embedding, reranker, e.get('RERANKER_ENABLED','true').lower() != 'false',
                         e.get('MODEL_TRUST_ENV','false').lower() == 'true',
                         enable_thinking=(thinking.lower() == 'true') if thinking else None)
