"""Existing upload, processing and evidence response contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from folio.responses import SourceTable

RequestState = Literal["open", "succeeded", "failed"]
AttemptState = Literal["pending", "running", "succeeded", "failed"]


class UploadReceipt(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "00000000-0000-4000-8000-000000000001",
                    "file_version_id": "00000000-0000-4000-8000-000000000002",
                    "request_id": "00000000-0000-4000-8000-000000000003",
                    "status_url": "/ingestion-requests/00000000-0000-4000-8000-000000000003",
                }
            ]
        }
    )
    document_id: UUID
    file_version_id: UUID
    request_id: UUID
    status_url: str


class ProcessingAttempt(BaseModel):
    id: UUID
    attempt_no: int
    state: AttemptState
    available_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_detail: str | None
    parser_status: str | None
    retryable: bool | None
    metrics: dict[str, float] = Field(examples=[{"parser_duration_seconds": 1.25}])
    dispatch_error: str | None
    dispatch_count: int
    terminal_delivery_failures: int


class RequestStatus(BaseModel):
    request_id: UUID
    document_id: UUID
    file_version_id: UUID
    state: RequestState = Field(examples=["open"])
    authorized_attempt_id: UUID | None
    created_at: datetime
    finished_at: datetime | None
    attempts: list[ProcessingAttempt]
    revision_id: UUID | None = Field(
        description="Published evidence revision, or null until usable extraction is saved."
    )


class DocumentMetadata(BaseModel):
    id: UUID
    display_name: str = Field(examples=["sample-guide.pdf"])
    created_at: datetime
    current_request_id: UUID | None
    active_revision_id: UUID | None


class ProcessingRun(BaseModel):
    request_id: UUID
    document_id: UUID
    revision_id: UUID | None
    filename: str = Field(examples=["sample-guide.pdf"])
    accepted_at: datetime
    extraction_state: RequestState
    current_attempt_state: AttemptState
    extraction_error_code: str | None
    summary_state: Literal["not_scheduled", "pending", "running", "ready", "unavailable", "failed"]
    summary_error_code: str | None


class RunPage(BaseModel):
    items: list[ProcessingRun]
    next_cursor: str | None = Field(
        description="Opaque cursor for the next, older page of runs; null on the final page.",
        examples=[None],
    )


class SourcePage(BaseModel):
    page_no: int
    width_pt: float | None
    height_pt: float | None
    content_observation: Literal["content_recovered", "no_content_recovered"]
    diagnostics: list[dict[str, JsonValue]]


class SourceLocation(BaseModel):
    page_no: int
    char_start: int | None
    char_end: int | None
    x0: float | None
    y0: float | None
    x1: float | None
    y1: float | None


class SourceElement(BaseModel):
    element_id: str = Field(examples=["e1"])
    kind: str = Field(examples=["text", "table"])
    reading_order: int
    parent_element_id: str | None
    text: str | None
    table_data: SourceTable | None
    locations: list[SourceLocation]


class RevisionEvidence(BaseModel):
    revision_id: UUID
    document_id: UUID
    file_version_id: UUID
    request_id: UUID
    created_at: datetime
    parser_manifest: dict[str, JsonValue] = Field(
        description="Versioned parser, model and normalization provenance."
    )
    normalization_version: int = Field(examples=[1])
    diagnostics: list[dict[str, JsonValue]]
    pages: list[SourcePage]
    next_after_order: int | None
    elements: list[SourceElement]
