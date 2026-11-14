"""Shared public response shapes, used for documentation without reserializing payloads."""

from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, Field, JsonValue


class EvidenceCoverage(BaseModel):
    diagnostics: list[dict[str, JsonValue]] = Field(
        description="Known parser/normalization diagnostics; individual keys depend on the source."
    )
    pages_without_content: list[int] = Field(
        description="Physical PDF pages with no recovered content; the cause may be unknown.",
        examples=[[2]],
    )


class AnswerCoverage(EvidenceCoverage):
    scope: Literal["available_evidence"]


class ResponseError(BaseModel):
    code: str
    message: str


class TableCell(TypedDict):
    row: int
    column: int
    row_span: int
    column_span: int
    text: str
    column_header: bool
    row_header: bool
    row_section: NotRequired[bool]


class SourceTable(BaseModel):
    row_count: int
    column_count: int
    cells: list[TableCell]
