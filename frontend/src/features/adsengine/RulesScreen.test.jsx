import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG43 — Écran Règles & anomalies : catalogue de gabarits FR (picker, jamais
   un builder libre), dry-run VISUALISÉ (objets touchés + effet), flux
   d'anomalies avec sévérités, historique des alertes. Objets/nombres = API
   ENG14/ENG16 mockée. */

const mocks = vi.hoisted(() => ({
  templates: vi.fn(),
  dryRun: vi.fn(),
  journal: vi.fn(),
  anomalies: vi.fn(),
  history: vi.fn(),
  policies: vi.fn(),
  policyCreate: vi.fn(),
  policyUpdate: vi.fn(),
  // WIR209/PUB90 — boucle d'apprentissage des anomalies.
  anomalyFeedback: vi.fn(),
  detectors: vi.fn(),
  // WIR272/PUB91 — rejeu historique d'une règle.
  backtest: vi.fn(),
  permissions: ['adsengine_view', 'adsengine_manage'],
}))

vi.mock('./adsengineApi', () => ({
  default: {
    rules: {
      templates: mocks.templates, dryRun: mocks.dryRun, journal: mocks.journal,
      list: mocks.policies, create: mocks.policyCreate, update: mocks.policyUpdate,
      backtest: mocks.backtest,
    },
    anomalies: {
      list: mocks.anomalies, feedback: mocks.anomalyFeedback,
      detectors: mocks.detectors,
    },
    alerts: { history: mocks.history },
  },
}))

// WIR209 — voter sur une anomalie exige `adsengine_manage` (backend) ; accès
// complet par défaut, restreint dans le test dédié.
vi.mock('./useAdsPermissions', () => ({
  useAdsPermissions: () => ({
    loading: false, has: (code) => mocks.permissions.includes(code),
  }),
}))

import RulesScreen from './RulesScreen'

const renderScreen = () => render(<MemoryRouter><RulesScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.templates.mockResolvedValue({ data: [
    { key: 'overlap', nom: 'Anti-chevauchement d\'enchères',
      condition_fr: 'deux ad sets ciblent la même audience',
      action_fr: 'mettre en pause le moins performant', cadence: 'daily' },
    { key: 'fatigue', nom: 'Fatigue créative',
      condition_fr: 'la fréquence dépasse 3', action_fr: 'proposer une rotation de créatif',
      cadence: 'critical' },
  ] })
  mocks.permissions = ['adsengine_view', 'adsengine_manage']
  mocks.policies.mockResolvedValue({ data: [] })
  mocks.policyCreate.mockResolvedValue({ data: { id: 1, template_key: 'overlap', enabled: true, dry_run: false } })
  mocks.policyUpdate.mockResolvedValue({ data: { id: 2, template_key: 'fatigue', enabled: false, dry_run: true } })
  mocks.dryRun.mockResolvedValue({ data: {
    resume_fr: '2 campagnes seraient touchées',
    objets_touches: [
      { id: 1, nom: 'Campagne Résidentiel', effet_fr: 'serait mise en pause' },
      { id: 2, nom: 'Campagne Pompage', effet_fr: 'inchangée' },
    ] } })
  mocks.anomalies.mockResolvedValue({ data: [
    { id: 9, titre: 'CPL en forte hausse', severite: 'critique',
      message: 'Le coût par lead a doublé en 24 h.', quand: '2026-07-15',
      // PUB90 — champs RÉELS de `AnomalyEventSerializer`.
      detector: 'cpl_spike', feedback: '' },
  ] })
  // PUB90 — forme RÉELLE de `anomaly.detector_stats` (précision = fraction).
  mocks.anomalyFeedback.mockImplementation((id, payload) => Promise.resolve({
    data: { id, detector: 'cpl_spike', feedback: payload.vote } }))
  mocks.detectors.mockResolvedValue({ data: { detecteurs: [
    { detector: 'cpl_spike', total: 4, labelled: 2, useful: 1, false_positive: 1,
      precision: 0.5, throttled: false, throttle_factor: 1 },
  ] } })
  // PUB91 — forme RÉELLE de `rule_backtest.backtest_rule`.
  mocks.backtest.mockResolvedValue({ data: {
    supported: true, reason: '', template_key: 'fatigue',
    label_fr: 'Fatigue créative',
    range: { debut: '2026-04-18', fin: '2026-07-16' },
    proposals: [
      { date: '2026-05-02', target_type: 'adset', target_meta_id: 'as1',
        action_kind: 'swap_creative',
        condition_fr: 'fréquence 3,4 > 3 → vrai.', computed: { frequency: 3.4 } },
      { date: '2026-06-11', target_type: 'adset', target_meta_id: 'as2',
        action_kind: 'swap_creative',
        condition_fr: 'fréquence 3,1 > 3 → vrai.', computed: { frequency: 3.1 } },
    ],
    summary: { days: 90, would_propose: 2, distinct_targets: 2,
      action_kind: 'swap_creative' },
  } })
  mocks.history.mockResolvedValue({ data: { alerts: [
    { id: 1, niveau: 'alerte', message: 'Fréquence élevée', quand: '2026-07-12' },
  ] } })
  // ADSDEEP43 — journal d'exécution enrichi (condition avec valeurs + delta).
  mocks.journal.mockResolvedValue({ data: { results: [
    { id: 1, template_key: 'surf_scale_budget',
      label_fr: 'Surf-scaling — CPL en amélioration', enabled: true, dry_run: false,
      last_evaluated_at: '2026-07-16T10:00:00Z', evaluated: true, fired: true,
      findings: [
        { target: 'as1', target_type: 'adset', fired: true, insufficient_data: false,
          condition_fr: 'cpl 1.0 sur 3 j < 3.0 × 0.9 = 2.7 sur 7 j → vrai.',
          action: { id: 5, kind: 'increase_pace', status: 'proposee',
            reason_fr: 'Surf-scaling : montée de budget learning-safe.',
            delta: { type: 'budget', current_mad: 100.0, new_mad: 115.0 } } },
      ] },
  ] } })
})

describe('RulesScreen (ENG43)', () => {
  it('affiche le catalogue de gabarits en clair (condition FR → action FR)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.templates).toHaveBeenCalled())
    const cards = await screen.findAllByTestId('ae-rule-template')
    expect(cards.length).toBe(2)
    expect(cards[0]).toHaveTextContent('Anti-chevauchement')
    expect(cards[0]).toHaveTextContent('deux ad sets ciblent la même audience')
    expect(cards[0]).toHaveTextContent('mettre en pause le moins performant')
  })

  it('le dry-run est VISUALISÉ : objets touchés + effet de l\'API', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-rule-dryrun-overlap'))
    await waitFor(() => expect(mocks.dryRun).toHaveBeenCalledWith('overlap'))
    const result = await screen.findByTestId('ae-rule-dryrun-result-overlap')
    expect(result).toHaveTextContent('2 campagnes seraient touchées')
    expect(result).toHaveTextContent('Campagne Résidentiel')
    expect(result).toHaveTextContent('serait mise en pause')
    expect(screen.getAllByTestId('ae-rule-dryrun-object').length).toBe(2)
  })

  it('affiche le flux d\'anomalies avec leur sévérité', async () => {
    renderScreen()
    const anomaly = await screen.findByTestId('ae-anomaly')
    expect(anomaly).toHaveTextContent('CPL en forte hausse')
    expect(screen.getByTestId('ae-anomaly-severity')).toHaveTextContent('Critique')
  })

  it('affiche l\'historique des alertes', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-alert-history-row')).toHaveTextContent('Fréquence élevée')
  })

  it('ADSDEEP43 — journal d\'exécution enrichi : condition (valeurs) + delta', async () => {
    renderScreen()
    const run = await screen.findByTestId('ae-rule-run')
    expect(run).toHaveTextContent('Surf-scaling')
    expect(screen.getByTestId('ae-rule-run-verdict')).toHaveTextContent('Déclenchée')
    const finding = screen.getByTestId('ae-rule-run-finding')
    expect(finding).toHaveTextContent('cpl 1.0 sur 3 j < 3.0 × 0.9 = 2.7 sur 7 j → vrai.')
    expect(screen.getByTestId('ae-rule-run-delta')).toHaveTextContent('100 → 115 MAD/j')
  })

  describe('PUB23 — armer/désarmer une règle', () => {
    it('une règle sans instance est « Désarmée » par défaut', async () => {
      renderScreen()
      const state = await screen.findByTestId('ae-rule-state-overlap')
      expect(state).toHaveTextContent('Désarmée')
    })

    it('Armer ouvre une confirmation avec le résumé + la cadence', async () => {
      renderScreen()
      fireEvent.click(await screen.findByTestId('ae-rule-arm-overlap'))
      const confirm = await screen.findByTestId('ae-rule-arm-confirm-overlap')
      expect(confirm).toHaveTextContent('Anti-chevauchement')
      expect(confirm).toHaveTextContent('Quotidienne')
      expect(confirm).toHaveTextContent('deux ad sets ciblent la même audience')
    })

    it('confirmer l\'armement crée la RulePolicy (enabled=true, dry_run=false)', async () => {
      renderScreen()
      fireEvent.click(await screen.findByTestId('ae-rule-arm-overlap'))
      fireEvent.click(await screen.findByTestId('ae-rule-arm-confirm-btn-overlap'))
      await waitFor(() => expect(mocks.policyCreate).toHaveBeenCalledWith(
        { template_key: 'overlap', enabled: true, dry_run: false }))
    })

    it('une règle armée affiche Désarmer + l\'état armé avec cadence', async () => {
      mocks.policies.mockResolvedValue({ data: [
        { id: 2, template_key: 'fatigue', enabled: true, dry_run: false },
      ] })
      renderScreen()
      const state = await screen.findByTestId('ae-rule-state-fatigue')
      expect(state).toHaveTextContent('Armée')
      expect(state).toHaveTextContent('critique')
      expect(await screen.findByTestId('ae-rule-disarm-fatigue')).toBeInTheDocument()
    })

    it('désarmer une règle armée la remet en enabled=false, dry_run=true', async () => {
      mocks.policies.mockResolvedValue({ data: [
        { id: 2, template_key: 'fatigue', enabled: true, dry_run: false },
      ] })
      renderScreen()
      fireEvent.click(await screen.findByTestId('ae-rule-disarm-fatigue'))
      await waitFor(() => expect(mocks.policyUpdate).toHaveBeenCalledWith(
        2, { enabled: false, dry_run: true }))
    })

    it('un armement refusé (403) affiche une erreur et n\'ouvre pas de crash', async () => {
      mocks.policyCreate.mockRejectedValue(new Error('403'))
      renderScreen()
      fireEvent.click(await screen.findByTestId('ae-rule-arm-overlap'))
      fireEvent.click(await screen.findByTestId('ae-rule-arm-confirm-btn-overlap'))
      expect(await screen.findByTestId('ae-rules-arm-err')).toHaveTextContent('refusé')
    })
  })
})

/* ==========================================================================
   WIR209/PUB90 — Boucle d'apprentissage des anomalies : vote utile /
   faux-positif + tuile de précision par détecteur (throttle visible).
   Avant : `anomalies/<id>/feedback/` et `anomalies/detecteurs/` n'avaient
   AUCUN appelant — la précision restait vide et le throttle ne partait jamais.
   ========================================================================== */
describe('RulesScreen — WIR209 votes d\'anomalie + précision par détecteur', () => {
  it('vote « utile » : poste {vote} sur l\'anomalie et relit les détecteurs', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-anomaly-vote-useful-9'))
    await waitFor(() => expect(mocks.anomalyFeedback)
      .toHaveBeenCalledWith(9, { vote: 'useful' }))
    // Le vote affiché est celui CONFIRMÉ par le serveur.
    expect(await screen.findByTestId('ae-anomaly-vote-state-9'))
      .toHaveTextContent('Utile')
    // La précision est relue après le vote (1 appel au montage + 1 après).
    await waitFor(() => expect(mocks.detectors).toHaveBeenCalledTimes(2))
  })

  it('vote « faux positif » : poste la valeur serveur false_positive', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-anomaly-vote-fp-9'))
    await waitFor(() => expect(mocks.anomalyFeedback)
      .toHaveBeenCalledWith(9, { vote: 'false_positive' }))
    expect(await screen.findByTestId('ae-anomaly-vote-state-9'))
      .toHaveTextContent('Faux positif')
  })

  it('un vote refusé affiche une erreur et n\'affiche AUCUN vote', async () => {
    mocks.anomalyFeedback.mockRejectedValue(new Error('403'))
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-anomaly-vote-useful-9'))
    expect(await screen.findByTestId('ae-anomaly-vote-err')).toHaveTextContent('refusé')
    expect(screen.queryByTestId('ae-anomaly-vote-state-9')).toBeNull()
  })

  it('la tuile rend les chiffres du serveur (précision + votes), jamais un calcul local', async () => {
    renderScreen()
    const tile = await screen.findByTestId('ae-detector-tile')
    expect(tile).toHaveTextContent('cpl_spike')
    expect(screen.getByTestId('ae-detector-precision-cpl_spike')).toHaveTextContent('50 %')
    expect(tile).toHaveTextContent('2 vote(s) sur 4 anomalie(s)')
    // Non throttlé ici : aucune pastille de cadence réduite.
    expect(screen.queryByTestId('ae-detector-throttled-cpl_spike')).toBeNull()
  })

  it('un détecteur throttlé le MONTRE (cadence réduite)', async () => {
    mocks.detectors.mockResolvedValue({ data: { detecteurs: [
      { detector: 'cpl_spike', total: 9, labelled: 6, useful: 1, false_positive: 5,
        precision: 0.1667, throttled: true, throttle_factor: 4 },
    ] } })
    renderScreen()
    expect(await screen.findByTestId('ae-detector-throttled-cpl_spike'))
      .toHaveTextContent('Cadence réduite')
  })

  it('aucun détecteur : message dédié (jamais un détecteur fabriqué)', async () => {
    mocks.detectors.mockResolvedValue({ data: { detecteurs: [] } })
    renderScreen()
    expect(await screen.findByTestId('ae-detectors-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-detector-tile')).toBeNull()
  })

  it('sans adsengine_manage : les deux votes sont grisés (permission backend respectée)', async () => {
    mocks.permissions = ['adsengine_view']
    renderScreen()
    expect(await screen.findByTestId('ae-anomaly-vote-useful-9')).toBeDisabled()
    expect(screen.getByTestId('ae-anomaly-vote-fp-9')).toBeDisabled()
    fireEvent.click(screen.getByTestId('ae-anomaly-vote-useful-9'))
    expect(mocks.anomalyFeedback).not.toHaveBeenCalled()
  })
})

/* ==========================================================================
   WIR272/PUB91 — « Qu'aurait fait cette règle ? » : rejeu historique avant
   l'armement. `RulePolicyViewSet.backtest` (detail=True) n'avait aucun
   appelant. LECTURE SEULE : aucune EngineAction n'est créée.
   ========================================================================== */
describe('RulesScreen — WIR272 backtest historique d\'une règle', () => {
  const AVEC_INSTANCE = [{ id: 2, template_key: 'fatigue', enabled: false, dry_run: true }]

  it('le bouton n\'existe QUE si une instance RulePolicy existe (endpoint detail=True)', async () => {
    // Par défaut aucune instance : aucun bouton de backtest.
    renderScreen()
    await screen.findAllByTestId('ae-rule-template')
    expect(screen.queryByTestId('ae-rule-backtest-fatigue')).toBeNull()
    expect(screen.queryByTestId('ae-rule-backtest-overlap')).toBeNull()
  })

  it('appelle backtest(id, 90) et rend les actions SIMULÉES', async () => {
    mocks.policies.mockResolvedValue({ data: AVEC_INSTANCE })
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-rule-backtest-fatigue'))
    // Le rejeu porte sur l'INSTANCE (id 2), sur la fenêtre serveur par défaut.
    await waitFor(() => expect(mocks.backtest).toHaveBeenCalledWith(2, 90))
    const panel = await screen.findByTestId('ae-rule-backtest-result-fatigue')
    expect(panel).toHaveTextContent('aurait proposé 2 action(s) sur 2 objet(s)')
    expect(panel).toHaveTextContent('aucune action n\'a été créée')
    expect(screen.getAllByTestId('ae-rule-backtest-proposal')).toHaveLength(2)
    expect(panel).toHaveTextContent('2026-05-02')
    expect(panel).toHaveTextContent('fréquence 3,4 > 3 → vrai.')
    // Aucune proposition n'a été CRÉÉE : rien n'est posté nulle part.
    expect(mocks.policyCreate).not.toHaveBeenCalled()
    expect(mocks.policyUpdate).not.toHaveBeenCalled()
  })

  it('le backtest est proposé AVANT l\'armement (règle désarmée, bouton Armer présent)', async () => {
    mocks.policies.mockResolvedValue({ data: AVEC_INSTANCE })
    renderScreen()
    expect(await screen.findByTestId('ae-rule-backtest-fatigue')).toBeInTheDocument()
    expect(screen.getByTestId('ae-rule-arm-fatigue')).toBeInTheDocument()
    expect(screen.getByTestId('ae-rule-state-fatigue')).toHaveTextContent('Désarmée')
  })

  it('règle non rejouable : le serveur dit pourquoi, rien n\'est inventé', async () => {
    mocks.policies.mockResolvedValue({ data: AVEC_INSTANCE })
    mocks.backtest.mockResolvedValue({ data: {
      supported: false,
      reason: 'Backtest indisponible pour ce type de règle (évaluateur non câblé).',
      template_key: 'fatigue', label_fr: 'Fatigue créative',
      proposals: [], summary: { days: 90, would_propose: 0, distinct_targets: 0, action_kind: null },
    } })
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-rule-backtest-fatigue'))
    expect(await screen.findByTestId('ae-rule-backtest-unsupported-fatigue'))
      .toHaveTextContent('évaluateur non câblé')
    expect(screen.queryAllByTestId('ae-rule-backtest-proposal')).toHaveLength(0)
  })

  it('aucun déclenchement sur la période : c\'est DIT, jamais un panneau vide', async () => {
    mocks.policies.mockResolvedValue({ data: AVEC_INSTANCE })
    mocks.backtest.mockResolvedValue({ data: {
      supported: true, reason: '', template_key: 'fatigue', label_fr: 'Fatigue créative',
      range: { debut: '2026-04-18', fin: '2026-07-16' }, proposals: [],
      summary: { days: 90, would_propose: 0, distinct_targets: 0, action_kind: 'swap_creative' },
    } })
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-rule-backtest-fatigue'))
    expect(await screen.findByTestId('ae-rule-backtest-empty-fatigue'))
      .toHaveTextContent('jamais déclenchée')
  })

  it('un backtest en échec affiche une erreur et ne rend aucun résultat', async () => {
    mocks.policies.mockResolvedValue({ data: AVEC_INSTANCE })
    mocks.backtest.mockRejectedValue(new Error('500'))
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-rule-backtest-fatigue'))
    expect(await screen.findByTestId('ae-rules-err')).toHaveTextContent('Backtest impossible')
    expect(screen.queryByTestId('ae-rule-backtest-result-fatigue')).toBeNull()
  })
})
