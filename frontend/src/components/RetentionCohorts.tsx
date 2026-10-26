import { useEffect, useState } from 'react'

interface RetentionData {
  definition: string
  data_through: string
  rolling_retention: {day:number;rate:number|null;eligible_users:number}[]
  weekly_retention: {cohort:string;week:number;eligible_users:number;rate:number}[]
  activation: {rate:number|null;eligible_users:number}
  churn: {rate:number|null;eligible_users:number}
  activation_definition: string
  churn_definition: string
  cohorts: { cohort: string; users: number; cells: { day: number; eligible_users: number; retained_users: number | null; rate: number | null }[] }[]
}

export function RetentionCohorts() {
  const [data, setData] = useState<RetentionData | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    fetch('/api/metrics/retention').then(async response => {
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? 'Unable to load retention')
      setData(body)
    }).catch(cause => setError(String(cause)))
  }, [])
  return <section className="mt-5 rounded-2xl border border-white/10 bg-panel p-5">
    <h2 className="font-medium">Signup cohort retention</h2>
    {data && <div className="my-4 space-y-3 text-xs text-slate-400"><p>Activation: {data.activation.rate==null?'—':`${(data.activation.rate*100).toFixed(1)}%`} · {data.activation.eligible_users} eligible users. {data.activation_definition}</p><p>Inactivity churn: {data.churn.rate==null?'—':`${(data.churn.rate*100).toFixed(1)}%`} · {data.churn.eligible_users} eligible users. {data.churn_definition}</p><p>Rolling retention: {data.rolling_retention.map(cell=>`Day ${cell.day}: ${cell.rate==null?'—':(cell.rate*100).toFixed(1)+'%'}`).join(' · ')}. Return on or after day N through the observation cutoff; follow-up lengths vary.</p><details><summary className="cursor-pointer text-accent">Complete observation week retention</summary><p className="mt-2">Seven-day age bins, grouped by Monday signup cohort. Each cell includes only users with the full age week observed. Denominators may vary by week.</p><div className="mt-3 max-h-72 overflow-auto"><table className="w-full text-left"><thead><tr><th>Cohort</th><th>Age week</th><th>Eligible users</th><th>Retained</th></tr></thead><tbody>{data.weekly_retention.map(cell=><tr key={`${cell.cohort}-${cell.week}`} className="border-t border-white/5"><td className="p-2">{cell.cohort}</td><td>{cell.week}</td><td>{cell.eligible_users}</td><td>{(cell.rate*100).toFixed(1)}%</td></tr>)}</tbody></table></div></details></div>}
    {error && <p role="alert" className="mt-3 text-sm text-amber-200">{error}</p>}
    {!data && !error && <p className="mt-3 text-sm text-slate-500">Loading retention…</p>}
    {data && <><p className="mt-2 text-xs leading-5 text-slate-400">{data.definition}</p><p className="mt-2 text-xs text-slate-500">All signup cohorts · observed through {data.data_through} · — means insufficient follow-up</p>
      <div className="mt-4 max-h-96 overflow-auto"><table className="w-full text-left text-sm"><thead className="text-slate-500"><tr><th className="p-2">Signup date</th><th className="p-2">Users</th>{[1, 7, 30].map(day => <th className="p-2" key={day}>Day {day}</th>)}</tr></thead><tbody>{data.cohorts.map(cohort => <tr className="border-t border-white/5" key={cohort.cohort}><td className="p-2 text-slate-400">{cohort.cohort}</td><td className="p-2">{cohort.users}</td>{cohort.cells.map(cell => <td key={cell.day} className="p-2" title={cell.rate == null ? 'Insufficient follow-up' : `${cell.retained_users} / ${cell.eligible_users} users`} style={{ backgroundColor: cell.rate == null ? 'transparent' : `rgba(142,168,255,${0.05 + cell.rate * 0.5})` }}>{cell.rate == null ? '—' : `${(cell.rate * 100).toFixed(1)}%`}</td>)}</tr>)}</tbody></table></div></>}
  </section>
}
