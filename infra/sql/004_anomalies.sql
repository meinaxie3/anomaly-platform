-- Anomalies table.
-- Stores every metric event that scored below the anomaly threshold.
-- Populated by the inference service; incident_id is set by the alert engine.

CREATE TABLE IF NOT EXISTS anomalies (
    anomaly_id   UUID             NOT NULL DEFAULT gen_random_uuid(),
    event_id     UUID             NOT NULL,
    timestamp    TIMESTAMPTZ      NOT NULL,
    service      TEXT             NOT NULL,
    metric       TEXT             NOT NULL,
    value        DOUBLE PRECISION NOT NULL,
    score        DOUBLE PRECISION NOT NULL,  -- raw decision_function output (negative = anomaly)
    threshold    DOUBLE PRECISION NOT NULL,  -- threshold in effect at scoring time
    model_id     TEXT             NOT NULL,
    incident_id  UUID,                       -- NULL until grouped by the alert engine
    status       TEXT             NOT NULL DEFAULT 'open',  -- open | resolved | suppressed

    PRIMARY KEY (anomaly_id)
);

-- Fast lookup by event (for idempotency checks)
CREATE UNIQUE INDEX IF NOT EXISTS anomalies_event_id
    ON anomalies (event_id);

-- Alert engine polling: fetch all ungrouped anomalies ordered by time
CREATE INDEX IF NOT EXISTS anomalies_incident_id_null
    ON anomalies (service, metric, timestamp DESC)
    WHERE incident_id IS NULL;

-- Dashboard: time-range queries per series
CREATE INDEX IF NOT EXISTS anomalies_service_metric_time
    ON anomalies (service, metric, timestamp DESC);
