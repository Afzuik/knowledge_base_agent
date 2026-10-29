import math
from .transport import post, ModelError


class Embedding:
    def __init__(self, settings):
        self.settings = settings
        self.endpoint = settings.embedding
        self.profile = self.endpoint.profile

    def embed(self, texts):
        if not texts:
            return []
        payload = {'model': self.endpoint.model, 'input': texts, 'encoding_format': 'float'}
        if self.endpoint.dimensions: payload['dimensions'] = self.endpoint.dimensions
        data = post(self.settings, self.endpoint, '/embeddings', payload)
        try:
            rows = sorted(data['data'], key=lambda r: r['index'])
            if [r['index'] for r in rows] != list(range(len(texts))): raise ValueError()
            vectors = [r['embedding'] for r in rows]
            dim = len(vectors[0])
            if self.endpoint.dimensions and dim != self.endpoint.dimensions: raise ValueError()
            if not dim or any(len(v) != dim or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in v) for v in vectors): raise ValueError()
            if any(sum(x*x for x in v) == 0 for v in vectors): raise ValueError()
            return vectors
        except (KeyError, TypeError, ValueError, IndexError):
            raise ModelError('Embedding 数量、索引或向量维度无效。') from None
