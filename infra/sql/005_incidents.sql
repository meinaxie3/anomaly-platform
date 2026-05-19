-- Incidents table.
-- Deduplicated, grouped anomaly incidents surfaced by the alert engine.
-- Incidents are soft-closed (resolved_at / status) — never hard-deleted.

CREATE TABLE IF NOT EXISTS incidents (
    incident_id  UUID             NOT NULL DEFAULT gen_random_uuid(),
    service      TEXT             NOT NULL,
    metric       TEXT             NOT NULL,
    status       TEXT             NOT NULL DEFAULT 'open',  -- open | resolved | suppressed
    started_at   TIMESTAMPTZ      NOT NULL,
    resolved_at  TIMESTAMPTZ,               -- NULL while open

    PRIMARY KEY (incident_id)
);

-- Dashboard: open incidents per service
CREATE INDEX IF NOT EXISTS incidents_service_status
    ON incidents (service, status, started_at DESC);

-- Alert engine: look up open incidents for a series
CREATE INDEX IF NOT EXISTS incidents_service_metric_open
    ON incidents (service, metric)
    WHERE status = 'open';
