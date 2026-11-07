"""Serializable evidence returned by the PDF parser, independent of Docling types."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Location:
    page_no: int
    x0: float | None = None
    y0: float | None = None
    x1: float | None = None
    y1: float | None = None
    char_start: int | None = None
    char_end: int | None = None


@dataclass(frozen=True)
class Page:
    page_no: int
    width_pt: float | None
    height_pt: float | None
    content_observation: str
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Element:
    element_id: str
    kind: str
    reading_order: int
    parent_element_id: str | None
    text: str | None
    table_data: dict[str, Any] | None
    provider_ref: str | None
    locations: list[Location]


@dataclass(frozen=True)
class Extraction:
    pages: list[Page]
    elements: list[Element]
    diagnostics: list[dict[str, Any]]
    parser_status: str
    parser_manifest: dict[str, Any]
    raw: dict[str, Any]
    duration_seconds: float


class ExtractionError(Exception):
    """An unavailable extraction, retaining whatever the parser actually reported."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        diagnostics: list[dict] | None = None,
        parser_status: str | None = None,
        parser_manifest: dict | None = None,
        raw: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.diagnostics = diagnostics or []
        self.parser_status = parser_status
        self.parser_manifest = parser_manifest or {}
        self.raw = raw
