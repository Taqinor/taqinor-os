import { describe, it, expect, vi } from 'vitest'
import { AUTH_LOGOUT_EVENT, emitAuthLogout } from './session-bridge'

// LW45 (suite) — `emitAuthLogout` est le point d'émission PARTAGÉ appelé par
// le thunk `logoutUser` (logout local, cf. `authSlice.logoutEvent.test.jsx`)
// et par le gestionnaire cross-onglet de `SessionProvider.jsx`. Sans lui, le
// listener `leadPrefetch.js` (LW45) reste inerte en production — aucun code
// ne dispatchait l'événement avant ce fix.

describe('session-bridge — emitAuthLogout', () => {
  it('dispatche AUTH_LOGOUT_EVENT sur window', () => {
    const listener = vi.fn()
    window.addEventListener(AUTH_LOGOUT_EVENT, listener)
    try {
      emitAuthLogout()
      expect(listener).toHaveBeenCalledTimes(1)
    } finally {
      window.removeEventListener(AUTH_LOGOUT_EVENT, listener)
    }
  })

  it('AUTH_LOGOUT_EVENT correspond au LOGOUT_EVENT écouté par leadPrefetch.js', async () => {
    const { LOGOUT_EVENT } = await import('../features/crm/workspace/leadPrefetch')
    expect(AUTH_LOGOUT_EVENT).toBe(LOGOUT_EVENT)
  })
})
