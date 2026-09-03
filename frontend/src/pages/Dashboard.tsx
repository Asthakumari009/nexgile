import type { ReactNode } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Drill } from '../components/LineagePanel'
import { fmt, shortMonth, signed, titleCase, useAnomalies, useDataQuality, useForecast, useHotspots, useScope2, useSummary, useTotals } from '../api'
import type { Role, SummaryRow } from '../types'

const SCOPE_COLOURS = ['#2a78d6', '#eb6834', '#1baf7a']
const chartTooltip = { contentStyle: { borderRadius: 4, borderColor: '#cbd5e1', fontSize: 12 } }

function Card({ title, value, detail, emissionId }: { title: string; value: string; detail: string; emissionId?: number | null }) {
  return <section className="border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-medium text-slate-500">{title}</p><Drill emissionId={emissionId} className="mt-2 inline-block text-2xl font-semibold tracking-tight text-slate-900">{value}</Drill><p className="mt-2 text-xs leading-relaxed text-slate-500">{detail}</p></section>
}

function ChartFrame({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return <section className="border border-slate-200 bg-white p-4 shadow-sm sm:p-5"><div className="mb-4 flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-sm font-semibold text-slate-900">{title}</h2>{note && <p className="text-xs text-slate-500">{note}</p>}</div>{children}</section>
}

export function Dashboard({ approvedOnly, role }: { approvedOnly: boolean; role: Role }) {
  const totals = useTotals(approvedOnly)
  const scope = useSummary('scope', approvedOnly)
  const marketScope = useSummary('scope', approvedOnly, 'market_based')
  const months = useSummary('month', approvedOnly)
  const hotspots = useHotspots(approvedOnly, 8)
  const anomalies = useAnomalies(approvedOnly, 5)
  const forecast = useForecast(approvedOnly)
  const quality = useDataQuality()
  const scope2 = useScope2(approvedOnly)
  const scopeRows = scope.data ?? []
  const leadEmission = scopeRows[0]?.emission_id
  const trendData = (months.data ?? []).map((row) => {
    const trend = forecast.data?.trend.find((point) => point.month === row.group)
    const pathway = forecast.data?.pathway.find((point) => point.month === row.group)
    return { month: shortMonth(row.group), actual: row.tco2e, trend: trend?.tco2e, pathway: pathway?.target_tco2e }
  })
  const latestScope = new Map(scopeRows.map((row) => [row.group, row]))
  const marketScopeRows = new Map((marketScope.data ?? []).map((row) => [row.group, row]))
  const loadError = totals.error || scope.error || months.error

  if (loadError) return <p className="border border-red-200 bg-red-50 p-4 text-sm text-red-800">Could not load the reporting inventory: {(loadError as Error).message}</p>

  return <div className="space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-medium text-sky-800">Enterprise inventory</p><h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Carbon performance overview</h1><p className="mt-1 text-sm text-slate-500">Jan 2024 to Dec 2025 · {approvedOnly ? 'Approved calculations only' : 'All current calculations'}</p></div>{role === 'Auditor' && <p className="border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900">Select any underlined number to inspect its recorded audit trail.</p>}</div>

    {totals.isLoading ? <DashboardSkeleton /> : totals.data && <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Card title="Gross inventory" value={`${fmt(totals.data.gross_tco2e)} tCO₂e`} emissionId={leadEmission} detail={`${totals.data.record_count.toLocaleString()} reported emissions · ${totals.data.consolidation.replace(/_/g, ' ')}`} />
      <Card title={`${totals.data.latest_year} versus prior year`} value={`${signed(totals.data.yoy_change_pct)}%`} emissionId={leadEmission} detail={`${fmt(totals.data.latest_year_tco2e)} tCO₂e in the latest reporting year`} />
      <Card title={`Target trajectory to ${totals.data.target_year}`} value={`${signed(totals.data.vs_target_pct)}%`} emissionId={leadEmission} detail={`${totals.data.target_reduction_pct}% reduction target; ${totals.data.baseline_is_proxy ? `${totals.data.baseline_year} is a reporting proxy` : 'baseline reported'}`} />
      <Card title="Primary-source coverage" value={`${fmt(totals.data.primary_data_pct)}%`} emissionId={leadEmission} detail={`${fmt(totals.data.approved_pct)}% of calculations approved`} />
    </div>}

    <div className="grid gap-5 xl:grid-cols-5"><div className="xl:col-span-2"><ChartFrame title="Inventory by scope" note="Location-based Scope 2"><div className="h-64"><ResponsiveContainer><PieChart><Pie data={scopeRows} dataKey="tco2e" nameKey="group" innerRadius={58} outerRadius={92} paddingAngle={2}>{scopeRows.map((row, index) => <Cell key={row.group} fill={SCOPE_COLOURS[index]} />)}</Pie><Tooltip {...chartTooltip} formatter={(value) => `${fmt(Number(value))} tCO₂e`} /><Legend verticalAlign="bottom" formatter={(value) => <span className="text-xs text-slate-600">{value}</span>} /></PieChart></ResponsiveContainer></div><ScopeTable rows={scopeRows} /></ChartFrame></div>
      <div className="xl:col-span-3"><ChartFrame title="Monthly inventory and target pathway" note={forecast.data?.on_track ? 'On trajectory' : 'Projected above target'}><div className="h-72"><ResponsiveContainer><LineChart data={trendData} margin={{ left: 4, right: 8 }}><XAxis dataKey="month" tick={{ fontSize: 11, fill: '#64748b' }} interval={3} axisLine={{ stroke: '#cbd5e1' }} tickLine={false} /><YAxis tick={{ fontSize: 11, fill: '#64748b' }} width={58} tickFormatter={(value) => `${Math.round(value / 1000)}k`} axisLine={false} tickLine={false} /><Tooltip {...chartTooltip} formatter={(value) => `${fmt(Number(value))} tCO₂e`} /><Legend formatter={(value) => <span className="text-xs text-slate-600">{titleCase(value)}</span>} /><Line type="monotone" dataKey="actual" name="reported" stroke="#1e3a5f" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="trend" name="trend" stroke="#64748b" strokeWidth={1.5} strokeDasharray="4 4" dot={false} /><Line type="monotone" dataKey="pathway" name="target pathway" stroke="#0c8f64" strokeWidth={1.5} dot={false} /></LineChart></ResponsiveContainer></div></ChartFrame></div></div>

    <div className="grid gap-5 xl:grid-cols-5"><div className="xl:col-span-3"><ChartFrame title="Emission hotspots" note={hotspots.data ? `${hotspots.data.hotspots_to_80pct} sources account for 80%` : undefined}><div className="h-72"><ResponsiveContainer><BarChart data={hotspots.data?.rows ?? []} layout="vertical" margin={{ left: 20, right: 10 }}><XAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} tickFormatter={(value) => `${Math.round(value / 1000)}k`} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="activity_type" width={115} tick={{ fontSize: 11, fill: '#475569' }} axisLine={false} tickLine={false} /><Tooltip {...chartTooltip} formatter={(value) => `${fmt(Number(value))} tCO₂e`} labelFormatter={(_, rows) => rows[0]?.payload?.facility ?? ''} /><Bar dataKey="tco2e" fill="#2a78d6" radius={[0, 2, 2, 0]} /></BarChart></ResponsiveContainer></div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">{(hotspots.data?.rows ?? []).slice(0, 4).map((item) => <Drill key={`${item.facility}-${item.activity_type}`} emissionId={item.emission_id}>{item.facility}: {fmt(item.tco2e)} tCO₂e</Drill>)}</div></ChartFrame></div>
      <div className="xl:col-span-2"><ChartFrame title="Scope 2 dual reporting" note="Current inventory"><div className="grid grid-cols-2 gap-3"><Drill emissionId={latestScope.get('Scope 2')?.emission_id} className="border border-slate-200 p-3 text-left"><p className="text-xs text-slate-500">Location-based</p><p className="num mt-1 text-lg font-semibold">{fmt(scope2.data?.location_based_tco2e)} <span className="text-xs font-medium">tCO₂e</span></p></Drill><Drill emissionId={marketScopeRows.get('Scope 2')?.emission_id} className="border border-slate-200 p-3 text-left"><p className="text-xs text-slate-500">Market-based</p><p className="num mt-1 text-lg font-semibold">{fmt(scope2.data?.market_based_tco2e)} <span className="text-xs font-medium">tCO₂e</span></p></Drill></div><p className="mt-3 text-xs leading-relaxed text-slate-500">{scope2.data?.note}</p><p className="num mt-3 border-t border-slate-100 pt-3 text-sm font-medium text-emerald-800">Contractual-instrument benefit: {fmt(scope2.data?.instrument_benefit_tco2e)} tCO₂e</p></ChartFrame></div></div>

    <div className="grid gap-5 xl:grid-cols-2"><ChartFrame title="Exceptions requiring review" note={`${anomalies.data?.count ?? 0} detected`}><div className="divide-y divide-slate-100">{(anomalies.data?.rows ?? []).map((item) => <div key={item.emission_id} className="flex items-center justify-between gap-3 py-3 first:pt-0"><div className="min-w-0"><p className="truncate text-sm font-medium text-slate-800">{item.facility} · {item.activity_type}</p><p className="mt-0.5 text-xs text-slate-500">{item.period_month} · {item.direction} · z-score {fmt(item.z_score, 2)}</p></div><Drill emissionId={item.emission_id} className="shrink-0 text-right text-sm font-semibold text-red-800">{fmt(item.tco2e)} tCO₂e</Drill></div>)}{!anomalies.isLoading && !anomalies.data?.rows.length && <p className="py-4 text-sm text-slate-500">No material anomalies found.</p>}</div></ChartFrame>
      <ChartFrame title="Data-quality gaps" note={`${fmt(quality.data?.overall_completeness_pct)}% complete`}><div className="divide-y divide-slate-100">{[...(quality.data?.gaps ?? []), ...(quality.data?.unreported_series ?? [])].slice(0, 5).map((gap) => <div key={`${gap.facility}-${gap.activity_type}`} className="flex items-center justify-between gap-3 py-3 first:pt-0"><div><p className="text-sm font-medium text-slate-800">{gap.facility} · {gap.activity_type}</p><p className="mt-0.5 text-xs text-slate-500">{gap.scope ? `Scope ${gap.scope}` : 'Not reported'} · {gap.missing_count} missing month{gap.missing_count === 1 ? '' : 's'}</p></div><span className="rounded bg-amber-50 px-2 py-1 text-xs font-medium text-amber-900 ring-1 ring-amber-200">Gap</span></div>)}{!quality.isLoading && !quality.data?.gaps.length && <p className="py-4 text-sm text-slate-500">No coverage gaps reported.</p>}</div></ChartFrame></div>
  </div>
}

function ScopeTable({ rows }: { rows: SummaryRow[] }) {
  return <div className="grid grid-cols-3 gap-2 border-t border-slate-100 pt-3">{rows.map((row, index) => <Drill key={row.group} emissionId={row.emission_id} className="text-left"><span className="flex items-center gap-1.5 text-xs text-slate-500"><span className="h-2 w-2 rounded-full" style={{ backgroundColor: SCOPE_COLOURS[index] }} />{row.group}</span><span className="num mt-1 block text-sm font-semibold text-slate-800">{fmt(row.tco2e)}</span><span className="text-xs text-slate-500">{fmt(row.share_pct)}%</span></Drill>)}</div>
}

function DashboardSkeleton() {
  return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((item) => <div key={item} className="h-32 animate-pulse border border-slate-200 bg-white" />)}</div>
}
