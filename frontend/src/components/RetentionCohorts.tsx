import { useEffect, useState } from 'react'

interface RetentionData {
  definition: string
  data_through: string
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
    {error && <p role="alert" className="mt-3 text-sm text-amber-200">{error}</p>}
    {!data && !error && <p className="mt-3 text-sm text-slate-500">Loading retention…</p>}
    {data && <><p className="mt-2 text-xs leading-5 text-slate-400">{data.definition}</p><p className="mt-2 text-xs text-slate-500">All signup cohorts · observed through {data.data_through} · — means insufficient follow-up</p>
      <div className="mt-4 max-h-96 overflow-auto"><table className="w-full text-left text-sm"><thead className="text-slate-500"><tr><th className="p-2">Signup date</th><th className="p-2">Users</th>{[1, 7, 30].map(day => <th className="p-2" key={day}>Day {day}</th>)}</tr></thead><tbody>{data.cohorts.map(cohort => <tr className="border-t border-white/5" key={cohort.cohort}><td className="p-2 text-slate-400">{cohort.cohort}</td><td className="p-2">{cohort.users}</td>{cohort.cells.map(cell => <td key={cell.day} className="p-2" title={cell.rate == null ? 'Insufficient follow-up' : `${cell.retained_users} / ${cell.eligible_users} users`} style={{ backgroundColor: cell.rate == null ? 'transparent' : `rgba(142,168,255,${0.05 + cell.rate * 0.5})` }}>{cell.rate == null ? '—' : `${(cell.rate * 100).toFixed(1)}%`}</td>)}</tr>)}</tbody></table></div></>}
  </section>
}
