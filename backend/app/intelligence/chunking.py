"""Stable source-scoped chunks, page-local character offsets; no invented page numbers."""
from hashlib import sha256


def chunk_document(source_id, document, size=800, overlap=100):
    if not 0 <= overlap < size:
        raise ValueError('Expected 0 <= overlap < size')
    chunks = []
    for page in document.pages:
        start = 0
        while start < len(page.text):
            end = min(start + size, len(page.text))
            text = page.text[start:end]
            if text.strip():
                ordinal = len(chunks)
                key = sha256(f'{source_id}:{page.page}:{start}:{end}:{text}'.encode()).hexdigest()
                chunks.append(dict(id=key, ordinal=ordinal, text=text,
                    page_start=page.page, page_end=page.page, char_start=start, char_end=end))
            if end == len(page.text):
                break
            start = end - overlap
    return chunks
