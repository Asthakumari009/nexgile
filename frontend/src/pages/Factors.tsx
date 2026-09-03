import { useState } from 'react'

import { fmt, signed, useFactorImpact, useFactors } from '../api'
import type { Factor, FactorImpact } from '../types'

export function Factors() {
  const factors = useFactors()
  const [selected, setSelected] = useState<Factor | null>(null)
  const impact = useFactorImpact(selected?.id ?? null)

  return <div className="space-y-5">
    <div><p className="text-xs font-medium text-sky-800">Controlled methodology library</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">Emission factors</h1><p className="mt-1 text-sm text-slate-500">Factors are versioned, never edited. Preview the impact before initiating a recalculation.</p></div>
    <div className="grid gap-5 xl:grid-cols-[1fr_360px]"><section className="overflow-hidden border border-slate-200 bg-white shadow-sm"><div className="overflow-x-auto"><table className="min-w-[760px] w-full text-left text-sm"><thead className="bg-slate-50 text-xs font-medium text-slate-500"><tr><th className="px-4 py-3">Factor</th><th className="px-4 py-3">Scope</th><th className="px-4 py-3">Value</th><th className="px-4 py-3">Source and validity</th><th className="px-4 py-3 text-right">Live use</th></tr></thead><tbody className="divide-y divide-slate-100">{factors.data?.map((factor) => <tr key={factor.id} onClick={() => setSelected(factor)} className={`cursor-pointer align-top transition hover:bg-slate-50 ${selected?.id === factor.id ? 'bg-sky-50/60' : ''}`}><td className="px-4 py-3"><p className="font-medium text-slate-800">{factor.code} <span className="font-normal text-slate-500">{factor.version}</span></p><p className="mt-0.5 text-xs text-slate-500">{factor.name}</p></td><td className="px-4 py-3">Scope {factor.scope}</td><td className="num px-4 py-3">{fmt(factor.value_kgco2e, 4)}<span className="ml-1 text-xs text-slate-500">kgCO₂e/{factor.unit}</span></td><td className="px-4 py-3"><p>{factor.source}</p><p className="mt-0.5 text-xs text-slate-500">{factor.valid_from} to {factor.valid_to}</p></td><td className="num px-4 py-3 text-right font-medium">{factor.calculations_using}</td></tr>)}</tbody></table></div>{factors.isLoading && <p className="p-4 text-sm text-slate-500">Loading factor library…</p>}</section><ImpactPanel factor={selected} impact={impact.data} isLoading={impact.isLoading} error={impact.error} /></div>
  </div>
}

function ImpactPanel({ factor, impact, isLoading, error }: { factor: Factor | null; impact: FactorImpact | undefined; isLoading: boolean; error: Error | null }) {
  if (!factor) return <aside className="border border-dashed border-slate-300 bg-white p-5 text-sm leading-relaxed text-slate-500">Select a factor to see its version family and the read-only impact preview for calculations currently pinned to it.</aside>
  if (error) return <aside className="border border-red-200 bg-red-50 p-5 text-sm text-red-800">{error.message}</aside>
  return <aside className="border border-slate-200 bg-white p-5 shadow-sm"><p className="text-xs font-medium text-sky-800">Version impact</p><h2 className="mt-1 text-base font-semibold">{factor.code} {factor.version}</h2>{isLoading ? <p className="mt-5 text-sm text-slate-500">Resolving currently valid replacements…</p> : impact ? <><div className="mt-5 grid grid-cols-2 gap-3"><Metric label="Affected calculations" value={String(impact.calculations_affected)} /><Metric label="Projected delta" value={`${signed(impact.delta_pct, 2)}%`} /></div><div className="mt-3 border-y border-slate-100 py-3 text-sm"><div className="flex justify-between gap-3"><span className="text-slate-500">Current</span><span className="num font-medium">{fmt(impact.current_tco2e)} tCO₂e</span></div><div className="mt-2 flex justify-between gap-3"><span className="text-slate-500">If recalculated</span><span className="num font-medium">{fmt(impact.projected_tco2e)} tCO₂e</span></div><div className="mt-2 flex justify-between gap-3"><span className="text-slate-500">Change</span><span className="num font-semibold text-sky-900">{signed(impact.delta_tco2e)} tCO₂e</span></div></div><p className="mt-4 text-xs leading-relaxed text-slate-500">This preview is read-only. A recalculation creates new calculation versions and retains the superseded calculations unchanged for auditability.</p>{impact.unresolved.length > 0 && <p className="mt-3 rounded bg-amber-50 p-3 text-xs text-amber-900">{impact.unresolved.length} calculation{impact.unresolved.length === 1 ? '' : 's'} cannot be resolved to a replacement factor.</p>}</> : null}</aside>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="border border-slate-200 p-3"><p className="text-xs text-slate-500">{label}</p><p className="num mt-1 text-lg font-semibold text-slate-900">{value}</p></div>
}
