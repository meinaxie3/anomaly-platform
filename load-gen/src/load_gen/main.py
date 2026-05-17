"""
CLI entrypoint for the synthetic load generator.

    python -m load_gen --help
    python -m load_gen --seed 42 --duration-days 7
    python -m load_gen --mode http --ingestion-url http://localhost:8001
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

import typer

from load_gen.config import load_anomaly_specs
from load_gen.generator import MetricGenerator
from load_gen.writer import FileWriter, GroundTruthWriter, HttpWriter

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)

_DEFAULT_ANOMALIES = Path(__file__).parent.parent.parent / "config" / "anomalies.yaml"


class OutputMode(StrEnum):
    file = "file"
    http = "http"


@app.command()
def run(
    seed: int = typer.Option(42, help="Random seed -- same seed -> identical output"),
    duration_days: int = typer.Option(7, help="Number of simulated days"),
    interval_secs: int = typer.Option(60, help="Seconds between metric ticks"),
    output: Path = typer.Option(
        Path("output/metrics.jsonl"), help="Metrics JSONL output (file mode)"
    ),
    ground_truth: Path = typer.Option(
        Path("output/ground_truth.jsonl"), help="Anomaly ground-truth JSONL output"
    ),
    anomalies: Path = typer.Option(_DEFAULT_ANOMALIES, help="Anomaly schedule YAML"),
    start_iso: str = typer.Option(
        "", help="Simulation start datetime (ISO 8601). Default: now - duration"
    ),
    mode: OutputMode = typer.Option(OutputMode.file, help="Output mode: file or http"),
    ingestion_url: str = typer.Option(
        "http://localhost:8001", help="Ingestion API base URL (http mode only)"
    ),
    http_batch_size: int = typer.Option(200, help="Events per POST request (http mode only)"),
) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = (
        datetime.fromisoformat(start_iso).replace(tzinfo=UTC)
        if start_iso
        else end - timedelta(days=duration_days)
    )

    specs = load_anomaly_specs(anomalies, start) if anomalies.exists() else []
    if not anomalies.exists():
        typer.echo(f"[warn] anomaly config not found at {anomalies} -- running without anomalies")

    generator = MetricGenerator(seed=seed, anomaly_specs=specs)
    interval = timedelta(seconds=interval_secs)
    expected = generator.event_count(start, end, interval)

    typer.echo(
        f"Generating {expected:,} events  "
        f"({duration_days}d window, {interval_secs}s interval, seed={seed})"
    )
    typer.echo(f"  {start.isoformat()} -> {end.isoformat()}")
    typer.echo(f"  {len(specs)} anomaly window(s) scheduled")
    typer.echo(f"  mode: {mode.value}")

    anomaly_count = 0

    if mode == OutputMode.file:
        with FileWriter(output) as file_writer:
            for event, is_anomalous in generator.events(start, end, interval):
                file_writer.write(event)
                if is_anomalous:
                    anomaly_count += 1
        typer.echo("\nDone.")
        typer.echo(f"  metrics      -> {output}  ({file_writer.count:,} events)")
        typer.echo(f"  anomalous       {anomaly_count:,} events across {len(specs)} window(s)")
        typer.echo(f"  ground truth -> {ground_truth}")

    else:
        typer.echo(f"  target: {ingestion_url}  (batch={http_batch_size})")
        with HttpWriter(ingestion_url, batch_size=http_batch_size) as http_writer:
            for event, is_anomalous in generator.events(start, end, interval):
                http_writer.write(event)
                if is_anomalous:
                    anomaly_count += 1
        typer.echo("\nDone.")
        typer.echo(f"  sent:         {http_writer.count:,} events")
        typer.echo(f"  errors:       {http_writer.errors:,} events rejected by API")
        typer.echo(f"  anomalous:    {anomaly_count:,} events across {len(specs)} window(s)")
        typer.echo(f"  ground truth -> {ground_truth}")

    GroundTruthWriter(ground_truth).write_all(specs)


def main() -> None:
    app()
