"""Schemas for chat endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., examples=["user", "assistant"])
    content: str = Field(..., description="Message body.")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User input text.")
    session_id: str = Field(default="default", description="Conversation session id.")


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    messages: list[ChatMessage]
    debug: dict[str, object] = Field(default_factory=dict)
