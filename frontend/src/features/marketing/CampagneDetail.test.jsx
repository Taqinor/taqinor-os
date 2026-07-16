import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

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

  it("« Envoyer un test » appelle l'action envoyer-test et affiche le résultat", async () => {
    mocks.envoyerTest.mockResolvedValue({ data: { nb_envoyes: 2 } })
    renderScreen()
    await screen.findByText('Relance été')
    fireEvent.change(screen.getByTestId('campagne-test-adresses'),
      { target: { value: 'a@x.ma, b@x.ma' } })
    fireEvent.click(screen.getByTestId('campagne-envoyer-test'))
    await waitFor(() => expect(mocks.envoyerTest).toHaveBeenCalledWith(
      '7', { adresses_seed: ['a@x.ma', 'b@x.ma'] }))
    expect(await screen.findByTestId('campagne-test-resultat')).toBeInTheDocument()
  })

  it('le pré-check bloquant désactive la confirmation d\'envoi', async () => {
    mocks.precheck.mockResolvedValue({
      data: { bloquants: ['Domaine non authentifié'], avertissements: [] },
    })
    renderScreen()
    await screen.findByText('Relance été')
    fireEvent.click(screen.getByTestId('campagne-precheck-btn'))
    await screen.findByTestId('campagne-precheck-resultat')
    expect(screen.getByTestId('campagne-confirmer-envoi')).toBeDisabled()
  })

  it('le pré-check propre laisse confirmer l\'envoi', async () => {
    mocks.precheck.mockResolvedValue({ data: { bloquants: [], avertissements: [] } })
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
