"""待实现 SQLAlchemy 实体，第一条真实链路开始时建表。

notebooks: id, owner_id, title, timestamps
sources: id, notebook_id, hash, filename, status, index_version
chunks: id, source_id, content, page_number, ordinal
conversations: id, notebook_id, title
messages: id, conversation_id, role, content, selected_source_ids, status
citations: id, message_id, chunk_id, number, source_snapshot, text_snapshot
notes: id, notebook_id, title, content, origin_message_id, citation_snapshot
jobs: id, owner_id, notebook_id, source_id, status, error, timestamps

SQLite is the source of truth. Chroma indexes are rebuildable.
"""
