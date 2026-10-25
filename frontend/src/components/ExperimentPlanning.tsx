import { useState } from 'react'

export function ExperimentPlanning() {
  const [baseline, setBaseline] = useState(20)
  const [effect, setEffect] = useState(3)
  const [sample, setSample] = useState(1000)
  const [result, setResult] = useState<{ required_users_per_arm: number; power_at_planned_sample: number; minimum_detectable_absolute_effect: number | null } | null>(null)
  const [error, setError] = useState('')
  async function calculate() {
    setError(''); setResult(null)
    try {
      const response = await fetch(`/api/experiments/power?baseline=${baseline/100}&effect=${effect/100}&per_arm=${sample}`)
      const body = await response.json()
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Check planning inputs')
      setResult(body)
    } catch (cause) { setError(String(cause)) }
  }
  return <section className="mt-8 rounded-2xl border border-white/10 bg-panel p-5"><h2 className="font-medium">Plan an experiment</h2><p className="mt-2 text-xs text-slate-400">Two-sided test at 5% alpha, 80% target power, equal allocation. Enter a baseline and a positive improvement to plan before collecting outcomes.</p><form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void calculate() }}>{[
    { label: 'Baseline conversion (%)', value: baseline, setter: setBaseline, min: .01, max: 99.99, step: .01 },
    { label: 'Absolute improvement (pp)', value: effect, setter: setEffect, min: .01, max: 99, step: .01 },
    { label: 'Planned users per arm', value: sample, setter: setSample, min: 2, max: 100000000, step: 1 },
  ].map(input => <label key={input.label} className="text-xs text-slate-400">{input.label}<input required type="number" {...{ min: input.min, max: input.max, step: input.step }} value={input.value} onChange={e => input.setter(Number(e.target.value))} className="mt-1 block w-44 rounded border border-white/10 bg-ink p-2"/></label>)}<button className="rounded bg-accent px-4 py-2 text-ink">Calculate plan</button></form>{error && <p role="alert" className="mt-3 text-amber-200">{error}</p>}{result && <div className="mt-4 space-y-2 text-sm text-slate-300"><p>Required users per arm: {result.required_users_per_arm.toLocaleString()}</p><p>Power at planned sample: {(result.power_at_planned_sample*100).toFixed(1)}%</p><p>Minimum detectable improvement: {result.minimum_detectable_absolute_effect == null ? 'Not achievable within the valid conversion range' : `${(result.minimum_detectable_absolute_effect*100).toFixed(2)} percentage points`}</p><p className="text-xs text-slate-500">Normal approximation. This is prospective planning, not observed power or a stopping rule.</p></div>}</section>
}
