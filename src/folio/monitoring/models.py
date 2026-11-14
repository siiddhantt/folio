from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PageStatistics(BaseModel):
    total: int
    with_content: int
    without_content: int
    documents_without_extraction: int


class DocumentStatistics(BaseModel):
    as_of: datetime
    total_documents: int
    original_bytes: int = Field(description="Bytes in current originals, not disk usage.")
    extraction_states: dict[str, int]
    summary_states: dict[str, int]
    index_states: dict[str, int]
    pages: PageStatistics


class DurationStatistics(BaseModel):
    samples: int = 0
    mean: float | None = None
    max: float | None = None


class JobStatistics(BaseModel):
    total: int = 0
    states: dict[str, int] = Field(default_factory=dict)


class AttemptStatistics(BaseModel):
    total: int = 0
    completed: int = 0
    unfinished: int = 0
    failed: int = 0
    duration_seconds: DurationStatistics = Field(default_factory=DurationStatistics)


class StageStatistics(BaseModel):
    jobs: JobStatistics = Field(default_factory=JobStatistics)
    attempts: AttemptStatistics = Field(default_factory=AttemptStatistics)
    terminal_errors: dict[str, int] = Field(default_factory=dict)


class ProcessingMetrics(BaseModel):
    as_of: datetime
    scope: Literal["all_retained"] = "all_retained"
    stages: dict[Literal["extraction", "summary", "indexing", "chat", "memory"], StageStatistics]
