"""Saved conversations and turns; transcript references remain distinct from PDF citations."""

from datetime import datetime
from typing import Literal, NotRequired, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from folio.responses import AnswerCoverage, ResponseError

TurnState = Literal["pending", "running", "ready", "failed", "unavailable"]


class Conversation(BaseModel):
    id: UUID
    index_id: UUID
    created_at: datetime
    document_id: UUID
    revision_id: UUID
    title: str = Field(examples=["Sample guide questions"])
    title_source: Literal["generated", "manual"] | None
    title_version: int
    document_name: str
    question: str | None
    state: Literal["empty", "pending", "running", "ready", "failed", "unavailable"]
    head_sequence: int
    max_turns: None = Field(description="No fixed turn-count limit; context limits still apply.")


class ConversationPage(BaseModel):
    items: list[Conversation]
    next_cursor: UUID | None = Field(examples=[None])


class ConversationDocument(BaseModel):
    document_id: UUID
    index_id: UUID
    display_name: str = Field(examples=["sample-guide.pdf"])
    created_at: datetime


class ConversationDocumentPage(BaseModel):
    items: list[ConversationDocument]
    next_cursor: UUID | None = Field(examples=[None])


class AnswerStatement(TypedDict):
    text: str
    source_ids: list[str]
    turn_ids: NotRequired[list[UUID]]


class SavedAnswer(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "outcome": "answer",
                    "statements": [
                        {"text": "The guide recommends insulation.", "source_ids": ["S1"]}
                    ],
                },
                {
                    "outcome": "transcript",
                    "statements": [
                        {
                            "text": "You said the home has two floors.",
                            "source_ids": [],
                            "turn_ids": ["00000000-0000-4000-8000-000000000007"],
                        }
                    ],
                },
            ]
        }
    )
    outcome: Literal["answer", "clarification", "insufficient_evidence", "transcript"]
    statements: list[AnswerStatement]


class TurnCitation(BaseModel):
    source_id: str
    chunk_ordinal: int
    text: str
    pages: list[int]


class ConversationTurn(BaseModel):
    id: UUID
    conversation_id: UUID
    sequence: int
    parent_sequence: int
    question: str = Field(examples=["What does the guide say about insulation?"])
    resolved_question: str | None
    state: TurnState
    answer: SavedAnswer | None
    context_state: Literal["preparing"] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    coverage: AnswerCoverage
    error: ResponseError | None
    citations: list[TurnCitation]


class TurnPage(BaseModel):
    items: list[ConversationTurn]
    next_after: int | None = Field(examples=[None])
    next_before: int | None = Field(examples=[4, None])
