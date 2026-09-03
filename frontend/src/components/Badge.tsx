import type { Confidence, Quality } from '../types'

const QUALITY: Record<Quality, string> = {
  primary: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20',
  secondary: 'bg-amber-50 text-amber-900 ring-amber-600/20',
  estimated: 'bg-red-50 text-red-800 ring-red-600/20',
}

const CONFIDENCE: Record<Confidence, string> = {
  high: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20',
  medium: 'bg-amber-50 text-amber-900 ring-amber-600/20',
  low: 'bg-red-50 text-red-800 ring-red-600/20',
}

export function QualityBadge({ quality }: { quality: Quality }) {
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ${QUALITY[quality]}`}>{quality}</span>
}

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ${CONFIDENCE[confidence]}`}>{confidence} confidence</span>
}
