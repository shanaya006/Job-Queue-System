# 💻 Job Queue System

Submits background tasks (like sending emails) to a queue, so they run
without making the user wait. Includes retries if a task fails, and a
live dashboard to watch it work.

Built with: Python (FastAPI), PostgreSQL, Redis, Docker

## What it does
- Submit a job (task) with a priority
- Workers pick up jobs and run them
- Failed jobs automatically retry a few times before giving up
- Dashboard shows live status of every job

## Demo
https://github.com/user-attachments/assets/527ee0c0-34d8-4ea2-853b-08fb4b01f21e

#### The video above shows two examples:
1. A "flaky" job that fails, automatically retries twice, then succeeds
2. An email job that gets queued and completes successfully

## How to run it
docker compose up --build

Then open frontend/index.html in your browser.
