/**
 * MSW request handlers -- shared between all tests.
 *
 * Uses absolute URLs (http://localhost/api/...) because MSW node mode
 * intercepts at the fetch level and needs to match the full URL that
 * jsdom produces from `window.location.origin` (= "http://localhost").
 */

import { http, HttpResponse } from 'msw'
import type { ServiceSummary, IncidentSummary, MetricSeries, ModelSummary } from '../api/types'

const now = new Date().toISOString()
const hour_ago = new Date(Date.now() - 3_600_000).toISOString()

export const DEFAULT_SERVICES: ServiceSummary[] = [
  {
    service: 'payment-api',
    open_incidents: 2,
    last_anomaly_at: now,
    health: 'degraded',
  },
  {
    service: 'auth-service',
    open_incidents: 0,
    last_anomaly_at: null,
    health: 'healthy',
  },
]

export const DEFAULT_METRIC_SERIES: MetricSeries = {
  service: 'payment-api',
  metric: 'cpu_percent',
  points: [
    { bucket: hour_ago, avg_value: 52.0, min_value: 48.0, max_value: 56.0, sample_count: 60 },
    { bucket: now, avg_value: 55.0, min_value: 50.0, max_value: 61.0, sample_count: 60 },
  ],
  anomalies: [
    { timestamp: now, value: 999.0, score: -0.21 },
  ],
}

export const DEFAULT_INCIDENTS: IncidentSummary[] = [
  {
    incident_id: 'aaaaaaaa-0000-0000-0000-000000000001',
    service: 'payment-api',
    metric: 'cpu_percent',
    status: 'open',
    started_at: hour_ago,
    resolved_at: null,
    anomaly_count: 3,
  },
]

export const DEFAULT_MODELS: ModelSummary[] = [
  {
    model_id: 'bbbbbbbb-0000-0000-0000-000000000001',
    service: 'payment-api',
    metric: 'cpu_percent',
    algorithm: 'IsolationForest',
    trained_at: hour_ago,
    n_samples: 12500,
    fit_seconds: 1.23,
    eval_f1: -1.0,
    is_current: true,
    window_start: new Date(Date.now() - 7 * 86_400_000).toISOString(),
    window_end: now,
  },
]

const BASE = 'http://localhost'

export const handlers = [
  http.get(`${BASE}/api/services`,                      () => HttpResponse.json(DEFAULT_SERVICES)),
  http.get(`${BASE}/api/metrics/:service/:metric`,      () => HttpResponse.json(DEFAULT_METRIC_SERIES)),
  http.get(`${BASE}/api/incidents`,                     () => HttpResponse.json(DEFAULT_INCIDENTS)),
  http.get(`${BASE}/api/models`,                        () => HttpResponse.json(DEFAULT_MODELS)),
]
