CREATE TABLE notes (
 id TEXT PRIMARY KEY,
 notebook_id TEXT NOT NULL REFERENCES notebooks(id),
 origin_message_id TEXT NOT NULL UNIQUE,
 title TEXT NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 120),
 body_markdown TEXT NOT NULL CHECK(length(body_markdown) <= 100000),
 citations_snapshot_json TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision >= 1),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX ix_notes_notebook_id ON notes(notebook_id);
