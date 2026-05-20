/**
 * App — shell with simple in-app navigation (no router dependency).
 *
 * Three views:
 *   overview     → Overview (service grid + incident feed)
 *   service      → ServiceDetail (metric chart + per-service incidents)
 *   models       → Models (model registry table)
 */

import { useState } from 'react'
import { Activity } from 'lucide-react'
import { Overview } from './views/Overview'
import { ServiceDetail } from './views/ServiceDetail'
import { Models } from './views/Models'

type View = 'overview' | 'service' | 'models'

export default function App() {
  const [view, setView] = useState<View>('overview')
  const [selectedService, setSelectedService] = useState<string>('')

  function navigateTo(v: View, service?: string) {
    setView(v)
    if (service) setSelectedService(service)
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ── Nav bar ── */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
          <button
            onClick={() => navigateTo('overview')}
            className="flex items-center gap-2 text-blue-600 hover:text-blue-700 focus:outline-none"
            aria-label="Go to overview"
          >
            <Activity className="h-5 w-5" />
            <span className="font-semibold text-slate-800">Anomaly Platform</span>
          </button>

          <nav aria-label="Main navigation">
            <ul className="flex items-center gap-1 text-sm">
              {(
                [
                  { label: 'Overview', target: 'overview' as View },
                  { label: 'Models',   target: 'models'   as View },
                ] as const
              ).map(({ label, target }) => (
                <li key={target}>
                  <button
                    onClick={() => navigateTo(target)}
                    aria-current={view === target ? 'page' : undefined}
                    className={`rounded-md px-3 py-1.5 font-medium transition
                      ${
                        view === target
                          ? 'bg-blue-50 text-blue-700'
                          : 'text-slate-600 hover:bg-slate-100'
                      }`}
                  >
                    {label}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>

      {/* ── Main content ── */}
      <main className="mx-auto max-w-7xl px-6 py-8">
        {view === 'overview' && (
          <Overview
            onSelectService={(svc) => navigateTo('service', svc)}
          />
        )}
        {view === 'service' && selectedService && (
          <ServiceDetail
            service={selectedService}
            onBack={() => navigateTo('overview')}
          />
        )}
        {view === 'models' && <Models />}
      </main>
    </div>
  )
}
