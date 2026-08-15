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
  // WIR209/PUB90 — vote sur anomalie + précision par détecteur.
  anomalyFeedback: vi.fn(),
  detectors: vi.fn(),
  permissions: ['adsengine_view', 'adsengine_manage'],
}))

vi.mock('./adsengineApi', () => ({
  default: {
    rules: {
      templates: mocks.templates, dryRun: mocks.dryRun, journal: mocks.journal,
      list: mocks.policies, create: mocks.policyCreate, update: mocks.policyUpdate,
    },
    anomalies: {
      list: mocks.anomalies, feedback: mocks.anomalyFeedback,
      detectors: mocks.detectors,
    },
    alerts: { history: mocks.history },
  },
}))

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
  mocks.policies.mockResolvedValue({ data: [] })
  mocks.policyCreate.mockResolvedValue({ data: { id: 1, template_key: 'overlap', enabled: true, dry_run: false } })
  mocks.policyUpdate.mockResolvedValue({ data: { id: 2, template_key: 'fatigue', enabled: false, dry_run: true } })
  mocks.dryRun.mockResolvedValue({ data: {
    resume_fr: '2 campagnes seraient touchées',
    objets_touches: [
      { id: 1, nom: 'Campagne Résidentiel', effet_fr: 'serait mise en pause' },
      { id: 2, nom: 'Campagne Pompage', effet_fr: 'inchangée' },
    ] } })
  mocks.permissions = ['adsengine_view', 'adsengine_manage']
  mocks.anomalies.mockResolvedValue({ data: [
    { id: 9, titre: 'CPL en forte hausse', severite: 'critique', detector: 'cpl_spike',
      feedback: '', message: 'Le coût par lead a doublé en 24 h.', quand: '2026-07-15' },
  ] })
  mocks.anomalyFeedback.mockResolvedValue({ data: { id: 9, feedback: 'useful' } })
  // Forme RÉELLE de `anomaly.all_detector_stats` (detector/total/labelled/
  // useful/false_positive/precision/throttled/throttle_factor).
  mocks.detectors.mockResolvedValue({ data: { detecteurs: [
    { detector: 'cpl_spike', total: 8, labelled: 4, useful: 3, false_positive: 1,
      precision: 0.75, throttled: false, throttle_factor: 1 },
    { detector: 'frequency', total: 9, labelled: 6, useful: 1, false_positive: 5,
      precision: 0.1667, throttled: true, throttle_factor: 4 },
  ] } })
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

  // ── WIR209/PUB90 — la boucle d'apprentissage des anomalies ──────────────
  describe('WIR209 — vote sur anomalie + précision par détecteur', () => {
    it('voter « utile » POSTe {vote} et met le vote à jour', async () => {
      renderScreen()
      fireEvent.click(await screen.findByTestId('ae-anomaly-useful-9'))
      await waitFor(() => expect(mocks.anomalyFeedback)
        .toHaveBeenCalledWith(9, 'useful'))
      expect(await screen.findByTestId('ae-anomaly-vote-9')).toHaveTextContent('utile')
      // Le vote recharge la précision par détecteur (elle vient d'évoluer).
      await waitFor(() => expect(mocks.detectors).toHaveBeenCalledTimes(2))
    })

    it('voter « faux positif » POSTe la valeur attendue par le serveur', async () => {
      mocks.anomalyFeedback.mockResolvedValue({ data: { id: 9, feedback: 'false_positive' } })
      renderScreen()
      fireEvent.click(await screen.findByTestId('ae-anomaly-fp-9'))
      await waitFor(() => expect(mocks.anomalyFeedback)
        .toHaveBeenCalledWith(9, 'false_positive'))
      expect(await screen.findByTestId('ae-anomaly-vote-9')).toHaveTextContent('faux positif')
    })

    it('la tuile de précision rend les chiffres du serveur, throttle inclus', async () => {
      renderScreen()
      await screen.findByTestId('ae-detectors')
      await waitFor(() => expect(screen.getAllByTestId('ae-detector')).toHaveLength(2))
      expect(screen.getByTestId('ae-detector-precision-cpl_spike')).toHaveTextContent('75 %')
      expect(screen.getByTestId('ae-detector-throttled-frequency')).toHaveTextContent('Ralenti')
      expect(screen.queryByTestId('ae-detector-throttled-cpl_spike')).toBeNull()
    })

    it('sans adsengine_manage les votes sont grisés (jamais un 403 découvert au clic)', async () => {
      mocks.permissions = ['adsengine_view']
      renderScreen()
      expect(await screen.findByTestId('ae-anomaly-useful-9')).toBeDisabled()
      expect(screen.getByTestId('ae-anomaly-fp-9')).toBeDisabled()
    })

    it('un vote refusé affiche une erreur FR sans faire disparaître l\'anomalie', async () => {
      mocks.anomalyFeedback.mockRejectedValue(new Error('403'))
      renderScreen()
      fireEvent.click(await screen.findByTestId('ae-anomaly-useful-9'))
      expect(await screen.findByTestId('ae-anomaly-vote-error')).toHaveTextContent('impossible')
      expect(screen.getAllByTestId('ae-anomaly')).toHaveLength(1)
    })
  })
})
