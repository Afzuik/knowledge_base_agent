ALTER TABLE sources ADD COLUMN index_status TEXT NOT NULL DEFAULT 'not_indexed' CHECK(index_status IN ('not_indexed','queued','indexing','ready','failed'));
ALTER TABLE sources ADD COLUMN index_profile TEXT;
ALTER TABLE sources ADD COLUMN index_revision TEXT;
ALTER TABLE sources ADD COLUMN index_dimension INTEGER;
ALTER TABLE sources ADD COLUMN index_error TEXT;
ALTER TABLE jobs ADD COLUMN kind TEXT NOT NULL DEFAULT 'parse' CHECK(kind IN ('parse','index'));
ALTER TABLE jobs ADD COLUMN target_profile TEXT;
ALTER TABLE jobs ADD COLUMN target_revision TEXT;
CREATE TABLE conversations (
 id TEXT PRIMARY KEY, notebook_id TEXT NOT NULL REFERENCES notebooks(id), title TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX ix_conversations_notebook_id ON conversations(notebook_id);
CREATE TABLE messages (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id), role TEXT NOT NULL CHECK(role IN ('user','assistant')),
 content TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('running','complete','failed','interrupted')),
 request_key TEXT NOT NULL, request_fingerprint TEXT NOT NULL, source_ids_json TEXT NOT NULL, warnings_json TEXT NOT NULL,
 error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(conversation_id,request_key,role)
);
CREATE INDEX ix_messages_conversation_id ON messages(conversation_id);
CREATE UNIQUE INDEX ix_messages_running ON messages(conversation_id) WHERE role='assistant' AND status='running';
CREATE TABLE citations (
 id TEXT PRIMARY KEY, message_id TEXT NOT NULL REFERENCES messages(id), label TEXT NOT NULL,
 chunk_id TEXT NOT NULL, source_id TEXT NOT NULL, filename TEXT NOT NULL, text TEXT NOT NULL,
 page_start INTEGER, page_end INTEGER, char_start INTEGER NOT NULL, char_end INTEGER NOT NULL,
 index_revision TEXT NOT NULL, UNIQUE(message_id,label)
);
CREATE INDEX ix_citations_message_id ON citations(message_id);
