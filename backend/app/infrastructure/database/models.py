"""Persistence models; schema creation and upgrades are versioned in migrations/."""
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Notebook(Base):
    __tablename__ = "notebooks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("notebook_id", "sha256"),
        CheckConstraint("status IN ('queued','parsing','parsed','failed')"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    notebook_id: Mapped[str] = mapped_column(ForeignKey("notebooks.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    index_status: Mapped[str] = mapped_column(String, default='not_indexed')
    index_profile: Mapped[str | None] = mapped_column(String)
    index_revision: Mapped[str | None] = mapped_column(String)
    index_dimension: Mapped[int | None] = mapped_column(Integer)
    index_error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("source_id", "ordinal"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    notebook_id: Mapped[str] = mapped_column(ForeignKey("notebooks.id"))
    owner_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")
    stage: Mapped[str] = mapped_column(String, default="queued")
    kind: Mapped[str] = mapped_column(String, default='parse')
    target_profile: Mapped[str | None] = mapped_column(String)
    target_revision: Mapped[str | None] = mapped_column(String)
    error_code: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now)
    started_at: Mapped[str | None] = mapped_column(String)
    finished_at: Mapped[str | None] = mapped_column(String)


class Conversation(Base):
    __tablename__ = 'conversations'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    notebook_id: Mapped[str] = mapped_column(ForeignKey('notebooks.id'), index=True)
    title: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Message(Base):
    __tablename__ = 'messages'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id'), index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String)
    request_key: Mapped[str] = mapped_column(String)
    request_fingerprint: Mapped[str] = mapped_column(String)
    source_ids_json: Mapped[str] = mapped_column(Text)
    warnings_json: Mapped[str] = mapped_column(Text, default='[]')
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class Citation(Base):
    __tablename__ = 'citations'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey('messages.id'), index=True)
    label: Mapped[str] = mapped_column(String)
    chunk_id: Mapped[str] = mapped_column(String)
    source_id: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    index_revision: Mapped[str] = mapped_column(String)
