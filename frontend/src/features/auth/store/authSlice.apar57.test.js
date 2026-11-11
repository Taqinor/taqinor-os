import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

// Décision fondateur 12/11/2026 (remplace APAR57) : `logoutUser` NE désabonne
// PLUS l'appareil du push — les notifications continuent tant que l'appareil
// est abonné. Simulé au niveau de l'API navigateur (ServiceWorker +
// PushManager), le module `features/pwa/pushSubscribe.js` est le VRAI.

const { post, get } = vi.hoisted(() => ({
  post: vi.fn(() => Promise.resolve({ data: {} })),
  get: vi.fn(() => Promise.resolve({ data: { public_key: 'BLvH' } })),
}))
vi.mock('../../../api/axios', () => ({ default: { post, get } }))
vi.mock('../../../providers/session-bridge', async () => {
  const actual = await vi.importActual('../../../providers/session-bridge')
  return { ...actual, broadcastLogout: vi.fn() }
})

import authReducer, { logoutUser } from './authSlice'
import {
  reabonnerPushSiAutorise, noterChoixPush, _reinitialiserTentativesPush,
} from '../../pwa/pushSubscribe'

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

describe('logoutUser garde les notifications push de l\'appareil', () => {
  it('ne désabonne pas PushManager et ne demande aucune suppression au serveur', async () => {
    installerNavigateurPush()
    const store = configureStore({ reducer: { auth: authReducer } })
    await store.dispatch(logoutUser())

    expect(subscription.unsubscribe).not.toHaveBeenCalled()
    const urls = post.mock.calls.map((c) => c[0])
    expect(urls).not.toContain('/notifications/push/unsubscribe/')
    const call = post.mock.calls.find((c) => c[0] === '/auth/logout/')
    expect(call[1]).toEqual({})
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

// 11/11/2026 — Meryem ne recevait plus aucun push : la déconnexion (APAR57,
// retiré depuis) désabonnait l'appareil et rien ne le réabonnait ensuite.
// `reabonnerPushSiAutorise` (appelé par le shell) refait l'abonnement quand la
// permission est déjà accordée, sauf refus explicite de CET utilisateur.
describe('réabonnement push à la connexion', () => {
  let subscribe

  function installerReabonnement({ permission = 'granted', abonne = false } = {}) {
    const sub = { endpoint: EP, toJSON: () => ({ endpoint: EP, keys: { p256dh: 'p', auth: 'a' } }) }
    subscribe = vi.fn(() => Promise.resolve(sub))
    const reg = { pushManager: { getSubscription: vi.fn(() => Promise.resolve(abonne ? sub : null)), subscribe } }
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: {
        ready: Promise.resolve(reg), controller: {},
        addEventListener: vi.fn(), removeEventListener: vi.fn(),
      },
    })
    hadPushManager = 'PushManager' in window
    hadNotification = 'Notification' in window
    if (!hadPushManager) window.PushManager = function PushManager() {}
    window.Notification = { permission, requestPermission: vi.fn() }
  }
  const abonnementsPostes = () => post.mock.calls.filter((c) => c[0] === '/notifications/push/subscribe/')

  beforeEach(() => {
    _reinitialiserTentativesPush()
    window.localStorage.clear()
  })

  it('réabonne un appareil déjà autorisé après une déconnexion', async () => {
    installerReabonnement()
    expect((await reabonnerPushSiAutorise(4)).ok).toBe(true)
    expect(subscribe).toHaveBeenCalledTimes(1)
    expect(abonnementsPostes()[0][1]).toEqual(expect.objectContaining({ endpoint: EP }))
  })

  it('ré-enregistre côté serveur un abonnement navigateur encore présent', async () => {
    installerReabonnement({ abonne: true })
    await reabonnerPushSiAutorise(4)
    expect(subscribe).not.toHaveBeenCalled()
    expect(abonnementsPostes()).toHaveLength(1)
  })

  it("n'affiche jamais d'invite : sans permission accordée, rien ne se passe", async () => {
    installerReabonnement({ permission: 'default' })
    expect((await reabonnerPushSiAutorise(4)).reason).toBe('denied')
    expect(window.Notification.requestPermission).not.toHaveBeenCalled()
    expect(abonnementsPostes()).toHaveLength(0)
  })

  it("respecte le push coupé par l'utilisateur sur cet appareil, et lui seul", async () => {
    installerReabonnement()
    noterChoixPush(false, 4)
    expect((await reabonnerPushSiAutorise(4)).reason).toBe('refus')
    expect(abonnementsPostes()).toHaveLength(0)
    // Poste partagé : le refus de l'un ne vaut pas pour l'autre.
    expect((await reabonnerPushSiAutorise(7)).ok).toBe(true)
  })

  it("poste partagé : celui qui a coupé le push ne reçoit pas les notifications du précédent", async () => {
    installerReabonnement({ abonne: true })
    const unsubscribe = vi.fn(() => Promise.resolve(true))
    const reg = await navigator.serviceWorker.ready
    reg.pushManager.getSubscription = vi.fn(() => Promise.resolve({ endpoint: EP, unsubscribe }))
    noterChoixPush(false, 7)
    expect((await reabonnerPushSiAutorise(7)).reason).toBe('refus')
    expect(unsubscribe).toHaveBeenCalledTimes(1)
    expect(post.mock.calls.map((c) => c[0])).toContain('/notifications/push/unsubscribe/')
  })

  it('le réactiver efface le refus', async () => {
    installerReabonnement()
    noterChoixPush(false, 4)
    noterChoixPush(true, 4)
    expect((await reabonnerPushSiAutorise(4)).ok).toBe(true)
  })

  it('une seule tentative par utilisateur et par page (Layout remonte à chaque navigation)', async () => {
    installerReabonnement()
    await reabonnerPushSiAutorise(4)
    await reabonnerPushSiAutorise(4)
    expect(abonnementsPostes()).toHaveLength(1)
  })

  it("le réglage manuel s'applique à l'utilisateur connecté", async () => {
    installerReabonnement()
    await reabonnerPushSiAutorise(4)
    noterChoixPush(false)
    _reinitialiserTentativesPush()
    expect((await reabonnerPushSiAutorise(4)).reason).toBe('refus')
  })
})
