"""Chinese tokenization, same-scope BM25 + vector RRF; bounded evidence budget."""
import re
import jieba
from rank_bm25 import BM25Okapi

jieba.setLogLevel(40)


def tokens(text):
    return [x.lower() for x in jieba.lcut(text) if re.search(r'[\w\u4e00-\u9fff]', x)] or ['_empty_']


def retrieve(query, notebook_id, sources, chunks, providers, vectors, recall_k=20, top_k=6, max_chars=12000):
    if not chunks: return [], []
    if any(c['source_id'] not in {s['id'] for s in sources} for c in chunks): raise ValueError('Chunk scope mismatch')
    revisions = {s['id']:s['index_revision'] for s in sources}
    # Bind evidence to the validated retrieval snapshot, not mutable current source metadata.
    allowed = {c['id']:{**c, 'index_revision':revisions[c['source_id']]} for c in chunks}
    embedding = providers.embedding.embed([query])[0]
    dimension = len(embedding)
    if any(s['index_dimension'] != dimension for s in sources):
        raise ValueError('Embedding dimension changed; rebuild selected indexes')
    scopes = [s['id'] + ':' + s['index_revision'] for s in sources]
    vector_ids = vectors.query(notebook_id, providers.embedding.profile, dimension, scopes, embedding, recall_k)
    if any(x not in allowed for x in vector_ids): raise ValueError('Vector returned out-of-scope chunk')
    bm = BM25Okapi([tokens(c['text']) for c in chunks])
    scores = bm.get_scores(tokens(query))
    lexical_ids = [chunks[i]['id'] for i in sorted(range(len(chunks)),key=lambda i:float(scores[i]),reverse=True) if scores[i] > 0][:recall_k]
    fused = {}
    for ranked in [vector_ids,lexical_ids]:
        for rank, cid in enumerate(dict.fromkeys(ranked),1): fused[cid] = fused.get(cid,0) + 1/(60+rank)
    candidates = [allowed[cid] for cid in sorted(fused,key=lambda c:(-fused[c],c))[:recall_k]]
    warnings = []
    if providers.reranker.enabled and candidates:
        try:
            indices = providers.reranker.rank(query, [c['text'] for c in candidates], top_k)
            candidates = [candidates[i] for i in indices]
        except Exception:
            warnings.append('精排不可用，本轮采用 RRF 排序。')
    evidence = []; used = 0
    for candidate in candidates[:top_k]:
        if used + len(candidate['text']) > max_chars: break
        used += len(candidate['text'])
        evidence.append({**candidate,'label':f'S{len(evidence)+1}'})
    return evidence, warnings
