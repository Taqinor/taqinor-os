import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { computeAbComparatif } from './campagneDetail'

// ── Vitest ne ramasse que `*.test.jsx` (voir vitest.config.js) — la logique
// pure de `campagneDetail.js` est donc testée ICI plutôt que dans un fichier
// `.test.js` séparé (qui ne serait exécuté par aucun des deux runners).
describe('computeAbComparatif (NTMKT3, logique pure)', () => {
  it('répartit les envois en 3 lots (A/B/reste) avec taux corrects', () => {
    const envois = [
      { variante_ab: 'a', statut: 'ouvert' },
      { variante_ab: 'a', statut: 'queued' },
      { variante_ab: 'b', statut: 'clique' },
      { variante_ab: 'b', statut: 'clique' },
      { variante_ab: '', statut: 'envoye' },
    ]
    const result = computeAbComparatif(envois)
    expect(result.a.total).toBe(2)
    expect(result.a.ouverts).toBe(1)
    expect(result.a.taux_ouverture_pct).toBe(50)
    expect(result.b.total).toBe(2)
    expect(result.b.cliques).toBe(2)
    expect(result.b.taux_clic_pct).toBe(100)
    expect(result.reste.total).toBe(1)
  })

  it('renvoie des lots à 0 sans division par zéro pour un tableau vide', () => {
    const result = computeAbComparatif([])
    expect(result.a).toEqual({
      total: 0, ouverts: 0, cliques: 0, taux_ouverture_pct: 0, taux_clic_pct: 0,
    })
    expect(result.b.total).toBe(0)
    expect(result.reste.total).toBe(0)
  })

  it('accepte null/undefined en entrée', () => {
    expect(computeAbComparatif(null).a.total).toBe(0)
    expect(computeAbComparatif(undefined).reste.total).toBe(0)
  })

  it('un envoi ouvert_le sans statut ouvert compte quand même comme ouvert', () => {
    const envois = [{ variante_ab: 'a', statut: 'envoye', ouvert_le: '2026-07-10T00:00:00Z' }]
    const result = computeAbComparatif(envois)
    expect(result.a.ouverts).toBe(1)
  })
})

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  envoisList: vi.fn(),
  envoyerTest: vi.fn(),
  precheck: vi.fn(),
  envoyer: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    campagnes: {
      get: mocks.get, envoyerTest: mocks.envoyerTest,
      precheck: mocks.precheck, envoyer: mocks.envoyer,
    },
    envoisCampagne: { list: mocks.envoisList },
  },
}))

import CampagneDetail from './CampagneDetail'

const renderScreen = () => render(
  <MemoryRouter initialEntries={['/marketing/campagnes/7']}>
    <Routes>
      <Route path="/marketing/campagnes/:id" element={<CampagneDetail />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({
    data: {
      id: 7, nom: 'Relance été', statut: 'envoyee', statut_display: 'Envoyée',
      nb_envois: 10, taux_ouverture_pct: 30, taux_clic_pct: 10,
      taux_desinscription_pct: 0,
    },
  })
  mocks.envoisList.mockResolvedValue({
    data: [
      { id: 1, destinataire: 'a@x.ma', statut: 'ouvert', statut_display: 'Ouvert' },
      { id: 2, destinataire: 'b@x.ma', statut: 'queued', statut_display: 'En file' },
    ],
  })
})

describe('CampagneDetail', () => {
  it('affiche les KPI et la trace par destinataire', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('7'))
    expect(mocks.envoisList).toHaveBeenCalledWith({ campagne: '7' })
    expect(await screen.findByText('Relance été')).toBeInTheDocument()
    expect(screen.getByText('a@x.ma')).toBeInTheDocument()
    expect(screen.getByText('b@x.ma')).toBeInTheDocument()
  })

  it('le filtre de statut réduit la trace affichée', async () => {
    renderScreen()
    await screen.findByText('a@x.ma')
    fireEvent.change(screen.getByTestId('envois-filtre-statut'),
      { target: { value: 'ouvert' } })
    expect(screen.getByText('a@x.ma')).toBeInTheDocument()
    expect(screen.queryByText('b@x.ma')).toBeNull()
  })

  it("« Envoyer un test » appelle l'action envoyer-test et affiche le nombre réel de seeds (PACT153)", async () => {
    // envoyer_test_campagne (apps/compta/services.py:8312-8326) renvoie
    // {seeds, corps_fusionne} — jamais nb_envoyes/envoyes.
    mocks.envoyerTest.mockResolvedValue({
      data: { seeds: ['a@x.ma', 'b@x.ma'], corps_fusionne: 'Bonjour...' },
    })
    renderScreen()
    await screen.findByText('Relance été')
    fireEvent.change(screen.getByTestId('campagne-test-adresses'),
      { target: { value: 'a@x.ma, b@x.ma' } })
    fireEvent.click(screen.getByTestId('campagne-envoyer-test'))
    await waitFor(() => expect(mocks.envoyerTest).toHaveBeenCalledWith(
      '7', { adresses_seed: ['a@x.ma', 'b@x.ma'] }))
    expect(await screen.findByTestId('campagne-test-resultat'))
      .toHaveTextContent('Test envoyé (2 destinataire(s) de test).')
  })

  it('le pré-check bloquant (bloque=true) désactive la confirmation d\'envoi (PACT153)', async () => {
    // precheck_sante_campagne (apps/compta/services.py:8342-8393) renvoie
    // {bloque, avertissements} — jamais un tableau `bloquants` séparé.
    mocks.precheck.mockResolvedValue({
      data: {
        bloque: true,
        avertissements: ['Lien de désinscription manquant — envoi email bloqué (loi 09-08).'],
      },
    })
    renderScreen()
    await screen.findByText('Relance été')
    fireEvent.click(screen.getByTestId('campagne-precheck-btn'))
    await screen.findByTestId('campagne-precheck-resultat')
    expect(screen.getByTestId('campagne-confirmer-envoi')).toBeDisabled()
    expect(screen.getByText(/Lien de désinscription manquant/)).toBeInTheDocument()
  })

  it('le pré-check propre (bloque=false) laisse confirmer l\'envoi (PACT153)', async () => {
    mocks.precheck.mockResolvedValue({ data: { bloque: false, avertissements: [] } })
    mocks.envoyer.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('Relance été')
    fireEvent.click(screen.getByTestId('campagne-precheck-btn'))
    await screen.findByTestId('campagne-precheck-resultat')
    expect(screen.getByTestId('campagne-confirmer-envoi')).not.toBeDisabled()
    fireEvent.click(screen.getByTestId('campagne-confirmer-envoi'))
    await waitFor(() => expect(mocks.envoyer).toHaveBeenCalledWith('7', {}))
  })
})

// ── NTMKT3 — panneau comparatif A/B (XMKT14) ──
describe('CampagneDetail — comparatif A/B (NTMKT3)', () => {
  it("n'affiche aucun panneau A/B sans configuration ab_test", async () => {
    renderScreen()
    await screen.findByText('Relance été')
    expect(screen.queryByTestId('campagne-ab-comparatif')).toBeNull()
  })

  it('affiche le comparatif A vs B vs reste + le gagnant quand décidé', async () => {
    mocks.get.mockResolvedValue({
      data: {
        id: 7, nom: 'Relance été', statut: 'envoyee', statut_display: 'Envoyée',
        nb_envois: 10, taux_ouverture_pct: 30, taux_clic_pct: 10,
        taux_desinscription_pct: 0,
        ab_test: { objet_b: 'Objet B', corps_b: 'Corps B' },
        ab_gagnant: 'b',
      },
    })
    mocks.envoisList.mockResolvedValue({
      data: [
        { id: 1, destinataire: 'a@x.ma', statut: 'ouvert', variante_ab: 'a' },
        { id: 2, destinataire: 'b@x.ma', statut: 'clique', variante_ab: 'b' },
      ],
    })
    renderScreen()
    const panel = await screen.findByTestId('campagne-ab-comparatif')
    expect(panel).toHaveTextContent('Gagnant : variante B')
    expect(screen.getByTestId('campagne-ab-ligne-a')).toHaveTextContent('1')
    expect(screen.getByTestId('campagne-ab-ligne-b')).toHaveTextContent('1')
  })
})
