import { describe, it, expect, vi, afterEach } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

// LW45 (suite) — le cache `leadPrefetch.js` (poste PARTAGÉ) n'écoute
// `taqinor:auth-logout` que si QUELQU'UN le dispatche. Ce test vérifie que le
// thunk `logoutUser` (déclenché par les boutons Déconnexion de Sidebar.jsx /
// Header.jsx) émet réellement l'événement — sans ça le fix LW45 était inerte
// en production. Cf. `session-bridge.js` (`AUTH_LOGOUT_EVENT`/`emitAuthLogout`)
// et `leadPrefetch.logout.test.jsx` (le côté écouteur, déjà couvert).

vi.mock('../../../api/axios', () => ({ default: { post: vi.fn(() => Promise.resolve({ data: {} })) } }))

const broadcastLogout = vi.fn()
vi.mock('../../../providers/session-bridge', async () => {
  const actual = await vi.importActual('../../../providers/session-bridge')
  return { ...actual, broadcastLogout }
})

import authReducer, { logoutUser } from './authSlice'

afterEach(() => { vi.clearAllMocks() })

describe('LW45 — logoutUser émet taqinor:auth-logout', () => {
  it('dispatche l\'événement window au logout', async () => {
    const store = configureStore({ reducer: { auth: authReducer } })
    const onLogoutEvent = vi.fn()
    window.addEventListener('taqinor:auth-logout', onLogoutEvent)
    try {
      await store.dispatch(logoutUser())
      expect(onLogoutEvent).toHaveBeenCalledTimes(1)
      expect(store.getState().auth.isAuthenticated).toBe(false)
    } finally {
      window.removeEventListener('taqinor:auth-logout', onLogoutEvent)
    }
  })
})
