"""Public index state and source-linked chunk contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from folio.responses import EvidenceCoverage


class IndexExclusion(BaseModel):
    element_id: str
    reason: str


class IndexStatus(BaseModel):
    index_id: UUID | None
    state: Literal["not_started", "pending", "running", "ready", "unavailable", "failed"] = Field(
        examples=["not_started", "ready"]
    )
    chunk_count: int
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    available_at: datetime | None
    lease_expires_at: datetime | None
    dispatch_error: str | None
    embedded_chunks: int
    model_id: str | None
    dimensions: int | None
    coverage: EvidenceCoverage
    exclusions: list[IndexExclusion]
    warnings: list[dict[str, JsonValue]]


class ChunkSource(BaseModel):
    element_id: str
    role: Literal["body", "context"]
    page_no: int


class IndexChunk(BaseModel):
    ordinal: int
    text: str
    tokens: int
    sources: list[ChunkSource]


class ChunkPage(BaseModel):
    index_id: UUID
    revision_id: UUID
    chunks: list[IndexChunk]
    next_after: int | None
    source_precision: Literal["whole_element"] = Field(
        description="Links identify whole stored elements, not verified character highlights.",
        examples=["whole_element"],
    )
