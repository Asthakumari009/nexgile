import type { ReactNode } from 'react'

import type { Role } from '../types'

export type Page = 'dashboard' | 'accounting' | 'entry' | 'factors' | 'setup' | 'suppliers'

const NAV: { id: Page; label: string; roles: Role[] }[] = [
  { id: 'dashboard', label: 'Overview', roles: ['CSO', 'Procurement', 'CFO', 'Auditor'] },
  { id: 'setup', label: 'Company setup', roles: ['CSO'] },
  { id: 'accounting', label: 'Carbon accounting', roles: ['CSO', 'Auditor'] },
  { id: 'entry', label: 'Enter activity', roles: ['CSO'] },
  { id: 'factors', label: 'Emission factors', roles: ['CSO', 'Auditor'] },
  { id: 'suppliers', label: 'Suppliers', roles: ['CSO', 'Procurement', 'Auditor'] },
]

export function Shell({
  activePage,
  approvedOnly,
  children,
  role,
  onApprovedOnlyChange,
  onNavigate,
  onRoleChange,
}: {
  activePage: Page
  approvedOnly: boolean
  children: ReactNode
  role: Role
  onApprovedOnlyChange: (value: boolean) => void
  onNavigate: (page: Page) => void
  onRoleChange: (role: Role) => void
}) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 border-r border-slate-200 bg-white lg:flex lg:flex-col">
        <div className="border-b border-slate-200 px-6 py-5">
          <p className="text-xs font-semibold tracking-wide text-sky-800">NEXGILE</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">DecarbX</p>
          <p className="mt-1 text-xs text-slate-500">Carbon intelligence</p>
        </div>
        <nav className="flex-1 px-3 py-4" aria-label="Primary navigation">
          {NAV.filter((item) => item.roles.includes(role)).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={`mb-1 flex w-full items-center rounded px-3 py-2.5 text-left text-sm font-medium transition ${
                activePage === item.id
                  ? 'bg-sky-50 text-sky-900 ring-1 ring-inset ring-sky-100'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="border-t border-slate-200 px-6 py-4 text-xs leading-relaxed text-slate-500">
          Inventory basis<br />
          <span className="font-medium text-slate-700">Equity share</span>
        </div>
      </aside>

      <div className="lg:pl-60">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur sm:px-6">
          <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3">
            <div className="lg:hidden"><p className="text-xs font-semibold tracking-wide text-sky-800">NEXGILE DECARBX</p></div>
            <div className="ml-auto flex flex-wrap items-center justify-end gap-2 sm:gap-3">
              <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
                <span>Role</span>
                <select value={role} onChange={(event) => onRoleChange(event.target.value as Role)} className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800 outline-none focus:border-sky-600 focus:ring-2 focus:ring-sky-100">
                  <option>CSO</option><option>Procurement</option><option>CFO</option><option>Auditor</option>
                </select>
              </label>
              <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600">
                <input type="checkbox" checked={approvedOnly} onChange={(event) => onApprovedOnlyChange(event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-sky-700 focus:ring-sky-600" />
                Approved only
              </label>
            </div>
          </div>
        </header>
        <nav className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-4 py-2 lg:hidden" aria-label="Primary navigation">
          {NAV.filter((item) => item.roles.includes(role)).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={`shrink-0 rounded px-3 py-1.5 text-sm font-medium ${activePage === item.id ? 'bg-sky-50 text-sky-900' : 'text-slate-600'}`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  )
}
