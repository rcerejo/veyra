import { useState } from 'react'
import ReactECharts from 'echarts-for-react'

interface Segment { segment: string; baseline_users: number; current_users: number; within_contribution: number; composition_contribution: number; total_contribution: number; small_sample: boolean }
interface Report { explanation: string; baseline_rate: number; current_rate: number; absolute_change: number; baseline_users: number; current_users: number; warnings: string[]; breakdowns: { dimension: string; segments: Segment[] }[] }

export function Investigations() {
  const [dates, setDates] = useState({ baseline_start: '2026-03-01', baseline_end: '2026-03-07', current_start: '2026-03-08', current_end: '2026-03-14' })
  const [event, setEvent] = useState('purchase')
  const [report, setReport] = useState<Report | null>(null)
  const [dimension, setDimension] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  async function investigate() {
    setLoading(true); setError(''); setReport(null)
    try {
      const response = await fetch('/api/investigations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...dates, conversion_event: event }) })
      const body = await response.json()
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Use equal-length, ordered, non-overlapping periods')
      setReport(body); setDimension(body.breakdowns[0]?.dimension ?? '')
    } catch (cause) { setError(String(cause)) }
    finally { setLoading(false) }
  }
  const selected = report?.breakdowns.find(item => item.dimension === dimension)
  const chart = { tooltip: { trigger: 'axis' }, legend: { textStyle: { color: '#94a3b8' } }, grid: { left: 120, right: 30, bottom: 35 }, xAxis: { type: 'value', name: 'percentage points', axisLabel: { color: '#94a3b8' } }, yAxis: { type: 'category', data: selected?.segments.map(s => s.segment), axisLabel: { color: '#94a3b8' } }, series: [{ name: 'Within-segment rate', type: 'bar', stack: 'change', data: selected?.segments.map(s => +(s.within_contribution*100).toFixed(3)), itemStyle: { color: '#8ea8ff' } }, { name: 'Population composition', type: 'bar', stack: 'change', data: selected?.segments.map(s => +(s.composition_contribution*100).toFixed(3)), itemStyle: { color: '#34d399' } }] }
  return <main className="mx-auto max-w-6xl px-6 py-10 lg:px-10"><div className="text-xs uppercase tracking-widest text-accent">Automated investigations</div><h1 className="mt-3 text-3xl font-semibold">What contributed to the conversion change?</h1><p className="mt-3 text-sm text-slate-400">Compare equal-length UTC periods. Conversion is the share of active users with the selected event during each period.</p><form onSubmit={e => { e.preventDefault(); void investigate() }} className="mt-6 flex flex-wrap items-end gap-3">{Object.entries(dates).map(([key,value]) => <label key={key} className="text-xs capitalize text-slate-400">{key.replaceAll('_',' ')}<input required type="date" value={value} onChange={e => setDates({ ...dates, [key]: e.target.value })} className="mt-1 block rounded border border-white/10 bg-panel p-2"/></label>)}<label className="text-xs text-slate-400">Conversion event<input required value={event} onChange={e => setEvent(e.target.value)} className="mt-1 block rounded border border-white/10 bg-panel p-2"/></label><button disabled={loading} className="rounded bg-accent px-4 py-2 text-ink">{loading ? 'Investigating…' : 'Investigate'}</button></form>{error && <p role="alert" className="mt-5 text-amber-200">{error}</p>}{report && <><section className="mt-6 rounded-xl border border-white/10 bg-panel p-5"><h2 className="font-medium">Evidence summary</h2><p className="mt-3 text-sm leading-6 text-slate-300">{report.explanation}</p><p className="mt-2 text-xs text-slate-500">Baseline: {report.baseline_users} active users · Current: {report.current_users} active users</p></section><label className="mt-5 block text-sm text-slate-400">Segment by<select value={dimension} onChange={e => setDimension(e.target.value)} className="ml-3 rounded bg-panel p-2">{report.breakdowns.map(item => <option key={item.dimension}>{item.dimension}</option>)}</select></label>{selected && <section className="mt-4 rounded-xl border border-white/10 bg-panel p-5"><ReactECharts option={chart} style={{ height: Math.max(300,selected.segments.length*35) }}/><div className="overflow-auto"><table className="w-full text-left text-xs"><thead><tr>{['Segment','Before users','After users','Rate contribution (pp)','Composition (pp)','Total (pp)'].map(h => <th key={h} className="p-2 text-slate-500">{h}</th>)}</tr></thead><tbody>{selected.segments.map(s => <tr key={s.segment} className="border-t border-white/5"><td className="p-2">{s.segment}{s.small_sample && ' · small sample'}</td><td className="p-2">{s.baseline_users}</td><td className="p-2">{s.current_users}</td>{[s.within_contribution,s.composition_contribution,s.total_contribution].map((v,i) => <td key={i} className="p-2">{(v*100).toFixed(3)}</td>)}</tr>)}</tbody></table></div></section>}<ul className="mt-5 space-y-2 text-xs leading-5 text-slate-500">{report.warnings.map(w => <li key={w}>{w}</li>)}</ul></>}</main>
}
