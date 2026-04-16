"""Pydantic models for contact, thread, and aggregate memory structures."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ContactMemory(BaseModel):
    email: str
    name: str | None = None
    importance: Literal["low", "normal", "high", "vip"] = "normal"
    preferences: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    interaction_count: int = 0
    last_seen_at: datetime | None = None


class ThreadMemory(BaseModel):
    thread_id: str
    summary: str | None = None
    last_outcome: str | None = None
    recent_messages: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class MemoryExtraction(BaseModel):
    importance: Literal["low", "normal", "high", "vip"] | None = None
    preferences: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    thread_summary: str | None = None
    business_facts: list[str] = Field(default_factory=list)


class MemoryBundle(BaseModel):
    contact: ContactMemory | None = None
    thread: ThreadMemory | None = None
    similar_replies: list[str] = Field(default_factory=list)
    business_facts: list[str] = Field(default_factory=list)
