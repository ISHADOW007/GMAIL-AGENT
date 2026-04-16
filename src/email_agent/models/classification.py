"""Pydantic models for classification decisions produced by the workflow."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    intent: Literal[
        "support",
        "sales",
        "meeting",
        "billing",
        "complaint",
        "spam",
        "newsletter",
        "other",
    ]
    urgency: Literal["low", "medium", "high"]
    risk: Literal["low", "medium", "high"]
    action: Literal["ignore", "draft", "human_review", "escalate"]
    reason: str
    confidence: float = Field(ge=0, le=1)

