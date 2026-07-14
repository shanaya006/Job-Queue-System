"""
Redis-backed job queue primitives.

Design:
- QUEUE_KEY is a sorted set. Score = priority * 10^13 + created_at_epoch_ms.
  This makes lower scores pop first: lower priority number (=higher priority)
  sorts first, and within the same priority, earlier jobs sort first (FIFO).
- DELAYED_KEY is a sorted set for retry backoff. Score = ready_at unix timestamp.
  A scheduler loop (run by the worker) moves due jobs from DELAYED_KEY into QUEUE_KEY.
- PROCESSING_KEY is a hash of job_id -> last heartbeat timestamp, so a monitor
  can detect crashed workers (no heartbeat within HEARTBEAT_TIMEOUT_SEC) and
  requeue their jobs.
- DEAD_LETTER_KEY is a plain list of job_ids that exhausted their retries.
"""
import time

import redis

from app.config import settings

PRIORITY_MULTIPLIER = 10 ** 13


def get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def enqueue(r: redis.Redis, job_id: str, priority: int) -> None:
    now_ms = int(time.time() * 1000)
    score = priority * PRIORITY_MULTIPLIER + now_ms
    r.zadd(settings.QUEUE_KEY, {job_id: score})


def schedule_retry(r: redis.Redis, job_id: str, delay_sec: float) -> None:
    ready_at = time.time() + delay_sec
    r.zadd(settings.DELAYED_KEY, {job_id: ready_at})


def promote_due_delayed_jobs(r: redis.Redis, priority_lookup) -> int:
    """Move any delayed jobs whose backoff has elapsed back into the main queue.
    priority_lookup(job_id) -> int priority, used to recompute the queue score.
    Returns number of jobs promoted."""
    now = time.time()
    due = r.zrangebyscore(settings.DELAYED_KEY, 0, now)
    for job_id in due:
        priority = priority_lookup(job_id)
        enqueue(r, job_id, priority)
        r.zrem(settings.DELAYED_KEY, job_id)
    return len(due)


def pop_next_job(r: redis.Redis, timeout: int = 5) -> str | None:
    """Blocking pop of the highest-priority, oldest job. Returns job_id or None on timeout."""
    result = r.bzpopmin(settings.QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, job_id, _score = result
    return job_id


def mark_processing(r: redis.Redis, job_id: str) -> None:
    r.hset(settings.PROCESSING_KEY, job_id, time.time())


def heartbeat(r: redis.Redis, job_id: str) -> None:
    r.hset(settings.PROCESSING_KEY, job_id, time.time())


def clear_processing(r: redis.Redis, job_id: str) -> None:
    r.hdel(settings.PROCESSING_KEY, job_id)


def find_stale_processing_jobs(r: redis.Redis, timeout_sec: float) -> list[str]:
    """Find jobs whose worker hasn't heartbeat recently -- likely crashed."""
    now = time.time()
    stale = []
    all_processing = r.hgetall(settings.PROCESSING_KEY)
    for job_id, last_beat in all_processing.items():
        if now - float(last_beat) > timeout_sec:
            stale.append(job_id)
    return stale


def move_to_dead_letter(r: redis.Redis, job_id: str) -> None:
    r.rpush(settings.DEAD_LETTER_KEY, job_id)


def queue_depth(r: redis.Redis) -> int:
    return r.zcard(settings.QUEUE_KEY)


def delayed_depth(r: redis.Redis) -> int:
    return r.zcard(settings.DELAYED_KEY)


def dead_letter_depth(r: redis.Redis) -> int:
    return r.llen(settings.DEAD_LETTER_KEY)


def processing_count(r: redis.Redis) -> int:
    return r.hlen(settings.PROCESSING_KEY)


def remove_from_queue(r: redis.Redis, job_id: str) -> None:
    """Used when cancelling a still-pending job."""
    r.zrem(settings.QUEUE_KEY, job_id)
    r.zrem(settings.DELAYED_KEY, job_id)
