import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricChart } from './MetricChart'
import type { MetricSeries } from '../api/types'

const now = new Date().toISOString()
const hour_ago = new Date(Date.now() - 3_600_000).toISOString()

const SERIES_WITH_ANOMALY: MetricSeries = {
  service: 'payment-api',
  metric: 'cpu_percent',
  points: [
    { bucket: hour_ago, avg_value: 52.0, min_value: 48.0, max_value: 56.0, sample_count: 60 },
    { bucket: now,      avg_value: 55.0, min_value: 50.0, max_value: 61.0, sample_count: 60 },
  ],
  anomalies: [{ timestamp: now, value: 999.0, score: -0.21 }],
}

const EMPTY_SERIES: MetricSeries = {
  service: 'payment-api',
  metric: 'cpu_percent',
  points: [],
  anomalies: [],
}

describe('MetricChart', () => {
  it('renders EmptyState when points array is empty', () => {
    render(<MetricChart series={EMPTY_SERIES} />)
    expect(screen.getByText('No metric data')).toBeInTheDocument()
  })

  it('renders a chart container when data is present', () => {
    const { container } = render(<MetricChart series={SERIES_WITH_ANOMALY} />)
    // Recharts renders an SVG
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('renders a screen-reader accessible anomaly list with correct count', () => {
    render(<MetricChart series={SERIES_WITH_ANOMALY} />)
    // A sr-only <ul> is rendered alongside the chart for accessibility
    const list = screen.getByRole('list', { name: /detected anomalies/i })
    expect(list).toBeInTheDocument()
    expect(list.querySelectorAll('li').length).toBe(1)
  })

  it('does not render anomaly list when series has no anomalies', () => {
    render(<MetricChart series={{ ...SERIES_WITH_ANOMALY, anomalies: [] }} />)
    expect(screen.queryByRole('list', { name: /detected anomalies/i })).not.toBeInTheDocument()
  })
})
