import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// 11/11/2026 — Meryem ne recevait plus aucun push : APAR57 désabonne
// l'appareil à chaque « Se déconnecter » et rien ne le réabonnait à la
// connexion suivante. `reabonnerPushSiAutorise` refait l'abonnement quand la
// permission est déjà accordée, sauf refus explicite de CET utilisateur.

const { pushSubscribe, getVapidPublicKey } = vi.hoisted(() => ({
  pushSubscribe: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  getVapidPublicKey: vi.fn(() => Promise.resolve({ data: { public_key: 'BLvH' } })),
}))
vi.mock('../../api/notificationsApi', () => ({
  default: { pushSubscribe, getVapidPublicKey, pushUnsubscribe: vi.fn() },
}))

import {
  reabonnerPushSiAutorise, noterChoixPush, _reinitialiserTentativesPush,
} from './pushSubscribe'

const EP = 'https://push.example.test/meryem/telephone'
let hadPushManager
let hadNotification
let subscribe

function installerNavigateur({ permission = 'granted', abonne = false } = {}) {
  subscribe = vi.fn(() => Promise.resolve({ endpoint: EP, toJSON: () => ({ endpoint: EP, keys: { p256dh: 'p', auth: 'a' } }) }))
  const existant = abonne ? { endpoint: EP, toJSON: () => ({ endpoint: EP, keys: { p256dh: 'p', auth: 'a' } }) } : null
  const reg = { pushManager: { getSubscription: vi.fn(() => Promise.resolve(existant)), subscribe } }
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: {
      ready: Promise.resolve(reg), controller: {},
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
    },
  })
  hadPushManager = 'PushManager' in window
  hadNotification = 'Notification' in window
  window.PushManager = window.PushManager || function PushManager() {}
  window.Notification = { permission, requestPermission: vi.fn() }
}

beforeEach(() => {
  pushSubscribe.mockClear()
  _reinitialiserTentativesPush()
  window.localStorage.clear()
})
afterEach(() => {
  delete navigator.serviceWorker
  if (!hadPushManager) delete window.PushManager
  if (!hadNotification) delete window.Notification
})

describe('réabonnement push à la connexion', () => {
  it('réabonne un appareil déjà autorisé après une déconnexion', async () => {
    installerNavigateur()
    const res = await reabonnerPushSiAutorise(4)
    expect(res.ok).toBe(true)
    expect(subscribe).toHaveBeenCalledTimes(1)
    expect(pushSubscribe).toHaveBeenCalledWith(expect.objectContaining({ endpoint: EP }))
  })

  it('ré-enregistre côté serveur un abonnement navigateur encore présent', async () => {
    installerNavigateur({ abonne: true })
    await reabonnerPushSiAutorise(4)
    expect(subscribe).not.toHaveBeenCalled()
    expect(pushSubscribe).toHaveBeenCalledTimes(1)
  })

  it("n'affiche jamais d'invite : sans permission accordée, rien ne se passe", async () => {
    installerNavigateur({ permission: 'default' })
    const res = await reabonnerPushSiAutorise(4)
    expect(res.reason).toBe('denied')
    expect(window.Notification.requestPermission).not.toHaveBeenCalled()
    expect(pushSubscribe).not.toHaveBeenCalled()
  })

  it("respecte le push coupé par l'utilisateur sur cet appareil, et lui seul", async () => {
    installerNavigateur()
    noterChoixPush(false, 4)
    expect((await reabonnerPushSiAutorise(4)).reason).toBe('refus')
    expect(pushSubscribe).not.toHaveBeenCalled()
    // Poste partagé : le refus de l'un ne vaut pas pour l'autre.
    expect((await reabonnerPushSiAutorise(7)).ok).toBe(true)
  })

  it('le réactiver efface le refus', async () => {
    installerNavigateur()
    noterChoixPush(false, 4)
    noterChoixPush(true, 4)
    expect((await reabonnerPushSiAutorise(4)).ok).toBe(true)
  })

  it('une seule tentative par utilisateur et par page (Layout remonte à chaque navigation)', async () => {
    installerNavigateur()
    await reabonnerPushSiAutorise(4)
    await reabonnerPushSiAutorise(4)
    expect(pushSubscribe).toHaveBeenCalledTimes(1)
  })

  it("le réglage manuel s'applique à l'utilisateur connecté", async () => {
    installerNavigateur()
    await reabonnerPushSiAutorise(4)
    noterChoixPush(false)
    _reinitialiserTentativesPush()
    expect((await reabonnerPushSiAutorise(4)).reason).toBe('refus')
  })
})
