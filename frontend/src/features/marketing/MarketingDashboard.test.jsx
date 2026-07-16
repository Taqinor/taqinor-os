import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import {
  campagnesActives, tauxOuvertureMoyen30j, leadsEngagesDuMois, roiCumulePct,
} from './marketingDashboard'

describe('marketingDashboard — logique pure des 4 KPI (NTMKT1)', () => {
  it('campagnesActives compte en_file/envoi_en_cours seulement', () => {
    const campagnes = [
      { statut: 'brouillon' }, { statut: 'en_file' },
      { statut: 'envoi_en_cours' }, { statut: 'envoyee' }, { statut: 'annulee' },
    ]
    expect(campagnesActives(campagnes)).toBe(2)
    expect(campagnesActives([])).toBe(0)
    expect(campagnesActives(null)).toBe(0)
  })

  it("tauxOuvertureMoyen30j pondère par nb_envois sur les campagnes envoyées récentes", () => {
    const now = new Date('2026-07-16T12:00:00Z')
    const campagnes = [
      // dans la fenêtre : 100 envois, 20 ouvertures
      { envoyee_le: '2026-07-10T00:00:00Z', nb_envois: 100, nb_ouvertures: 20 },
      // dans la fenêtre : 50 envois, 25 ouvertures
      { envoyee_le: '2026-07-01T00:00:00Z', nb_envois: 50, nb_ouvertures: 25 },
      // hors fenêtre (> 30j) : ignorée
      { envoyee_le: '2026-01-01T00:00:00Z', nb_envois: 1000, nb_ouvertures: 1000 },
      // jamais envoyée : ignorée
      { envoyee_le: null, nb_envois: 10, nb_ouvertures: 10 },
    ]
    // (20 + 25) / (100 + 50) = 45/150 = 30 %
    expect(tauxOuvertureMoyen30j(campagnes, { now })).toBe(30)
  })

  it('tauxOuvertureMoyen30j renvoie 0 sans campagne éligible (jamais NaN)', () => {
    expect(tauxOuvertureMoyen30j([], { now: new Date() })).toBe(0)
    expect(tauxOuvertureMoyen30j(
      [{ envoyee_le: null }], { now: new Date() })).toBe(0)
  })

  it('leadsEngagesDuMois compte les contacts distincts ouverts/cliqués ce mois-ci', () => {
    const now = new Date('2026-07-16T12:00:00Z')
    const envois = [
      { statut: 'ouvert', contact_ref: 'lead:1', date_creation: '2026-07-05T00:00:00Z' },
      { statut: 'clique', contact_ref: 'lead:1', date_creation: '2026-07-06T00:00:00Z' }, // doublon contact
      { statut: 'clique', contact_ref: 'lead:2', date_creation: '2026-07-08T00:00:00Z' },
      { statut: 'queued', contact_ref: 'lead:3', date_creation: '2026-07-08T00:00:00Z' }, // pas engagé
      { statut: 'ouvert', contact_ref: 'lead:4', date_creation: '2026-06-01T00:00:00Z' }, // mois précédent
    ]
    expect(leadsEngagesDuMois(envois, { now })).toBe(2)
  })

  it('roiCumulePct agrège coût/revenu de plusieurs campagnes', () => {
    const entries = [
      { cout_mad: '1000', revenu_ttc_mad: '1500' },
      { cout_mad: '500', revenu_ttc_mad: '400' },
    ]
    // coût total 1500, revenu total 1900 → (1900-1500)/1500*100 = 26.7%
    expect(roiCumulePct(entries)).toBeCloseTo(26.7, 1)
  })

  it('roiCumulePct renvoie 0 sans coût engagé (pas de division par zéro)', () => {
    expect(roiCumulePct([])).toBe(0)
    expect(roiCumulePct([{ cout_mad: '0', revenu_ttc_mad: '500' }])).toBe(0)
  })
})

// ── Rendu smoke de l'écran (API mockée — aucun appel réseau réel) ──
const mocks = vi.hoisted(() => ({
  campagnesList: vi.fn(),
  envoisList: vi.fn(),
  roi: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      if (Array.isArray(data)) return data
      if (Array.isArray(data?.results)) return data.results
      return []
    },
    campagnes: { list: mocks.campagnesList, roi: mocks.roi },
    envoisCampagne: { list: mocks.envoisList },
  },
}))

import marketingApi from '../../api/marketingApi'
import MarketingDashboard from './MarketingDashboard'

function renderScreen() {
  return render(
    <MemoryRouter>
      <MarketingDashboard />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.campagnesList.mockResolvedValue({ data: [] })
  mocks.envoisList.mockResolvedValue({ data: [] })
})

describe('MarketingDashboard (smoke)', () => {
  it('affiche les 4 KPI après chargement, sans exposer prix_achat', async () => {
    mocks.campagnesList.mockResolvedValue({
      data: [
        { id: 1, statut: 'en_file' },
        { id: 2, statut: 'envoyee', envoyee_le: new Date().toISOString(), nb_envois: 10, nb_ouvertures: 5 },
      ],
    })
    mocks.envoisList.mockResolvedValue({ data: [] })
    mocks.roi.mockResolvedValue({ data: { cout_mad: '100', revenu_ttc_mad: '200' } })

    renderScreen()
    await waitFor(() => expect(marketingApi.campagnes.list).toHaveBeenCalled())
    expect(await screen.findByTestId('mkt-kpi-campagnes-actives')).toBeInTheDocument()
    expect(screen.getByTestId('mkt-kpi-taux-ouverture')).toBeInTheDocument()
    expect(screen.getByTestId('mkt-kpi-leads-engages')).toBeInTheDocument()
    expect(screen.getByTestId('mkt-kpi-roi-cumule')).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/prix_achat/i)
  })

  it('un échec réseau affiche un message plutôt que de rester bloqué', async () => {
    mocks.campagnesList.mockRejectedValue(new Error('500'))
    renderScreen()
    await waitFor(() => expect(screen.queryByText(/impossible/i)).toBeInTheDocument())
  })
})
