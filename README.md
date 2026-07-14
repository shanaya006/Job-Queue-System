# Job Queue System

Submits background tasks (like sending emails) to a queue, so they run
without making the user wait. Includes retries if a task fails, and a
live dashboard to watch it work.

Built with: Python (FastAPI), PostgreSQL, Redis, Docker

## How to run it

docker compose up --build

Then open frontend/index.html in your browser.

## What it does

- Submit a job (task) with a priority
- Workers pick up jobs and run them
- Failed jobs automatically retry a few times before giving up
- Dashboard shows live status of every job
