import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../test/server'
import { DEFAULT_MODELS } from '../test/handlers'
import { Models } from './Models'
import type { ModelSummary } from '../api/types'

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('Models', () => {
  it('renders model table rows', async () => {
    render(<Models />, { wrapper })
    await waitFor(() => {
      // payment-api appears in both the select option and the table cell
      expect(screen.getAllByText('payment-api').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('IsolationForest')).toBeInTheDocument()
    })
  })

  it('shows evaluated precision, recall, and F1 scores', async () => {
    render(<Models />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('0.870')).toBeInTheDocument()         // precision (table only)
      expect(screen.getByText('0.820')).toBeInTheDocument()         // recall (table only)
      // F1 appears twice: avg-stat card + table cell (single model → avg = same value)
      expect(screen.getAllByText('0.845').length).toBeGreaterThanOrEqual(1)
    })
  })

  it('shows — for unevaluated scores (-1)', async () => {
    const unevaluated: ModelSummary[] = [
      {
        ...DEFAULT_MODELS[0],
        eval_precision: -1.0,
        eval_recall: -1.0,
        eval_f1: -1.0,
      },
    ]
    server.use(http.get('http://localhost/api/models', () => HttpResponse.json(unevaluated)))
    render(<Models />, { wrapper })
    await waitFor(() => {
      // Three "—" cells: precision, recall, F1
      expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(3)
    })
  })

  it('shows average F1 stat when models are evaluated', async () => {
    render(<Models />, { wrapper })
    await waitFor(() => {
      expect(screen.getByLabelText(/average f1/i)).toBeInTheDocument()
    })
  })

  it('renders EmptyState when no models exist', async () => {
    server.use(http.get('http://localhost/api/models', () => HttpResponse.json([])))
    render(<Models />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('No models found')).toBeInTheDocument()
    })
  })

  it('renders ErrorBanner when /models returns error', async () => {
    server.use(http.get('http://localhost/api/models', () => HttpResponse.error()))
    render(<Models />, { wrapper })
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('shows current badge for is_current=true models', async () => {
    render(<Models />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('current')).toBeInTheDocument()
    })
  })

  it('current-only checkbox toggles filter', async () => {
    const user = userEvent.setup()
    render(<Models />, { wrapper })
    await waitFor(() => screen.getByText('IsolationForest'))
    const checkbox = screen.getByRole('checkbox', { name: /current models only/i })
    await user.click(checkbox)
    expect(checkbox).toBeChecked()
  })
})
