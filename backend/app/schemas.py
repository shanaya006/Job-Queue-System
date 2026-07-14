import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models import JobStatus


class JobCreate(BaseModel):
    type: str = Field(..., examples=["echo", "send_email", "ai_summarize"])
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10, description="1 = highest priority, 10 = lowest")
    max_retries: int = Field(default=3, ge=0, le=10)


class JobOut(BaseModel):
    id: uuid.UUID
    type: str
    payload: dict[str, Any]
    status: JobStatus
    priority: int
    retry_count: int
    max_retries: int
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    status_counts: dict[str, int]
    queue_depth: int
    delayed_depth: int
    dead_letter_depth: int
    processing_count: int
