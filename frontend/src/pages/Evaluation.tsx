import { useState } from 'react'

interface Benchmark { system: string; total: number; correct: number; cases: { question: string; correct: boolean; latency_ms: number; error?: string }[] }
export function Evaluation() {
  const [systems,setSystems]=useState<Benchmark[]>([])
  const [models,setModels]=useState(false)
  const [status,setStatus]=useState('')
  const [loading,setLoading]=useState(false)
  async function run() {
    setLoading(true);setStatus('Running measured benchmark…');setSystems([])
    try {
      const response=await fetch(`/api/evaluation?include_models=${models}`,{method:'POST'})
      const body=await response.json()
      if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:'Benchmark failed')
      setSystems(body.systems);setStatus(body.model_baselines)
    } catch(cause) { setStatus(String(cause)) }
    finally {setLoading(false)}
  }
  return <main className="mx-auto max-w-6xl px-6 py-10"><h1 className="text-3xl font-semibold">Evaluation</h1><p className="mt-3 text-sm text-slate-400">Reference-query benchmark cases. Results are measured against the active database. Includes basic queries, joins, retention, conversion, cohorts and experiment assignments. Metric mathematics also has dedicated backend tests.</p><label className="mt-5 block text-sm text-slate-400"><input type="checkbox" checked={models} onChange={e=>setModels(e.target.checked)}/> Include direct and schema-aware Ollama baselines (can take several minutes)</label><button onClick={()=>void run()} disabled={loading} className="mt-3 rounded bg-accent px-4 py-2 text-ink disabled:opacity-40">Run benchmark</button><p role="status" className="mt-3 text-sm text-slate-400">{status}</p>{systems.map(system=><section key={system.system} className="mt-5 rounded-xl border border-white/10 bg-panel p-5"><h2>{system.system}: {system.correct}/{system.total} correct</h2><div className="mt-3 max-h-96 overflow-auto">{system.cases.map((item,i)=><div key={i} className="border-t border-white/5 py-2 text-xs"><span className={item.correct?'text-emerald-300':'text-amber-300'}>{item.correct?'Pass':'Fail'}</span> · {item.question} · {item.latency_ms} ms{item.error&&<p className="mt-1 text-slate-500">{item.error}</p>}</div>)}</div></section>)}</main>
}
