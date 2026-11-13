import { describe, it, expect, vi, beforeAll, beforeEach, afterAll } from 'vitest'

/* AERR123 — une décision d'approbation prise depuis la notification push
   (`decider-push`) qui échoue (401 jeton expiré, réseau) n'était JAMAIS dite :
   `postApprovalToken` faisait `.catch(() => undefined)` sans lire `res.ok`, et
   la notification était déjà fermée. Le vrai `src/sw.js` est chargé avec les
   modules workbox bouchonnés et un `self` simulé. */

vi.mock('workbox-precaching', () => ({
  precacheAndRoute: vi.fn(), cleanupOutdatedCaches: vi.fn(), matchPrecache: vi.fn(),
}))
vi.mock('workbox-routing', () => ({ NavigationRoute: class {}, registerRoute: vi.fn() }))
vi.mock('workbox-strategies', () => ({ StaleWhileRevalidate: class {} }))
vi.mock('workbox-expiration', () => ({ ExpirationPlugin: class {} }))

const ecouteurs = {}
const showNotification = vi.fn(() => Promise.resolve())
const fetchMock = vi.fn()

beforeAll(async () => {
  vi.stubGlobal('self', {
    addEventListener: (type, fn) => { ecouteurs[type] = fn },
    registration: { showNotification },
    clients: { matchAll: vi.fn(() => Promise.resolve([])), claim: vi.fn() },
    location: { origin: 'https://erp.test' },
    __WB_MANIFEST: [],
  })
  vi.stubGlobal('fetch', fetchMock)
  await import('../../sw.js')
})
afterAll(() => { vi.unstubAllGlobals() })
beforeEach(() => { showNotification.mockClear(); fetchMock.mockReset() })

async function approuver() {
  const attentes = []
  ecouteurs.notificationclick({
    action: 'approve',
    notification: { data: { approval: { approveToken: 'jeton', rejectToken: 'r' } }, close: vi.fn() },
    waitUntil: (p) => attentes.push(p),
  })
  await Promise.all(attentes)
}

describe('sw.js — decider-push (AERR123)', () => {
  it('decider-push 401 : notification d’échec vers /approbations', async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 401 })
    await approuver()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ token: 'jeton' })
    expect(showNotification).toHaveBeenCalledTimes(1)
    expect(showNotification.mock.calls[0][0]).toBe('Décision non enregistrée')
    expect(showNotification.mock.calls[0][1].data.link).toBe('/approbations')
  })

  it('réponse 2xx : aucune notification', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 200 })
    await approuver()
    expect(showNotification).not.toHaveBeenCalled()
  })

  it('rejet réseau : même notification d’échec', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await approuver()
    expect(showNotification).toHaveBeenCalledTimes(1)
    expect(showNotification.mock.calls[0][0]).toBe('Décision non enregistrée')
  })
})
