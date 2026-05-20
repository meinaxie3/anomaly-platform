import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { IncidentRow } from './IncidentRow'
import type { IncidentSummary } from '../api/types'

const OPEN_INCIDENT: IncidentSummary = {
  incident_id: 'aaaaaaaa-0000-0000-0000-000000000001',
  service: 'payment-api',
  metric: 'cpu_percent',
  status: 'open',
  started_at: new Date(Date.now() - 5 * 60_000).toISOString(), // 5 min ago
  resolved_at: null,
  anomaly_count: 3,
}

const RESOLVED_INCIDENT: IncidentSummary = {
  ...OPEN_INCIDENT,
  incident_id: 'aaaaaaaa-0000-0000-0000-000000000002',
  status: 'resolved',
  resolved_at: new Date().toISOString(),
}

describe('IncidentRow', () => {
  it('renders service and metric names', () => {
    render(<IncidentRow incident={OPEN_INCIDENT} />)
    expect(screen.getByText('payment-api')).toBeInTheDocument()
    expect(screen.getByText('cpu_percent')).toBeInTheDocument()
  })

  it('shows open status badge for open incidents', () => {
    render(<IncidentRow incident={OPEN_INCIDENT} />)
    expect(screen.getByText('open')).toBeInTheDocument()
  })

  it('shows resolved status badge for resolved incidents', () => {
    render(<IncidentRow incident={RESOLVED_INCIDENT} />)
    expect(screen.getByText('resolved')).toBeInTheDocument()
  })

  it('shows anomaly count', () => {
    render(<IncidentRow incident={OPEN_INCIDENT} />)
    expect(screen.getByText(/3 anomalies/)).toBeInTheDocument()
  })

  it('uses singular "anomaly" for count of 1', () => {
    render(<IncidentRow incident={{ ...OPEN_INCIDENT, anomaly_count: 1 }} />)
    expect(screen.getByText(/1 anomaly/)).toBeInTheDocument()
  })

  it('shows relative time "ago" in started label', () => {
    render(<IncidentRow incident={OPEN_INCIDENT} />)
    expect(screen.getByText(/ago/)).toBeInTheDocument()
  })
})
