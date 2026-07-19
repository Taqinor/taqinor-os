import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { axe } from 'vitest-axe'
import * as axeMatchers from 'vitest-axe/matchers'
import { AE_HOOKS } from './hooks'

/* ENG46 — specs a11y (axe SANS violation) + contrat de hooks `ae-*` sur les
   NOUVEAUX écrans P7 à fort enjeu : le plan de vol (écran-amiral) et les
   expérimentations. API entièrement mockée (ADSENG12/28/38). */

expect.extend(axeMatchers)

const mocks = vi.hoisted(() => ({
  // Experiments (ENG12).
  expList: vi.fn(),
  expGet: vi.fn(),
  expDecisions: vi.fn(),
  // FlightPlan (ENG28/38).
  templates: vi.fn(),
  backlogArms: vi.fn(),
  preflight: vi.fn(),
  // PUB5 — EngagementAudiencePicker mounted in the FlightPlan composer.
  engagementPresets: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    experiments: { list: mocks.expList, get: mocks.expGet, decisionLog: mocks.expDecisions },
    flightplan: {
      templates: mocks.templates, backlogArms: mocks.backlogArms, preflight: mocks.preflight,
    },
    audiences: { engagementPresets: mocks.engagementPresets },
  },
}))

// PUB10 — FlightPlanScreen reads adsengine_manage for Valider/Simuler; full
// access here so the a11y/hook assertions below aren't affected.
vi.mock('./useAdsPermissions', () => ({
  useAdsPermissions: () => ({ loading: false, has: () => true }),
}))

import ExperimentsScreen from './ExperimentsScreen'
import FlightPlanScreen from './FlightPlanScreen'

const renderExp = () => render(<MemoryRouter><ExperimentsScreen /></MemoryRouter>)
const renderFp = () => render(<MemoryRouter><FlightPlanScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.expList.mockResolvedValue({ data: [{ id: 3, nom: 'Test créatif' }] })
  mocks.expGet.mockResolvedValue({ data: {
    id: 3, nom: 'Test créatif', metrique_label: 'Coût par lead', metrique_fmt: 'mad',
    phases: [{ key: 'exploration', label: 'Exploration', statut: 'en_cours', statut_display: 'En cours' }],
    bras: [
      { id: 1, nom: 'Bras A', p_best: 0.7, mean: 88, ci_low: 80, ci_high: 96, allocation: 0.6 },
      { id: 2, nom: 'Bras B', p_best: 0.3, mean: 104, ci_low: 92, ci_high: 120, allocation: 0.4 },
    ] } })
  mocks.expDecisions.mockResolvedValue({ data: [
    { id: 1, phase: 'exploration', decision_fr: 'Exploration à parts égales.', chiffres: { impressions: 4200 } },
  ] })
  mocks.templates.mockResolvedValue({ data: [
    { key: 'lancement', nom: 'Lancement 6 mois', phases: [
      { key: 'amorce', label: 'Amorçage', duree_mois: 1 } ] },
  ] })
  mocks.backlogArms.mockResolvedValue({ data: [{ id: 1, nom: 'Reel toiture' }] })
  mocks.preflight.mockResolvedValue({ data: { pret: false, portes: [
    { key: 'loop', label: 'Signal du loop', ok: true },
    { key: 'backlog', label: 'Backlog volume + diversité', ok: false, detail: 'Runway trop court.' },
  ] } })
  mocks.engagementPresets.mockResolvedValue({ data: { presets: [
    { key: 'lead_submitted', label: 'Formulaire soumis', source_type: 'lead', retention_days: 90 },
  ] } })
})

describe('ENG46 — a11y (axe) sans violation sur les écrans P7', () => {
  it('ExperimentsScreen : zéro violation axe', async () => {
    const { container } = renderExp()
    await waitFor(() => expect(screen.getByTestId('ae-exp-arms')).toBeInTheDocument())
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('FlightPlanScreen : zéro violation axe', async () => {
    const { container } = renderFp()
    await waitFor(() => expect(screen.getByTestId('ae-fp-preflight')).toBeInTheDocument())
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})

describe('ENG46 — contrat de hooks ae-* des écrans P7', () => {
  it('les hooks documentés des Expérimentations sont présents', async () => {
    renderExp()
    await waitFor(() => expect(screen.getByTestId(AE_HOOKS.experiments.arms)).toBeInTheDocument())
    expect(screen.getByTestId(AE_HOOKS.experiments.root)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.experiments.phases)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.experiments.decisions)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.experiments.decisionFilter)).toBeInTheDocument()
    expect(screen.getByTestId(`${AE_HOOKS.experiments.pbestPrefix}1`)).toBeInTheDocument()
  })

  it('les hooks documentés du Plan de vol sont présents', async () => {
    renderFp()
    await waitFor(() => expect(screen.getByTestId(AE_HOOKS.flightplan.preflight)).toBeInTheDocument())
    expect(screen.getByTestId(AE_HOOKS.flightplan.root)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.flightplan.compose)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.flightplan.template)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.flightplan.validate)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.flightplan.preflightVerdict)).toBeInTheDocument()
    // Portes vertes ET rouges présentes.
    expect(screen.getByTestId(AE_HOOKS.flightplan.gateOk)).toBeInTheDocument()
    expect(screen.getByTestId(AE_HOOKS.flightplan.gateKo)).toBeInTheDocument()
  })
})
