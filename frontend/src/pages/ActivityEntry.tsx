import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useOrg } from '../api'

const TYPES = {
  electricity: { label: 'Electricity consumption', scope: 2, activity_type: 'purchased_electricity', description: 'Purchased electricity', unit: 'kWh' },
  diesel: { label: 'Diesel consumption', scope: 1, activity_type: 'mobile_combustion', description: 'Diesel consumption', unit: 'litre' },
  gas: { label: 'Natural gas consumption', scope: 1, activity_type: 'stationary_combustion', description: 'Natural gas consumption', unit: 'm3' },
} as const

export function ActivityEntry() {
  const org = useOrg(); const cache = useQueryClient()
  const facilities = org.data?.entities.flatMap((entity) => entity.facilities) ?? []
  const [facilityId, setFacilityId] = useState(''); const [type, setType] = useState<keyof typeof TYPES>('electricity')
  const [quantity, setQuantity] = useState(''); const [period, setPeriod] = useState('2025-12'); const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState(''); const [saving, setSaving] = useState(false)
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setMessage('')
    try {
      let evidence_id: number | null = null
      if (file) { const body = new FormData(); body.append('file', file); const uploaded = await fetch('/api/v1/activities/evidence', { method: 'POST', body }); if (!uploaded.ok) throw new Error('Invoice upload failed'); evidence_id = (await uploaded.json()).id }
      const selected = TYPES[type]; const response = await fetch('/api/v1/activities', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ facility_id: Number(facilityId), scope: selected.scope, activity_type: selected.activity_type, description: selected.description, quantity: Number(quantity), unit: selected.unit, period_start: `${period}-01`, period_end: `${period}-28`, evidence_id, data_source: 'invoice', data_quality: 'primary' }) })
      if (!response.ok) { const body = await response.json(); throw new Error(body.detail ?? 'Calculation failed') }
      const result = await response.json(); await cache.invalidateQueries(); setMessage(`Recorded and calculated. Emission ID ${result.emission_ids[0]} is now available in the dashboard lineage.`); setQuantity(''); setFile(null)
    } catch (error) { setMessage((error as Error).message) } finally { setSaving(false) }
  }
  return <div className="max-w-2xl space-y-5"><div><p className="text-xs font-medium text-sky-800">Factory manager workflow</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">Enter activity data</h1><p className="mt-1 text-sm text-slate-500">Upload the invoice, then the backend resolves the correct factor and records the calculation for audit.</p></div><form onSubmit={submit} className="space-y-5 border border-slate-200 bg-white p-5 shadow-sm"><label className="grid gap-1 text-sm font-medium">Facility<select required value={facilityId} onChange={(e) => setFacilityId(e.target.value)} className="rounded border border-slate-300 p-2 font-normal"><option value="">Select a facility</option>{facilities.map((facility) => <option key={facility.id} value={facility.id}>{facility.name}</option>)}</select></label><label className="grid gap-1 text-sm font-medium">Activity type<select value={type} onChange={(e) => setType(e.target.value as keyof typeof TYPES)} className="rounded border border-slate-300 p-2 font-normal">{Object.entries(TYPES).map(([key, item]) => <option key={key} value={key}>{item.label} · Scope {item.scope}</option>)}</select></label><div className="grid gap-4 sm:grid-cols-2"><label className="grid gap-1 text-sm font-medium">Quantity<input required min="0.001" step="any" type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="rounded border border-slate-300 p-2 font-normal" /><span className="text-xs font-normal text-slate-500">Unit: {TYPES[type].unit}</span></label><label className="grid gap-1 text-sm font-medium">Reporting month<input required type="month" value={period} onChange={(e) => setPeriod(e.target.value)} className="rounded border border-slate-300 p-2 font-normal" /></label></div><label className="grid gap-1 text-sm font-medium">Supporting invoice (optional)<input type="file" accept=".pdf,.csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm font-normal" /></label><button disabled={saving} className="rounded bg-sky-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{saving ? 'Calculating…' : 'Record and calculate'}</button>{message && <p className="rounded bg-slate-50 p-3 text-sm text-slate-700">{message}</p>}</form></div>
}
