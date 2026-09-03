import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { LineageProvider } from './components/LineagePanel'
import { Shell, type Page } from './components/Shell'
import { Accounting } from './pages/Accounting'
import { Dashboard } from './pages/Dashboard'
import { ActivityEntry } from './pages/ActivityEntry'
import { Factors } from './pages/Factors'
import { Suppliers } from './pages/Suppliers'
import type { Role } from './types'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [role, setRole] = useState<Role>('CSO')
  const [approvedOnly, setApprovedOnly] = useState(false)

  return (
    <QueryClientProvider client={queryClient}>
      <LineageProvider>
        <Shell
          activePage={page}
          approvedOnly={approvedOnly}
          role={role}
          onApprovedOnlyChange={setApprovedOnly}
          onNavigate={setPage}
          onRoleChange={setRole}
        >
          {page === 'dashboard' && <Dashboard approvedOnly={approvedOnly} role={role} />}
          {page === 'accounting' && <Accounting />}
          {page === 'entry' && <ActivityEntry />}
          {page === 'factors' && <Factors />}
          {page === 'suppliers' && <Suppliers />}
        </Shell>
      </LineageProvider>
    </QueryClientProvider>
  )
}
