import { useEffect, useState } from 'react'

// Phase 0 hello world: proves the Vite -> FastAPI proxy is wired.
// Replaced by the real shell in Phase 3.
export default function App() {
  const [health, setHealth] = useState<string>('checking...')

  useEffect(() => {
    fetch('/api/v1/health')
      .then((r) => r.json())
      .then((d) => setHealth(`${d.app}: ${d.status}`))
      .catch((e) => setHealth(`unreachable (${e.message})`))
  }, [])

  return (
    <div className="min-h-screen grid place-items-center">
      <div className="rounded-lg border border-slate-200 bg-white px-8 py-6 shadow-sm">
        <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
          Nexgile DecarbX
        </p>
        <h1 className="mt-1 text-lg font-semibold">Internal enterprise app</h1>
        <p className="mt-4 text-sm text-slate-600">
          backend <span className="num font-medium text-slate-900">{health}</span>
        </p>
      </div>
    </div>
  )
}
