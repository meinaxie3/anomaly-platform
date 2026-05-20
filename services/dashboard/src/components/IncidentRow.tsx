import { formatDistanceToNow, parseISO } from 'date-fns'
import { AlertTriangle, CheckCircle } from 'lucide-react'
import type { IncidentSummary } from '../api/types'

interface Props {
  incident: IncidentSummary
}

export function IncidentRow({ incident }: Props) {
  const isOpen = incident.status === 'open'
  const startedAgo = formatDistanceToNow(parseISO(incident.started_at), { addSuffix: true })

  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center gap-3">
        {isOpen ? (
          <AlertTriangle
            className="h-4 w-4 shrink-0 text-amber-500"
            aria-label="Open incident"
          />
        ) : (
          <CheckCircle
            className="h-4 w-4 shrink-0 text-emerald-500"
            aria-label="Resolved incident"
          />
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
      <span
        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
          isOpen
            ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
            : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
        }`}
      >
        {incident.status}
      </span>
    </div>
  )
}
