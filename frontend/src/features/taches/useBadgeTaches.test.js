import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('../../api/axios')).default
const {
  useBadgeTaches, poserBadgeApp, reinitialiserBadgeTaches, chargerBadgeTaches, ajusterBadgeATrier,
} = await import('./useBadgeTaches')

/* NOUVEAU FICHIER DE TEST : premier test de ce domaine dans le nouveau module (pastille). Le
   serveur est mocké sur `badge.json` et `aujourdhui.json` ; la pastille de l'icône se pose par
   `navigator.setAppBadge` seulement s'il existe, 0 l'efface, et seules les tâches GARDÉES comptent
   (A16-N5 : c'est le `n` du serveur, jamais recalculé ici). */

const contrat = (nom) => structuredClone(exempleContrat('taches', nom))

function servir({ badge = contrat('badge'), journee = contrat('aujourdhui') } = {}) {
  api.get.mockImplementation((url) => {
    if (url === '/taches/badge/') return Promise.resolve({ data: badge })
    if (url === '/taches/aujourdhui/') return Promise.resolve({ data: journee })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBadgeTaches()
  navigator.setAppBadge = vi.fn(() => Promise.resolve())
  navigator.clearAppBadge = vi.fn(() => Promise.resolve())
})

describe('TCH101 — useBadgeTaches', () => {
  it('lit n (badge.json) et le compte À trier (a_trier.boite_reception), et pose la pastille de l\'icône', async () => {
    servir()
    const { result } = renderHook(() => useBadgeTaches())
    expect(result.current).toMatchObject({ n: 0, aTrier: 0 }) // jamais bloquant : zéros d'abord
    await waitFor(() => expect(result.current.n).toBe(3))
    expect(result.current.jour).toBe('2026-11-17')
    expect(result.current.aTrier).toBe(contrat('aujourdhui').a_trier.boite_reception)
    expect(navigator.setAppBadge).toHaveBeenCalledWith(3)
    expect(navigator.clearAppBadge).not.toHaveBeenCalled()
  })

  it('F3 — badge/ porte a_trier : une seule requête, aujourdhui/ n\'est pas lu', async () => {
    servir({ badge: { n: 2, jour: '2026-11-17', a_trier: 4 } })
    const { result } = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(result.current.n).toBe(2))
    expect(result.current.aTrier).toBe(4)
    expect(api.get.mock.calls.map(([url]) => url)).toEqual(['/taches/badge/'])
  })

  it('F3 — sans a_trier dans badge/ (serveur plus ancien), repli sur aujourdhui/', async () => {
    servir({ badge: { n: 2, jour: '2026-11-17' } })
    const { result } = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(result.current.aTrier).toBe(contrat('aujourdhui').a_trier.boite_reception))
    expect(api.get.mock.calls.map(([url]) => url).sort()).toEqual(['/taches/aujourdhui/', '/taches/badge/'])
  })

  it('n = 0 efface la pastille de l\'icône (clearAppBadge)', async () => {
    servir({ badge: { n: 0, jour: '2026-11-17' } })
    const { result } = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(navigator.clearAppBadge).toHaveBeenCalledTimes(1))
    expect(result.current.n).toBe(0)
    expect(navigator.setAppBadge).not.toHaveBeenCalled()
  })

  it('sans setAppBadge dans le navigateur, rien ne casse et les nombres sont lus', async () => {
    delete navigator.setAppBadge
    delete navigator.clearAppBadge
    servir()
    const { result } = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(result.current.n).toBe(3))
    expect(await poserBadgeApp(3)).toBe(false)
  })

  it('un refus de setAppBadge est absorbé (la pastille de l\'icône est un plus)', async () => {
    navigator.setAppBadge = vi.fn(() => Promise.reject(new Error('refusé')))
    servir()
    const { result } = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(result.current.n).toBe(3))
    expect(result.current.erreur).toBe(false)
  })

  it('un échec du serveur garde les derniers nombres et le dit', async () => {
    servir()
    const premier = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(premier.result.current.n).toBe(3))
    api.get.mockRejectedValue(new Error('hors ligne'))
    await act(async () => { window.dispatchEvent(new Event('online')) })
    await waitFor(() => expect(premier.result.current.erreur).toBe(true))
    expect(premier.result.current.n).toBe(3)
  })

  it('deux montages partagent la même requête ; actif:false ne frappe rien', async () => {
    servir()
    const a = renderHook(() => useBadgeTaches())
    const b = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(a.result.current.n).toBe(3))
    await waitFor(() => expect(b.result.current.n).toBe(3))
    expect(api.get.mock.calls.filter(([url]) => url === '/taches/badge/')).toHaveLength(1)
    vi.clearAllMocks()
    reinitialiserBadgeTaches()
    const inactif = renderHook(() => useBadgeTaches({ actif: false }))
    expect(inactif.result.current).toMatchObject({ n: 0, aTrier: 0 })
    expect(api.get).not.toHaveBeenCalled()
  })
})

describe('R2-024 — la pastille d\'À trier suit les gestes tout de suite', () => {
  it('ajusterBadgeATrier corrige la pastille aussitôt, la relecture forcée confirme', async () => {
    servir({ badge: { n: 2, jour: '2026-11-17', a_trier: 4 } })
    const { result } = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(result.current.aTrier).toBe(4))
    act(() => { ajusterBadgeATrier(-2) })
    expect(result.current.aTrier).toBe(2) // avant tout aller-retour
    servir({ badge: { n: 2, jour: '2026-11-17', a_trier: 2 } })
    await act(async () => { await chargerBadgeTaches({ force: true }) })
    expect(result.current.aTrier).toBe(2)
    act(() => { ajusterBadgeATrier(-5) })
    expect(result.current.aTrier).toBe(0) // jamais négative
  })

  it('une relecture forcée demandée pendant une lecture en vol relit APRÈS elle (jamais le nombre d\'avant le geste)', async () => {
    let rendre
    api.get.mockImplementationOnce(() => new Promise((resolve) => { rendre = () => resolve({ data: { n: 0, jour: '2026-11-17', a_trier: 4 } }) }))
    api.get.mockImplementation(() => Promise.resolve({ data: { n: 0, jour: '2026-11-17', a_trier: 2 } }))
    const enVol = chargerBadgeTaches()
    const forcee = chargerBadgeTaches({ force: true })
    rendre()
    await enVol
    const apres = await forcee
    expect(apres.aTrier).toBe(2)
    expect(api.get.mock.calls.filter(([url]) => url === '/taches/badge/')).toHaveLength(2)
  })

  it('une création (saisie, collage, file rejouée) relit la pastille, sur tous les écrans', async () => {
    servir({ badge: { n: 0, jour: '2026-11-17', a_trier: 3 } })
    const { result } = renderHook(() => useBadgeTaches())
    await waitFor(() => expect(result.current.aTrier).toBe(3))
    servir({ badge: { n: 0, jour: '2026-11-17', a_trier: 4 } })
    await act(async () => { window.dispatchEvent(new CustomEvent('taqinor:taches:creees', { detail: {} })) })
    await waitFor(() => expect(result.current.aTrier).toBe(4))
  })

  it('sans lecture préalable, ajusterBadgeATrier ne fabrique aucun nombre', () => {
    expect(() => ajusterBadgeATrier(-1)).not.toThrow()
    const { result } = renderHook(() => useBadgeTaches({ actif: false }))
    expect(result.current.aTrier).toBe(0)
  })
})
