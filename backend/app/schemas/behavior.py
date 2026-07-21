from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VisitorEventCreate(BaseModel):
    user_id: int | None = None
    session_id: str | None = Field(default=None, max_length=128)
    event_type: str = Field(min_length=1, max_length=64)
    target_type: str | None = Field(default=None, max_length=64)
    target_id: int | None = None
    spot_id: int | None = None
    page_path: str | None = Field(default=None, max_length=255)
    source: str | None = Field(default="web", max_length=64)
    duration_seconds: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None
    occurred_at: datetime | None = None


class VisitorEventOut(BaseModel):
    id: int
    user_id: int | None
    session_id: str | None
    event_type: str
    target_type: str | None
    target_id: int | None
    spot_id: int | None
    page_path: str | None
    source: str | None
    duration_seconds: int | None
    metadata: dict[str, Any] | None = None
    occurred_at: datetime
    created_at: datetime


class VisitorEventImportResult(BaseModel):
    imported_count: int
    skipped_count: int
    errors: list[str]


class VisitorEventStatsOut(BaseModel):
    total: int
    event_type_counts: dict[str, int]
    source_counts: dict[str, int]
    top_spot_counts: dict[str, int]
    average_duration_seconds: float
