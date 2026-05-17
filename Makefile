COMPOSE     := docker compose -f infra/docker-compose.yml
COMPOSE_DEV := docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml

.DEFAULT_GOAL := help

.PHONY: help up down logs test lint fmt typecheck seed clean install

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ── Infrastructure ──────────────────────────────────────────────────────────

up:  ## Bring up infrastructure (Postgres, Redis, MinIO) and wait for health
	$(COMPOSE) up -d --wait

down:  ## Stop and remove containers
	$(COMPOSE) down

logs:  ## Tail infrastructure logs
	$(COMPOSE) logs -f

clean:  ## Stop containers AND delete volumes (destructive)
	$(COMPOSE) down -v
	docker system prune -f

# ── Python toolchain ────────────────────────────────────────────────────────

install:  ## Install all workspace dependencies
	uv sync --all-packages

lint:  ## Check code style (read-only)
	uv run ruff check .
	uv run ruff format --check .

fmt:  ## Auto-fix formatting and lint issues
	uv run ruff format .
	uv run ruff check --fix .

typecheck:  ## Run mypy across all packages with source code
	uv run mypy libs/ services/ load-gen/

test:  ## Run the full unit/component test suite
	uv run pytest

test-integration:  ## Run integration tests (requires: make up + ingestion service running)
	uv run pytest tests/integration -m integration --tb=short

# ── Data ────────────────────────────────────────────────────────────────────

seed:  ## Generate synthetic metrics to output/ (7 days, seed 42)
	uv run load-gen

seed-http:  ## Stream synthetic metrics directly to the ingestion API
	uv run load-gen --mode http --ingestion-url http://localhost:8001

verify-dod:  ## Run Phase 2 definition-of-done checks (requires: make up + services running)
	uv run python scripts/verify_dod.py
