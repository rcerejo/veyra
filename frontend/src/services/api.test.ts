import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

describe('API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('posts a natural-language question as JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'clarification_required', question: 'why?', message: 'More detail', suggestions: [] }),
    })
    vi.stubGlobal('fetch', fetchMock)
    await api.ask('why?')
    expect(fetchMock).toHaveBeenCalledWith('/api/query', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ question: 'why?' }),
    }))
  })

  it('uploads a SQLite file as an opaque binary body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: 'uploads/example.db', size_bytes: 16, active: true }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const file = new File([new Uint8Array(16)], 'example.db')
    await api.uploadDatabase(file)
    expect(fetchMock).toHaveBeenCalledWith('/api/databases/upload?filename=example.db', expect.objectContaining({
      method: 'POST', body: file,
    }))
  })

  it('encodes the selected activity date window', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)
    await api.activityMetrics('2026-03-01', '2026-03-31')
    expect(fetchMock).toHaveBeenCalledWith('/api/metrics/activity?start=2026-03-01&end=2026-03-31', undefined)
  })
})
