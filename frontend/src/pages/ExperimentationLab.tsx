import { useEffect, useState } from 'react'
import { ExperimentPlanning } from '../components/ExperimentPlanning'

interface Experiment {
  experiment_id: number; experiment_name: string; status: string
  groups: Record<string, { users: number; conversions: number }>
  effect: number | null; interval: number[] | null; p_value: number | null
  excluded_immature_users: number
  assignment_balance: { status: string; p_value: number | null; expected_treatment_share: number | null }
  relative_lift: number | null
  warnings: string[]
  guardrails: { metric: string; control_mean: number | null; treatment_mean: number | null; effect: number | null; interval: number[] | null; p_value: number | null; status: string }[]
}

export function ExperimentationLab() {
  const [allResults, setResults] = useState<Experiment[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [allocation, setAllocation] = useState('')
  const [event, setEvent] = useState('purchase')
  const [days, setDays] = useState(7)
  const [metric, setMetric] = useState({ event: 'purchase', days: 7 })
  const [selected, setSelected] = useState('')
  const results = allResults.filter(result => !selected || String(result.experiment_id) === selected)
  const visible = results
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError(''); setResults([])
    const params = new URLSearchParams({ conversion_event: metric.event, window_days: String(metric.days) })
    if (allocation) params.set('expected_treatment_share', allocation)
    fetch(`/api/experiments?${params}`, { signal: controller.signal }).then(async response => {
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? 'Experiment analysis failed')
      setResults(body)
    }).catch(cause => { if (!controller.signal.aborted) setError(String(cause)) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [allocation, metric])
  return <main className="mx-auto max-w-6xl px-6 py-10 lg:px-10"><div className="text-xs uppercase tracking-widest text-accent">Experimentation Lab</div><h1 className="mt-3 text-3xl font-semibold">Compare outcomes after assignment.</h1><p className="mt-3 text-sm leading-6 text-slate-400">{metric.event} conversion within {metric.days} × 24 hours of assignment, counted once per user. Only users with a full observation window are eligible. Data completeness is inferred from the latest event.</p>
    <form className="mt-5 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); setMetric({ event: event.trim(), days }) }}><label className="text-sm text-slate-400">Conversion event<input required maxLength={100} value={event} onChange={e => setEvent(e.target.value)} className="mt-1 block rounded-lg border border-white/10 bg-panel p-2"/></label><label className="text-sm text-slate-400">Window in days<input required type="number" min={1} max={90} value={days} onChange={e => setDays(Number(e.target.value))} className="mt-1 block w-24 rounded-lg border border-white/10 bg-panel p-2"/></label><button className="rounded-lg bg-accent px-4 py-2 text-ink">Analyze</button></form>
    <p className="mt-3 text-xs leading-5 text-slate-500">Two-sided pooled proportion z-test; approximate 95% interval for the absolute rate difference. Inference requires at least 10 converted and 10 non-converted users per group. Results assume independent randomized assignments and a fixed analysis point; randomization and repeated testing are not verified here.</p>
    <label className="mt-5 block text-sm text-slate-400">Planned treatment allocation (applies to all displayed experiments)<select className="ml-3 rounded-lg border border-white/10 bg-panel p-2" value={allocation} onChange={event => setAllocation(event.target.value)}><option value="">Not specified</option><option value="0.5">50% treatment / 50% control</option><option value="0.1">10% treatment / 90% control</option><option value="0.9">90% treatment / 10% control</option></select></label><p className="mt-2 text-xs text-slate-500">Choose the allocation planned before the experiment. The balance check uses all assignments and flags a mismatch at p &lt; 0.001.</p>
    <label className="mt-5 block text-sm text-slate-400">Experiment<select value={selected} onChange={e => setSelected(e.target.value)} className="ml-3 rounded bg-panel p-2"><option value="">All experiments</option>{allResults.map(result => <option key={result.experiment_id} value={result.experiment_id}>{result.experiment_name}</option>)}</select></label>
    {visible.map(result => <div key={result.experiment_id} className="mt-5 rounded-xl border border-white/10 p-4 text-sm"><span className="text-slate-400">{result.experiment_name} · assignment balance: </span>{result.assignment_balance.status.replaceAll('_', ' ')}{result.assignment_balance.p_value != null && ` (p = ${result.assignment_balance.p_value.toPrecision(3)})`}{result.assignment_balance.status === 'mismatch' && <p className="mt-2 text-amber-200">Resolve the assignment mismatch before interpreting the effect. Inferential results are withheld.</p>}{result.assignment_balance.status === 'not_configured' && <p className="mt-2 text-slate-500">Allocation balance has not been checked.</p>}</div>)}
    {visible.map(result => <section key={result.experiment_id} className="mt-5 rounded-xl border border-white/10 p-5"><h2>{result.experiment_name}: supporting evidence</h2><p className="mt-2 text-sm text-accent">Relative lift: {result.relative_lift == null ? 'Undefined (no control conversions or insufficient users)' : `${(result.relative_lift*100).toFixed(2)}%`}</p>{result.guardrails.map(guardrail => <div className="mt-4 text-sm text-slate-400" key={guardrail.metric}><h3>Session engagement guardrail · Welch’s t-test</h3><p>Mean sessions per assigned user: control {guardrail.control_mean?.toFixed(2) ?? '—'}; treatment {guardrail.treatment_mean?.toFixed(2) ?? '—'}</p><p>Difference: {guardrail.effect?.toFixed(3) ?? '—'} · 95% interval: {guardrail.interval?.map(x => x.toFixed(3)).join(' to ') ?? 'Unavailable'} · p = {guardrail.p_value?.toPrecision(3) ?? '—'}</p><p>{guardrail.status.replaceAll('_', ' ')}. A lower session count may signal degradation; assess practical importance separately.</p></div>)}<ul className="mt-4 space-y-1 text-xs text-slate-500">{result.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul></section>)}
    {loading && <p className="mt-6 text-slate-400">Analyzing experiments…</p>}{error && <p role="alert" className="mt-6 text-amber-200">{error}</p>}
    {!loading && !error && results.length === 0 && <p className="mt-6 text-slate-400">No experiments found.</p>}
    {results.map(result => <section key={result.experiment_id} className="mt-6 rounded-2xl border border-white/10 bg-panel p-6"><h2 className="text-lg font-medium">{result.experiment_name}</h2><p className="mt-2 text-sm text-accent">{result.status.replaceAll('_', ' ')}</p><div className="mt-5 grid gap-4 sm:grid-cols-2">{Object.entries(result.groups).map(([variant, group]) => <div key={variant} className="rounded-xl bg-ink p-4"><div className="capitalize text-slate-400">{variant}</div><div className="mt-2 text-2xl">{group.users ? `${(100 * group.conversions / group.users).toFixed(1)}%` : '—'}</div><div className="mt-1 text-xs text-slate-500">{group.conversions} conversions / {group.users} eligible users</div></div>)}</div><div className="mt-5 text-sm text-slate-300">Treatment − control: {result.effect == null ? '—' : `${(result.effect * 100).toFixed(2)} percentage points`}</div><p className="mt-2 text-sm text-slate-400">95% interval: {result.interval ? result.interval.map(value => (value * 100).toFixed(2)).join(' to ') + ' percentage points' : 'Insufficient data'} · p-value: {result.p_value == null ? '—' : result.p_value.toPrecision(3)}</p><p className="mt-3 text-xs text-slate-500">{result.excluded_immature_users} assignments excluded for insufficient follow-up. An inconclusive result does not establish equivalence.</p></section>)}
    <ExperimentPlanning/>
  </main>
}
