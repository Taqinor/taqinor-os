import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG44 — Visionneuse de simulation (rejeu ADSENG36) : verdicts par scénario,
   allocations dans le temps (budget par bras/étape), décisions annotées FR +
   chiffres. Tous les nombres = ceux du rapport de simulation mocké. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: { simulations: { list: mocks.list, get: mocks.get } },
}))

import SimulationScreen from './SimulationScreen'

const renderScreen = () => render(<MemoryRouter><SimulationScreen /></MemoryRouter>)

// Forme du rapport ADSENG36 supposée (mockée).
const REPORT = {
  id: 7, nom: 'Lancement solaire', cree_le: '2026-07-14',
  scenarios: [
    { key: 'base', nom: 'Scénario de base', verdict: 'gagnant', verdict_display: 'Gagnant',
      resume_fr: 'Coût par signature en baisse de 18 %.' },
    { key: 'pessimiste', nom: 'Scénario pessimiste', verdict: 'perdant', verdict_display: 'Perdant',
      resume_fr: 'Dépassement du plafond mensuel.' },
  ],
  allocations: [
    { etape: 1, label: 'Semaine 1', bras: [
      { nom: 'Créatif A', budget_mad: 600 }, { nom: 'Créatif B', budget_mad: 400 } ] },
    { etape: 2, label: 'Semaine 2', bras: [
      { nom: 'Créatif A', budget_mad: 800 }, { nom: 'Créatif B', budget_mad: 200 } ] },
  ],
  decisions: [
    { id: 1, etape: 2, label: 'Semaine 2',
      decision_fr: 'Le moteur a déplacé 200 MAD vers le Créatif A (meilleur coût par réponse).',
      chiffres: { transfert_mad: 200 } },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [{ id: 7, nom: 'Lancement solaire', cree_le: '2026-07-14' }] })
  mocks.get.mockResolvedValue({ data: REPORT })
})

describe('SimulationScreen (ENG44)', () => {
  it('charge et lit un rapport de simulation (auto-sélection du premier run)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(7))
    expect(await screen.findByTestId('ae-sim-report')).toBeInTheDocument()
  })

  it('affiche le verdict par scénario', async () => {
    renderScreen()
    await screen.findByTestId('ae-sim-report')
    const scenarios = screen.getAllByTestId('ae-sim-scenario')
    expect(scenarios.length).toBe(2)
    expect(scenarios[0]).toHaveTextContent('Scénario de base')
    expect(scenarios[0]).toHaveTextContent('Gagnant')
    expect(scenarios[1]).toHaveTextContent('Perdant')
  })

  it('affiche les allocations dans le temps avec les budgets par bras', async () => {
    renderScreen()
    await screen.findByTestId('ae-sim-allocations')
    expect(screen.getAllByTestId('ae-sim-step').length).toBe(2)
    const budgets = screen.getAllByTestId('ae-sim-arm-budget')
    expect(budgets[0]).toHaveTextContent('Créatif A : 600 MAD')
    expect(budgets[1]).toHaveTextContent('Créatif B : 400 MAD')
  })

  it('affiche les décisions annotées FR + chiffres', async () => {
    renderScreen()
    const decision = await screen.findByTestId('ae-sim-decision')
    expect(decision).toHaveTextContent('déplacé 200 MAD vers le Créatif A')
    expect(decision).toHaveTextContent('transfert_mad : 200')
  })

  it('affiche un état vide sans simulation', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    renderScreen()
    expect(await screen.findByTestId('ae-sim-empty')).toBeInTheDocument()
  })
})
