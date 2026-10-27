import { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { ArrowUp, Check, Clock3, Code2, Copy, Database, Sparkles } from 'lucide-react'
import { api } from '../services/api'
import type { Clarification, QueryResult } from '../types/api'
import { ResultTable } from '../components/ResultTable'
import { GettingStarted } from '../components/GettingStarted'
import { starterQuestions } from '../services/onboarding'

export function AskVeyra({ onNavigate }: { onNavigate: (page: string) => void }) {
  const [examples, setExamples] = useState<string[]>([])
  useEffect(() => {
    let current = true
    api.schema().then(schema => { if (current) setExamples(starterQuestions(schema.tables)) }).catch(() => { /* The schema explorer provides a retryable error view. */ })
    return () => { current = false }
  }, [])
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [clarification, setClarification] = useState<Clarification | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sqlOpen, setSqlOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  async function submit(value = question) {
    const clean = value.trim(); if (clean.length < 3 || loading) return
    if (clean.length > 1000) { setError('Keep questions within 1,000 characters. Start with one measure and a clear filter.'); return }
    setQuestion(clean); setLoading(true); setError(''); setResult(null); setClarification(null)
    try {
      const response = await api.ask(clean)
      if ('status' in response) setClarification(response); else setResult(response)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to reach VEYRA') }
    finally { setLoading(false) }
  }

  const chart = useMemo(() => {
    if (!result || result.rows.length < 2 || result.columns.length < 2) return null
    const [dimension, measure] = result.columns
    if (!result.rows.every(row => typeof row[measure] === 'number')) return null
    return { backgroundColor: 'transparent', grid: { left: 42, right: 16, top: 16, bottom: 52 },
      xAxis: { type: 'category', data: result.rows.map(row => String(row[dimension])), axisLabel: { color: '#94a3b8', rotate: result.rows.length > 10 ? 35 : 0 }, axisLine: { lineStyle: { color: '#334155' } } },
      yAxis: { type: 'value', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#ffffff0b' } } },
      tooltip: { trigger: 'axis' }, series: [{ type: 'bar', data: result.rows.map(row => row[measure]), itemStyle: { color: '#8EA8FF', borderRadius: [5,5,0,0] } }] }
  }, [result])

  return <main className="mx-auto max-w-6xl px-6 py-10 lg:px-10">
    <section className="mb-8 max-w-3xl"><div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent"><Sparkles size={14}/> Ask Veyra</div>
      <h1 className="text-3xl font-semibold tracking-tight text-slate-50">Turn product questions into evidence.</h1>
      <p className="mt-3 text-sm leading-6 text-slate-400">Ask in plain language. VEYRA plans, validates, and runs a read-only query against your connected workspace.</p>
    </section>
    {!result && !clarification && !loading && <GettingStarted onNavigate={onNavigate}/>}
    <section className="rounded-2xl border border-white/10 bg-panel/90 p-3 shadow-2xl shadow-black/20">
      <textarea aria-label="Question" maxLength={1000} className="min-h-28 w-full resize-none rounded-lg bg-transparent px-3 py-3 text-[15px] leading-6 text-slate-100 outline-none placeholder:text-slate-600 focus-visible:ring-2 focus-visible:ring-accent" placeholder="Name a table, what to measure, and any filters or dates…" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) void submit() }} />
      <div className="flex items-center justify-between border-t border-white/[0.07] px-2 pt-3"><span className="text-xs text-slate-600">Ctrl + Enter to run</span><button onClick={() => void submit()} disabled={loading || question.trim().length < 3} className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-ink transition hover:bg-[#a8baff] disabled:cursor-not-allowed disabled:opacity-40">{loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink/30 border-t-ink"/> : <ArrowUp size={16}/>} {loading ? 'Analyzing' : 'Run analysis'}</button></div>
    </section>
    {!result && !clarification && !error && <div className="mt-4 flex flex-wrap gap-2">{examples.map(example => <button className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-400 hover:border-accent/40 hover:text-slate-200" onClick={() => void submit(example)} key={example}>{example}</button>)}</div>}
    {error && <div role="alert" className="mt-6 rounded-xl border border-red-400/20 bg-red-400/[0.06] p-4 text-sm text-red-200">{error}</div>}
    {clarification && <div role="status" className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-5"><h2 className="font-medium text-amber-200">No query was run — more detail is needed</h2><p className="mt-2 text-sm text-slate-400">{clarification.message}</p><p className="mt-2 text-xs leading-5 text-slate-400">Edit your question above. Name the table and field, define the metric, and include the year for date filters. Suggestions below are alternative questions, not answers to your original request.</p><div className="mt-4 flex flex-wrap gap-2">{clarification.suggestions.map(item => <button className="rounded-lg bg-white/[0.05] px-3 py-2 text-xs text-slate-300 hover:bg-white/[0.09]" onClick={() => void submit(item)} key={item}>{item}</button>)}</div></div>}
    {result && <section className="mt-7 space-y-4">
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400"><span className="inline-flex items-center gap-1.5 text-emerald-400"><Check size={14}/> Read-only SQL checks passed</span><span className="inline-flex items-center gap-1.5"><Database size={14}/>{result.metadata.row_count} rows</span><span className="inline-flex items-center gap-1.5"><Clock3 size={14}/>{result.metadata.duration_ms} ms</span><span className="rounded bg-white/[0.05] px-2 py-1">{result.metadata.source}</span>{result.metadata.correction_attempts > 0 && <span className="rounded bg-blue-400/10 px-2 py-1 text-blue-300">Corrected {result.metadata.correction_attempts}×</span>}{result.metadata.truncated && <span className="rounded bg-amber-400/10 px-2 py-1 text-amber-300">Partial results — row limit reached; CSV contains only displayed rows</span>}</div>
      <p className="text-xs leading-5 text-slate-400">Safety checks do not guarantee the business interpretation is correct. Review filters, joins and date boundaries before making decisions.</p>
      <div className="flex flex-wrap gap-2 rounded-xl border border-white/[0.07] bg-white/[0.02] p-3 text-xs"><span className="text-slate-600">Interpreted as</span><span className="rounded bg-accent/10 px-2 py-1 text-accent">{result.plan.intent}</span>{result.plan.relevant_tables.map(table => <span key={table} className="rounded bg-white/[0.05] px-2 py-1 font-mono text-slate-300">{table}</span>)}{Object.entries(result.plan.filters).map(([field, value]) => <span key={field} className="rounded bg-emerald-400/[0.08] px-2 py-1 font-mono text-emerald-300">{field} = {String(value)}</span>)}{result.plan.time_range && <span className="rounded bg-blue-400/[0.08] px-2 py-1 text-blue-300">{result.plan.time_range.replaceAll('_', ' ')}</span>}</div>
      {chart && <div className="rounded-2xl border border-white/10 bg-panel p-4"><ReactECharts option={chart} style={{height: 290}} /></div>}
      {result.plan.composition && <details className="rounded-xl border border-white/10 bg-panel p-4 text-xs text-slate-300"><summary className="cursor-pointer">Inspect structured query plan</summary><pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap">{JSON.stringify(result.plan.composition, null, 2)}</pre></details>}
      <div className="rounded-2xl border border-white/10 bg-panel p-5"><div className="mb-4 flex items-center justify-between"><div><h2 className="font-medium text-slate-100">Query results</h2><p className="mt-1 text-xs text-slate-500">{result.explanation}</p></div><button className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:bg-white/[0.04]" onClick={() => setSqlOpen(!sqlOpen)}><Code2 size={14}/> {sqlOpen ? 'Hide' : 'Inspect'} SQL</button></div>
        {sqlOpen && <div className="mb-4 rounded-xl bg-ink p-4"><button aria-label="Copy SQL" className="mb-3 inline-flex items-center gap-2 text-xs text-slate-300" onClick={() => { void navigator.clipboard.writeText(result.sql).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) }).catch(() => setError('Copy unavailable. Select the SQL text and copy it manually.')) }}>{copied ? <Check size={15}/> : <Copy size={15}/>} {copied ? 'Copied' : 'Copy SQL'}</button><pre tabIndex={0} aria-label="Generated SQL" className="max-h-72 overflow-auto whitespace-pre-wrap break-all font-mono text-xs text-slate-300"><code>{result.sql}</code></pre></div>}
        <ResultTable columns={result.columns} rows={result.rows}/>
      </div>
    </section>}
  </main>
}

