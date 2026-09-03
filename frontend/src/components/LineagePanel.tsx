// THE screen. Any number in the app opens this drawer and walks the full audit trail:
// reported value -> calculation -> unit conversion -> factor version -> activity record
// -> source document -> approval. Nothing here is recomputed client-side; every step is
// what the calculator recorded at the time.
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { fmt, useLineage } from '../api'
import type { Confidence, LineageStep } from '../types'

// ------------------------------------------------------------------- open/close
const LineageCtx = createContext<(emissionId: number | null) => void>(() => {})

/** Opens the lineage drawer. Any component can drill in without prop-threading. */
export const useOpenLineage = () => useContext(LineageCtx)

export function LineageProvider({ children }: { children: ReactNode }) {
  const [emissionId, setEmissionId] = useState<number | null>(null)
  const open = useCallback((id: number | null) => setEmissionId(id), [])

  useEffect(() => {
    if (emissionId === null) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setEmissionId(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [emissionId])

  return (
    <LineageCtx.Provider value={open}>
      {children}
      {emissionId !== null && (
        <LineageDrawer emissionId={emissionId} onClose={() => setEmissionId(null)} />
      )}
    </LineageCtx.Provider>
  )
}

/** A figure that drills into its own audit trail. */
export function Drill({
  emissionId,
  children,
  className = '',
  title,
}: {
  emissionId: number | null | undefined
  children: ReactNode
  className?: string
  title?: string
}) {
  const open = useOpenLineage()
  if (emissionId === null || emissionId === undefined) {
    return <span className={className}>{children}</span>
  }
  return (
    <button
      type="button"
      className={`drill ${className}`}
      title={title ?? 'Open the audit trail for this figure'}
      onClick={() => open(emissionId)}
    >
      {children}
    </button>
  )
}

// ----------------------------------------------------------------------- chrome
const STEP_META: Record<LineageStep['step'], { n: string; label: string }> = {
  reported_value: { n: '1', label: 'Reported' },
  calculation: { n: '2', label: 'Calculation' },
  unit_conversion: { n: '3', label: 'Conversion' },
  emission_factor: { n: '4', label: 'Factor' },
  activity_data: { n: '5', label: 'Activity' },
  evidence: { n: '6', label: 'Evidence' },
  approval: { n: '7', label: 'Approval' },
}

const CONFIDENCE: Record<Confidence, { cls: string; label: string }> = {
  high: { cls: 'bg-emerald-50 text-emerald-800 ring-emerald-600/30', label: 'High confidence' },
  medium: { cls: 'bg-amber-50 text-amber-900 ring-amber-600/30', label: 'Medium confidence' },
  low: { cls: 'bg-red-50 text-red-800 ring-red-600/30', label: 'Low confidence' },
}

function StepRow({ step, last }: { step: LineageStep; last: boolean }) {
  const meta = STEP_META[step.step]
  // A missing document is a real finding, not a blank row - it gets flagged, not hidden.
  const isGap = step.step === 'evidence' && !step.url
  const isPending = step.step === 'approval' && step.label !== 'Approved'

  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      {!last && (
        <span aria-hidden className="absolute left-[15px] top-8 h-full w-px bg-slate-200" />
      )}
      <span
        aria-hidden
        className={`relative z-10 mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full
          text-[11px] font-semibold ring-1 ${
            isGap || isPending
              ? 'bg-amber-50 text-amber-900 ring-amber-600/40'
              : 'bg-white text-slate-600 ring-slate-300'
          }`}
      >
        {meta?.n ?? '·'}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            {meta?.label ?? step.step}
          </span>
          <span className="text-sm font-medium text-slate-900">{step.label}</span>
          {(isGap || isPending) && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-900">
              {isGap ? 'gap' : 'unsigned'}
            </span>
          )}
        </div>

        <p className="num mt-1 break-words text-[13px] font-medium text-slate-800">
          {step.value}
        </p>
        <p className="mt-0.5 break-words text-xs leading-relaxed text-slate-500">{step.detail}</p>

        {step.url && (
          <a
            href={step.url}
            target="_blank"
            rel="noreferrer"
            className="mt-2 inline-flex items-center gap-1.5 rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-sky-800 transition hover:border-sky-400 hover:bg-sky-50"
          >
            Open source document
            <span aria-hidden>↗</span>
          </a>
        )}
      </div>
    </li>
  )
}

function LineageDrawer({ emissionId, onClose }: { emissionId: number; onClose: () => void }) {
  const { data, isLoading, error } = useLineage(emissionId)

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close audit trail"
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/25"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Emission audit trail"
        className="relative flex h-full w-full max-w-lg flex-col border-l border-slate-300 bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Audit trail
            </p>
            {data ? (
              <>
                <p className="num mt-0.5 text-xl font-semibold text-slate-900">
                  {fmt(data.emission.tco2e)} tCO<sub>2</sub>e
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  Emission #{data.emission.id} · Scope {data.emission.scope} ·{' '}
                  {data.emission.facility} · {data.emission.period}
                </p>
              </>
            ) : (
              <p className="mt-0.5 text-sm text-slate-500">Emission #{emissionId}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          {isLoading && <p className="text-sm text-slate-500">Loading audit trail…</p>}
          {error && (
            <p className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {(error as Error).message}
            </p>
          )}

          {data && (
            <>
              <div className="mb-5 flex flex-wrap gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-[11px] font-medium ring-1 ${
                    CONFIDENCE[data.confidence].cls
                  }`}
                >
                  {CONFIDENCE[data.confidence].label}
                </span>
                <span className="num rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 ring-1 ring-slate-300">
                  Uncertainty ±{fmt(data.uncertainty_pct, 1)}%
                </span>
              </div>

              <ol className="mb-6">
                {data.chain.map((step, i) => (
                  <StepRow
                    key={`${step.step}-${i}`}
                    step={step}
                    last={i === data.chain.length - 1}
                  />
                ))}
              </ol>

              <section className="rounded border border-slate-200 bg-slate-50 p-4">
                <h3 className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Assumptions and stated limitations
                </h3>
                <ul className="mt-2 space-y-1.5">
                  {data.assumptions.map((a) => (
                    <li key={a} className="flex gap-2 text-xs leading-relaxed text-slate-600">
                      <span aria-hidden className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                      <span>{a}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </div>
      </aside>
    </div>
  )
}
