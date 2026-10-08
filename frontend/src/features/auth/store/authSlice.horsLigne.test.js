import { describe, it, expect, vi, beforeEach } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

// ADEP33 (C-ADEP-021) — `fetchMe` distingue un REFUS d'authentification
// (401/403 → déconnexion, comme avant) d'une PANNE (pas de réponse, 5xx →
// session courante conservée, `sessionInconnue` vrai). Avant : un échec réseau
// ou un 503 pendant une relance en cours de session (PreferencesPanel,
// PresentationModeToggle, DemoOnboardingSection, PortailMotDePasse) déconnectait
// l'utilisateur exactement comme un 401.
// Test-du-test : remettre `isAuthenticated = false` inconditionnel dans
// `fetchMe.rejected` ⇒ les cas réseau et 503 échouent.

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../../../api/axios', () => ({ default: { get, post: vi.fn() } }))

import authReducer, { fetchMe, setCredentials } from './authSlice'

const PROFIL = { user: { username: 'meriem' }, menu_tier: 'admin', permissions: ['ventes.view'] }

const storeConnecte = () => {
  const store = configureStore({ reducer: { auth: authReducer } })
  store.dispatch(setCredentials(PROFIL))
  return store
}

const erreurHttp = (status) => Object.assign(new Error(`HTTP ${status}`), {
  response: { status, data: { detail: 'x' } },
})

beforeEach(() => { get.mockReset() })

describe('ADEP33 — fetchMe hors ligne / panne serveur', () => {
  it('échec réseau (aucune réponse) : la session reste, sessionInconnue vrai', async () => {
    const store = storeConnecte()
    get.mockRejectedValueOnce(Object.assign(new Error('Network Error'), { request: {} }))
    const action = await store.dispatch(fetchMe())
    expect(action.payload).toEqual({ status: null, reseau: true })
    const auth = store.getState().auth
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.sessionInconnue).toBe(true)
    expect(auth.user).toEqual({ username: 'meriem' })
    expect(auth.permissions).toEqual(['ventes.view'])
    expect(auth.loading).toBe(false)
  })

  it('503 : la session reste, sessionInconnue vrai', async () => {
    const store = storeConnecte()
    get.mockRejectedValueOnce(erreurHttp(503))
    const action = await store.dispatch(fetchMe())
    expect(action.payload).toEqual({ status: 503, reseau: false })
    const auth = store.getState().auth
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.sessionInconnue).toBe(true)
    expect(auth.role).toBe('admin')
  })

  it.each([401, 403])('%i : déconnecte comme avant', async (status) => {
    const store = storeConnecte()
    get.mockRejectedValueOnce(erreurHttp(status))
    const action = await store.dispatch(fetchMe())
    expect(action.payload).toEqual({ status, reseau: false })
    const auth = store.getState().auth
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.sessionInconnue).toBe(false)
  })

  it('démarrage à froid hors ligne : jamais authentifié par une panne', async () => {
    const store = configureStore({ reducer: { auth: authReducer } })
    get.mockRejectedValueOnce(Object.assign(new Error('Network Error'), { request: {} }))
    await store.dispatch(fetchMe())
    const auth = store.getState().auth
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.sessionInconnue).toBe(true)
    expect(auth.loading).toBe(false)
  })

  it('un fetchMe réussi après une panne lève sessionInconnue', async () => {
    const store = storeConnecte()
    get.mockRejectedValueOnce(erreurHttp(502))
    await store.dispatch(fetchMe())
    expect(store.getState().auth.sessionInconnue).toBe(true)
    get.mockResolvedValueOnce({ data: { username: 'meriem', menu_tier: 'admin' } })
    await store.dispatch(fetchMe())
    expect(store.getState().auth.sessionInconnue).toBe(false)
    expect(store.getState().auth.isAuthenticated).toBe(true)
  })
})
