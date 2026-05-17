-- Metrics hypertable.
-- Runs automatically on first `docker compose up` via /docker-entrypoint-initdb.d.

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS metrics (
    timestamp   TIMESTAMPTZ      NOT NULL,
    event_id    UUID             NOT NULL,
    service     TEXT             NOT NULL,
    metric      TEXT             NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    labels      JSONB            NOT NULL DEFAULT '{}',
    PRIMARY KEY (timestamp, event_id)   -- timestamp first: TimescaleDB requirement
);

-- Partition by time (7-day chunks).
SELECT create_hypertable(
    'metrics', 'timestamp',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists       => TRUE
);

-- Fast queries by service + metric over a time range (the common dashboard pattern).
CREATE INDEX IF NOT EXISTS metrics_service_metric_time
    ON metrics (service, metric, timestamp DESC);

-- Fast lookup by event_id for idempotency checks / debugging.
CREATE INDEX IF NOT EXISTS metrics_event_id
    ON metrics (event_id);
