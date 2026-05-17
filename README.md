# Anomaly Detection Platform

A production-patterned system that ingests real-time service metrics, trains per-service anomaly detection models on a nightly schedule, and surfaces anomalies through an alert engine and live dashboard.

## Architecture

```
┌──────────────────┐
│  Load Generator  │  (synthetic traffic + injectable anomalies)
└────────┬─────────┘
         │ metric events (JSON)
         ▼
┌──────────────────┐      ┌──────────────────┐
│  Ingestion API   │─────▶│  Redis Streams   │
│  (FastAPI)       │      └────────┬─────────┘
└──────────────────┘               │
                                   ▼
                          ┌──────────────────┐
                          │ Stream Consumer  │
                          │ (Python worker)  │
                          └───┬──────────┬───┘
                              │          │
                    ┌─────────┘          └──────────┐
                    ▼                               ▼
           ┌──────────────┐               ┌──────────────────┐
           │ TimescaleDB  │◀──────────────│ Inference Service│
           │ (metrics +   │               │ (FastAPI)        │
           │  anomalies)  │               └────────┬─────────┘
           └──────┬───────┘                        │
                  │                        ┌───────┘
                  │                        ▼
                  │               ┌──────────────────┐
                  │               │  Alert Engine    │
                  │               │  (dedup/notify)  │
                  │               └────────┬─────────┘
                  │                        │
                  ▼                        ▼
           ┌──────────────────────────────────────┐
           │         Dashboard API (FastAPI)       │
           └──────────────────┬───────────────────┘
                              ▼
                     ┌─────────────────┐
                     │ React Dashboard │
                     └─────────────────┘
```

**Training path** (offline): TimescaleDB → Training Job (Prefect, nightly) → MinIO model store → loaded by Inference Service on startup.

## Quickstart

**Prerequisites:** Docker, [uv](https://docs.astral.sh/uv/getting-started/installation/)

> On Windows, use WSL 2 or Git Bash for `make` commands.

```bash
git clone <repo-url> && cd anomaly-platform
cp .env.example .env          # review defaults, change passwords

make install                  # install all Python workspace deps
make up                       # start Postgres, Redis, MinIO (waits for health)
make test                     # run full test suite
```

Infrastructure UIs (once `make up` is healthy):
- **MinIO console:** http://localhost:9001 — user `minio` / pass `minio123`
- **Postgres:** `psql -h localhost -U anomaly -d anomaly`

## Repository layout

```
anomaly-platform/
├── services/
│   ├── ingestion/       # FastAPI — validates + enqueues metrics (Phase 2)
│   ├── consumer/        # Redis Stream worker → TimescaleDB (Phase 2)
│   ├── inference/       # FastAPI — online scoring per batch (Phase 4)
│   ├── alerts/          # Alert engine — dedup + incident creation (Phase 4)
│   ├── dashboard-api/   # FastAPI — serves dashboard queries (Phase 5)
│   └── training/        # Nightly training job — fits + versions models (Phase 3)
├── frontend/            # React 18 + TypeScript dashboard (Phase 5)
├── load-gen/            # Synthetic metric generator + anomaly injection (Phase 1)
├── libs/
│   ├── schemas/         # Shared Pydantic models (MetricEvent, AnomalyRecord …)
│   └── logging/         # Shared structlog configuration
├── infra/
│   ├── docker-compose.yml      # Infrastructure: Postgres, Redis, MinIO
│   ├── docker-compose.dev.yml  # Dev overrides (verbose logging)
│   └── sql/                    # TimescaleDB init scripts (Phase 2)
├── .github/workflows/ci.yml    # Lint → typecheck → test on every push
├── .pre-commit-config.yaml
├── Makefile
└── pyproject.toml              # uv workspace root + ruff/mypy/pytest config
```

## Developer workflow

| Command | What it does |
|---|---|
| `make up` | Start infrastructure, wait for healthchecks |
| `make down` | Stop containers |
| `make test` | Run pytest across all packages |
| `make lint` | Ruff check (read-only) |
| `make fmt` | Ruff format + auto-fix |
| `make typecheck` | mypy across all packages |
| `make clean` | Stop containers **and delete volumes** |

Pre-commit hooks run ruff and detect-secrets on every commit. Install once:
```bash
uv run pre-commit install
```

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Package manager | [uv](https://docs.astral.sh/uv/) (workspace mode) |
| APIs | FastAPI + Uvicorn |
| Queue | Redis Streams |
| Time-series DB | TimescaleDB (Postgres 16) |
| Model store | MinIO (S3-compatible) |
| ML | scikit-learn (Isolation Forest), Prophet |
| Orchestration | Prefect 2 |
| Frontend | React 18, TypeScript, Vite, TanStack Query, Recharts, Tailwind |
| Linting | Ruff |
| Type checking | Mypy |
| Testing | pytest + pytest-asyncio |
| CI | GitHub Actions |

## Build status

<!-- Add CI badge here once the first workflow run completes -->

## Phase progress

- [x] Phase 0 — Setup & Scaffolding
- [ ] Phase 1 — Load Generator & Metrics Schema
- [ ] Phase 2 — Ingestion Pipeline
- [ ] Phase 3 — Training Pipeline
- [ ] Phase 4 — Inference Service & Alert Engine
- [ ] Phase 5 — Dashboard API & Frontend
- [ ] Phase 6 — Evaluation & Polish
