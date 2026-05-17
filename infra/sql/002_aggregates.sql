-- 1-minute continuous aggregate over the metrics hypertable.
-- The dashboard queries this view instead of the raw table for time ranges > a few hours.
-- Requires TimescaleDB 2.x.

CREATE MATERIALIZED VIEW IF NOT EXISTS metrics_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS bucket,
    service,
    metric,
    avg(value)   AS avg_value,
    min(value)   AS min_value,
    max(value)   AS max_value,
    count(*)     AS sample_count
FROM metrics
GROUP BY bucket, service, metric
WITH NO DATA;

-- Automatically refresh the last 3 hours every minute.
SELECT add_continuous_aggregate_policy(
    'metrics_1min',
    start_offset      => INTERVAL '3 hours',
    end_offset        => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists     => TRUE
);
