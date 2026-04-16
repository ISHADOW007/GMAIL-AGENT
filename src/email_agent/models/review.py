"""Pydantic models for safety results and human review decisions."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SafetyResult(BaseModel):
    safe_to_send: bool
    needs_human: bool
    issues: list[str] = Field(default_factory=list)
    policy_tags: list[str] = Field(default_factory=list)


class HumanDecision(BaseModel):
    decision: Literal["pending", "approve", "revise", "reject"]
    comments: str | None = None
    reviewer: str | None = None
    reviewed_at: datetime | None = None

