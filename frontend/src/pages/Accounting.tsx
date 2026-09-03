import type { ReactNode } from 'react'
import { useMemo, useState } from 'react'

import { QualityBadge } from '../components/Badge'
import { Drill } from '../components/LineagePanel'
import { fmt, titleCase, useActivities, useFacets } from '../api'
import type { ActivityFilters } from '../api'
import type { Quality } from '../types'

const initialFilters: ActivityFilters = { limit: 50 }

export function Accounting() {
  const [filters, setFilters] = useState<ActivityFilters>(initialFilters)
  const facets = useFacets()
  const activities = useActivities(filters)
  const activeFilters = useMemo(() => Object.values(filters).filter((value) => value !== '' && value !== undefined && value !== 50).length, [filters])
  const update = <K extends keyof ActivityFilters>(key: K, value: ActivityFilters[K]) => setFilters((current) => ({ ...current, [key]: value }))

  return <div className="space-y-5">
    <div><p className="text-xs font-medium text-sky-800">Source activity data</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">Carbon accounting</h1><p className="mt-1 text-sm text-slate-500">Filter source records and open a result to trace its calculation, factor version, evidence, and approval.</p></div>
    <section className="border border-slate-200 bg-white p-4 shadow-sm"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <Filter label="Scope"><select value={filters.scope ?? ''} onChange={(event) => update('scope', event.target.value ? Number(event.target.value) : '')}><option value="">All scopes</option>{facets.data?.scopes.map((scope) => <option key={scope} value={scope}>Scope {scope}</option>)}</select></Filter>
      <Filter label="Facility"><select value={filters.facility_id ?? ''} onChange={(event) => update('facility_id', event.target.value ? Number(event.target.value) : '')}><option value="">All facilities</option>{facets.data?.facilities.map((facility) => <option key={facility.id} value={facility.id}>{facility.name}</option>)}</select></Filter>
      <Filter label="Period"><select value={filters.period ?? ''} onChange={(event) => update('period', event.target.value)}><option value="">All periods</option>{facets.data?.periods.map((period) => <option key={period}>{period}</option>)}</select></Filter>
      <Filter label="Quality"><select value={filters.quality ?? ''} onChange={(event) => update('quality', event.target.value as Quality | '')}><option value="">All quality</option>{facets.data?.qualities.map((quality) => <option key={quality}>{quality}</option>)}</select></Filter>
      <Filter label="Activity type"><select value={filters.activity_type ?? ''} onChange={(event) => update('activity_type', event.target.value)}><option value="">All types</option>{facets.data?.activity_types.map((type) => <option key={type} value={type}>{titleCase(type)}</option>)}</select></Filter>
    </div><div className="mt-3 flex items-center justify-between gap-3"><input value={filters.q ?? ''} onChange={(event) => update('q', event.target.value)} placeholder="Search descriptions" className="w-full max-w-sm rounded border border-slate-300 px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-sky-600 focus:ring-2 focus:ring-sky-100" /><button type="button" onClick={() => setFilters(initialFilters)} className="shrink-0 text-sm font-medium text-sky-800 hover:text-sky-950">Clear {activeFilters ? `(${activeFilters})` : ''}</button></div></section>
    {activities.error && <p className="border border-red-200 bg-red-50 p-4 text-sm text-red-800">{(activities.error as Error).message}</p>}
    <section className="overflow-hidden border border-slate-200 bg-white shadow-sm"><div className="flex items-baseline justify-between border-b border-slate-200 px-4 py-3"><h2 className="text-sm font-semibold">Activity records</h2><p className="text-xs text-slate-500">{activities.data?.total ?? 0} matching records</p></div><div className="overflow-x-auto"><table className="min-w-[900px] w-full text-left text-sm"><thead className="bg-slate-50 text-xs font-medium text-slate-500"><tr><th className="px-4 py-3">Period / facility</th><th className="px-4 py-3">Activity</th><th className="px-4 py-3">Source / quality</th><th className="px-4 py-3">Calculation</th><th className="px-4 py-3 text-right">Reported result</th></tr></thead><tbody className="divide-y divide-slate-100">{activities.data?.rows.map((activity) => { const calculation = activity.calculations[0]; return <tr key={activity.id} className="align-top hover:bg-slate-50"><td className="px-4 py-3"><p className="font-medium text-slate-800">{activity.period_month}</p><p className="mt-0.5 text-xs text-slate-500">{activity.facility} · Scope {activity.scope}</p></td><td className="px-4 py-3"><p className="font-medium text-slate-800">{titleCase(activity.activity_type)}</p><p className="mt-0.5 max-w-xs truncate text-xs text-slate-500">{activity.description}</p><p className="num mt-1 text-xs text-slate-600">{fmt(activity.quantity, 2)} {activity.unit}</p></td><td className="px-4 py-3"><QualityBadge quality={activity.data_quality} /><p className="mt-2 text-xs text-slate-500">{activity.data_source}{activity.evidence_filename ? ` · ${activity.evidence_filename}` : ' · No evidence linked'}</p></td><td className="px-4 py-3"><p className="text-xs font-medium text-slate-700">{calculation?.factor_code} {calculation?.factor_version}</p><p className="mt-1 text-xs text-slate-500">{calculation?.methodology.replace(/_/g, ' ')}</p><p className="mt-1 text-xs text-slate-500">{calculation?.status.replace(/_/g, ' ')}</p></td><td className="px-4 py-3 text-right">{calculation ? <Drill emissionId={calculation.emission_id} className="num text-sm font-semibold text-sky-900">{fmt(calculation.tco2e)} tCO₂e</Drill> : <span className="text-xs text-slate-400">Not calculated</span>}</td></tr> })}</tbody></table></div>{activities.isLoading && <p className="p-4 text-sm text-slate-500">Loading activity records…</p>}{!activities.isLoading && !activities.data?.rows.length && <p className="p-6 text-sm text-slate-500">No activity records match these filters.</p>}</section>
  </div>
}

function Filter({ label, children }: { label: string; children: ReactNode }) {
  return <label className="grid gap-1 text-xs font-medium text-slate-600"><span>{label}</span><span className="[&>select]:w-full [&>select]:rounded [&>select]:border [&>select]:border-slate-300 [&>select]:bg-white [&>select]:px-2 [&>select]:py-2 [&>select]:text-sm [&>select]:text-slate-800 [&>select]:outline-none [&>select]:focus:border-sky-600">{children}</span></label>
}
