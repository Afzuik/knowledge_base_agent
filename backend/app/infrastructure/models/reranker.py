from .transport import post, ModelError


class Reranker:
    def __init__(self, settings):
        self.settings = settings
        self.endpoint = settings.reranker
        self.enabled = settings.reranker_enabled and self.endpoint.configured

    def rank(self, query, texts, top_n):
        data = post(self.settings, self.endpoint, '/rerank', dict(model=self.endpoint.model, query=query,
            documents=texts, top_n=min(top_n,len(texts)), return_documents=False))
        try:
            rows = sorted(data['results'], key=lambda r: r['relevance_score'], reverse=True)
            indices = [r['index'] for r in rows]
            if not indices or len(indices) != len(set(indices)) or any(type(i) is not int or not 0 <= i < len(texts) for i in indices): raise ValueError()
            return indices[:top_n]
        except (KeyError,TypeError,ValueError):
            raise ModelError('精排结果无效。') from None
