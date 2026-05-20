import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders Healthy text and correct aria-label for healthy status', () => {
    render(<StatusBadge health="healthy" />)
    const badge = screen.getByRole('status', { name: /Health status: Healthy/i })
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveTextContent('Healthy')
  })

  it('renders Degraded text for degraded status', () => {
    render(<StatusBadge health="degraded" />)
    expect(screen.getByText('Degraded')).toBeInTheDocument()
  })

  it('renders Critical text for critical status', () => {
    render(<StatusBadge health="critical" />)
    expect(screen.getByText('Critical')).toBeInTheDocument()
  })

  it('applies emerald color classes for healthy', () => {
    render(<StatusBadge health="healthy" />)
    expect(screen.getByRole('status')).toHaveClass('text-emerald-700')
  })

  it('applies amber color classes for degraded', () => {
    render(<StatusBadge health="degraded" />)
    expect(screen.getByRole('status')).toHaveClass('text-amber-700')
  })

  it('applies red color classes for critical', () => {
    render(<StatusBadge health="critical" />)
    expect(screen.getByRole('status')).toHaveClass('text-red-700')
  })
})
