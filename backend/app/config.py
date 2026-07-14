import os

class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://jobqueue:jobqueue@localhost:5432/jobqueue"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Queue keys
    QUEUE_KEY: str = "jobqueue:pending"        # sorted set: score = priority-weighted timestamp
    DELAYED_KEY: str = "jobqueue:delayed"      # sorted set: score = ready_at unix timestamp
    PROCESSING_KEY: str = "jobqueue:processing"  # hash: job_id -> heartbeat timestamp (crash detection)
    DEAD_LETTER_KEY: str = "jobqueue:dead_letter"  # list of job_ids that exhausted retries

    # Worker tuning
    HEARTBEAT_INTERVAL_SEC: float = 2.0
    HEARTBEAT_TIMEOUT_SEC: float = 15.0   # if a worker hasn't heartbeat in this long, assume it crashed
    BASE_BACKOFF_SEC: float = 2.0         # backoff = BASE_BACKOFF_SEC * 2^retry_count

    # Optional AI job type
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

settings = Settings()
