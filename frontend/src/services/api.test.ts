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

  it('inspects a source without activating it', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ tables: [] }) })
    vi.stubGlobal('fetch', fetchMock)
    await api.sourceSchema('uploads/team data.db')
    expect(fetchMock).toHaveBeenCalledWith('/api/databases/schema?name=uploads%2Fteam+data.db', undefined)
  })

  it('posts explicit source and key mappings without an activation request', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)
    const configuration = { name: 'demo', sources: [{ name: 'a.db', alias: 'crm' }, { name: 'b.db', alias: 'product' }], relationships: [{ child_source: 'product', child_table: 'events', child_columns: ['user_ref'], parent_source: 'crm', parent_table: 'users', parent_columns: ['id'] }] }
    await api.combineDatabases(configuration)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/api/databases/combine', expect.objectContaining({ method: 'POST', body: JSON.stringify(configuration) }))
  })

  it('retrieves saved snapshot provenance', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)
    await api.snapshotProvenance('combined/demo/dataset.db')
    expect(fetchMock).toHaveBeenCalledWith('/api/databases/provenance?name=combined%2Fdemo%2Fdataset.db', undefined)
  })

  it('turns structured validation errors into a useful message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: [{ msg: 'invalid' }] }) }))
    await expect(api.sourceSchema('bad')).rejects.toThrow('Check the selected sources')
  })

  it('explains backend connection failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.health()).rejects.toThrow('launcher terminal')
  })

  it('does not display an unstructured upload error object', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 422, json: async () => ({ detail: [{ msg: 'invalid' }] }) }))
    await expect(api.uploadDatabase(new File(['data'], 'data.db'))).rejects.toThrow('Invalid request')
  })

  it('handles non-JSON server and successful proxy responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => { throw new Error('HTML') } }))
    await expect(api.schema()).rejects.toThrow('server could not complete')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => { throw new Error('HTML') } }))
    await expect(api.schema()).rejects.toThrow('unreadable response')
  })
})
