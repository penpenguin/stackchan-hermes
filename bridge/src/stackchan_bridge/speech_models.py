"""Shared speech data models independent of Control API initialization."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

SpeechText = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=1_000)
]
SpeechState = Literal["ACCEPTED", "RUNNING", "COMPLETED", "CANCELLED", "FAILED"]


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: SpeechText


class SpeechStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    turn_id: UUID
    state: SpeechState
    error_code: str | None = None
