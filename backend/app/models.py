import enum
import uuid

from sqlalchemy import Column, String, Integer, DateTime, Enum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"        # failed this attempt, will retry
    dead_letter = "dead_letter"  # exhausted retries
    cancelled = "cancelled"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String, nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.pending, index=True)
    priority = Column(Integer, nullable=False, default=5)  # 1 (highest) - 10 (lowest)

    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    result = Column(JSONB, nullable=True)
    error = Column(String, nullable=True)

    worker_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
