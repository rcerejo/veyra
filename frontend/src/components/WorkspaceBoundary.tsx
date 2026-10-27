import { Component, type ReactNode } from 'react'

export class WorkspaceBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    if (!this.state.failed) return this.props.children
    return <main role="alert" className="mx-auto max-w-xl p-10"><h1 className="text-xl font-semibold">This view couldn’t be displayed</h1><p className="mt-3 text-sm leading-6 text-slate-400">Try opening another page, or reload the app. Unsaved questions and form entries will be lost on reload. If an upload or snapshot was in progress, check Settings before retrying it.</p><button onClick={() => window.location.reload()} className="mt-4 rounded-lg bg-accent px-4 py-2 text-sm text-ink">Reload app</button></main>
  }
}
