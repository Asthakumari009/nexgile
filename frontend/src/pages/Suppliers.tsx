import { useMemo, useState } from 'react'

import { fmt, signed, useSuppliers } from '../api'
import type { Supplier } from '../types'

const STATUS: Record<Supplier['engagement_status'], string> = {
  not_invited: 'bg-slate-100 text-slate-700',
  invited: 'bg-sky-50 text-sky-800',
  in_progress: 'bg-amber-50 text-amber-900',
  submitted: 'bg-indigo-50 text-indigo-800',
  validated: 'bg-emerald-50 text-emerald-800',
}

export function Suppliers() {
  const suppliers = useSuppliers()
  const [query, setQuery] = useState('')
  const rows = useMemo(() => (suppliers.data ?? []).filter((supplier) => `${supplier.name} ${supplier.category} ${supplier.country}`.toLowerCase().includes(query.toLowerCase())), [query, suppliers.data])
  const totalScope3 = (suppliers.data ?? []).reduce((total, supplier) => total + supplier.scope3_tco2e, 0)
  const validated = (suppliers.data ?? []).filter((supplier) => supplier.engagement_status === 'validated').length
  const submitted = (suppliers.data ?? []).filter((supplier) => supplier.engagement_status === 'submitted').length

  return <div className="space-y-5">
    <div><p className="text-xs font-medium text-sky-800">Supplier engagement</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">Supply-chain reporting</h1><p className="mt-1 text-sm text-slate-500">Supplier-reported emissions and engagement are managed separately from approved corporate actuals.</p></div>
    <div className="grid gap-3 sm:grid-cols-3"><Metric label="Supplier Scope 3 exposure" value={`${fmt(totalScope3)} tCO₂e`} /><Metric label="Validated submissions" value={`${validated} of ${(suppliers.data ?? []).length}`} /><Metric label="Awaiting review" value={String(submitted)} /></div>
    <section className="overflow-hidden border border-slate-200 bg-white shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4"><div><h2 className="text-sm font-semibold">Supplier directory</h2><p className="mt-1 text-xs text-slate-500">Ranked by modelled Scope 3 exposure; supplier submissions remain pending until validated.</p></div><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search supplier or category" className="w-full max-w-xs rounded border border-slate-300 px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-sky-600 focus:ring-2 focus:ring-sky-100" /></div><div className="overflow-x-auto"><table className="min-w-[900px] w-full text-left text-sm"><thead className="bg-slate-50 text-xs font-medium text-slate-500"><tr><th className="px-4 py-3">Supplier</th><th className="px-4 py-3">Engagement</th><th className="px-4 py-3 text-right">Score</th><th className="px-4 py-3 text-right">Scope 3 exposure</th><th className="px-4 py-3 text-right">YoY change</th><th className="px-4 py-3 text-right">Carbon intensity</th></tr></thead><tbody className="divide-y divide-slate-100">{rows.map((supplier) => <tr key={supplier.id} className="hover:bg-slate-50"><td className="px-4 py-3"><p className="font-medium text-slate-800">{supplier.name}</p><p className="mt-0.5 text-xs text-slate-500">{supplier.category} · Tier {supplier.tier} · {supplier.country}</p></td><td className="px-4 py-3"><span className={`rounded px-2 py-1 text-xs font-medium ${STATUS[supplier.engagement_status]}`}>{supplier.engagement_status.replace(/_/g, ' ')}</span><p className="mt-1.5 text-xs text-slate-500">{supplier.maturity} maturity</p></td><td className="num px-4 py-3 text-right font-medium">{fmt(supplier.score, 0)}</td><td className="num px-4 py-3 text-right font-medium">{fmt(supplier.scope3_tco2e)}</td><td className="num px-4 py-3 text-right"><span className={supplier.yoy_change_pct <= 0 ? 'text-emerald-800' : 'text-red-800'}>{signed(supplier.yoy_change_pct)}%</span></td><td className="num px-4 py-3 text-right">{fmt(supplier.carbon_intensity, 3)}</td></tr>)}</tbody></table></div>{suppliers.isLoading && <p className="p-4 text-sm text-slate-500">Loading suppliers…</p>}{!suppliers.isLoading && !rows.length && <p className="p-6 text-sm text-slate-500">No suppliers match this search.</p>}</section>
  </div>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <section className="border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-medium text-slate-500">{label}</p><p className="num mt-2 text-xl font-semibold text-slate-900">{value}</p></section>
}
