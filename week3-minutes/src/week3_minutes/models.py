"""What the model must return for each part of the transcript, and the final minutes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Decision(_Strict):
    decision: str = Field(min_length=1)
    evidence: str = Field(min_length=1, description="Exact words from the transcript.")


class ActionItem(_Strict):
    owner: str = Field(min_length=1)
    task: str = Field(min_length=1)
    due: str | None = None
    evidence: str = Field(min_length=1, description="Exact words from the transcript.")


class PartNotes(_Strict):
    """The model's notes for one part of the transcript."""

    summary: str = Field(min_length=1)
    attendees: list[str] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


class Minutes(BaseModel):
    title: str
    summary: str
    attendees: list[str]
    decisions: list[Decision]
    action_items: list[ActionItem]
    # Items whose quoted evidence or owner could not be found in the transcript.
    needs_checking: list[tuple[str, str]] = Field(default_factory=list)  # (item, reason)
    parts_failed: list[int] = Field(default_factory=list)  # parts the model never answered
