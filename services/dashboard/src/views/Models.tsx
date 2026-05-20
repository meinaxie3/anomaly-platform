import { useState } from 'react'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { EmptyState } from '../components/EmptyState'
import { ErrorBanner } from '../components/ErrorBanner'
import { useModels, useServices } from '../hooks'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format an eval score (-1 = not yet evaluated). */
function fmtScore(v: number): string {
  return v < 0 ? '—' : v.toFixed(3)
}

function fmtSamples(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

/**
 * Return Tailwind classes for an eval score cell.
 *  ≥ 0.80  → green   (good)
 *  ≥ 0.60  → amber   (needs improvement)
 *  0–0.59  → red     (poor)
 *  < 0     → muted   (not evaluated)
 */
function scoreClass(v: number): string {
  if (v < 0)   return 'text-slate-400'
  if (v >= 0.8) return 'text-emerald-700 font-semibold'
  if (v >= 0.6) return 'text-amber-600'
  return 'text-red-600'
}

// ---------------------------------------------------------------------------
// Models page
// ---------------------------------------------------------------------------

export function Models() {
  const [selectedService, setSelectedService] = useState<string>('')
  const [currentOnly, setCurrentOnly] = useState(false)

  const servicesQuery = useServices()
  const modelsQuery = useModels(selectedService || undefined, currentOnly)

  // Compute quick stats for evaluated models
  const evaluated = modelsQuery.data?.filter((m) => m.eval_f1 >= 0) ?? []
  const avgF1 =
    evaluated.length > 0
      ? evaluated.reduce((s, m) => s + m.eval_f1, 0) / evaluated.length
      : null

  return (
    <div className="space-y-6">
      {/* ── Filters ── */}
      <div className="flex flex-wrap items-center gap-4">
        <div>
          <label htmlFor="service-filter" className="mr-2 text-sm text-slate-600">
            Service
          </label>
          <select
            id="service-filter"
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm
                       text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All services</option>
            {servicesQuery.data?.map((s) => (
              <option key={s.service} value={s.service}>
                {s.service}
              </option>
            ))}
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={currentOnly}
            onChange={(e) => setCurrentOnly(e.target.checked)}
            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
          />
          Current models only
        </label>

        {/* Aggregate stat */}
        {avgF1 !== null && (
          <div
            className="ml-auto rounded-lg border border-slate-200 bg-white px-4 py-2 shadow-sm"
            aria-label="Average F1 across evaluated models"
          >
            <p className="text-xs text-slate-500">Avg F1 ({evaluated.length} models)</p>
            <p className={`text-lg font-semibold ${scoreClass(avgF1)}`}>
              {avgF1.toFixed(3)}
            </p>
          </div>
        )}
      </div>

      {/* ── Error ── */}
      {modelsQuery.isError && (
        <ErrorBanner message="Could not load models." />
      )}

      {/* ── Empty ── */}
      {modelsQuery.isSuccess && modelsQuery.data.length === 0 && (
        <EmptyState
          title="No models found"
          description="Run uv run training --run-once to train the first batch of models."
        />
      )}

      {/* ── Score legend ── */}
      {modelsQuery.isSuccess && modelsQuery.data.length > 0 && (
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
          <span className="font-medium">Eval scores:</span>
          <span className="text-emerald-700 font-semibold">≥ 0.80 good</span>
          <span className="text-amber-600">0.60 – 0.79 fair</span>
          <span className="text-red-600">{'< 0.60 poor'}</span>
          <span className="text-slate-400">— not evaluated</span>
        </div>
      )}

      {/* ── Table ── */}
      {modelsQuery.isSuccess && modelsQuery.data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm" aria-label="Trained models">
            <thead className="border-b border-slate-100 bg-slate-50">
              <tr>
                {[
                  'Service',
                  'Metric',
                  'Algorithm',
                  'Trained',
                  'Samples',
                  'Precision',
                  'Recall',
                  'F1',
                  'Current',
                ].map((h) => (
                  <th
                    key={h}
                    scope="col"
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {modelsQuery.data.map((m) => (
                <tr key={m.model_id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-800">
                    {m.service}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-slate-600">
                    {m.metric}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                    {m.algorithm}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                    {formatDistanceToNow(parseISO(m.trained_at), { addSuffix: true })}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right font-mono text-slate-600">
                    {fmtSamples(m.n_samples)}
                  </td>
                  <td className={`whitespace-nowrap px-4 py-3 text-right font-mono ${scoreClass(m.eval_precision)}`}>
                    {fmtScore(m.eval_precision)}
                  </td>
                  <td className={`whitespace-nowrap px-4 py-3 text-right font-mono ${scoreClass(m.eval_recall)}`}>
                    {fmtScore(m.eval_recall)}
                  </td>
                  <td className={`whitespace-nowrap px-4 py-3 text-right font-mono ${scoreClass(m.eval_f1)}`}>
                    {fmtScore(m.eval_f1)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-center">
                    {m.is_current ? (
                      <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
                        current
                      </span>
                    ) : (
                      <span className="text-slate-400">&mdash;</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
