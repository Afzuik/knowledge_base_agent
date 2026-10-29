"""Explicit-embedding local Chroma adapter; no automatic models or downloads."""
from hashlib import sha256
from threading import Lock


class ChromaVectors:
    def __init__(self, directory):
        self.directory = directory
        self._client = None
        self._lock = Lock()

    def _collection(self, notebook_id, profile, dimension):
        with self._lock:
            if self._client is None:
                import chromadb
                from chromadb.config import Settings
                self._client = chromadb.PersistentClient(path=str(self.directory), settings=Settings(anonymized_telemetry=False))
            name = 'kb-' + sha256(f'{notebook_id}:{profile}:{dimension}'.encode()).hexdigest()[:48]
            return self._client.get_or_create_collection(name=name, embedding_function=None,
                configuration={'hnsw': {'space': 'cosine'}})

    def upsert(self, notebook_id, profile, dimension, source_id, revision, chunks, embeddings):
        collection = self._collection(notebook_id, profile, dimension)
        collection.upsert(ids=[revision + ':' + c['id'] for c in chunks], embeddings=embeddings,
            metadatas=[{'scope': source_id + ':' + revision, 'chunk_id': c['id']} for c in chunks])

    def verify(self, notebook_id, profile, dimension, source_id, revision, chunk_ids):
        collection = self._collection(notebook_id, profile, dimension)
        rows = collection.get(where={'scope': source_id + ':' + revision}, include=[])
        return set(rows['ids']) == {revision + ':' + x for x in chunk_ids}

    def query(self, notebook_id, profile, dimension, scopes, vector, k):
        if not scopes: raise ValueError('Empty vector scope is forbidden')
        collection = self._collection(notebook_id, profile, dimension)
        result = collection.query(query_embeddings=[vector], where={'scope': {'$in': scopes}}, n_results=k, include=['metadatas'])
        rows = result['metadatas'][0]
        if any(x['scope'] not in scopes for x in rows): raise RuntimeError('Vector scope mismatch')
        return [x['chunk_id'] for x in rows]
