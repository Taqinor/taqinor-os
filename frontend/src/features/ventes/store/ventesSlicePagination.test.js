import { describe, it, expect, vi } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

// ADEV35 — le store des bons de commande lit TOUTES les pages DRF
// `{count,next,results}` (sonde : count 57, 50 reçus sur la page 1) ; une
// liste de 10 éléments ne fait qu'une requête. Le vrai thunk + le vrai réducteur
// tournent ; seul le réseau (ventesApi) est simulé, avec la forme paginée réelle.
vi.mock('../../../api/ventesApi', () => ({
  default: { getBonsCommande: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import ventesReducer, { fetchBonsCommande } from './ventesSlice'

const bc = (i) => ({ id: i, reference: `BC-${i}` })
const store = () => configureStore({ reducer: { ventes: ventesReducer } })

describe('ADEV35 — fetchBonsCommande lit toutes les pages', () => {
  it('57 BC sur deux pages → 57 dans le store', async () => {
    ventesApi.getBonsCommande.mockImplementation(({ page } = {}) => Promise.resolve({
      data: page === 2
        ? { count: 57, next: null, results: Array.from({ length: 7 }, (_, i) => bc(51 + i)) }
        : { count: 57, next: '?page=2', results: Array.from({ length: 50 }, (_, i) => bc(i + 1)) },
    }))
    const s = store()
    await s.dispatch(fetchBonsCommande())
    expect(s.getState().ventes.bonsCommande).toHaveLength(57)
  })

  it('une liste de 10 éléments fait une seule requête', async () => {
    ventesApi.getBonsCommande.mockReset()
    ventesApi.getBonsCommande.mockResolvedValue({
      data: { count: 10, next: null, results: Array.from({ length: 10 }, (_, i) => bc(i + 1)) },
    })
    const s = store()
    await s.dispatch(fetchBonsCommande())
    expect(ventesApi.getBonsCommande).toHaveBeenCalledTimes(1)
    expect(s.getState().ventes.bonsCommande).toHaveLength(10)
  })
})
