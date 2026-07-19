import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { axe } from 'vitest-axe'
import * as axeMatchers from 'vitest-axe/matchers'
import { AE_HOOKS } from './hooks'

/* ENG29 — specs a11y (axe SANS violation) + contrat de hooks `ae-*` sur les
   deux écrans à fort enjeu : ApprovalsScreen (vaisseau-amiral) et
   DashboardScreen. API entièrement mockée. */

expect.extend(axeMatchers)

const mocks = vi.hoisted(() => ({
  dashboard: vi.fn(),
  leads: vi.fn(),
  alerts: vi.fn(),
  pending: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: { dashboard: mocks.dashboard, leads: mocks.leads },
    // PUB48 — cloche console (AlertCenter) : `history` distinct du bandeau `list`.
    alerts: { list: mocks.alerts, history: () => Promise.resolve({ data: [] }) },
    actions: { pending: mocks.pending, approve: mocks.approve, reject: mocks.reject },
    // PUB57 — tuile score d'audit auto-chargée (AuditScoreTile).
    reports: { audit: () => Promise.resolve({ data: { score_tile: null } }) },
  },
}))

import DashboardScreen from './DashboardScreen'
import ApprovalsScreen from './ApprovalsScreen'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.dashboard.mockResolvedValue({ data: {
    cost_per_signature: 1850, spend: 4200, cpl: 95, frequency: 1.8 } })
  mocks.alerts.mockResolvedValue({ data: { alerts: [
    { id: 1, niveau: 'critique', message: 'Plafond quotidien dépassé' } ] } })
  mocks.leads.mockResolvedValue({ data: [] })
  mocks.pending.mockResolvedValue({ data: [
    { id: 11, type: 'adjust_budget', reason_fr: 'CPL en baisse — augmenter la portée.',
      budget_avant: 80, budget_apres: 120 },
    { id: 12, type: 'swap_creative', reason_fr: 'Créatif fatigué.',
      creative: { designation: 'Reel toiture v2', type: 'reel', preview_url: 'https://cdn/x.jpg' } },
  ] })
})

const renderDashboard = () => render(<MemoryRouter><DashboardScreen /></MemoryRouter>)
const renderApprovals = () => render(<MemoryRouter><ApprovalsScreen /></MemoryRouter>)

describe('ENG29 — a11y (axe) sans violation', () => {
  it('DashboardScreen : zéro violation axe', async () => {
    const { container } = renderDashboard()
    await waitFor(() => expect(screen.getByTestId('ae-hero')).toBeInTheDocument())
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('ApprovalsScreen : zéro violation axe', async () => {
    const { container } = renderApprovals()
    await waitFor(() => expect(screen.getAllByTestId('ae-action-card').length).toBeGreaterThan(0))
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})

describe('ENG29 — contrat de hooks ae-* stable', () => {
  it('les hooks documentés du dashboard sont présents dans le DOM', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByTestId(AE_HOOKS.dashboard.hero)).toBeInTheDocument())
    expect(screen.getByTestId(AE_HOOKS.dashboard.alertBanner)).toBeInTheDocument()
    AE_HOOKS.dashboard.tiles.forEach(t =>
      expect(screen.getByTestId(t)).toBeInTheDocument())
  })

  it('les hooks documentés de la boîte d\'approbation sont présents', async () => {
    renderApprovals()
    await waitFor(() => expect(screen.getAllByTestId(AE_HOOKS.approvals.card).length).toBe(2))
    // Hooks d'item suffixés par l'id.
    expect(screen.getByTestId(`${AE_HOOKS.approvals.approvePrefix}11`)).toBeInTheDocument()
    expect(screen.getByTestId(`${AE_HOOKS.approvals.rejectPrefix}11`)).toBeInTheDocument()
    expect(screen.getByTestId(`${AE_HOOKS.approvals.batchTogglePrefix}11`)).toBeInTheDocument()
    // Artefacts réels.
    expect(screen.getByTestId(AE_HOOKS.approvals.artifactBudget)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.approvals.artifactCreative)).toBeInTheDocument()
  })
})
