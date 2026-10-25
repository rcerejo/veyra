import { useCallback, useEffect, useState } from 'react'
import { Activity, BarChart3, Beaker, Bot, ChevronDown, FlaskConical, LayoutDashboard, Network, Search, Settings, ShieldCheck } from 'lucide-react'
import { AskVeyra } from './pages/AskVeyra'
import { SchemaExplorer } from './pages/SchemaExplorer'
import { SettingsPage } from './pages/SettingsPage'
import { ProductAnalytics } from './pages/ProductAnalytics'
import { ExperimentationLab } from './pages/ExperimentationLab'
import { Investigations } from './pages/Investigations'
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
    <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-white/[0.07] bg-[#0d1526] md:flex md:flex-col">
      <div className="border-b border-white/[0.07] px-6 py-6"><div className="text-2xl font-bold tracking-[-0.05em] text-white">veyra<span className="text-accent">.</span></div><div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-slate-600">Intelligence behind every decision</div></div>
      <nav className="flex-1 space-y-1 px-3 py-5">{navigation.map(([label, Icon]) => <button key={label} onClick={() => setActive(label)} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${active === label ? 'bg-accent/10 text-accent' : 'text-slate-500 hover:bg-white/[0.035] hover:text-slate-200'}`}><Icon size={17}/>{label}{!['Ask Veyra', 'Product Analytics', 'Experimentation Lab', 'Investigations', 'Schema Explorer', 'Settings'].includes(label) && <span className="ml-auto rounded bg-white/[0.04] px-1.5 py-0.5 text-[9px] uppercase text-slate-600">soon</span>}</button>)}</nav>
      <div className="m-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-3 text-xs text-slate-500"><div className="mb-2 flex items-center gap-2 text-slate-300"><ShieldCheck size={15} className="text-emerald-400"/> Local-first</div>Your data stays on this machine.</div>
    </aside>
    <div className="md:pl-64"><header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-white/[0.07] bg-ink/90 px-6 backdrop-blur lg:px-10"><button className="flex items-center gap-2 text-sm text-slate-300"><span className="grid h-7 w-7 place-items-center rounded-md bg-accent/15 text-xs font-bold text-accent">V</span> Product Demo <ChevronDown size={13} className="text-slate-600"/></button><div className="flex items-center gap-2"><StatusPill active={health?.database.connected ?? false} label={health?.database.name ?? 'Database offline'}/><StatusPill active={health?.ollama.available ?? false} label={health?.ollama.available ? health.ollama.model : 'Offline mode'}/></div></header>
      {active === 'Investigations' ? <Investigations/> : active === 'Experimentation Lab' ? <ExperimentationLab/> : active === 'Ask Veyra' ? <AskVeyra/> : active === 'Product Analytics' ? <ProductAnalytics/> : active === 'Schema Explorer' ? <SchemaExplorer/> : active === 'Settings' ? <SettingsPage onDatabaseChanged={refreshHealth}/> : <Empty title={active} description="This workspace is intentionally reserved for a later VEYRA phase." icon={<Activity/>}/>}
    </div>
  </div>
}

function Empty({title, description, icon}: {title: string; description: string; icon: React.ReactNode}) {
  return <main className="grid min-h-[calc(100vh-4rem)] place-items-center p-8"><div className="max-w-md text-center"><div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl border border-white/10 bg-white/[0.035] text-accent">{icon}</div><h1 className="text-xl font-semibold">{title}</h1><p className="mt-2 text-sm leading-6 text-slate-500">{description}</p></div></main>
}

