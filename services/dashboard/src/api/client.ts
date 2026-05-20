/**
 * Typed API client.
 *
 * In development, Vite proxies /api → http://localhost:8003 (see vite.config.ts).
 * In production builds, the React app should be served from the same origin as
 * the dashboard-api, or CORS must be configured on the API.
 */

import type { IncidentSummary, MetricSeries, ModelSummary, ServiceSummary } from './types'

const BASE = '/api'

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    const body = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, body)
  }
  return res.json() as Promise<T>
}

export const api = {
  /** GET /services — one row per service with health roll-up. */
  services(): Promise<ServiceSummary[]> {
    return get<ServiceSummary[]>('/services')
  },

  /** GET /metrics/{service}/{metric} — time-series + anomaly markers. */
  metricSeries(service: string, metric: string, from: string, to: string): Promise<MetricSeries> {
    return get<MetricSeries>(`/metrics/${encodeURIComponent(service)}/${encodeURIComponent(metric)}`, {
      from,
      to,
    })
  },

  /** GET /incidents — paginated incident feed. */
  incidents(status?: string, limit = 50, offset = 0): Promise<IncidentSummary[]> {
    const params: Record<string, string> = {
      limit: String(limit),
      offset: String(offset),
    }
    if (status) params.status = status
    return get<IncidentSummary[]>('/incidents', params)
  },

  /** GET /models — model registry, optionally filtered. */
  models(service?: string, currentOnly?: boolean): Promise<ModelSummary[]> {
    const params: Record<string, string> = {}
    if (service) params.service = service
    if (currentOnly) params.current_only = 'true'
    return get<ModelSummary[]>('/models', params)
  },
}
