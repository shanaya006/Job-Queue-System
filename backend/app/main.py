import uuid

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import queue as q
from app.database import Base, engine, get_db
from app.models import Job, JobStatus
from app.schemas import JobCreate, JobOut, StatsOut

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Job Queue System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo project -- lock this down in production
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_client = q.get_redis()


@app.post("/jobs", response_model=JobOut, status_code=201)
def create_job(job_in: JobCreate, db: Session = Depends(get_db)):
    job = Job(
        type=job_in.type,
        payload=job_in.payload,
        priority=job_in.priority,
        max_retries=job_in.max_retries,
        status=JobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    q.enqueue(redis_client, str(job.id), job.priority)
    return job


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(
    status: JobStatus | None = None,
    type: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = db.query(Job)
    if status:
        stmt = stmt.filter(Job.status == status)
    if type:
        stmt = stmt.filter(Job.type == type)
    stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(limit)
    return stmt.all()


@app.delete("/jobs/{job_id}", response_model=JobOut)
def cancel_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.pending,):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel a job in '{job.status}' state; only pending jobs can be cancelled",
        )
    job.status = JobStatus.cancelled
    db.commit()
    db.refresh(job)

    q.remove_from_queue(redis_client, str(job.id))
    return job


@app.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    rows = db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    status_counts = {status.value: count for status, count in rows}
    for s in JobStatus:
        status_counts.setdefault(s.value, 0)

    return StatsOut(
        status_counts=status_counts,
        queue_depth=q.queue_depth(redis_client),
        delayed_depth=q.delayed_depth(redis_client),
        dead_letter_depth=q.dead_letter_depth(redis_client),
        processing_count=q.processing_count(redis_client),
    )


@app.get("/health")
def health():
    return {"status": "ok"}
