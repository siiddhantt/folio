"""Saved summary response; reads never invoke a model."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from folio.responses import AnswerCoverage, ResponseError, SourceTable


class CitedStatement(BaseModel):
    text: str
    source_ids: list[str]


class SummaryCitation(BaseModel):
    source_id: str
    text: str | None
    table_data: SourceTable | None
    pages: list[int]


class SummaryUsage(BaseModel):
    attempts: int
    prompt_tokens: int | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    response_characters: int | None
    last_finish_reason: str | None
    cost_usd: str | None = Field(
        description="Decimal USD string; null if no known cost or any reservation is unresolved.",
        examples=["0.00012000"],
    )
    uncertain_cost_usd: str = Field(
        description="Decimal USD string for outstanding reserved or unknown charges.",
        examples=["0"],
    )


class DocumentSummary(BaseModel):
    revision_id: UUID
    run_id: UUID | None
    state: Literal["pending", "running", "ready", "unavailable", "failed", "not_scheduled"] = Field(
        examples=["ready", "not_scheduled"]
    )
    overview: CitedStatement | None = Field(
        examples=[
            {"text": "The guide describes home insulation options.", "source_ids": ["e1"]},
            None,
        ]
    )
    points: list[CitedStatement]
    citations: list[SummaryCitation]
    coverage: AnswerCoverage
    error: ResponseError | None
    usage: SummaryUsage
    created_at: datetime | None
    finished_at: datetime | None
