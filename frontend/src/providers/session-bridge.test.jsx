import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  AUTH_LOGOUT_EVENT, SESSION_EXPIRED_EVENT, brancherSourceDeSession,
  emitAuthLogout, emitSessionExpired, sessionEstActive,
} from './session-bridge'

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

// Correctif « modale Session expirée sur page publique » — une session ne peut
// EXPIRER que si elle a EXISTÉ. `emitSessionExpired` interroge la source de
// vérité branchée par `store/index.js` (`auth.isAuthenticated`) avant d'émettre.
describe('session-bridge — emitSessionExpired exige une session préalable', () => {
  afterEach(() => { brancherSourceDeSession(null) })

  const capturer = (fn) => {
    const listener = vi.fn()
    window.addEventListener(SESSION_EXPIRED_EVENT, listener)
    try {
      fn()
    } finally {
      window.removeEventListener(SESSION_EXPIRED_EVENT, listener)
    }
    return listener
  }

  it('sans source branchée, aucune session n\'est supposée', () => {
    brancherSourceDeSession(null)
    expect(sessionEstActive()).toBe(false)
    expect(capturer(emitSessionExpired)).not.toHaveBeenCalled()
  })

  it('n\'émet rien quand la source dit « pas connecté »', () => {
    brancherSourceDeSession(() => false)
    expect(capturer(emitSessionExpired)).not.toHaveBeenCalled()
  })

  it('émet quand la source dit « connecté »', () => {
    brancherSourceDeSession(() => true)
    expect(capturer(emitSessionExpired)).toHaveBeenCalledTimes(1)
  })

  it('relit la source à CHAQUE appel (jamais figée au démarrage)', () => {
    let connecte = false
    brancherSourceDeSession(() => connecte)
    expect(capturer(emitSessionExpired)).not.toHaveBeenCalled()
    connecte = true
    expect(capturer(emitSessionExpired)).toHaveBeenCalledTimes(1)
  })

  it('une source qui lève est traitée comme « pas de session »', () => {
    brancherSourceDeSession(() => { throw new Error('store pas prêt') })
    expect(sessionEstActive()).toBe(false)
    expect(capturer(emitSessionExpired)).not.toHaveBeenCalled()
  })
})
