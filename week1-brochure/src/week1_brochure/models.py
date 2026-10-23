"""Schemas the link-selection model must answer in (enforced by Structured Outputs)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LinkType = Literal[
    "about", "careers", "products", "customers", "investors", "team", "news", "other"
]


class RelevantLink(BaseModel):
    type: LinkType = Field(description="What the page covers.")
    url: str = Field(description="One URL copied exactly from the candidate list.")


class LinkSelection(BaseModel):
    links: list[RelevantLink]
