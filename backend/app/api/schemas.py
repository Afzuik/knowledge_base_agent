from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: Literal['ok'] = 'ok'
    stage: Literal['ingestion'] = 'ingestion'
    mode: Literal['local-single-user'] = 'local-single-user'
    business_ready: bool = False  # Full research workflow is still unavailable.
    ingestion_ready: bool = True
    qa_ready: bool = False
    max_upload_bytes: int


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
    index_status: Literal['not_indexed'] = 'not_indexed'
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
