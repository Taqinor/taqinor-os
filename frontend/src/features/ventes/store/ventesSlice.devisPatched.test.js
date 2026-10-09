import { describe, it, expect } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'
import ventesReducer, { devisPatched } from './ventesSlice'

// APRF8 — réducteur RÉEL : une ligne remplacée par id, ordre conservé, ligne
// absente ignorée (jamais ajoutée).
const store = (devis) => configureStore({
  reducer: { ventes: ventesReducer },
  preloadedState: { ventes: { ...ventesReducer(undefined, { type: '@@init' }), devis } },
})

describe('APRF8 — devisPatched', () => {
  it('remplace la seule ligne touchée, ordre conservé', () => {
    const s = store([1, 2, 3, 4].map((id) => ({ id, statut: 'brouillon' })))
    s.dispatch(devisPatched({ id: 3, statut: 'envoye' }))
    const d = s.getState().ventes.devis
    expect(d.map((x) => x.id)).toEqual([1, 2, 3, 4])
    expect(d.map((x) => x.statut)).toEqual(['brouillon', 'brouillon', 'envoye', 'brouillon'])
  })

  it('ligne absente ignorée', () => {
    const s = store([{ id: 1, statut: 'brouillon' }])
    s.dispatch(devisPatched({ id: 99, statut: 'envoye' }))
    expect(s.getState().ventes.devis).toEqual([{ id: 1, statut: 'brouillon' }])
  })

  it('charge utile sans id ignorée', () => {
    const s = store([{ id: 1, statut: 'brouillon' }])
    s.dispatch(devisPatched({ statut: 'x' }))
    s.dispatch(devisPatched(null))
    expect(s.getState().ventes.devis).toEqual([{ id: 1, statut: 'brouillon' }])
  })
})
