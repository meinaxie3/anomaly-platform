import '@testing-library/jest-dom'
import { server } from './server'
import { afterAll, afterEach, beforeAll } from 'vitest'

// Recharts' ResponsiveContainer uses ResizeObserver which doesn't exist in jsdom
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver

// Recharts also calls getBoundingClientRect — return a sensible size
Element.prototype.getBoundingClientRect = () => ({
  x: 0, y: 0, width: 800, height: 300,
  top: 0, right: 800, bottom: 300, left: 0,
  toJSON: () => {},
})

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
