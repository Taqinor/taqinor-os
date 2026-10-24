import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

import parametresReducer from '../../features/parametres/store/parametresSlice'
import parametresApi from '../../api/parametresApi'
import api from '../../api/axios'
import SecuriteTerrainSection from './SecuriteTerrainSection'

/* APAR82 — l'enregistrement au blur de « Sécurité & terrain » passe par le
   thunk `saveProfile` du store : le profil du store (donc l'`updated_at` que le
   « Enregistrer » de Paramètres enverra ensuite) suit la réponse du serveur.
   Avant : appel direct à `parametresApi.updateProfile`, store figé sur
   l'ancien horodatage → 409 contre soi-même au « Enregistrer » suivant. */

const T0 = '2026-10-08T10:00:00.123456Z'
const T1 = '2026-10-08T10:05:00.654321Z'

function monter() {
  const store = configureStore({ reducer: { parametres: parametresReducer } })
  render(<Provider store={store}><SecuriteTerrainSection /></Provider>)
  return store
}

describe('APAR82 — Sécurité & terrain enregistre par le store', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks() })

  it('le blur du seuil pose l’updated_at de la réponse dans le store', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: { results: [], count: 0, next: null } })
    vi.spyOn(parametresApi, 'getProfile')
      .mockResolvedValue({ data: { overage_seuil_pct: 10, updated_at: T0 } })
    const updateProfile = vi.spyOn(parametresApi, 'updateProfile')
      .mockResolvedValue({ data: { overage_seuil_pct: 15, updated_at: T1 } })
    const store = monter()
    const champ = await screen.findByDisplayValue('10')
    fireEvent.change(champ, { target: { value: '15' } })
    fireEvent.blur(champ)
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile).toHaveBeenCalledWith({ overage_seuil_pct: '15' })
    await waitFor(() => expect(store.getState().parametres.profile?.updated_at).toBe(T1))
    expect(store.getState().parametres.verrouUpdatedAt).toBe(T1)
  })

  it('un refus du serveur laisse le profil du store intact', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({ data: { results: [], count: 0, next: null } })
    vi.spyOn(parametresApi, 'getProfile')
      .mockResolvedValue({ data: { overage_seuil_pct: 10, updated_at: T0 } })
    const updateProfile = vi.spyOn(parametresApi, 'updateProfile').mockRejectedValue({
      response: { status: 400, data: { overage_seuil_pct: ['Valeur invalide.'] } },
    })
    const store = monter()
    const champ = await screen.findByDisplayValue('10')
    fireEvent.change(champ, { target: { value: '-3' } })
    fireEvent.blur(champ)
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(store.getState().parametres.saving).toBe(false))
    expect(store.getState().parametres.profile).toBeNull()
  })
})
