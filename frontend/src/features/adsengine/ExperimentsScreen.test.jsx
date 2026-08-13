import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG39/PACT110 — Écran Expérimentations : timeline de phases, bras RÉELS
   (ExperimentArm, enrichis des seules stats que le DecisionLog le plus récent
   renvoie), DecisionLog rendu « pourquoi le moteur a fait X » en FR (summary_fr
   réel) + chiffres réels (allocations). Toutes les formes mockées ici
   reproduisent EXACTEMENT les sérialiseurs réels (ExperimentSerializer,
   ExperimentArmSerializer, DecisionLogSerializer, ArmDailyStatSerializer) —
   aucun champ inventé (PACT13). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  decisionLog: vi.fn(),
  mde: vi.fn(),
  arms: vi.fn(),
  armStats: vi.fn(),
  allDecisions: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    experiments: {
      list: mocks.list, get: mocks.get, decisionLog: mocks.decisionLog,
      mde: mocks.mde, arms: mocks.arms, armStats: mocks.armStats,
      allDecisions: mocks.allDecisions,
    },
  },
}))

import ExperimentsScreen from './ExperimentsScreen'

const renderScreen = () => render(<MemoryRouter><ExperimentsScreen /></MemoryRouter>)

// Forme RÉELLE d'ExperimentSerializer (id/name/tested_variable/status/...).
const EXP = {
  id: 3, name: 'Test créatif toiture', tested_variable: 'cout_par_lead',
  status: 'in_progress', campaign: 1, adset: 2, start_date: '2026-07-01',
  end_date: null, notes: '', meta_study_id: null,
  created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
}

// Forme RÉELLE de DecisionLogSerializer, ordre serveur (-created_at, -id).
const DECISIONS = [
  {
    id: 2, experiment: 3,
    inputs: { arms: [], daily_budget_mad: 1000, seed: 7 },
    posteriors: { alpha_beta: [[9, 4], [4, 9]], labels: ['Créatif A — toiture', 'Créatif B — pompe'] },
    allocations: {
      budget_mad: { 'Créatif A — toiture': 600, 'Créatif B — pompe': 400 },
      prob_best: { 'Créatif A — toiture': 0.72, 'Créatif B — pompe': 0.28 },
      reweighted: true,
    },
    summary_fr: 'Bras le plus probable « Créatif A — toiture » (P=72%), budget 600 MAD/jour.',
    action: null, created_at: '2026-07-14T00:00:00Z', updated_at: '2026-07-14T00:00:00Z',
  },
  {
    id: 1, experiment: 3,
    inputs: { arms: [], daily_budget_mad: 1000, seed: 7 },
    posteriors: { alpha_beta: [[1, 1], [1, 1]], labels: ['Créatif A — toiture', 'Créatif B — pompe'] },
    allocations: {
      budget_mad: { 'Créatif A — toiture': 500, 'Créatif B — pompe': 500 },
      prob_best: { 'Créatif A — toiture': 0.5, 'Créatif B — pompe': 0.5 },
      reweighted: false,
    },
    summary_fr: 'Données insuffisantes (< 100 impressions/bras) : partage égal maintenu, poids du bandit non appliqués.',
    action: null, created_at: '2026-07-10T00:00:00Z', updated_at: '2026-07-10T00:00:00Z',
  },
]

// Forme RÉELLE d'ExperimentArmSerializer — un troisième bras appartient à une
// AUTRE expérience et doit être filtré côté client (le ViewSet ne filtre pas
// par expérience côté serveur, il est company-scopé seulement).
const ARMS = [
  { id: 1, experiment: 3, creative_asset: null, label: 'Créatif A — toiture', ad_id: '123',
    hook_id: 'h1', visual_id: 'v1', is_active: true, created_at: '', updated_at: '' },
  { id: 2, experiment: 3, creative_asset: null, label: 'Créatif B — pompe', ad_id: '124',
    hook_id: 'h2', visual_id: 'v2', is_active: true, created_at: '', updated_at: '' },
  { id: 9, experiment: 99, creative_asset: null, label: 'Bras d\'une autre expérience', ad_id: '900',
    hook_id: '', visual_id: '', is_active: true, created_at: '', updated_at: '' },
]

// Forme RÉELLE d'ArmDailyStatSerializer.
const ARM_STATS = [
  { id: 11, arm: 1, date: '2026-07-11', impressions: 3900, clicks: 77, conversations: 10, spend: 300,
    created_at: '', updated_at: '' },
  { id: 10, arm: 1, date: '2026-07-10', impressions: 4200, clicks: 84, conversations: 12, spend: 320,
    created_at: '', updated_at: '' },
  { id: 20, arm: 2, date: '2026-07-10', impressions: 1000, clicks: 20, conversations: 3, spend: 150,
    created_at: '', updated_at: '' },
]

// Journal global (toutes expériences) — une décision d'une expérience absente
// de `list()` doit retomber sur le libellé générique « Expérimentation N ».
const ALL_DECISIONS = [
  DECISIONS[0],
  {
    id: 4, experiment: 7,
    inputs: {}, posteriors: {}, allocations: {},
    summary_fr: 'Décision sur une autre expérimentation.',
    action: null, created_at: '2026-07-09T00:00:00Z', updated_at: '2026-07-09T00:00:00Z',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [{ id: 3, name: 'Test créatif toiture' }] })
  mocks.get.mockResolvedValue({ data: EXP })
  mocks.decisionLog.mockResolvedValue({ data: DECISIONS })
  mocks.arms.mockResolvedValue({ data: ARMS })
  mocks.armStats.mockResolvedValue({ data: ARM_STATS })
  mocks.allDecisions.mockResolvedValue({ data: ALL_DECISIONS })
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

describe('ExperimentsScreen (ENG39/PACT110)', () => {
  it('affiche un état vide de phases (le backend ne renvoie aucune phase par expérience)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(3))
    const phases = await screen.findByTestId('ae-exp-phases')
    expect(phases).toHaveTextContent('Aucune phase définie.')
  })

  it('affiche les bras RÉELS (ExperimentArm) filtrés par expérience, avec les stats du dernier DecisionLog', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.arms).toHaveBeenCalled())
    const armCards = await screen.findAllByTestId('ae-exp-arm')
    // Seuls les 2 bras de l'expérience 3 apparaissent — pas le bras de l'expérience 99.
    expect(armCards.length).toBe(2)
    expect(screen.queryByText(/Bras d'une autre expérience/)).not.toBeInTheDocument()
    // P(meilleur) vient de allocations.prob_best du DecisionLog le plus RÉCENT (id 2).
    expect(screen.getByTestId('ae-exp-pbest-1')).toHaveTextContent('72 %')
    expect(screen.getByTestId('ae-exp-pbest-2')).toHaveTextContent('28 %')
    // Budget alloué vient de allocations.budget_mad du même DecisionLog.
    expect(screen.getByTestId('ae-exp-budget-1')).toHaveTextContent('600 MAD')
    // Le bras le plus probable est marqué favori.
    expect(screen.getByTestId('ae-exp-arm-best')).toHaveTextContent('Favori du moteur')
  })

  it('charge et affiche la série quotidienne d\'un bras au clic (vue jamais construite)', async () => {
    renderScreen()
    await screen.findAllByTestId('ae-exp-arm')
    expect(mocks.armStats).not.toHaveBeenCalled()
    fireEvent.click(screen.getByTestId('ae-exp-arm-series-toggle-1'))
    await waitFor(() => expect(mocks.armStats).toHaveBeenCalled())
    const rows = await screen.findAllByTestId('ae-exp-arm-series-row')
    // Seules les 2 lignes du bras 1 (pas celle du bras 2), triées par date croissante.
    expect(rows.length).toBe(2)
    expect(rows[0]).toHaveTextContent('2026-07-10')
    expect(rows[1]).toHaveTextContent('2026-07-11')
  })

  it('rend le DecisionLog avec la phrase FR réelle (summary_fr) et les chiffres réels (allocations)', async () => {
    renderScreen()
    // La décision id=2 (la plus récente de l'expérience 3) apparaît
    // légitimement DEUX fois à l'écran : dans le journal de l'expérience
    // sélectionnée (``ae-exp-decisions``) ET dans le journal global toutes
    // expérimentations (``ae-exp-decisions-all``, ENG39/PACT110). On scope
    // donc sur le journal de l'expérience sélectionnée, celui que ce test vise.
    const decisionsSection = await screen.findByTestId('ae-exp-decisions')
    expect(within(decisionsSection)
      .getByText(/Bras le plus probable « Créatif A — toiture »/)).toBeInTheDocument()
    expect(within(decisionsSection).getByText(/Données insuffisantes/)).toBeInTheDocument()
    expect(within(decisionsSection).getAllByTestId('ae-exp-decision').length).toBe(2)
    // Les chiffres affichés sont les VRAIS montants/probas de `allocations` —
    // les DEUX décisions portent un chiffre pour « Créatif A — toiture », donc
    // on vérifie le montant RÉEL (600) de la décision la plus récente (id=2),
    // pas seulement la présence du libellé.
    expect(within(decisionsSection)
      .getByText(/Créatif A — toiture — budget MAD\/j : 600/)).toBeInTheDocument()
  })

  it('affiche le journal des décisions toutes expérimentations (vue jamais construite)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.allDecisions).toHaveBeenCalled())
    const allRows = await screen.findAllByTestId('ae-exp-decision-all')
    expect(allRows.length).toBe(2)
    expect(allRows[0]).toHaveTextContent('Test créatif toiture')
    // Expérience 7 absente de `list()` → repli sur le libellé générique.
    expect(allRows[1]).toHaveTextContent('Expérimentation 7')
    expect(allRows[1]).toHaveTextContent('Décision sur une autre expérimentation.')
  })

  /* PACT110-FIX — troncature de pagination RENDUE VISIBLE.
     `bras/`, `stats-bras/` et `decisions/` sont paginées (StandardPagination :
     50 par défaut, plafond dur 200) et filtrées CÔTÉ CLIENT faute de filtre
     serveur par expérience/bras. Au-delà du plafond, les lignes non renvoyées
     disparaissaient EN SILENCE : l'écran affichait « aucun bras créé » — un
     vide qui se lit « rien n'a été créé ». Ces trois tests prouvent que
     l'enveloppe DRF (`count`/`next`) est lue et DITE à l'écran. */
  it('bras : dit que la liste est tronquée par le serveur au lieu de mentir sur un vide', async () => {
    // Enveloppe DRF réelle : le serveur annonce 342 bras et n'en renvoie que 2,
    // AUCUN de l'expérience sélectionnée (ils sont sur les pages suivantes).
    mocks.arms.mockResolvedValue({ data: {
      count: 342, next: 'http://api/adsengine/bras/?page=2', previous: null,
      results: [ARMS[2], { ...ARMS[2], id: 10, experiment: 98 }],
    } })
    renderScreen()
    await waitFor(() => expect(mocks.arms).toHaveBeenCalled())
    // Le vide est affiché — mais JAMAIS seul : le bandeau dit pourquoi.
    expect(await screen.findByTestId('ae-exp-arms-empty')).toBeInTheDocument()
    const notice = await screen.findByTestId('ae-exp-arms-truncated')
    expect(notice).toHaveTextContent('Liste tronquée par le serveur')
    expect(notice).toHaveTextContent('2 ligne(s) reçue(s)')
    expect(notice).toHaveTextContent('342')
  })

  it('bras : aucun bandeau de troncature quand le serveur a tout envoyé', async () => {
    // Enveloppe DRF complète (`next` nul, `count` == nombre de résultats).
    mocks.arms.mockResolvedValue({ data: {
      count: ARMS.length, next: null, previous: null, results: ARMS,
    } })
    renderScreen()
    const armCards = await screen.findAllByTestId('ae-exp-arm')
    expect(armCards.length).toBe(2)
    expect(screen.queryByTestId('ae-exp-arms-truncated')).toBeNull()
  })

  it('série d\'un bras : signale la troncature (les jours les plus anciens manquent)', async () => {
    mocks.armStats.mockResolvedValue({ data: {
      count: 900, next: 'http://api/adsengine/stats-bras/?page=2', previous: null,
      results: ARM_STATS,
    } })
    renderScreen()
    await screen.findAllByTestId('ae-exp-arm')
    fireEvent.click(screen.getByTestId('ae-exp-arm-series-toggle-1'))
    const notice = await screen.findByTestId('ae-exp-arm-series-truncated')
    expect(notice).toHaveTextContent('Liste tronquée par le serveur')
    expect(notice).toHaveTextContent('900')
    // Les lignes reçues du bras 1 restent affichées — on tronque, on ne cache pas.
    expect(screen.getAllByTestId('ae-exp-arm-series-row').length).toBe(2)
  })

  it('journal global : signale la troncature du serveur', async () => {
    mocks.allDecisions.mockResolvedValue({ data: {
      count: 4210, next: 'http://api/adsengine/decisions/?page=2', previous: null,
      results: ALL_DECISIONS,
    } })
    renderScreen()
    await waitFor(() => expect(mocks.allDecisions).toHaveBeenCalled())
    const notice = await screen.findByTestId('ae-exp-decisions-all-truncated')
    expect(notice).toHaveTextContent('Liste tronquée par le serveur')
    expect(notice).toHaveTextContent('4 210')
    expect(screen.getAllByTestId('ae-exp-decision-all').length).toBe(2)
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
