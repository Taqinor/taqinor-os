import { describe, it, expect, vi, beforeEach } from 'vitest'

/* ASTK185 (C-ASTK-042, FOUR-8) — StandardPagination sert 50 lignes par page :
   les écrans qui ne lisaient que `r.data.results` perdaient le 51ᵉ
   fournisseur. getAllFournisseurs suit `next` jusqu'au bout. */
vi.mock('./axios', () => ({ default: { get: vi.fn() } }))

import api from './axios'
import stockApi from './stockApi'

const page = (debut, n, next) => ({
  data: {
    count: 51,
    next,
    results: Array.from({ length: n }, (_, i) => ({ id: debut + i, nom: `F${debut + i}` })),
  },
})

describe('stockApi.getAllFournisseurs (ASTK185)', () => {
  beforeEach(() => { api.get.mockReset() })

  it('getAllFournisseurs suit next', async () => {
    api.get
      .mockResolvedValueOnce(page(1, 50, 'http://x/api/django/stock/fournisseurs/?page=2'))
      .mockResolvedValueOnce(page(51, 1, null))
    const r = await stockApi.getAllFournisseurs({ ordering: 'nom' })
    expect(r.data).toHaveLength(51)
    expect(r.data[50]).toEqual({ id: 51, nom: 'F51' })
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(api.get).toHaveBeenNthCalledWith(1, '/stock/fournisseurs/',
      { params: { page_size: 200, ordering: 'nom', page: 1 } })
    expect(api.get).toHaveBeenNthCalledWith(2, '/stock/fournisseurs/',
      { params: { page_size: 200, ordering: 'nom', page: 2 } })
  })

  it('une réponse non paginée (tableau) est rendue telle quelle', async () => {
    api.get.mockResolvedValueOnce({ data: [{ id: 1 }] })
    const r = await stockApi.getAllFournisseurs()
    expect(r.data).toEqual([{ id: 1 }])
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('getAllFournisseursArchived suit next avec show_archived', async () => {
    api.get
      .mockResolvedValueOnce(page(1, 50, 'next'))
      .mockResolvedValueOnce(page(51, 1, null))
    const r = await stockApi.getAllFournisseursArchived()
    expect(r.data).toHaveLength(51)
    expect(api.get.mock.calls[1][1].params).toMatchObject({ show_archived: 'true', page: 2 })
  })
})
