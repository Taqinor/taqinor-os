import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB54 — Aide contextuelle FR (« ? ») sur chaque métrique du Dashboard :
   héro + tuiles, MER mixte, pacing (4 métriques), réconciliation, signaux
   (2 scores + quadrant de garde-fous). Le « ? » vit toujours EN DEHORS des
   boutons cliquables existants (jamais un bouton imbriqué dans un bouton) —
   ces derniers gardent leur comportement de clic inchangé. */

const mocks = vi.hoisted(() => ({
  dashboard: vi.fn(),
  dashboardV2: vi.fn(),
  leads: vi.fn(),
  alerts: vi.fn(),
  pacing: vi.fn(),
  reconciliation: vi.fn(),
  signalsGet: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: {
      dashboard: mocks.dashboard, dashboardV2: mocks.dashboardV2, leads: mocks.leads,
      pacing: mocks.pacing,
    },
    alerts: { list: mocks.alerts, history: () => Promise.resolve({ data: [] }) },
    reconciliation: { list: mocks.reconciliation },
    signals: { get: mocks.signalsGet, cohort: () => Promise.resolve({ data: [] }) },
  },
}))

import DashboardScreen from './DashboardScreen'

const renderScreen = () => render(<MemoryRouter><DashboardScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.dashboard.mockResolvedValue({ data: {
    cost_per_signature: 1850, spend: 4200, cpl: 95, frequency: 1.8 } })
  mocks.dashboardV2.mockResolvedValue({ data: null })
  mocks.alerts.mockResolvedValue({ data: { alerts: [] } })
  mocks.leads.mockResolvedValue({ data: [] })
  mocks.pacing.mockResolvedValue({ data: {
    enveloppe_mad: 30000, depense_mad: 12000, projection_mad: 31500,
    jours_restants: 12, etat: 'sur_rythme', etat_display: 'Sur le rythme', lignes: [] } })
  mocks.reconciliation.mockResolvedValue({ data: [] })
  mocks.signalsGet.mockResolvedValue({ data: {
    creatif: { score: 0.72, bande: 'vert', bande_display: 'OK' },
    operations: { score: 0.65, bande: 'orange', bande_display: 'Attention' },
    guardrails: [],
  } })
})

describe('DashboardScreen — PUB54 aide contextuelle (héro + tuiles)', () => {
  it('le héro et les 3 tuiles ont chacun leur « ? »', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-hero')).toBeInTheDocument())
    expect(screen.getByTestId('ae-metric-help-toggle-cost_per_signature')).toBeInTheDocument()
    expect(screen.getByTestId('ae-metric-help-toggle-spend')).toBeInTheDocument()
    expect(screen.getByTestId('ae-metric-help-toggle-cpl')).toBeInTheDocument()
    expect(screen.getByTestId('ae-metric-help-toggle-frequency')).toBeInTheDocument()
  })

  it('cliquer le "?" du héro ouvre l\'explication SANS déclencher le drill-down des leads', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-hero')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ae-metric-help-toggle-cost_per_signature'))
    expect(screen.getByTestId('ae-metric-help-popover-cost_per_signature')).toBeInTheDocument()
    // Le clic sur le « ? » n'a pas ouvert le panneau de drill (comportement
    // du bouton-tuile préservé, jamais déclenché par accident).
    expect(screen.queryByTestId('ae-drill-panel')).toBeNull()
  })

  it('la tuile-héro reste cliquable et ouvre bien le drill (comportement inchangé)', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-hero')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('ae-hero'))
    expect(await screen.findByTestId('ae-drill-panel')).toBeInTheDocument()
  })
})

describe('DashboardScreen — PUB54 aide contextuelle (pacing)', () => {
  it('les 4 métriques de pacing ont leur « ? »', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-pacing'))
    await screen.findByTestId('ae-pacing-enveloppe-val')
    expect(screen.getByTestId('ae-metric-help-toggle-pacing_enveloppe')).toBeInTheDocument()
    expect(screen.getByTestId('ae-metric-help-toggle-pacing_burn')).toBeInTheDocument()
    expect(screen.getByTestId('ae-metric-help-toggle-pacing_projection')).toBeInTheDocument()
    expect(screen.getByTestId('ae-metric-help-toggle-pacing_etat')).toBeInTheDocument()
  })

  it('le burn reste cliquable vers le détail (le "?" ne l\'intercepte pas)', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-pacing'))
    await screen.findByTestId('ae-pacing-burn-val')
    fireEvent.click(screen.getByTestId('ae-pacing-burn'))
    expect(await screen.findByTestId('ae-pacing-detail')).toBeInTheDocument()
  })
})

describe('DashboardScreen — PUB54 aide contextuelle (signaux)', () => {
  it('les 2 scores de santé + le quadrant de garde-fous ont leur « ? »', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-signaux'))
    await screen.findByTestId('ae-signal-creatif-score')
    expect(screen.getByTestId('ae-metric-help-toggle-sante_creative')).toBeInTheDocument()
    expect(screen.getByTestId('ae-metric-help-toggle-sante_operations')).toBeInTheDocument()
    expect(screen.getByTestId('ae-metric-help-toggle-guardrail_quadrant')).toBeInTheDocument()
  })

  it('les cartes de score restent cliquables vers le drill par cohorte', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tab-signaux'))
    await screen.findByTestId('ae-signal-creatif')
    fireEvent.click(screen.getByTestId('ae-signal-creatif'))
    expect(await screen.findByTestId('ae-signal-drill')).toBeInTheDocument()
  })
})
