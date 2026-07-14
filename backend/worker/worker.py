"""
Worker process. Run one or many of these (each with a unique WORKER_ID) to
process jobs concurrently. Usage:

    WORKER_ID=worker-1 python -m worker.worker

Responsibilities:
1. Pull the next job off the priority queue (blocking pop).
2. Mark it 'running' in Postgres and start heartbeating in Redis.
3. Execute the handler for its job type.
4. On success: mark 'success', store result, clear heartbeat.
5. On failure: increment retry_count. If under max_retries, schedule a
   delayed retry with exponential backoff. Otherwise move to dead-letter.
6. Periodically scan for jobs whose worker stopped heartbeating (crashed)
   and requeue them.
"""
import os
import time
import traceback
import uuid

from sqlalchemy.orm import Session

from app import queue as q
from app.config import settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from worker.job_types import JOB_HANDLERS

WORKER_ID = os.getenv("WORKER_ID", f"worker-{uuid.uuid4().hex[:8]}")


def get_priority(db: Session, job_id: str) -> int:
    job = db.get(Job, uuid.UUID(job_id))
    return job.priority if job else 5


def process_job(db: Session, r, job_id: str) -> None:
    job = db.get(Job, uuid.UUID(job_id))
    if job is None:
        print(f"[{WORKER_ID}] Job {job_id} not found in DB, skipping")
        q.clear_processing(r, job_id)
        return

    if job.status == JobStatus.cancelled:
        print(f"[{WORKER_ID}] Job {job_id} was cancelled, skipping")
        q.clear_processing(r, job_id)
        return

    job.status = JobStatus.running
    job.worker_id = WORKER_ID
    db.commit()

    handler = JOB_HANDLERS.get(job.type)
    if handler is None:
        job.status = JobStatus.dead_letter
        job.error = f"No handler registered for job type '{job.type}'"
        db.commit()
        q.move_to_dead_letter(r, job_id)
        q.clear_processing(r, job_id)
        return

    try:
        result = handler(job.payload or {})
        job.status = JobStatus.success
        job.result = result
        job.error = None
        db.commit()
        print(f"[{WORKER_ID}] Job {job_id} ({job.type}) succeeded")

    except Exception as e:
        job.retry_count += 1
        job.error = f"{e}\n{traceback.format_exc(limit=2)}"

        if job.retry_count <= job.max_retries:
            backoff = settings.BASE_BACKOFF_SEC * (2 ** (job.retry_count - 1))
            job.status = JobStatus.failed
            db.commit()
            q.schedule_retry(r, job_id, backoff)
            print(
                f"[{WORKER_ID}] Job {job_id} ({job.type}) failed "
                f"(attempt {job.retry_count}/{job.max_retries}), "
                f"retrying in {backoff:.1f}s: {e}"
            )
        else:
            job.status = JobStatus.dead_letter
            db.commit()
            q.move_to_dead_letter(r, job_id)
            print(
                f"[{WORKER_ID}] Job {job_id} ({job.type}) exhausted retries, "
                f"moved to dead-letter: {e}"
            )

    finally:
        q.clear_processing(r, job_id)


def recover_stale_jobs(db: Session, r) -> None:
    """Detect jobs whose worker crashed mid-execution (no recent heartbeat)
    and requeue them for another worker to pick up."""
    stale_ids = q.find_stale_processing_jobs(r, settings.HEARTBEAT_TIMEOUT_SEC)
    for job_id in stale_ids:
        job = db.get(Job, uuid.UUID(job_id))
        q.clear_processing(r, job_id)
        if job and job.status == JobStatus.running:
            print(f"[{WORKER_ID}] Detected crashed worker for job {job_id}, requeuing")
            job.status = JobStatus.pending
            db.commit()
            q.enqueue(r, job_id, job.priority)


def main_loop():
    r = q.get_redis()
    print(f"[{WORKER_ID}] Worker started, waiting for jobs...")
    last_maintenance = 0.0

    while True:
        db = SessionLocal()
        try:
            # Periodic maintenance: promote due delayed (retry) jobs, and
            # recover jobs from crashed workers. Runs roughly every 3s.
            now = time.time()
            if now - last_maintenance > 3.0:
                q.promote_due_delayed_jobs(r, lambda jid: get_priority(db, jid))
                recover_stale_jobs(db, r)
                last_maintenance = now

            job_id = q.pop_next_job(r, timeout=5)
            if job_id is None:
                continue  # no job available within timeout, loop again

            q.mark_processing(r, job_id)
            process_job(db, r, job_id)

        except Exception as loop_err:
            # Never let the worker die from an unexpected error -- log and continue.
            print(f"[{WORKER_ID}] Unexpected error in main loop: {loop_err}")
            traceback.print_exc()
            time.sleep(1)
        finally:
            db.close()


if __name__ == "__main__":
    main_loop()
