import { useState } from 'react'

interface FunnelResult {
  definition: string
  excluded_immature_users: number
  steps: { event: string; users: number; conversion_rate: number | null; step_conversion_rate: number | null; drop_off_users: number }[]
}

export function ConversionFunnel() {
  const [steps, setSteps] = useState('app_open, view_product, add_to_cart, purchase')
  const [days, setDays] = useState(7)
  const [result, setResult] = useState<FunnelResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  async function calculate() {
    setLoading(true); setError(''); setResult(null)
    try {
      const response = await fetch('/api/metrics/funnel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ steps: steps.split(',').map(step => step.trim()), window_days: days }) })
      const body = await response.json()
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Enter 2–8 steps and a window of 1–90 days')
      setResult(body)
    } catch (cause) { setError(String(cause)) }
    finally { setLoading(false) }
  }
  return <section className="mt-5 rounded-2xl border border-white/10 bg-panel p-5">
    <h2 className="font-medium">Conversion funnel</h2><p className="mt-2 text-xs text-slate-400">Enter event names in sequence, separated by commas. Includes all available entry dates.</p>
    <div className="mt-4 flex flex-wrap gap-3"><label className="min-w-64 flex-1 text-xs text-slate-500">Ordered events<input value={steps} onChange={e => setSteps(e.target.value)} className="mt-1 block w-full rounded-lg border border-white/10 bg-ink p-3 text-sm text-slate-200"/></label><label className="text-xs text-slate-500">Window (days)<input type="number" min={1} max={90} value={days} onChange={e => setDays(Number(e.target.value))} className="mt-1 block w-24 rounded-lg border border-white/10 bg-ink p-3 text-sm text-slate-200"/></label><button disabled={loading} onClick={() => void calculate()} className="self-end rounded-lg bg-accent px-4 py-3 text-sm text-ink disabled:opacity-40">{loading ? 'Calculating…' : 'Calculate'}</button></div>
    {error && <p role="alert" className="mt-3 text-sm text-amber-200">{error}</p>}
    {result && <><p className="mt-4 text-xs leading-5 text-slate-400">{result.definition}</p><p className="mt-2 text-xs text-slate-500">{result.excluded_immature_users} users excluded for insufficient follow-up.</p><div className="mt-4 space-y-3">{result.steps.map((step, index) => <div key={index}><div className="mb-1 flex justify-between text-sm"><span>{index + 1}. {step.event}</span><span>{step.users} users · {step.conversion_rate == null ? '—' : `${(step.conversion_rate * 100).toFixed(1)}%`}</span></div><div className="h-3 rounded bg-white/5"><div className="h-3 rounded bg-accent" style={{ width: `${(step.conversion_rate ?? 0) * 100}%` }}/></div>{index > 0 && <p className="mt-1 text-xs text-slate-500">{step.drop_off_users} dropped off · step conversion {step.step_conversion_rate == null ? '—' : `${(step.step_conversion_rate * 100).toFixed(1)}%`}</p>}</div>)}</div></>}
  </section>
}
