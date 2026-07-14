"""
Job type handlers. Each handler takes the job's payload dict and returns a
result dict, or raises an exception on failure (which triggers the retry path).

To add a new job type: write a function(payload: dict) -> dict, and register
it in JOB_HANDLERS below.
"""
import time
import urllib.request
import json

from app.config import settings


def handle_echo(payload: dict) -> dict:
    """Trivial job type for testing the pipeline end to end."""
    time.sleep(0.5)
    return {"echoed": payload}


def handle_send_email(payload: dict) -> dict:
    """Mock email sender -- simulates latency and occasional failure so you
    can see retry/backoff behavior in action."""
    to = payload.get("to")
    subject = payload.get("subject", "(no subject)")
    if not to:
        raise ValueError("payload.to is required")

    time.sleep(1)  # simulate network latency to an email provider
    print(f"[send_email] Pretending to send '{subject}' to {to}")
    return {"sent_to": to, "subject": subject}


def handle_ai_summarize(payload: dict) -> dict:
    """Calls the Anthropic API to summarize provided text. Falls back to a
    stub response if no API key is configured, so the project still runs
    end-to-end without a key."""
    text = payload.get("text", "")
    if not text:
        raise ValueError("payload.text is required")

    if not settings.ANTHROPIC_API_KEY:
        return {
            "summary": f"[stub -- no ANTHROPIC_API_KEY set] First 100 chars: {text[:100]}",
            "stub": True,
        }

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 300,
        "messages": [
            {"role": "user", "content": f"Summarize this in 2-3 sentences:\n\n{text}"}
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    summary = "".join(block.get("text", "") for block in data.get("content", []))
    return {"summary": summary}


def handle_flaky(payload: dict) -> dict:
    """Deliberately fails ~60% of the time -- useful for demoing retry/backoff
    and dead-letter behavior without waiting on a real flaky dependency."""
    import random
    if random.random() < 0.6:
        raise RuntimeError("Simulated transient failure")
    return {"ok": True}


JOB_HANDLERS = {
    "echo": handle_echo,
    "send_email": handle_send_email,
    "ai_summarize": handle_ai_summarize,
    "flaky": handle_flaky,
}
