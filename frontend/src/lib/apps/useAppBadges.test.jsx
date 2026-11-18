// ODY10 — Tests du chargeur de badges : UN appel agrégé, cache court, échec
// silencieux, jamais de ré-agrégation côté client.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

const { kpiBadgesMock, tachesApiMock } = vi.hoisted(() => ({
  kpiBadgesMock: vi.fn(() => Promise.resolve({ data: { badges: [] } })),
  tachesApiMock: {
    lireBadge: vi.fn(() => Promise.resolve({ data: { n: 3, jour: '2026-11-17' } })),
    lireAujourdhui: vi.fn(() => Promise.resolve({ data: { a_trier: { boite_reception: 2 } } })),
  },
}))
vi.mock('../../api/reportingApi', () => ({ default: { kpiBadges: kpiBadgesMock } }))
// TCH124 — la pastille personnelle de Tâches lit `badge/` et Aujourd'hui (mock au niveau du client).
vi.mock('../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...tachesApiMock }))

import { chargerBadges, indexerBadges, _resetBadgeCache, useAppBadges, badgePersonnel } from './useAppBadges'
import { reinitialiserBadgeTaches } from '../../features/taches/useBadgeTaches'

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

// ADRG141 — kpi-federes est IsResponsableOrAdmin : un Viewer ne l'appelle pas.
describe('ADRG141 — badges selon le palier', () => {
  function Sonde() { useAppBadges(); return null }
  const monter = (auth) => {
    const store = configureStore({ reducer: { auth: (state = auth) => state } })
    return render(<Provider store={store}><Sonde /></Provider>)
  }
  beforeEach(() => { cleanup(); kpiBadgesMock.mockClear(); _resetBadgeCache() })

  it('Viewer : aucun GET badges', async () => {
    monter({ role: 'normal', role_nom: 'Viewer', permissions: ['ventes_voir', 'crm_voir'] })
    await Promise.resolve()
    expect(kpiBadgesMock).not.toHaveBeenCalled()
  })

  it('Commercial terrain : aucun appel (responsable sans code reporting_*)', async () => {
    monter({ role: 'responsable', role_nom: 'Commercial terrain', permissions: ['ventes_voir', 'devis_gerer', 'crm_gerer'] })
    await Promise.resolve()
    expect(kpiBadgesMock).not.toHaveBeenCalled()
  })

  it('responsable avec un code reporting_* : badges lus', async () => {
    monter({ role: 'responsable', role_nom: 'Responsable', permissions: ['devis_gerer', 'reporting_voir'] })
    await Promise.resolve()
    expect(kpiBadgesMock).toHaveBeenCalledTimes(1)
  })

  it('Directeur : badges lus', async () => {
    monter({ role: 'admin', role_nom: 'Directeur', permissions: ['ventes_voir'] })
    await Promise.resolve()
    expect(kpiBadgesMock).toHaveBeenCalledTimes(1)
  })
})

// TCH124 — badge PERSONNEL de l'app Tâches : pur, puis fusionné au fédéré sous le droit `taches_voir`.
describe('TCH124 — badgePersonnel', () => {
  it('« taches » : le nombre de gardées ouvertes ; 0, inconnu ou autre app → null', () => {
    expect(badgePersonnel('taches', { n: 3 })).toEqual({ valeur: 3, label: 'Tâches du jour', unite: 'tâches' })
    expect(badgePersonnel('taches', { n: 0 })).toBeNull()
    expect(badgePersonnel('taches', {})).toBeNull()
    expect(badgePersonnel('taches')).toBeNull()
    expect(badgePersonnel('crm', { n: 3 })).toBeNull()
  })

  it('sans le droit taches_voir, aucune requête Tâches ; avec, la tuile « taches » apparaît', async () => {
    let vu = null
    function Sonde() { vu = useAppBadges(); return null }
    const monter = (auth) => render(
      <Provider store={configureStore({ reducer: { auth: (state = auth) => state } })}><Sonde /></Provider>,
    )
    cleanup(); kpiBadgesMock.mockClear(); _resetBadgeCache(); reinitialiserBadgeTaches()
    monter({ role: 'normal', role_nom: 'Viewer', permissions: ['ventes_voir'] })
    await Promise.resolve()
    expect(tachesApiMock.lireBadge).not.toHaveBeenCalled()
    cleanup()
    monter({ role: 'normal', role_nom: 'Viewer', permissions: ['taches_voir'] })
    await waitFor(() => expect(vu.taches).toEqual({ valeur: 3, label: 'Tâches du jour', unite: 'tâches' }))
  })
})
