import type { HealthStatus } from '../api/types'

const CONFIG: Record<HealthStatus, { label: string; classes: string; dot: string }> = {
  healthy:  { label: 'Healthy',  classes: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200', dot: 'bg-emerald-500' },
  degraded: { label: 'Degraded', classes: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',      dot: 'bg-amber-500'   },
  critical: { label: 'Critical', classes: 'bg-red-50 text-red-700 ring-1 ring-red-200',            dot: 'bg-red-500'     },
}

interface Props {
  health: HealthStatus
  className?: string
}

export function StatusBadge({ health, className = '' }: Props) {
  const { label, classes, dot } = CONFIG[health]
  return (
    <span
      role="status"
      aria-label={`Health status: ${label}`}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${classes} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden="true" />
      {label}
    </span>
  )
}
