from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: Literal['ok'] = 'ok'
    stage: Literal['research'] = 'research'
    mode: Literal['local-single-user'] = 'local-single-user'
    business_ready: bool = False  # Reserved release-readiness flag, not production certification.
    ingestion_ready: bool = True
    qa_ready: bool = False
    max_upload_bytes: int
    model_services: dict


class NotebookCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name', mode='before')
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class NotebookOut(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str


class SourceOut(BaseModel):
    id: str
    notebook_id: str
    filename: str
    kind: str
    size_bytes: int
    sha256: str
    status: Literal['queued', 'parsing', 'parsed', 'failed']
    index_status: Literal['not_indexed','queued','indexing','ready','failed']
    index_profile: str | None
    index_revision: str | None
    index_dimension: int | None
    index_error: str | None
    index_compatible: bool = False
    page_count: int
    chunk_count: int
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str


class UploadOut(BaseModel):
    source: SourceOut
    duplicate: bool


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    stage: str
    error_code: str | None
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class SourceDetail(BaseModel):
    source: SourceOut
    jobs: list[JobOut]


class ChunkOut(BaseModel):
    id: str
    source_id: str
    ordinal: int
    text: str
    page_start: int | None
    page_end: int | None
    char_start: int
    char_end: int


class ChunkPage(BaseModel):
    items: list[ChunkOut]
    total: int
    offset: int
    limit: int


class IndexRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    force: bool = False


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='研究对话', max_length=100)


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=1, max_length=10)
    request_key: str = Field(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9_-]+$')

    @field_validator('question', mode='before')
    @classmethod
    def trim_question(cls, value):
        return value.strip() if isinstance(value,str) else value


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    origin_message_id: str = Field(min_length=1,max_length=128)
    title: str | None = Field(default=None,min_length=1,max_length=120)


class NoteUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    title: str = Field(min_length=1,max_length=120)
    body_markdown: str = Field(max_length=100000)


class NoteSummary(BaseModel):
    id: str
    notebook_id: str
    origin_message_id: str
    title: str
    revision: int
    created_at: str
    updated_at: str


class NoteOut(NoteSummary):
    body_markdown: str
    citations: list[dict]
    used_labels: list[str]
    invalid_labels: list[str]


class NoteCreateOut(BaseModel):
    note: NoteOut
    created: bool
