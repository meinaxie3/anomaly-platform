import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from '../test/server'
import { Models } from './Models'

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

  it('shows — for unevaluated F1 score (-1)', async () => {
    render(<Models />, { wrapper })
    await waitFor(() => {
      // eval_f1 = -1 should render as "—"
      expect(screen.getByText('—')).toBeInTheDocument()
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
