import { useQuery } from '@tanstack/react-query'
import { subHours, subDays } from 'date-fns'
import { api } from '../api/client'

// ---------------------------------------------------------------------------
// /services — refetch every 10 s (live health roll-up)
// ---------------------------------------------------------------------------

export function useServices() {
  return useQuery({
    queryKey: ['services'],
    queryFn: api.services,
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}

// ---------------------------------------------------------------------------
// /metrics/{service}/{metric} — refetch every 15 s
// ---------------------------------------------------------------------------

export type TimeWindow = '1h' | '3h' | '24h' | '7d'

function windowToDates(window: TimeWindow): { from: string; to: string } {
  const to = new Date()
  const from = {
    '1h': subHours(to, 1),
    '3h': subHours(to, 3),
    '24h': subHours(to, 24),
    '7d': subDays(to, 7),
  }[window]
  return { from: from.toISOString(), to: to.toISOString() }
}

export function useMetricSeries(service: string, metric: string, window: TimeWindow) {
  const { from, to } = windowToDates(window)
  return useQuery({
    queryKey: ['metric-series', service, metric, window],
    queryFn: () => api.metricSeries(service, metric, from, to),
    refetchInterval: 15_000,
    staleTime: 10_000,
    enabled: Boolean(service && metric),
  })
}

// ---------------------------------------------------------------------------
// /incidents — refetch every 10 s
// ---------------------------------------------------------------------------

export function useIncidents(status?: string) {
  return useQuery({
    queryKey: ['incidents', status ?? 'all'],
    queryFn: () => api.incidents(status),
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}

// ---------------------------------------------------------------------------
// /models — refetch every 60 s (models change infrequently)
// ---------------------------------------------------------------------------

export function useModels(service?: string, currentOnly?: boolean) {
  return useQuery({
    queryKey: ['models', service ?? 'all', currentOnly ?? false],
    queryFn: () => api.models(service, currentOnly),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
}
