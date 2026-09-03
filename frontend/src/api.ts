// One fetch helper plus typed query hooks. TanStack Query is already a dependency, so
// caching, loading and error state come for free - no custom data layer.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type {
  Activity,
  ActivityPage,
  Anomaly,
  Basis,
  DataQuality,
  Facets,
  Factor,
  FactorImpact,
  Forecast,
  Hotspots,
  Lineage,
  OrgTree,
  Quality,
  RecalcResult,
  Scope2Dual,
  SummaryRow,
  Supplier,
  Totals,
  ComplianceRow,
  FinanceSummary,
  Product,
  ProductAlternatives,
  ProductBom,
  ProductPcf,
  ScenarioResult,
} from './types'

const BASE = '/api/v1'

async function get<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
  }
  const url = `${BASE}${path}${qs.size ? `?${qs}` : ''}`
  const res = await fetch(url)
  if (!res.ok) {
    // Surface the API's own message - FastAPI puts it in `detail`.
    const body = await res.text()
    let detail = body
    try {
      detail = (JSON.parse(body) as { detail?: string }).detail ?? body
    } catch {
      /* non-JSON error body, keep the raw text */
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

// ------------------------------------------------------------------ read hooks
export const useOrg = () => useQuery({ queryKey: ['org'], queryFn: () => get<OrgTree>('/org/tree') })

export const useTotals = (approvedOnly: boolean) =>
  useQuery({
    queryKey: ['totals', approvedOnly],
    queryFn: () => get<Totals>('/emissions/totals', { approved_only: approvedOnly }),
  })

export const useSummary = (groupBy: string, approvedOnly: boolean, basis: Basis = 'location_based') =>
  useQuery({
    queryKey: ['summary', groupBy, approvedOnly, basis],
    queryFn: () =>
      get<{ rows: SummaryRow[] }>('/emissions/summary', {
        group_by: groupBy,
        approved_only: approvedOnly,
        basis,
      }).then((r) => r.rows),
  })

export const useScope2 = (approvedOnly: boolean) =>
  useQuery({
    queryKey: ['scope2', approvedOnly],
    queryFn: () => get<Scope2Dual>('/emissions/scope2', { approved_only: approvedOnly }),
  })

export const useHotspots = (approvedOnly: boolean, limit = 10) =>
  useQuery({
    queryKey: ['hotspots', approvedOnly, limit],
    queryFn: () => get<Hotspots>('/analytics/hotspots', { approved_only: approvedOnly, limit }),
  })

export const useAnomalies = (approvedOnly: boolean, limit = 5) =>
  useQuery({
    queryKey: ['anomalies', approvedOnly, limit],
    queryFn: () =>
      get<{ rows: Anomaly[]; count: number }>('/analytics/anomalies', {
        approved_only: approvedOnly,
        limit,
      }),
  })

export const useForecast = (approvedOnly: boolean) =>
  useQuery({
    queryKey: ['forecast', approvedOnly],
    queryFn: () => get<Forecast>('/analytics/forecast', { approved_only: approvedOnly }),
  })

export const useDataQuality = () =>
  useQuery({ queryKey: ['data-quality'], queryFn: () => get<DataQuality>('/analytics/data-quality') })

export const useFacets = () =>
  useQuery({ queryKey: ['facets'], queryFn: () => get<Facets>('/activities/facets') })

export interface ActivityFilters {
  scope?: number | ''
  facility_id?: number | ''
  period?: string
  quality?: Quality | ''
  activity_type?: string
  q?: string
  offset?: number
  limit?: number
}

export const useActivities = (filters: ActivityFilters) =>
  useQuery({
    queryKey: ['activities', filters],
    queryFn: () => get<ActivityPage>('/activities', filters as Record<string, unknown>),
  })

export const useActivity = (id: number | null) =>
  useQuery({
    queryKey: ['activity', id],
    queryFn: () => get<Activity>(`/activities/${id}`),
    enabled: id !== null,
  })

export const useLineage = (emissionId: number | null) =>
  useQuery({
    queryKey: ['lineage', emissionId],
    queryFn: () => get<Lineage>(`/emissions/${emissionId}/lineage`),
    enabled: emissionId !== null,
  })

export const useFactors = () =>
  useQuery({
    queryKey: ['factors'],
    queryFn: () => get<{ rows: Factor[] }>('/factors').then((r) => r.rows),
  })

export const useSuppliers = () =>
  useQuery({
    queryKey: ['suppliers'],
    queryFn: () => get<{ rows: Supplier[] }>('/suppliers').then((r) => r.rows),
  })

export const useProducts = () =>
  useQuery({ queryKey: ['products'], queryFn: () => get<{ rows: Product[] }>('/products').then((r) => r.rows) })

export const useProductBom = (productId: number | null) =>
  useQuery({ queryKey: ['product-bom', productId], queryFn: () => get<ProductBom>(`/products/${productId}/bom`), enabled: productId !== null })

export const useProductPcf = (productId: number | null) =>
  useQuery({ queryKey: ['product-pcf', productId], queryFn: () => get<ProductPcf>(`/products/${productId}/pcf`), enabled: productId !== null })

export const useProductAlternatives = (productId: number | null) =>
  useQuery({ queryKey: ['product-alternatives', productId], queryFn: () => get<ProductAlternatives>(`/products/${productId}/alternatives`), enabled: productId !== null })

export const useCompliance = () =>
  useQuery({ queryKey: ['compliance'], queryFn: () => get<{ rows: ComplianceRow[] }>('/compliance/readiness').then((r) => r.rows) })

export const useFinance = (carbonPrice: number) =>
  useQuery({ queryKey: ['finance', carbonPrice], queryFn: () => get<FinanceSummary>('/finance/summary', { carbon_price: carbonPrice }) })

export const useFactorVersions = (factorId: number | null) =>
  useQuery({
    queryKey: ['factor-versions', factorId],
    queryFn: () => get<{ versions: Factor[] }>(`/factors/${factorId}/versions`),
    enabled: factorId !== null,
  })

export const useFactorImpact = (factorId: number | null) =>
  useQuery({
    queryKey: ['factor-impact', factorId],
    queryFn: () => get<FactorImpact>(`/factors/${factorId}/impact`),
    enabled: factorId !== null,
  })

// ----------------------------------------------------------------- mutations
/** Anything that changes emissions invalidates every derived read. */
function useEmissionMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries(),
  })
}

export const useApprove = () =>
  useEmissionMutation(({ calcId, actor }: { calcId: number; actor: string }) =>
    post<{ id: number; status: string }>(`/calculations/${calcId}/approve?actor=${encodeURIComponent(actor)}`)
  )

export const useRevise = () =>
  useEmissionMutation(
    (args: { factorId: number; value_kgco2e: number; source: string; note?: string }) =>
      post<{ calculations_affected: number; delta_pct: number; published: Factor }>(
        `/factors/${args.factorId}/revise`,
        { value_kgco2e: args.value_kgco2e, source: args.source, note: args.note }
      )
  )

export const useRecalculate = () =>
  useEmissionMutation(({ factorId, actor }: { factorId: number; actor: string }) =>
    post<RecalcResult>('/calculations/recalculate', { factor_id: factorId, actor })
  )

export const useScenario = () =>
  useMutation({ mutationFn: (args: { renewable_electricity_pct: number; recycled_material_pct: number; freight_mode_shift_pct: number; supplier_switch_pct: number }) => post<ScenarioResult>('/scenarios', args) })

// ------------------------------------------------------------------- format
export const fmt = (n: number | null | undefined, digits = 1) =>
  n === null || n === undefined
    ? '—'
    : n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const fmtInt = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : Math.round(n).toLocaleString('en-US')

export const signed = (n: number | null | undefined, digits = 1) =>
  n === null || n === undefined ? '—' : `${n > 0 ? '+' : ''}${fmt(n, digits)}`

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** '2025-07' -> 'Jul 25'. Axis labels have to stay short. */
export const shortMonth = (ym: string) => {
  const [y, m] = ym.split('-')
  return `${MONTHS[Number(m) - 1]} ${y.slice(2)}`
}

export const titleCase = (s: string) =>
  s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
