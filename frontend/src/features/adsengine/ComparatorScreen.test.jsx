import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB52 — Comparateur côte-à-côte : sélectionner 2-4 ads/campagnes → colonnes
   alignées, écarts en surbrillance (jamais recalculés, uniquement les
   chiffres déjà renvoyés par l'API ads-cockpit / campaigns). */

const mocks = vi.hoisted(() => ({
  adsCockpit: vi.fn(),
  campaignsList: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: { adsCockpit: mocks.adsCockpit },
    campaigns: { list: mocks.campaignsList },
  },
}))

import ComparatorScreen from './ComparatorScreen'

const renderScreen = () => render(<MemoryRouter><ComparatorScreen /></MemoryRouter>)

const ADS = [
  { id: 1, nom: 'Reel toiture v1', statut_display: 'Actif', depense_mad: '1500', nb_leads: 12,
    cpl_mad: '125', conversations: 8, signatures: 2, cost_per_signature_mad: '750', frequency: '1.8' },
  { id: 2, nom: 'Statique prix', statut_display: 'Actif', depense_mad: '900', nb_leads: 20,
    cpl_mad: '45', conversations: 15, signatures: 4, cost_per_signature_mad: '225', frequency: '3.6' },
  { id: 3, nom: 'Carousel avant-après', statut_display: 'En pause', depense_mad: '400', nb_leads: 3,
    cpl_mad: '133', conversations: 2, signatures: 0, cost_per_signature_mad: null, frequency: '4.1' },
]

const CAMPAIGNS = [
  { id: 11, name: 'Campagne Résidentiel Casa', status: 'ACTIVE', objective: 'OUTCOME_LEADS', budget: 5000 },
  { id: 12, name: 'Campagne Pompage Agadir', status: 'PAUSED', objective: 'OUTCOME_LEADS', budget: 2000 },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.adsCockpit.mockResolvedValue({ data: ADS })
  mocks.campaignsList.mockResolvedValue({ data: CAMPAIGNS })
})

describe('ComparatorScreen (PUB52)', () => {
  it('charge le pool d\'ads par défaut', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.adsCockpit).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-comparator-pick-1')).toHaveTextContent('Reel toiture v1')
    expect(screen.getByTestId('ae-comparator-pick-2')).toHaveTextContent('Statique prix')
  })

  it('moins de 2 sélections → message plutôt qu\'un tableau', async () => {
    renderScreen()
    await screen.findByTestId('ae-comparator-pick-1')
    fireEvent.click(screen.getByTestId('ae-comparator-pick-1'))
    expect(screen.getByTestId('ae-comparator-need-more')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-comparator-table')).toBeNull()
  })

  it('2 sélections alignent les métriques en colonnes', async () => {
    renderScreen()
    await screen.findByTestId('ae-comparator-pick-1')
    fireEvent.click(screen.getByTestId('ae-comparator-pick-1'))
    fireEvent.click(screen.getByTestId('ae-comparator-pick-2'))
    const table = await screen.findByTestId('ae-comparator-table')
    expect(table).toHaveTextContent('Reel toiture v1')
    expect(table).toHaveTextContent('Statique prix')
    expect(screen.getByTestId('ae-comparator-row-cpl_mad')).toHaveTextContent('Coût par lead')
  })

  it('met en surbrillance la meilleure (vert) et la pire (rouge) valeur d\'une ligne', async () => {
    renderScreen()
    await screen.findByTestId('ae-comparator-pick-1')
    fireEvent.click(screen.getByTestId('ae-comparator-pick-1')) // CPL 125
    fireEvent.click(screen.getByTestId('ae-comparator-pick-2')) // CPL 45 (meilleur, plus bas)
    await screen.findByTestId('ae-comparator-table')
    // CPL : plus bas = meilleur → ad 2 (45) en vert, ad 1 (125) en rouge.
    expect(screen.getByTestId('ae-comparator-best-cpl_mad-2')).toBeInTheDocument()
    expect(screen.getByTestId('ae-comparator-worst-cpl_mad-1')).toBeInTheDocument()
    // Leads : plus haut = meilleur → ad 2 (20) en vert, ad 1 (12) en rouge.
    expect(screen.getByTestId('ae-comparator-best-nb_leads-2')).toBeInTheDocument()
    expect(screen.getByTestId('ae-comparator-worst-nb_leads-1')).toBeInTheDocument()
  })

  it('un maximum de 4 sélections : la 5e est désactivée', async () => {
    renderScreen()
    await screen.findByTestId('ae-comparator-pick-1')
    fireEvent.click(screen.getByTestId('ae-comparator-pick-1'))
    fireEvent.click(screen.getByTestId('ae-comparator-pick-2'))
    fireEvent.click(screen.getByTestId('ae-comparator-pick-3'))
    expect(screen.getByText(/3\/4/)).toBeInTheDocument()
  })

  it('la recherche filtre le pool', async () => {
    renderScreen()
    await screen.findByTestId('ae-comparator-pick-1')
    fireEvent.change(screen.getByTestId('ae-comparator-search'), { target: { value: 'carousel' } })
    expect(screen.queryByTestId('ae-comparator-pick-1')).toBeNull()
    expect(screen.getByTestId('ae-comparator-pick-3')).toBeInTheDocument()
  })

  it('bascule sur les campagnes (autre source de données)', async () => {
    renderScreen()
    await screen.findByTestId('ae-comparator-pick-1')
    fireEvent.click(screen.getByTestId('ae-comparator-source-campaigns'))
    await waitFor(() => expect(mocks.campaignsList).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-comparator-pick-11')).toHaveTextContent('Campagne Résidentiel Casa')
  })
})
