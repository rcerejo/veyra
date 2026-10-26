import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Activity, BarChart3, Beaker, Bot, ChevronDown, FlaskConical, LayoutDashboard, Network, Search, Settings, ShieldCheck } from 'lucide-react'
const AskVeyra = lazy(() => import('./pages/AskVeyra').then(module => ({ default: module.AskVeyra })))
const SchemaExplorer = lazy(() => import('./pages/SchemaExplorer').then(module => ({ default: module.SchemaExplorer })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(module => ({ default: module.SettingsPage })))
const ProductAnalytics = lazy(() => import('./pages/ProductAnalytics').then(module => ({ default: module.ProductAnalytics })))
const ExperimentationLab = lazy(() => import('./pages/ExperimentationLab').then(module => ({ default: module.ExperimentationLab })))
const Investigations = lazy(() => import('./pages/Investigations').then(module => ({ default: module.Investigations })))
const Overview = lazy(() => import('./pages/Overview').then(module => ({ default: module.Overview })))
const Evaluation = lazy(() => import('./pages/Evaluation').then(module => ({ default: module.Evaluation })))
import { api } from './services/api'
import type { Health } from './types/api'
import { StatusPill } from './components/StatusPill'

const navigation = [
  ['Overview', LayoutDashboard], ['Ask Veyra', Bot], ['Product Analytics', BarChart3], ['Experimentation Lab', FlaskConical],
  ['Investigations', Search], ['Schema Explorer', Network], ['Evaluation', Beaker], ['Settings', Settings],
] as const

export default function App() {
  const [active, setActive] = useState('Ask Veyra')
  const [health, setHealth] = useState<Health | null>(null)
  const refreshHealth = useCallback(() => { api.health().then(setHealth).catch(() => setHealth(null)) }, [])
  useEffect(() => { refreshHealth() }, [refreshHealth])
  return <div className="min-h-screen bg-ink text-slate-100">
    <nav className="flex gap-2 overflow-x-auto border-b border-white/10 p-3 md:hidden" aria-label="Workspace navigation">{navigation.map(([label])=><button key={label} onClick={()=>setActive(label)} className={`whitespace-nowrap rounded px-3 py-2 text-xs ${active===label?'bg-accent/10 text-accent':'text-slate-400'}`}>{label}</button>)}</nav>
    <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-white/[0.07] bg-[#0d1526] md:flex md:flex-col">
      <div className="border-b border-white/[0.07] px-6 py-6"><div className="text-2xl font-bold tracking-[-0.05em] text-white">veyra<span className="text-accent">.</span></div><div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-slate-600">Intelligence behind every decision</div></div>
      <nav className="flex-1 space-y-1 px-3 py-5">{navigation.map(([label, Icon]) => <button key={label} onClick={() => setActive(label)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${active === label ? 'bg-accent/10 text-accent' : 'text-slate-500 hover:bg-white/[0.035] hover:text-slate-200'}`}><Icon size={17}/>{label}</button>)}</nav>
      <div className="m-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-3 text-xs text-slate-500"><div className="mb-2 flex items-center gap-2 text-slate-300"><ShieldCheck size={15} className="text-emerald-400"/> Local-first</div>Your data stays on this machine.</div>
    </aside>
    <div className="md:pl-64"><header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-white/[0.07] bg-ink/90 px-6 backdrop-blur lg:px-10"><button className="flex items-center gap-2 text-sm text-slate-300"><span className="grid h-7 w-7 place-items-center rounded-md bg-accent/15 text-xs font-bold text-accent">V</span> Product Demo <ChevronDown size={13} className="text-slate-600"/></button><div className="flex items-center gap-2"><StatusPill active={health?.database.connected ?? false} label={health?.database.name ?? 'Database offline'}/><StatusPill active={health?.ollama.available ?? false} label={health?.ollama.available ? health.ollama.model : 'Offline mode'}/></div></header>
      <Suspense fallback={<p className="p-10 text-slate-400">Loading workspace…</p>}>{active === 'Overview' ? <Overview/> : active === 'Evaluation' ? <Evaluation/> : active === 'Investigations' ? <Investigations/> : active === 'Experimentation Lab' ? <ExperimentationLab/> : active === 'Ask Veyra' ? <AskVeyra/> : active === 'Product Analytics' ? <ProductAnalytics/> : active === 'Schema Explorer' ? <SchemaExplorer/> : active === 'Settings' ? <SettingsPage onDatabaseChanged={refreshHealth}/> : <Empty title={active} description="This workspace is intentionally reserved for a later VEYRA phase." icon={<Activity/>}/>}</Suspense>
    </div>
  </div>
}

function Empty({title, description, icon}: {title: string; description: string; icon: React.ReactNode}) {
  return <main className="grid min-h-[calc(100vh-4rem)] place-items-center p-8"><div className="max-w-md text-center"><div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl border border-white/10 bg-white/[0.035] text-accent">{icon}</div><h1 className="text-xl font-semibold">{title}</h1><p className="mt-2 text-sm leading-6 text-slate-500">{description}</p></div></main>
}

