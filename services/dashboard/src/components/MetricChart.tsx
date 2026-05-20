/**
 * MetricChart — Recharts ComposedChart for one (service, metric) series.
 *
 * Renders:
 *   • Area fill for avg_value (main signal)
 *   • Thin lines for min/max envelope
 *   • Red ReferenceDot + ⚠ label for each anomaly marker
 *   • Custom tooltip showing bucket time, avg, min/max, and anomaly score
 */

import { format, parseISO } from 'date-fns'
import {
  Area,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps,
} from 'recharts'
import type { AnomalyMarker, MetricPoint, MetricSeries } from '../api/types'
import { EmptyState } from './EmptyState'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtBucket(iso: string, windowHours: number): string {
  const d = parseISO(iso)
  return windowHours <= 24 ? format(d, 'HH:mm') : format(d, 'MMM d HH:mm')
}

function fmtFull(iso: string): string {
  return format(parseISO(iso), 'MMM d HH:mm:ss')
}

// ---------------------------------------------------------------------------
// Custom tooltip
// ---------------------------------------------------------------------------

interface CustomTooltipPayload {
  payload?: { payload: MetricPoint & { _anomaly?: AnomalyMarker } }[]
  active?: boolean
  label?: string
}

function CustomTooltip({ active, payload }: CustomTooltipPayload & TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const anomaly = d._anomaly

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-lg text-xs space-y-1">
      <p className="font-medium text-slate-700">{fmtFull(d.bucket)}</p>
      <p className="text-slate-600">
        avg: <span className="font-mono font-medium">{d.avg_value.toFixed(2)}</span>
      </p>
      <p className="text-slate-500">
        range: {d.min_value.toFixed(2)} – {d.max_value.toFixed(2)}
      </p>
      {anomaly && (
        <p className="text-red-600 font-medium">
          ⚠ Anomaly detected &mdash; score: {anomaly.score.toFixed(4)}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chart props
// ---------------------------------------------------------------------------

interface Props {
  series: MetricSeries
  windowHours?: number
  height?: number
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function MetricChart({ series, windowHours = 3, height = 280 }: Props) {
  if (series.points.length === 0) {
    return (
      <EmptyState
        title="No metric data"
        description="No data points in the selected time window."
      />
    )
  }

  // Build a lookup of anomalies by nearest bucket timestamp so we can
  // annotate the tooltip and add ReferenceDots.
  const anomalyByBucket = new Map<string, AnomalyMarker>()
  for (const a of series.anomalies) {
    anomalyByBucket.set(a.timestamp, a)
  }

  // Enrich each point with an _anomaly field for the tooltip
  const data = series.points.map((p) => ({
    ...p,
    _anomaly: anomalyByBucket.get(p.bucket) ?? null,
  }))

  return (
    <div>
      {/* Screen-reader-accessible anomaly list — Recharts SVG can't carry aria-labels reliably */}
      {series.anomalies.length > 0 && (
        <ul className="sr-only" aria-label="Detected anomalies">
          {series.anomalies.map((a) => (
            <li key={a.timestamp}>
              Anomaly at {fmtFull(a.timestamp)}, value {a.value}, score {a.score.toFixed(4)}
            </li>
          ))}
        </ul>
      )}
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <XAxis
          dataKey="bucket"
          tickFormatter={(v: string) => fmtBucket(v, windowHours)}
          tick={{ fontSize: 11, fill: '#64748b' }}
          tickLine={false}
          axisLine={false}
          minTickGap={60}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#64748b' }}
          tickLine={false}
          axisLine={false}
          width={48}
        />
        <Tooltip content={<CustomTooltip />} />

        {/* Min/max envelope lines (subtle) */}
        <Line
          type="monotone"
          dataKey="max_value"
          stroke="#94a3b8"
          strokeWidth={1}
          dot={false}
          strokeDasharray="3 3"
          name="max"
        />
        <Line
          type="monotone"
          dataKey="min_value"
          stroke="#94a3b8"
          strokeWidth={1}
          dot={false}
          strokeDasharray="3 3"
          name="min"
        />

        {/* Main avg area */}
        <Area
          type="monotone"
          dataKey="avg_value"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="#eff6ff"
          name="avg"
          dot={false}
          activeDot={{ r: 4, fill: '#3b82f6' }}
        />

        {/* Anomaly markers — red dot + ⚠ label */}
        {series.anomalies.map((a) => (
          <ReferenceDot
            key={a.timestamp}
            x={a.timestamp}
            y={a.value}
            r={6}
            fill="#ef4444"
            stroke="#fff"
            strokeWidth={2}
            label={{
              value: '⚠',
              position: 'top',
              fontSize: 12,
              fill: '#ef4444',
            }}
            aria-label={`Anomaly at ${fmtFull(a.timestamp)}, score ${a.score.toFixed(4)}`}
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
    </div>
  )
}
