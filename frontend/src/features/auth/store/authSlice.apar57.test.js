import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

// APAR57 — `logoutUser` désabonne l'appareil du push AVANT `/auth/logout/` et
// transmet l'endpoint au serveur (qui supprime la PushSubscription). Simulé au
// niveau de l'API navigateur (ServiceWorker + PushManager), le module
// `features/pwa/pushSubscribe.js` est le VRAI (non mocké).

const { post } = vi.hoisted(() => ({ post: vi.fn(() => Promise.resolve({ data: {} })) }))
vi.mock('../../../api/axios', () => ({ default: { post, get: vi.fn() } }))
vi.mock('../../../providers/session-bridge', async () => {
  const actual = await vi.importActual('../../../providers/session-bridge')
  return { ...actual, broadcastLogout: vi.fn() }
})

import authReducer, { logoutUser } from './authSlice'

const EP = 'https://push.example.test/apar57/poste-partage'

let subscription
let hadNotification
let hadPushManager

function installerNavigateurPush({ abonne = true } = {}) {
  subscription = abonne
    ? { endpoint: EP, unsubscribe: vi.fn(() => Promise.resolve(true)) }
    : null
  const reg = { pushManager: { getSubscription: vi.fn(() => Promise.resolve(subscription)) } }
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: {
      ready: Promise.resolve(reg),
      getRegistration: vi.fn(() => Promise.resolve(reg)),
      controller: {},
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    },
  })
  hadPushManager = 'PushManager' in window
  hadNotification = 'Notification' in window
  if (!hadPushManager) window.PushManager = function PushManager() {}
  if (!hadNotification) window.Notification = { permission: 'granted' }
}

beforeEach(() => { post.mockClear() })
afterEach(() => {
  delete navigator.serviceWorker
  if (!hadPushManager) delete window.PushManager
  if (!hadNotification) delete window.Notification
})

describe('APAR57 — logoutUser désabonne le push de l\'appareil', () => {
  it('désabonne PushManager puis poste /auth/logout/ avec push_endpoint', async () => {
    installerNavigateurPush()
    const store = configureStore({ reducer: { auth: authReducer } })
    await store.dispatch(logoutUser())

    expect(subscription.unsubscribe).toHaveBeenCalledTimes(1)
    const urls = post.mock.calls.map((c) => c[0])
    const iUnsub = urls.indexOf('/notifications/push/unsubscribe/')
    const iLogout = urls.indexOf('/auth/logout/')
    expect(iLogout).toBeGreaterThanOrEqual(0)
    // Désabonnement AVANT la déconnexion (session encore valide).
    expect(iUnsub).toBeGreaterThanOrEqual(0)
    expect(iUnsub).toBeLessThan(iLogout)
    expect(post.mock.calls[iLogout][1]).toEqual({ push_endpoint: EP })
    expect(store.getState().auth.isAuthenticated).toBe(false)
  })

  it('sans abonnement : logout normal, corps vide', async () => {
    installerNavigateurPush({ abonne: false })
    const store = configureStore({ reducer: { auth: authReducer } })
    await store.dispatch(logoutUser())
    const call = post.mock.calls.find((c) => c[0] === '/auth/logout/')
    expect(call[1]).toEqual({})
    expect(store.getState().auth.isAuthenticated).toBe(false)
  })
})
