// ODY10 — Tests du chargeur de badges : UN appel agrégé, cache court, échec
// silencieux, jamais de ré-agrégation côté client.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { kpiBadgesMock } = vi.hoisted(() => ({
  kpiBadgesMock: vi.fn(() => Promise.resolve({ data: { badges: [] } })),
}))
vi.mock('../../api/reportingApi', () => ({ default: { kpiBadges: kpiBadgesMock } }))

import { chargerBadges, indexerBadges, _resetBadgeCache } from './useAppBadges'

describe('ODY10 — useAppBadges', () => {
  beforeEach(() => {
    kpiBadgesMock.mockClear()
    kpiBadgesMock.mockImplementation(() => Promise.resolve({ data: { badges: [] } }))
    _resetBadgeCache()
  })

  it('indexerBadges : liste serveur → dictionnaire par clé d’app', () => {
    const out = indexerBadges({
      badges: [
        { app: 'crm', valeur: 3, label: 'Relances', unite: 'leads' },
        { app: 'ventes', valeur: 1, label: 'Devis expirants' },
      ],
    })
    expect(out.crm).toEqual({ valeur: 3, label: 'Relances', unite: 'leads' })
    expect(out.ventes.valeur).toBe(1)
  })

  it('indexerBadges : entrées malformées ignorées, jamais un plantage', () => {
    expect(indexerBadges(undefined)).toEqual({})
    expect(indexerBadges({ badges: 'pas une liste' })).toEqual({})
    expect(indexerBadges({ badges: [{ app: 'x' }, { valeur: 2 }, null] })).toEqual({})
  })

  it('UN SEUL appel réseau même pour deux consommateurs simultanés', async () => {
    const p1 = chargerBadges()
    const p2 = chargerBadges()
    await Promise.all([p1, p2])
    expect(kpiBadgesMock).toHaveBeenCalledTimes(1)
  })

  it('cache court : un second chargement immédiat ne rappelle pas le serveur', async () => {
    await chargerBadges()
    await chargerBadges()
    expect(kpiBadgesMock).toHaveBeenCalledTimes(1)
  })

  it('échec réseau : dictionnaire vide, jamais une exception propagée', async () => {
    kpiBadgesMock.mockImplementationOnce(() => Promise.reject(new Error('offline')))
    await expect(chargerBadges()).resolves.toEqual({})
  })

  it('l’appel vise l’endpoint fédéré ARC40 (aucune ré-agrégation par app)', async () => {
    await chargerBadges()
    expect(kpiBadgesMock).toHaveBeenCalledTimes(1)
    expect(kpiBadgesMock).toHaveBeenCalledWith()
  })
})
