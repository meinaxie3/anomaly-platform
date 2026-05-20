import { useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { MetricChart } from '../components/MetricChart'
import { IncidentRow } from '../components/IncidentRow'
import { useIncidents, useMetricSeries, useModels, type TimeWindow } from '../hooks'

// ---------------------------------------------------------------------------
// Time-window toggle
// ---------------------------------------------------------------------------

const WINDOWS: { label: string; value: TimeWindow; hours: number }[] = [
  { label: '1 h',  value: '1h',  hours: 1  },
  { label: '3 h',  value: '3h',  hours: 3  },
  { label: '24 h', value: '24h', hours: 24 },
  { label: '7 d',  value: '7d',  hours: 168 },
]

interface WindowToggleProps {
  value: TimeWindow
  onChange: (w: TimeWindow) => void
}

function WindowToggle({ value, onChange }: WindowToggleProps) {
  return (
    <div className="flex rounded-lg border border-slate-200 bg-white" role="group" aria-label="Time window">
      {WINDOWS.map((w) => (
        <button
          key={w.value}
          onClick={() => onChange(w.value)}
          aria-pressed={value === w.value}
          className={`px-3 py-1.5 text-xs font-medium transition first:rounded-l-lg last:rounded-r-lg
            ${
              value === w.value
                ? 'bg-blue-600 text-white'
                : 'text-slate-600 hover:bg-slate-50'
            }`}
        >
          {w.label}
        </button>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Service Detail page
// ---------------------------------------------------------------------------

interface Props {
  service: string
  initialMetric?: string   // pre-select a metric tab (e.g. when navigating from an incident row)
  onBack: () => void
}

export function ServiceDetail({ service, initialMetric = '', onBack }: Props) {
  const [window, setWindow] = useState<TimeWindow>('24h')
  const [selectedMetric, setSelectedMetric] = useState<string>(initialMetric)

  // Use model list to derive available metrics for this service
  const modelsQuery = useModels(service, true)
  const metrics = modelsQuery.data?.map((m) => m.metric) ?? []

  // If initialMetric was provided use it; otherwise fall back to first available metric
  const activeMetric = selectedMetric || metrics[0] || ''

  const windowHours = WINDOWS.find((w) => w.value === window)?.hours ?? 3
  const seriesQuery = useMetricSeries(service, activeMetric, window)
  const incidentsQuery = useIncidents('open')
  const serviceIncidents = incidentsQuery.data?.filter((i) => i.service === service) ?? []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-slate-600
                     hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Back to overview"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <h2 className="text-xl font-semibold text-slate-800">{service}</h2>
      </div>

      {/* Metric tabs + window toggle */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Metrics">
          {modelsQuery.isSuccess && metrics.length === 0 && (
            <p className="text-sm text-slate-500">No trained models for this service.</p>
          )}
          {metrics.map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={m === activeMetric}
              onClick={() => setSelectedMetric(m)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition
                ${
                  m === activeMetric
                    ? 'bg-blue-100 text-blue-700 ring-1 ring-blue-300'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
            >
              {m}
            </button>
          ))}
        </div>
        <WindowToggle value={window} onChange={setWindow} />
      </div>

      {/* Chart */}
      <section
        aria-label={`${activeMetric} time series for ${service}`}
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <p className="mb-4 text-sm font-medium text-slate-600">
          <span className="font-mono">{activeMetric}</span>
          {seriesQuery.data && (
            <span className="ml-2 text-slate-400 text-xs">
              {seriesQuery.data.anomalies.length} anomal
              {seriesQuery.data.anomalies.length === 1 ? 'y' : 'ies'} in window
            </span>
          )}
        </p>

        {seriesQuery.isError && (
          <ErrorBanner message="Could not load metric data." />
        )}

        {seriesQuery.isSuccess && seriesQuery.data.points.length === 0 && (
          <div className="flex h-[280px] flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm text-slate-500">No data in the last {WINDOWS.find(w => w.value === window)?.label ?? window}</p>
            {window !== '7d' && (
              <button
                onClick={() => setWindow('7d')}
                className="rounded-md bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700
                           ring-1 ring-blue-200 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Try 7 d
              </button>
            )}
          </div>
        )}

        {seriesQuery.isSuccess && seriesQuery.data.points.length > 0 && (
          <MetricChart
            series={seriesQuery.data}
            windowHours={windowHours}
          />
        )}

        {!seriesQuery.isSuccess && !seriesQuery.isError && activeMetric && (
          <div className="flex h-[280px] items-center justify-center">
            <p className="text-sm text-slate-400">Loading…</p>
          </div>
        )}
      </section>

      {/* Open incidents for this service */}
      <section aria-labelledby="service-incidents-heading">
        <h3 id="service-incidents-heading" className="mb-3 text-base font-semibold text-slate-800">
          Open Incidents
        </h3>
        {serviceIncidents.length === 0 ? (
          <EmptyState title="No open incidents" description="This service has no active incidents." />
        ) : (
          <div className="space-y-2">
            {serviceIncidents.map((inc) => (
              <IncidentRow
                key={inc.incident_id}
                incident={inc}
                onClick={() => setSelectedMetric(inc.metric)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
