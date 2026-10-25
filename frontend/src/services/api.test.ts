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
})
