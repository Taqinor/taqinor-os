import { describe, it, expect, vi } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

// AFAC64 — `fetchBonsCommande` lit toutes les pages de `/ventes/bons-commande/`
// (comme `fetchFactures`) : une société à 60 BC voit ses 60 BC dans le store
// (liste + badge), le 60e est donc actionnable ; un re-dispatch (après
// « Créer la facture ») en garde toujours 60. Comportemental : état du store
// après le thunk réel, réponses paginées de forme DRF réelle.
vi.mock('../../../api/ventesApi', () => ({
  default: { getBonsCommande: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import ventesReducer, { fetchBonsCommande } from './ventesSlice'

const bc = (i) => ({ id: i, reference: `BC-${i}` })

describe('AFAC64 — 60 bons de commande dans le store', () => {
  it('le store contient les 60 BC, y compris après un re-dispatch', async () => {
    ventesApi.getBonsCommande.mockImplementation(({ page } = {}) => Promise.resolve({
      data: page === 2
        ? { count: 60, next: null, results: Array.from({ length: 10 }, (_, i) => bc(51 + i)) }
        : { count: 60, next: '?page=2', results: Array.from({ length: 50 }, (_, i) => bc(i + 1)) },
    }))
    const s = configureStore({ reducer: { ventes: ventesReducer } })
    await s.dispatch(fetchBonsCommande())
    expect(s.getState().ventes.bonsCommande).toHaveLength(60)
    expect(s.getState().ventes.bonsCommande.some((b) => b.id === 60)).toBe(true)
    await s.dispatch(fetchBonsCommande())
    expect(s.getState().ventes.bonsCommande).toHaveLength(60)
  })
})
