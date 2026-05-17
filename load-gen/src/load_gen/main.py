"""
CLI entrypoint for the synthetic load generator.

    python -m load_gen --help
    python -m load_gen --seed 42 --duration-days 7
    python -m load_gen --interval-secs 30 --output /tmp/metrics.jsonl
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer

from load_gen.config import load_anomaly_specs
from load_gen.generator import MetricGenerator
from load_gen.writer import FileWriter, GroundTruthWriter

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)

# Default anomaly schedule sits next to the config/ dir at the package root.
_DEFAULT_ANOMALIES = Path(__file__).parent.parent.parent / "config" / "anomalies.yaml"


@app.command()
def run(
    seed: int = typer.Option(42, help="Random seed — same seed → identical output"),
    duration_days: int = typer.Option(7, help="Number of simulated days"),
    interval_secs: int = typer.Option(60, help="Seconds between metric ticks"),
    output: Path = typer.Option(Path("output/metrics.jsonl"), help="Metrics JSONL output"),
    ground_truth: Path = typer.Option(
        Path("output/ground_truth.jsonl"), help="Anomaly ground-truth JSONL output"
    ),
    anomalies: Path = typer.Option(_DEFAULT_ANOMALIES, help="Anomaly schedule YAML"),
    start_iso: str = typer.Option(
        "", help="Simulation start datetime (ISO 8601). Default: now - duration"
    ),
) -> None:
    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = (
        datetime.fromisoformat(start_iso).replace(tzinfo=UTC)
        if start_iso
        else end - timedelta(days=duration_days)
    )

    specs = load_anomaly_specs(anomalies, start) if anomalies.exists() else []
    if not anomalies.exists():
        typer.echo(f"[warn] anomaly config not found at {anomalies} — running without anomalies")

    generator = MetricGenerator(seed=seed, anomaly_specs=specs)
    interval = timedelta(seconds=interval_secs)
    expected = generator.event_count(start, end, interval)

    typer.echo(
        f"Generating {expected:,} events  "
        f"({duration_days}d window, {interval_secs}s interval, seed={seed})"
    )
    typer.echo(f"  {start.isoformat()} -> {end.isoformat()}")
    typer.echo(f"  {len(specs)} anomaly window(s) scheduled")

    anomaly_count = 0
    with FileWriter(output) as writer:
        for event, is_anomalous in generator.events(start, end, interval):
            writer.write(event)
            if is_anomalous:
                anomaly_count += 1

    GroundTruthWriter(ground_truth).write_all(specs)

    typer.echo("\nDone.")
    typer.echo(f"  metrics      -> {output}  ({writer.count:,} events)")
    typer.echo(f"  anomalous       {anomaly_count:,} events across {len(specs)} window(s)")
    typer.echo(f"  ground truth -> {ground_truth}")


def main() -> None:
    app()
