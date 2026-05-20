import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { server } from '../test/server'
import { DEFAULT_SERVICES, DEFAULT_INCIDENTS } from '../test/handlers'
import { Overview } from './Overview'

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('Overview', () => {
  it('renders service cards after data loads', async () => {
    render(<Overview onSelectService={vi.fn()} />, { wrapper })
    await waitFor(() => {
      // payment-api appears in the service card AND the incident row,
      // so use getAllByText and confirm at least 1 element exists
      expect(screen.getAllByText('payment-api').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('auth-service')).toBeInTheDocument()
    })
  })

  it('shows correct health badges', async () => {
    render(<Overview onSelectService={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('Degraded')).toBeInTheDocument()
      expect(screen.getByText('Healthy')).toBeInTheDocument()
    })
  })

  it('renders EmptyState when services list is empty', async () => {
    server.use(http.get('http://localhost/api/services', () => HttpResponse.json([])))
    render(<Overview onSelectService={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('No services seen yet')).toBeInTheDocument()
    })
  })

  it('renders ErrorBanner when /services returns 500', async () => {
    server.use(http.get('http://localhost/api/services', () => HttpResponse.error()))
    render(<Overview onSelectService={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('calls onSelectService with service name when card is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<Overview onSelectService={onSelect} />, { wrapper })
    // Wait for the service cards to appear (at least one button contains payment-api)
    await waitFor(() => screen.getAllByText('payment-api'))
    // Click the service CARD button (distinct from the incident row which is a div)
    const buttons = screen.getAllByRole('button')
    const paymentBtn = buttons.find((b) => b.textContent?.includes('payment-api') && b.textContent?.includes('open incident'))
    expect(paymentBtn).toBeDefined()
    await user.click(paymentBtn!)
    expect(onSelect).toHaveBeenCalledWith('payment-api')
  })

  it('shows open incidents section', async () => {
    render(<Overview onSelectService={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('Open Incidents')).toBeInTheDocument()
    })
  })

  it('shows EmptyState in incidents section when none are open', async () => {
    server.use(http.get('http://localhost/api/incidents', () => HttpResponse.json([])))
    render(<Overview onSelectService={vi.fn()} />, { wrapper })
    await waitFor(() => {
      expect(screen.getByText('No open incidents')).toBeInTheDocument()
    })
  })
})
