import { describe, it, expect, vi, afterEach } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

/* ============================================================================
   CHT28 — installationsSlice.js n'avait AUCUN test unitaire (fetchInstallations,
   updateInstallation, upsertInstallation). Couverts ici au niveau du reducer
   + d'un store réel (patron RTK standard : dispatch d'un thunk mocké côté API,
   lecture de l'état résultant).
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  getInstallations: vi.fn(),
  updateInstallation: vi.fn(),
}))

vi.mock('../../../api/installationsApi', () => ({
  default: {
    getInstallations: (...args) => mocks.getInstallations(...args),
    updateInstallation: (...args) => mocks.updateInstallation(...args),
  },
}))

import reducer, {
  fetchInstallations, updateInstallation, upsertInstallation,
} from './installationsSlice'

function makeStore() {
  return configureStore({ reducer: { installations: reducer } })
}

afterEach(() => vi.clearAllMocks())

describe('installationsSlice (CHT28)', () => {
  it('état initial', () => {
    expect(reducer(undefined, { type: '@@INIT' })).toEqual({
      items: [], loading: false, error: null,
    })
  })

  it('fetchInstallations : pending -> loading=true, fulfilled -> items peuplés', async () => {
    mocks.getInstallations.mockResolvedValue({
      data: {
        count: 2,
        results: [
          { id: 1, reference: 'CH-1' },
          { id: 2, reference: 'CH-2' },
        ],
      },
    })
    const store = makeStore()
    const promise = store.dispatch(fetchInstallations())
    expect(store.getState().installations.loading).toBe(true)

    await promise
    const state = store.getState().installations
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.items).toHaveLength(2)
    expect(state.items[0]).toEqual({ id: 1, reference: 'CH-1' })
  })

  it('fetchInstallations : rejected -> error peuplé, loading retombe à false', async () => {
    mocks.getInstallations.mockRejectedValue({
      response: { data: { detail: 'Erreur serveur' } },
    })
    const store = makeStore()
    await store.dispatch(fetchInstallations())
    const state = store.getState().installations
    expect(state.loading).toBe(false)
    expect(state.error).toEqual({ detail: 'Erreur serveur' })
    expect(state.items).toEqual([])
  })

  it('updateInstallation.fulfilled remplace l\'item existant (par id)', async () => {
    mocks.getInstallations.mockResolvedValue({
      data: { count: 1, results: [{ id: 9, reference: 'CH-9', statut: 'signe' }] },
    })
    mocks.updateInstallation.mockResolvedValue({
      data: { id: 9, reference: 'CH-9', statut: 'materiel_commande' },
    })
    const store = makeStore()
    await store.dispatch(fetchInstallations())
    await store.dispatch(updateInstallation({ id: 9, data: { statut: 'materiel_commande' } }))

    const { items } = store.getState().installations
    expect(items).toHaveLength(1)
    expect(items[0].statut).toBe('materiel_commande')
  })

  it('upsertInstallation : ajoute un nouvel item EN TÊTE, remplace un existant en place', () => {
    let state = reducer(undefined, { type: '@@INIT' })
    state = reducer(state, upsertInstallation({ id: 1, reference: 'CH-1' }))
    expect(state.items).toEqual([{ id: 1, reference: 'CH-1' }])

    state = reducer(state, upsertInstallation({ id: 2, reference: 'CH-2' }))
    expect(state.items[0]).toEqual({ id: 2, reference: 'CH-2' })
    expect(state.items).toHaveLength(2)

    state = reducer(state, upsertInstallation({ id: 1, reference: 'CH-1-MAJ' }))
    expect(state.items).toHaveLength(2)
    expect(state.items.find((x) => x.id === 1)).toEqual({ id: 1, reference: 'CH-1-MAJ' })
  })
})
