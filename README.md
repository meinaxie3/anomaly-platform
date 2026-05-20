# Anomaly Detection Platform

[![CI](https://github.com/meinaxie3/anomaly-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/meinaxie3/anomaly-platform/actions/workflows/ci.yml)

A production-patterned ML system that ingests real-time service metrics, trains per-metric anomaly detection models on a nightly schedule, and surfaces detected anomalies through an alert engine and live React dashboard.

## Screenshots

**Overview — service health grid and open incidents**
![Dashboard overview](demo/dashboard.png)

**Service detail — metric chart with anomaly markers**
![Anomaly detection graph](demo/anomaly%20detection%20graph.png)

**Models — ML eval scores (precision / recall / F1)**
![ML training results](demo/ml%20train%20results.png)

**Dashboard API — Swagger docs**
![Dashboard API](demo/dashboard%20api.png)

**Ingestion API — Swagger docs**
![Ingestion API](demo/ingestion%20api.png)

**Inference API — Swagger docs**
![Inference API](demo/interference%20api.png)

## Architecture

```
┌──────────────────┐
│  Load Generator  │  (synthetic traffic + injectable spikes)
└────────┬─────────┘
         │ POST /ingest  (JSON metric events)
         ▼
┌──────────────────┐      ┌──────────────────────┐
│  Ingestion API   │─────▶│   Redis Streams       │
│  FastAPI :8001   │      └──────────┬───────────┘
└──────────────────┘                 │
                                     ▼
                          ┌──────────────────────┐
                          │   Stream Consumer    │  fan-out worker
                          └──────┬───────┬───────┘
                                 │       │
                    ┌────────────┘       └─────────────┐
                    ▼                                   ▼
           ┌──────────────┐                  ┌──────────────────┐
           │ TimescaleDB  │◀─────────────────│ Inference API    │
           │  :5432       │   anomaly write  │ FastAPI :8002    │
           │ metrics      │                  └────────┬─────────┘
           │ anomalies    │                           │ anomaly event
           │ incidents    │                           ▼
           │ model_reg.   │                  ┌──────────────────┐
           └──────┬───────┘                  │  Alert Engine    │
                  │                          │  dedup + group   │
                  │ nightly                  └────────┬─────────┘
                  ▼                                   │ incident write
           ┌──────────────┐                           │
           │ Training Job │   ──→  MinIO model store  │
           │ (Prefect)    │        :9000               │
           └──────────────┘                           ▼
                                           ┌──────────────────────┐
                                           │  Dashboard API       │
                                           │  FastAPI :8003       │
                                           └──────────┬───────────┘
                                                      ▼
                                             ┌─────────────────┐
                                             │  React UI :5173 │
                                             └─────────────────┘
```

**Training path (offline):** TimescaleDB → Training Job → MinIO → Inference API loads model on startup.

## Quickstart

### Prerequisites

| Tool | Notes |
|------|-------|
| **Docker** (with Compose v2) | `docker compose version` |
| **[uv](https://docs.astral.sh/uv/)** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js ≥ 18** | Only for the React dashboard |

> **Windows:** Use the provided PowerShell script (`scripts\start.ps1`) — it opens each service in its own terminal window. Alternatively use WSL 2 and `scripts/start.sh`.

### 1 — Clone and configure

```bash
git clone <repo-url>
cd anomaly-platform
cp .env.example .env          # review passwords; defaults work for local dev
```

### 2 — Install Python dependencies

```bash
uv sync --all-packages        # installs every workspace package into .venv
```

### 3 — Start infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d --wait
```

Waits until Postgres, Redis, and MinIO pass their health checks.

### 4 — Run the full stack

**Windows (PowerShell):**
```powershell
.\scripts\start.ps1
```

**Linux / macOS / WSL:**
```bash
bash scripts/start.sh
```

Both scripts start all five Python services and the React dev server, then ask if you want to start the load generator.

### 5 — Alternative: run services individually

```bash
make run-ingestion      # FastAPI ingestion (port 8001)
make run-consumer       # Redis stream → TimescaleDB worker
make run-inference      # FastAPI inference (port 8002)
make run-alerts         # Alert engine
make run-dashboard-api  # FastAPI dashboard API (port 8003)
make run-ui             # React dev server (port 5173)
```

### 6 — Train the first models

The inference service needs trained models to score incoming metrics.

```bash
make run-training       # runs one cycle and exits
```

After training, the Models view in the dashboard shows eval precision / recall / F1 scores.

### 7 — Verify everything works

```bash
make verify-dod-6       # Phase 6 end-to-end health check
```

## Service URLs

| Service | URL |
|---------|-----|
| Ingestion API (Swagger) | http://localhost:8001/docs |
| Inference API (Swagger) | http://localhost:8002/docs |
| Dashboard API (Swagger) | http://localhost:8003/docs |
| React dashboard | http://localhost:5173 |
| MinIO console | http://localhost:9001 &nbsp;(`minio` / `minio123`) |

## Repository layout

```
anomaly-platform/
├── services/
│   ├── ingestion/        FastAPI — validates + enqueues metric events
│   ├── consumer/         Redis Stream worker → TimescaleDB
│   ├── inference/        FastAPI — online scoring per batch
│   ├── alerts/           Alert engine — dedup + incident creation
│   ├── dashboard-api/    FastAPI — serves dashboard queries (port 8003)
│   │   └── tests/        pytest unit tests (no live DB)
│   ├── training/         Nightly training job — fits + versions models
│   └── dashboard/        React 18 + TypeScript frontend
│       └── src/
│           ├── api/          typed fetch client + TypeScript types
│           ├── components/   StatusBadge, MetricChart, IncidentRow …
│           ├── hooks/        TanStack Query hooks with auto-refresh
│           └── views/        Overview, ServiceDetail, Models pages
├── libs/
│   ├── schemas/          Shared Pydantic models (MetricEvent, AnomalyRecord …)
│   └── logging/          Shared structlog configuration
├── load-gen/             Synthetic metric generator + anomaly injection
├── infra/
│   ├── docker-compose.yml      Postgres, Redis, MinIO
│   └── sql/                    TimescaleDB init scripts + continuous aggregates
├── scripts/
│   ├── start.ps1               Windows one-command startup
│   ├── start.sh / stop.sh      Unix one-command startup/shutdown
│   ├── verify_dod_phase*.py    Phase DoD check scripts
│   └── verify_dod.py           Phase 2 integration checks
├── tests/
│   └── integration/      Cross-service integration tests
├── .github/workflows/ci.yml
├── Makefile
└── pyproject.toml        uv workspace root + ruff / mypy / pytest config
```

## Developer workflow

| Command | What it does |
|---------|-------------|
| `make up` | Start infrastructure, wait for health checks |
| `make down` | Stop containers |
| `make install` | Install all Python workspace dependencies |
| `make test` | Run pytest across all packages |
| `make lint` | Ruff check (read-only) |
| `make fmt` | Ruff format + auto-fix |
| `make typecheck` | mypy across all packages |
| `make clean` | Stop containers **and delete volumes** |
| `make run-training` | Train one cycle — populates eval scores |
| `make verify-dod-6` | End-to-end Phase 6 health check |

Pre-commit hooks (ruff + detect-secrets) run on every commit:
```bash
uv run pre-commit install
```

## Metrics & anomaly detection

### How anomaly detection works

Every anomaly marker on the dashboard was flagged by a machine learning model — there are no hardcoded thresholds. Here is the full pipeline from raw metric to red dot on the chart:

```
Load Generator
    │
    │  sends cpu_percent = 42.3 every 10 seconds
    ▼
Ingestion API  →  Redis Stream  →  Consumer
                                       │
                                       │  batches readings, calls...
                                       ▼
                                 Inference API
                                       │
                                       │  loads the trained Isolation Forest
                                       │  model for (payment-api, cpu_percent)
                                       │  scores the new reading
                                       │
                              ┌────────┴────────┐
                              │                 │
                           normal            ANOMALY
                              │                 │
                         do nothing        write to anomalies table
                                                │
                                                ▼
                                          Alert Engine
                                                │
                                          groups anomalies
                                          into an Incident
                                                │
                                                ▼
                                          Dashboard
                                    (red dot on the chart)
```

### ML vs simple threshold alerting

| Simple threshold alerting | This platform |
|---|---|
| `if cpu > 80% → alert` | No hardcoded number |
| Fires at 81% even at 3am when that's normal | Knows 3am baseline is different |
| Silent if normal is 90% and value drops to 50% | Catches drops too |
| Someone has to set every threshold manually | Model learns from data automatically |
| Same rule for every service | Separate model per service + metric |

The model learns that `payment-api cpu_percent` peaks at ~57% during business hours and sits at ~28% overnight — so 75% at 2am is anomalous, but 75% at noon might not be.

> **Note:** anomalies can be high *or* low. A sudden drop in `latency_p50` (service responding near-instantly) is just as suspicious as a spike — it may indicate the service is short-circuiting and returning errors rather than doing real work.

### What "anomaly detected" means

The platform trains an **Isolation Forest** model on each service + metric pair using weeks of historical data. The model learns what *normal* looks like — the typical range, the daily peaks, the quiet overnight hours. When a new metric reading arrives, the model scores it. If the score is unusual enough relative to history, it is flagged as an anomaly.

An anomaly does not mean the service is down — it means the value is behaving in a way the model has not seen before. Whether that is a problem depends on the metric (a CPU spike is more urgent than a memory blip).

### Metric reference

Each of the five synthetic services tracks the same 7 metrics. Baselines below are for `payment-api`.

| Metric | Unit | What it measures | Normal baseline | Anomaly means… |
|---|---|---|---|---|
| `cpu_percent` | % | CPU consumed by the service | ~42% | Runaway process, traffic surge, or inefficient query |
| `memory_percent` | % | RAM usage as a share of total available | ~58% | Creeping growth = memory leak; sudden jump = large allocation |
| `request_rate` | req/s | Requests arriving per second | ~120 req/s | Spike = retry storm or traffic surge; drop = upstream failure |
| `latency_p50` | ms | Median response time — half of requests are faster | ~45 ms | Typical user experience has degraded |
| `latency_p95` | ms | 95th-percentile — only 5% of requests are slower | ~120 ms | Slow tail latency is affecting a significant share of users |
| `latency_p99` | ms | 99th-percentile — the slowest 1% of requests | ~280 ms | Worst-case experience; often GC pauses or lock contention |
| `error_rate` | 0 – 1 | Fraction of requests that returned an error | ~0.5% | Even a small jump is serious — users are hitting failures |

### Why three latency tabs?

A single average latency hides a lot. The three percentiles tell different stories:

| Tab | Question it answers |
|---|---|
| `latency_p50` | Is the *typical* experience good? |
| `latency_p95` | Are *most* users happy? |
| `latency_p99` | Are the *worst cases* acceptable? |

Anomalies at p99 but not p50 usually point to something intermittent (lock contention, cold cache, garbage collection). Anomalies at all three together mean the whole service is struggling.

## ML evaluation

Each training run:
1. Loads the training window from TimescaleDB (default: 30 days)
2. Splits 80% train / 20% holdout
3. Fits an Isolation Forest on the training split
4. Injects synthetic anomalies into the holdout (5% of rows, 5–10× spike)
5. Evaluates precision / recall / F1 against ground-truth labels
6. Stores the model + scores in MinIO and `model_registry`

The **Models** page in the dashboard displays these scores with colour coding:

| Score range | Colour | Meaning |
|-------------|--------|---------|
| ≥ 0.80 | Green | Good |
| 0.60 – 0.79 | Amber | Fair — consider tuning contamination |
| < 0.60 | Red | Poor — check data quality |
| — | Grey | Not evaluated yet |

## Tech stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Package manager | [uv](https://docs.astral.sh/uv/) (workspace mode) |
| APIs | FastAPI + Uvicorn |
| Queue | Redis Streams |
| Time-series DB | TimescaleDB (Postgres 16) |
| Continuous aggregates | `metrics_1min` materialized view |
| Model store | MinIO (S3-compatible) |
| ML | scikit-learn Isolation Forest |
| Orchestration | Prefect 2 |
| Frontend | React 18 · TypeScript · Vite · TanStack Query · Recharts · Tailwind CSS |
| Linting | Ruff |
| Type checking | mypy |
| Testing | pytest · pytest-asyncio · Vitest · Testing Library · MSW |
| CI | GitHub Actions |

## Phase progress

- [x] Phase 0 — Setup & Scaffolding
- [x] Phase 1 — Load Generator & Metrics Schema
- [x] Phase 2 — Ingestion Pipeline (FastAPI + Redis Streams + TimescaleDB)
- [x] Phase 3 — Training Pipeline (Isolation Forest + MinIO + holdout eval)
- [x] Phase 4 — Inference Service & Alert Engine
- [x] Phase 5 — Dashboard API & React Frontend
- [x] Phase 6 — Evaluation & Polish
