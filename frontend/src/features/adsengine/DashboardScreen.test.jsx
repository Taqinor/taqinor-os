import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG23 — Dashboard « un chiffre » : héro = coût par signature, tuiles
   spend/CPL/fréquence, CHAQUE chiffre cliquable → leads réels (traçabilité
   Northbeam), bandeau alertes ENG13. Les nombres = ceux de l'API mockée. */

const mocks = vi.hoisted(() => ({
  dashboard: vi.fn(),
  leads: vi.fn(),
  alerts: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: { dashboard: mocks.dashboard, leads: mocks.leads },
    alerts: { list: mocks.alerts },
  },
}))

import DashboardScreen from './DashboardScreen'

const renderScreen = () => render(
  <MemoryRouter><DashboardScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.dashboard.mockResolvedValue({ data: {
    cost_per_signature: 1850, spend: 4200, cpl: 95, frequency: 1.8 } })
  mocks.alerts.mockResolvedValue({ data: { alerts: [
    { id: 1, niveau: 'critique', message: 'Plafond quotidien dépassé' },
  ] } })
  mocks.leads.mockResolvedValue({ data: [
    { id: 7, nom: 'Ahmed Benali', ville: 'Casablanca', stage_label: 'SIGNÉ', devis_ref: 'DV-2026-07-0042', montant: 78000 },
  ] })
})

describe('DashboardScreen (ENG23)', () => {
  it('affiche le héro coût-par-signature et les tuiles avec les chiffres de l\'API', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.dashboard).toHaveBeenCalled())
    expect(screen.getByTestId('ae-value-cost_per_signature')).toHaveTextContent('1 850 MAD')
    expect(screen.getByTestId('ae-value-spend')).toHaveTextContent('4 200 MAD')
    expect(screen.getByTestId('ae-value-cpl')).toHaveTextContent('95 MAD')
    expect(screen.getByTestId('ae-value-frequency')).toHaveTextContent('1,8')
  })

  it('le bandeau d\'alertes ENG13 affiche les alertes', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-alert-banner')).toBeInTheDocument()
    expect(screen.getByText('Plafond quotidien dépassé')).toBeInTheDocument()
    expect(screen.getByText('Critique')).toBeInTheDocument()
  })

  it('cliquer le héro ouvre le drill-down des leads réels (metric=signature)', async () => {
    renderScreen()
    const hero = await screen.findByTestId('ae-hero')
    fireEvent.click(hero)
    await waitFor(() => expect(mocks.leads).toHaveBeenCalledWith('signature'))
    expect(await screen.findByTestId('ae-drill-panel')).toBeInTheDocument()
    expect(screen.getByText('Ahmed Benali')).toBeInTheDocument()
    expect(screen.getByText('Casablanca')).toBeInTheDocument()
    // Le lead est cliquable jusqu'à la fiche CRM réelle (traçabilité).
    expect(screen.getByTestId('ae-drill-lead-link')).toHaveAttribute('href', '/crm/leads/7')
  })

  it('cliquer une tuile draille sur SA métrique (ex. spend)', async () => {
    renderScreen()
    const tile = await screen.findByTestId('ae-tile-spend')
    fireEvent.click(tile)
    await waitFor(() => expect(mocks.leads).toHaveBeenCalledWith('spend'))
    expect(await screen.findByTestId('ae-drill-panel')).toHaveTextContent('Dépense')
  })

  it('fermer le drill-down le retire', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-hero'))
    await screen.findByTestId('ae-drill-panel')
    fireEvent.click(screen.getByTestId('ae-drill-close'))
    await waitFor(() => expect(screen.queryByTestId('ae-drill-panel')).toBeNull())
  })

  // ── PUB40 — Sélecteur de période + comparaison ─────────────────────────
  describe('PUB40 — sélecteur de période', () => {
    it('affiche la barre de période et recharge le dashboard au changement', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.dashboard).toHaveBeenCalled())
      expect(screen.getByTestId('ae-daterange')).toBeInTheDocument()
      mocks.dashboard.mockClear()
      fireEvent.click(screen.getByTestId('ae-daterange-preset-hier'))
      await waitFor(() => expect(mocks.dashboard).toHaveBeenCalled())
      const params = mocks.dashboard.mock.calls[0][0]
      expect(params.debut).toBe(params.fin) // « hier » = un seul jour
    })

    it('aucun bloc `previous` -> aucun delta affiché (jamais un badge fabriqué)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.dashboard).toHaveBeenCalled())
      expect(screen.queryByTestId('ae-delta-spend')).toBeNull()
    })

    it('bloc `previous` fourni -> delta % affiché sur les tuiles (jamais le héro)', async () => {
      mocks.dashboard.mockResolvedValue({ data: {
        cost_per_signature: 1850, spend: 4200, cpl: 95, frequency: 1.8,
        previous: { spend: 3500, cpl: 100, frequency: 1.5 },
      } })
      renderScreen()
      await waitFor(() => expect(mocks.dashboard).toHaveBeenCalled())
      expect(screen.getByTestId('ae-delta-spend')).toHaveTextContent('vs période précédente')
      expect(screen.queryByTestId('ae-delta-cost_per_signature')).toBeNull()
    })
  })
})
