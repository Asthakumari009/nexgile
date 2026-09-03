// Shapes returned by the FastAPI backend. Hand-written rather than generated: the
// surface is small and a codegen step is not worth the build time here.

export type Role = 'CSO' | 'Procurement' | 'CFO' | 'Auditor'
export type Quality = 'primary' | 'secondary' | 'estimated'
export type Confidence = 'high' | 'medium' | 'low'
export type Basis = 'location_based' | 'market_based'

export interface OrgTree {
  id: number
  name: string
  base_currency: string
  baseline_year: number
  target_year: number
  target_reduction_pct: number
  consolidation_method: string
  entities: {
    id: number
    name: string
    country: string
    ownership_pct: number
    facilities: {
      id: number
      name: string
      city: string
      country: string
      lat: number
      lon: number
      facility_type: string
      floor_area_m2: number
      departments: { id: number; name: string; cost_center: string }[]
    }[]
  }[]
}

export interface Totals {
  gross_tco2e: number
  by_scope: Record<string, number>
  latest_year: string | null
  latest_year_tco2e: number
  prior_year_tco2e: number
  yoy_change_pct: number | null
  baseline_year: number | null
  baseline_is_proxy: boolean
  baseline_tco2e: number
  target_year: number
  target_reduction_pct: number
  target_tco2e: number
  vs_target_pct: number | null
  primary_data_pct: number
  record_count: number
  approved_pct: number
  consolidation: string
  organization: string
}

export interface SummaryRow {
  group: string
  group_id: number | string | null
  tco2e: number
  share_pct: number
  count: number
  emission_id: number | null
  primary_pct: number
}

export interface Scope2Dual {
  location_based_tco2e: number
  market_based_tco2e: number
  instrument_benefit_tco2e: number
  note: string
}

export interface Hotspots {
  total_tco2e: number
  hotspots_to_80pct: number
  hotspot_count: number
  rows: {
    facility: string
    activity_type: string
    scope: number
    tco2e: number
    share_pct: number
    cumulative_pct: number
    emission_id: number | null
  }[]
}

export interface Anomaly {
  emission_id: number
  activity_id: number
  facility: string
  activity_type: string
  scope: number
  period_month: string
  tco2e: number
  expected_tco2e: number
  deviation_pct: number | null
  z_score: number
  direction: 'spike' | 'dip'
}

export interface Forecast {
  baseline_year: number
  baseline_tco2e: number
  target_year: number
  target_tco2e: number
  target_reduction_pct: number
  monthly_slope_tco2e: number
  actual: { month: string; tco2e: number }[]
  trend: { month: string; tco2e: number }[]
  pathway: { month: string; target_tco2e: number }[]
  projected_target_year_tco2e: number
  gap_tco2e: number
  on_track: boolean
}

export interface DataQuality {
  overall_completeness_pct: number
  reporting_months: number
  by_facility: {
    facility: string
    scope: number
    records: number
    primary_pct: number
    secondary_pct: number
    estimated_pct: number
    missing_months: number
  }[]
  gaps: {
    facility: string
    activity_type: string
    scope: number | null
    missing_months: string[]
    missing_count: number
  }[]
  unreported_series: {
    facility: string
    activity_type: string
    scope: number | null
    missing_months: string[]
    missing_count: number
  }[]
}

export interface CalcSummary {
  id: number
  methodology: string
  calc_version: number
  status: 'draft' | 'pending_approval' | 'approved' | 'superseded'
  formula_text: string
  tco2e: number
  factor_code: string
  factor_version: string
  approved_by: string | null
  emission_id: number | null
}

export interface Activity {
  id: number
  facility: string
  facility_id: number
  scope: number
  ghg_category: number | null
  activity_type: string
  description: string
  quantity: number
  unit: string
  period_start: string
  period_end: string
  period_month: string
  data_source: string
  data_quality: Quality
  evidence_id: number | null
  evidence_filename: string | null
  supplier_id: number | null
  calculations: CalcSummary[]
}

export interface ActivityPage {
  total: number
  offset: number
  limit: number
  rows: Activity[]
}

export interface Facets {
  activity_types: string[]
  periods: string[]
  facilities: { id: number; name: string }[]
  qualities: Quality[]
  scopes: number[]
}

export interface LineageStep {
  step:
    | 'reported_value'
    | 'calculation'
    | 'unit_conversion'
    | 'emission_factor'
    | 'activity_data'
    | 'evidence'
    | 'approval'
  label: string
  value: string
  detail: string
  url?: string | null
}

export interface Lineage {
  emission: { id: number; tco2e: number; period: string; facility: string; scope: number }
  chain: LineageStep[]
  assumptions: string[]
  uncertainty_pct: number
  confidence: Confidence
}

export interface Factor {
  id: number
  code: string
  name: string
  scope: number
  category: string
  unit: string
  value_kgco2e: number
  source: string
  version: string
  valid_from: string
  valid_to: string
  uncertainty_pct: number
  region: string | null
  method: string | null
  is_active: boolean
  calculations_using: number
}

export interface FactorImpact {
  factor: Factor
  calculations_affected: number
  current_tco2e: number
  projected_tco2e: number
  delta_tco2e: number
  delta_pct: number
  replacement_factors: Factor[]
  would_change: boolean
  samples: {
    calculation_id: number
    facility: string
    period_month: string
    from_factor: string
    to_factor: string
    old_tco2e: number
    new_tco2e: number
  }[]
  unresolved: { calculation_id: number; error: string }[]
}

export interface RecalcResult {
  recalculated: number
  before_tco2e: number
  after_tco2e: number
  delta_tco2e: number
  delta_pct: number
  note: string
  changes: {
    old_calculation_id: number
    new_calculation_id: number
    calc_version: number
    facility: string
    period_month: string
    from_factor: string
    to_factor: string
    old_tco2e: number
    new_tco2e: number
  }[]
}

export interface Supplier {
  id: number
  name: string
  country: string
  lat: number
  lon: number
  tier: number
  parent_supplier_id: number | null
  category: string
  annual_spend: number
  currency: string
  engagement_status: 'not_invited' | 'invited' | 'in_progress' | 'submitted' | 'validated'
  maturity: 'low' | 'developing' | 'advanced'
  score: number
  scope3_tco2e: number
  carbon_intensity: number
  yoy_change_pct: number
}
