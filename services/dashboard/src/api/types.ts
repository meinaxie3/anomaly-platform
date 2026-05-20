// Mirror of the Pydantic schemas in services/dashboard-api/src/dashboard_api/schemas.py
// Keep these in sync when the API changes.

export type HealthStatus = 'healthy' | 'degraded' | 'critical'

export interface ServiceSummary {
  service: string
  open_incidents: number
  last_anomaly_at: string | null  // ISO-8601
  health: HealthStatus
}

export interface MetricPoint {
  bucket: string        // ISO-8601
  avg_value: number
  min_value: number
  max_value: number
  sample_count: number
}

export interface AnomalyMarker {
  timestamp: string     // ISO-8601
  value: number
  score: number         // negative = anomaly
}

export interface MetricSeries {
  service: string
  metric: string
  points: MetricPoint[]
  anomalies: AnomalyMarker[]
}

export interface IncidentSummary {
  incident_id: string
  service: string
  metric: string
  status: string
  started_at: string    // ISO-8601
  resolved_at: string | null
  anomaly_count: number
}

export interface ModelSummary {
  model_id: string
  service: string
  metric: string
  algorithm: string
  trained_at: string    // ISO-8601
  n_samples: number
  fit_seconds: number
  eval_f1: number       // -1.0 means not evaluated
  is_current: boolean
  window_start: string  // ISO-8601
  window_end: string    // ISO-8601
}
