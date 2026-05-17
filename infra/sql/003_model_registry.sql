-- Model registry table.
-- Tracks every versioned training artifact; is_current marks the live model.
-- Runs automatically on first `docker compose up` via /docker-entrypoint-initdb.d.

CREATE TABLE IF NOT EXISTS model_registry (
    model_id        UUID             NOT NULL DEFAULT gen_random_uuid(),
    service         TEXT             NOT NULL,
    metric          TEXT             NOT NULL,
    algorithm       TEXT             NOT NULL,

    trained_at      TIMESTAMPTZ      NOT NULL,
    window_start    TIMESTAMPTZ      NOT NULL,
    window_end      TIMESTAMPTZ      NOT NULL,

    n_samples       INTEGER          NOT NULL,
    fit_seconds     DOUBLE PRECISION NOT NULL,

    eval_precision  DOUBLE PRECISION NOT NULL DEFAULT -1,
    eval_recall     DOUBLE PRECISION NOT NULL DEFAULT -1,
    eval_f1         DOUBLE PRECISION NOT NULL DEFAULT -1,

    artifact_path   TEXT             NOT NULL,
    is_current      BOOLEAN          NOT NULL DEFAULT FALSE,

    PRIMARY KEY (model_id)
);

-- Only one current model per (service, metric) pair.
CREATE UNIQUE INDEX IF NOT EXISTS model_registry_one_current
    ON model_registry (service, metric)
    WHERE is_current = TRUE;

-- Fast lookup of current model during inference.
CREATE INDEX IF NOT EXISTS model_registry_service_metric
    ON model_registry (service, metric, trained_at DESC);
