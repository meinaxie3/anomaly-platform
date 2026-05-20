import { formatDistanceToNow, parseISO } from 'date-fns'
import { AlertTriangle, CheckCircle, ChevronRight } from 'lucide-react'
import type { IncidentSummary } from '../api/types'

interface Props {
  incident: IncidentSummary
  /** When provided the row becomes a clickable button that navigates to the metric chart. */
  onClick?: () => void
}

export function IncidentRow({ incident, onClick }: Props) {
  const isOpen = incident.status === 'open'
  const startedAgo = formatDistanceToNow(parseISO(incident.started_at), { addSuffix: true })

  const inner = (
    <>
      <div className="flex items-center gap-3">
        {isOpen ? (
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" aria-label="Open incident" />
        ) : (
          <CheckCircle className="h-4 w-4 shrink-0 text-emerald-500" aria-label="Resolved incident" />
        )}
        <div>
          <p className="text-sm font-medium text-slate-800">
            {incident.service}{' '}
            <span className="font-mono text-xs text-slate-500">{incident.metric}</span>
          </p>
          <p className="text-xs text-slate-500">
            Started {startedAgo} &middot; {incident.anomaly_count} anomal
            {incident.anomaly_count === 1 ? 'y' : 'ies'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            isOpen
              ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
              : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
          }`}
        >
          {incident.status}
        </span>
        {onClick && (
          <ChevronRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
        )}
      </div>
    </>
  )

  if (onClick) {
    return (
      <button
        onClick={onClick}
        className="flex w-full items-center justify-between rounded-lg border border-slate-200
                   bg-white px-4 py-3 shadow-sm text-left transition
                   hover:border-blue-300 hover:shadow-md
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
        aria-label={`View ${incident.service} ${incident.metric} chart`}
      >
        {inner}
      </button>
    )
  }

  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      {inner}
    </div>
  )
}
