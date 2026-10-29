CREATE TABLE notebooks (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 100),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX ix_notebooks_owner_id ON notebooks(owner_id);
CREATE TABLE sources (
 id TEXT PRIMARY KEY, notebook_id TEXT NOT NULL REFERENCES notebooks(id), filename TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('pdf','md','txt')), size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
 sha256 TEXT NOT NULL, storage_key TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL CHECK(status IN ('queued','parsing','parsed','failed')),
 page_count INTEGER NOT NULL DEFAULT 0, chunk_count INTEGER NOT NULL DEFAULT 0,
 error_code TEXT, error_message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(notebook_id,sha256)
);
CREATE INDEX ix_sources_notebook_id ON sources(notebook_id);
CREATE TABLE chunks (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), ordinal INTEGER NOT NULL,
 text TEXT NOT NULL, page_start INTEGER, page_end INTEGER,
 char_start INTEGER NOT NULL, char_end INTEGER NOT NULL,
 UNIQUE(source_id,ordinal)
);
CREATE INDEX ix_chunks_source_id ON chunks(source_id);
CREATE TABLE jobs (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), notebook_id TEXT NOT NULL REFERENCES notebooks(id),
 owner_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
 stage TEXT NOT NULL, error_code TEXT, error_message TEXT, created_at TEXT NOT NULL,
 started_at TEXT, finished_at TEXT
);
CREATE INDEX ix_jobs_source_id ON jobs(source_id);
CREATE UNIQUE INDEX ix_jobs_active_source ON jobs(source_id) WHERE status IN ('queued','running');
