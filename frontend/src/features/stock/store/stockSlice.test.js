import { describe, it, expect, vi } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

/* ACNC66 — une saisie de mouvement dont la réponse a expiré a peut-être
   abouti : le thunk rejette le message ACNC52 de `getApiError`, jamais le
   texte brut d'axios (« timeout of 20000ms exceeded »). */

vi.mock('../../../api/stockApi', () => ({ default: { createMouvement: vi.fn() } }))

import stockApi from '../../../api/stockApi'
import stockReducer, { createMouvement } from './stockSlice'

describe('createMouvement', () => {
  it("délai dépassé : message d'écriture peut-être aboutie", async () => {
    stockApi.createMouvement.mockRejectedValueOnce(Object.assign(
      new Error('timeout of 20000ms exceeded'),
      { code: 'ECONNABORTED', config: { method: 'post' } },
    ))
    const store = configureStore({ reducer: { stock: stockReducer } })
    const action = await store.dispatch(createMouvement({ produit: 1, type_mouvement: 'entree', quantite: 3 }))
    expect(action.type).toBe('stock/createMouvement/rejected')
    expect(action.payload).toBe(
      "La réponse n'est pas arrivée : l'action a peut-être abouti. Vérifiez avant de recommencer.",
    )
    expect(String(action.payload)).not.toMatch(/timeout of/)
  })

  it('réponse servie : le corps DRF reste rejeté tel quel', async () => {
    stockApi.createMouvement.mockRejectedValueOnce({ response: { status: 400, data: { quantite: ['Stock insuffisant.'] } } })
    const store = configureStore({ reducer: { stock: stockReducer } })
    const action = await store.dispatch(createMouvement({ produit: 1, quantite: 99 }))
    expect(action.payload).toEqual({ quantite: ['Stock insuffisant.'] })
  })
})
