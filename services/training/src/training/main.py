"""Training service entry point.

Runs one training job immediately, then schedules nightly runs via APScheduler.

Usage:
    uv run training                  # run once then schedule nightly
    uv run training --run-once       # run once and exit (useful for DoD checks / CI)
"""

from __future__ import annotations

import asyncio
import signal
import sys

import asyncpg
import typer
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ap_logging import get_logger
from training.job import run_training_job
from training.settings import get_settings
from training.store import ModelStore

log = get_logger(__name__)
app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


async def _run_once() -> int:
    """Execute a single training run. Returns the number of models trained."""
    settings = get_settings()

    store = ModelStore(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
    )
    store.ensure_bucket()

    pool = await asyncpg.create_pool(settings.postgres_url, min_size=1, max_size=4)
    try:
        results = await run_training_job(pool, store, settings)
    finally:
        await pool.close()

    log.info("run_complete", models_trained=len(results))
    return len(results)


async def _scheduler_loop(schedule_hour: int) -> None:
    """Start APScheduler and block until a SIGINT/SIGTERM is received."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_once,
        trigger=CronTrigger(hour=schedule_hour, minute=0),
        id="nightly_training",
        replace_existing=True,
    )
    scheduler.start()
    log.info("scheduler_started", hour=schedule_hour)

    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        log.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows does not support add_signal_handler for all signals
            pass

    await stop_event.wait()
    scheduler.shutdown(wait=False)


@app.command()
def main(
    run_once: bool = typer.Option(
        False,
        "--run-once",
        help="Run one training job and exit (skips the nightly scheduler).",
    ),
) -> None:
    settings = get_settings()

    if run_once:
        n = asyncio.run(_run_once())
        typer.echo(f"Training complete. Models trained: {n}")
        if n == 0:
            typer.echo("Warning: no models were trained (no data or all pairs skipped).", err=True)
        raise typer.Exit(code=0 if n >= 0 else 1)

    # Run immediately on startup, then hand off to the scheduler
    typer.echo("Running initial training job...")
    n = asyncio.run(_run_once())
    typer.echo(f"Initial run complete. Models trained: {n}")

    typer.echo(f"Scheduler active — nightly job at {settings.schedule_hour:02d}:00 UTC. Press Ctrl+C to stop.")
    asyncio.run(_scheduler_loop(settings.schedule_hour))


if __name__ == "__main__":
    app()
