import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG39 — Écran Expérimentations : timeline de phases, bras avec posteriors
   (P(meilleur), estimation + bande de crédibilité), DecisionLog filtrable rendu
   « pourquoi le moteur a fait X » en FR + chiffres. Tous les nombres = ceux de
   l'API ENG12 mockée. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  decisionLog: vi.fn(),
  mde: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    experiments: {
      list: mocks.list, get: mocks.get, decisionLog: mocks.decisionLog,
      mde: mocks.mde,
    },
  },
}))

import ExperimentsScreen from './ExperimentsScreen'

const renderScreen = () => render(<MemoryRouter><ExperimentsScreen /></MemoryRouter>)

const EXP = {
  id: 3, nom: 'Test créatif toiture', metrique_label: 'Coût par lead', metrique_fmt: 'mad',
  phases: [
    { key: 'exploration', label: 'Exploration', statut: 'terminee', statut_display: 'Terminée' },
    { key: 'exploitation', label: 'Exploitation', statut: 'en_cours', statut_display: 'En cours' },
  ],
  bras: [
    { id: 1, nom: 'Créatif A — toiture', p_best: 0.72, mean: 88, ci_low: 80, ci_high: 96, allocation: 0.6 },
    { id: 2, nom: 'Créatif B — pompe', p_best: 0.28, mean: 104, ci_low: 92, ci_high: 120, allocation: 0.4 },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [{ id: 3, nom: 'Test créatif toiture' }] })
  mocks.get.mockResolvedValue({ data: EXP })
  mocks.decisionLog.mockResolvedValue({ data: [
    { id: 1, phase: 'exploration', quand: '2026-07-10', phase_label: 'Exploration',
      decision_fr: 'Le moteur a exploré les deux créatifs à parts égales pour récolter des preuves.',
      chiffres: { impressions: 4200 } },
    { id: 2, phase: 'exploitation', quand: '2026-07-14', phase_label: 'Exploitation',
      decision_fr: 'Le moteur a donné plus de budget au Créatif A car il a 72 % de chances d\'être le meilleur.',
      chiffres: { p_best: 0.72 } },
  ] })
  mocks.mde.mockResolvedValue({ data: {
    p: 0.02, volume: 300, cible_relative: 0.20, jours_pour_cible: 14,
    phrase_fr: 'Avec votre volume (~300 essais/bras/jour), il faut ~14 jour(s) pour détecter un effet de +20 % de façon fiable.',
    mde_par_horizon: [
      { jours: 7, mde_relatif_pct: 28.3 },
      { jours: 14, mde_relatif_pct: 20.0 },
      { jours: 28, mde_relatif_pct: 14.1 },
    ],
  } })
})

describe('ExperimentsScreen (ENG39)', () => {
  it('affiche la timeline des phases avec leurs statuts', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(3))
    const phases = await screen.findByTestId('ae-exp-phases')
    expect(phases).toHaveTextContent('Exploration')
    expect(phases).toHaveTextContent('Terminée')
    expect(phases).toHaveTextContent('Exploitation')
    expect(phases).toHaveTextContent('En cours')
  })

  it('affiche P(meilleur) et la bande de crédibilité de chaque bras avec les chiffres de l\'API', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    // P(meilleur) formaté depuis la fraction API (0.72 → 72 %).
    expect(await screen.findByTestId('ae-exp-pbest-1')).toHaveTextContent('72 %')
    expect(screen.getByTestId('ae-exp-pbest-2')).toHaveTextContent('28 %')
    // Estimation ponctuelle en MAD.
    expect(screen.getByTestId('ae-exp-mean-1')).toHaveTextContent('88 MAD')
    // Bande de crédibilité [bas ; haut].
    expect(screen.getByTestId('ae-exp-band-1')).toHaveTextContent('80 MAD – 96 MAD')
    // Le bras le plus probable est marqué favori.
    expect(screen.getByTestId('ae-exp-arm-best')).toHaveTextContent('Favori du moteur')
  })

  it('rend le DecisionLog en phrases FR lisibles + chiffres', async () => {
    renderScreen()
    expect(await screen.findByText(/plus de budget au Créatif A/)).toBeInTheDocument()
    // Chiffres exacts en chip.
    expect(screen.getByText('Le moteur a exploré les deux créatifs à parts égales pour récolter des preuves.'))
      .toBeInTheDocument()
    expect(screen.getAllByTestId('ae-exp-decision').length).toBe(2)
  })

  it('filtre le DecisionLog par phase', async () => {
    renderScreen()
    await screen.findByTestId('ae-exp-decision-filter')
    expect(screen.getAllByTestId('ae-exp-decision').length).toBe(2)
    fireEvent.change(screen.getByTestId('ae-exp-decision-filter'), { target: { value: 'exploitation' } })
    await waitFor(() => expect(screen.getAllByTestId('ae-exp-decision').length).toBe(1))
    expect(screen.getByText(/plus de budget au Créatif A/)).toBeInTheDocument()
  })

  it('affiche un état vide quand aucune expérimentation', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    renderScreen()
    expect(await screen.findByTestId('ae-exp-empty')).toBeInTheDocument()
  })

  it('PUB87 — affiche le calcul MDE (jours pour détecter +20 %) avant lancement', async () => {
    renderScreen()
    // Le panneau interroge l'API mde au montage avec les valeurs par défaut.
    await waitFor(() => expect(mocks.mde).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-mde-phrase'))
      .toHaveTextContent('~14 jour(s) pour détecter un effet de +20 %')
    expect(screen.getAllByTestId('ae-mde-horizon').length).toBe(3)
  })

  it('PUB87 — recalcule le MDE quand l\'opérateur change le volume', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.mde).toHaveBeenCalled())
    mocks.mde.mockClear()
    fireEvent.change(screen.getByTestId('ae-mde-volume'), { target: { value: '600' } })
    fireEvent.click(screen.getByTestId('ae-mde-compute'))
    await waitFor(() => expect(mocks.mde).toHaveBeenCalledWith(
      expect.objectContaining({ volume: '600' })))
  })
})
