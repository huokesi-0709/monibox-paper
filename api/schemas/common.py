"""Common API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApiMessage(BaseModel):
    message: str = Field(..., description="Human-readable message.")
