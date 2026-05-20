import { formatDistanceToNow, parseISO } from 'date-fns'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { IncidentRow } from '../components/IncidentRow'
import { StatusBadge } from '../components/StatusBadge'
import { useIncidents, useServices } from '../hooks'

// ---------------------------------------------------------------------------
// Service card
// ---------------------------------------------------------------------------

interface ServiceCardProps {
  service: string
  openIncidents: number
  health: 'healthy' | 'degraded' | 'critical'
  lastAnomalyAt: string | null
  onClick: () => void
}

function ServiceCard({ service, openIncidents, health, lastAnomalyAt, onClick }: ServiceCardProps) {
  return (
    <button
      onClick={onClick}
      className="w-full rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm
                 transition hover:border-blue-300 hover:shadow-md focus:outline-none focus:ring-2
                 focus:ring-blue-500 focus:ring-offset-2"
    >
      <div className="flex items-start justify-between">
        <p className="font-semibold text-slate-800 truncate">{service}</p>
        <StatusBadge health={health} />
      </div>
      <div className="mt-3 text-sm text-slate-500 space-y-1">
        <p>
          <span className="font-medium text-slate-700">{openIncidents}</span> open incident
          {openIncidents !== 1 ? 's' : ''}
        </p>
        {lastAnomalyAt ? (
          <p>
            Last anomaly{' '}
            <span className="font-medium">
              {formatDistanceToNow(parseISO(lastAnomalyAt), { addSuffix: true })}
            </span>
          </p>
        ) : (
          <p className="text-slate-400">No anomalies recorded</p>
        )}
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Overview page
// ---------------------------------------------------------------------------

interface Props {
  onSelectService: (service: string, metric?: string) => void
}

export function Overview({ onSelectService }: Props) {
  const servicesQuery = useServices()
  const incidentsQuery = useIncidents('open')

  return (
    <div className="space-y-8">
      {/* ── Services grid ── */}
      <section aria-labelledby="services-heading">
        <h2 id="services-heading" className="mb-4 text-lg font-semibold text-slate-800">
          Services
          {servicesQuery.data && (
            <span className="ml-2 text-sm font-normal text-slate-500">
              ({servicesQuery.data.length})
            </span>
          )}
        </h2>

        {servicesQuery.isError && (
          <ErrorBanner message="Could not load services. Retrying in 10 s…" />
        )}

        {servicesQuery.isSuccess && servicesQuery.data.length === 0 && (
          <EmptyState
            title="No services seen yet"
            description="Services appear here once the ingestion pipeline processes events."
          />
        )}

        {servicesQuery.isSuccess && servicesQuery.data.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {servicesQuery.data.map((svc) => (
              <ServiceCard
                key={svc.service}
                service={svc.service}
                openIncidents={svc.open_incidents}
                health={svc.health}
                lastAnomalyAt={svc.last_anomaly_at}
                onClick={() => onSelectService(svc.service)}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── Recent open incidents ── */}
      <section aria-labelledby="incidents-heading">
        <h2 id="incidents-heading" className="mb-4 text-lg font-semibold text-slate-800">
          Open Incidents
        </h2>

        {incidentsQuery.isError && (
          <ErrorBanner message="Could not load incidents. Retrying in 10 s…" />
        )}

        {incidentsQuery.isSuccess && incidentsQuery.data.length === 0 && (
          <EmptyState
            title="No open incidents"
            description="All clear! Incidents appear here when the alert engine groups anomalies."
          />
        )}

        {incidentsQuery.isSuccess && incidentsQuery.data.length > 0 && (
          <div className="space-y-2">
            {incidentsQuery.data.slice(0, 10).map((inc) => (
              <IncidentRow
                key={inc.incident_id}
                incident={inc}
                onClick={() => onSelectService(inc.service, inc.metric)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
