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
  // Experiments (ENG12/PACT110 — bras RÉELS + DecisionLog réel, séparés de
  // GET experiences/<id>/ depuis le recâblage : `arms` et `allDecisions` sont
  // de NOUVEAUX appels que ExperimentsScreen ne faisait pas avant PACT110).
  expList: vi.fn(),
  expGet: vi.fn(),
  expDecisionLog: vi.fn(),
  expArms: vi.fn(),
  expAllDecisions: vi.fn(),
  // FlightPlan (ENG28/38, PACT113 — `list` charge le plan persistant le plus
  // récent au montage, un appel que FlightPlanScreen ne faisait pas avant
  // PACT113).
  fpList: vi.fn(),
  templates: vi.fn(),
  backlogArms: vi.fn(),
  preflight: vi.fn(),
  // PUB5 — EngagementAudiencePicker mounted in the FlightPlan composer.
  engagementPresets: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    experiments: {
      list: mocks.expList, get: mocks.expGet, decisionLog: mocks.expDecisionLog,
      arms: mocks.expArms, allDecisions: mocks.expAllDecisions,
    },
    flightplan: {
      list: mocks.fpList,
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
  } })
  // PACT110 — bras RÉELS (``ExperimentArm``, endpoint ``bras/``) : le posterior
  // (p_best/budget_mad) n'est plus stocké sur le bras, il est dérivé du
  // DecisionLog le plus récent ci-dessous (mêmes ``label`` que les allocations).
  mocks.expArms.mockResolvedValue({ data: [
    { id: 1, label: 'bras_a', ad_id: 'AD1', is_active: true, experiment: 3 },
    { id: 2, label: 'bras_b', ad_id: 'AD2', is_active: true, experiment: 3 },
  ] })
  // PACT110 — DecisionLog RÉEL (``DecisionLogSerializer``) : ``summary_fr`` (pas
  // ``decision_fr``) + ``allocations.prob_best``/``budget_mad`` indexées par
  // ``label`` de bras (pas un champ ``chiffres`` synthétique).
  mocks.expDecisionLog.mockResolvedValue({ data: [
    { id: 1, experiment: 3, summary_fr: 'Exploration à parts égales.', created_at: '2026-08-01T10:00:00Z',
      allocations: { budget_mad: { bras_a: 120, bras_b: 80 }, prob_best: { bras_a: 0.7, bras_b: 0.3 } } },
  ] })
  // PACT110 — journal des décisions toutes expériences confondues : aucune
  // décision inter-expériences dans ce fixture (vue jamais construite avant).
  mocks.expAllDecisions.mockResolvedValue({ data: [] })
  // PACT113 — aucun plan de vol déjà enregistré pour cette société.
  mocks.fpList.mockResolvedValue({ data: [] })
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
    // `decisionFilter` retiré par PACT110 : il filtrait sur une phase que
    // `DecisionLogSerializer` ne renvoie pas (cf. commentaire dans hooks.js).
    expect(screen.queryByTestId('ae-exp-decision-filter')).toBeNull()
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
