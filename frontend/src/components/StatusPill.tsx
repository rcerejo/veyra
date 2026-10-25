interface Props { label: string; active: boolean }

export function StatusPill({ label, active }: Props) {
  return <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.035] px-3 py-1.5 text-xs text-slate-300">
    <span className={`h-1.5 w-1.5 rounded-full ${active ? 'bg-emerald-400 shadow-[0_0_8px_#22c55e]' : 'bg-amber-400'}`} />{label}
  </span>
}

