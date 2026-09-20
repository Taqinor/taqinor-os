import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG22 — l'écran Connexion : identifiants WRITE-ONLY (jamais relus), statuts
   de câblage (ENG12), édition plafond/band, et AUCUN toggle d'activation
   (le client naît PAUSED, par design). API entièrement mockée. */

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  save: vi.fn(),
  health: vi.fn(),
  guardGet: vi.fn(),
  guardUpdate: vi.fn(),
  policyList: vi.fn(),
  policyCreate: vi.fn(),
  policyUpdate: vi.fn(),
  // PUB129 — cockpit d'autonomie (portes + cérémonie).
  autonomie: vi.fn(),
  activerAutonomie: vi.fn(),
  desactiverAutonomie: vi.fn(),
  acquitterSimulation: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    connection: { get: mocks.get, save: mocks.save, health: mocks.health },
    guardrail: { get: mocks.guardGet, update: mocks.guardUpdate },
    creativePolicy: { list: mocks.policyList, create: mocks.policyCreate, update: mocks.policyUpdate },
    flightplan: {
      autonomie: mocks.autonomie,
      activerAutonomie: mocks.activerAutonomie,
      desactiverAutonomie: mocks.desactiverAutonomie,
      acquitterSimulation: mocks.acquitterSimulation,
    },
  },
}))

// PUB129 — forme RÉELLE de `GET /adsengine/plans-vol/autonomie/` (vue mince sur
// `preflight.status` + la remédiation FR par porte).
const autonomyPayload = (over = {}) => ({
  pret: false,
  actif: false,
  portes: [
    { key: 'loop', label: 'Boucle ENG12 verte (connexion Meta active)', ok: true, detail: '',
      remediation: { texte: 'Connecter le compte Meta.', route: '/publicite/connexion',
        cta: 'Ouvrir Connexion & garde-fous' } },
    { key: 'simulation', label: 'Simulation ADSENG36 revue OK', ok: false,
      detail: 'Simulation non revue/acquittée (voir la visionneuse P7).',
      remediation: { texte: "Revoir le rapport puis l'acquitter ici.",
        route: '/publicite/simulation', cta: 'Ouvrir la simulation',
        action: 'acquitter_simulation' } },
    { key: 'field_tests', label: 'Tests terrain (7 inconnues) tranchés', ok: false,
      detail: 'Inconnues terrain non tranchées : FT1.',
      remediation: { texte: 'Consigner le résultat mesuré des 7 micro-tests.',
        route: '/publicite/tests-terrain', cta: 'Ouvrir les tests terrain' } },
    { key: 'alerts', label: 'Alertes câblées', ok: false,
      detail: 'Aucune règle de garde-fou activée.',
      remediation: { texte: 'Armer au moins une règle.', route: '/publicite/regles',
        cta: 'Ouvrir les règles', commande: 'python manage.py seed_adsengine' } },
  ],
  manquantes: ['Simulation non revue/acquittée (voir la visionneuse P7).',
    'Inconnues terrain non tranchées : FT1.',
    'Aucune règle de garde-fou activée.'],
  ...over,
})

import ConnectionScreen from './ConnectionScreen'

const renderScreen = () => render(
  <MemoryRouter><ConnectionScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  // Le serveur ne renvoie qu'un STATUT — jamais un secret.
  mocks.get.mockResolvedValue({ data: { connected: true, ad_account_id_masque: '***4321' } })
  mocks.health.mockResolvedValue({ data: { statuses: [
    { key: 'token', ok: true },
    { key: 'ad_account', ok: true },
    { key: 'pixel', ok: false, detail: 'Non configuré' },
    { key: 'paused', ok: true },
  ] } })
  // PUB9 — `adsengineApi.guardrail` appelle ``/adsengine/guardrail/``
  // (`GuardrailSingletonView`) : les 2 plafonds gardent leur alias
  // historique (max_daily_budget_mad/max_monthly_budget_mad, mappage CÔTÉ
  // SERVEUR) ; le reste voyage sous son nom modèle direct — avant cette
  // tâche, ce singleton n'exposait QUE les 2 plafonds (le reste de
  // GuardrailConfig était sérialisé ailleurs — garde-fous/ — mais invisible
  // ici, donc jamais édité par cet écran).
  mocks.guardGet.mockResolvedValue({ data: {
    max_daily_budget_mad: 100, max_monthly_budget_mad: 2000,
    require_approval_above_mad: null,
    weekly_change_pct_max: 20, anomaly_window_hours: 48,
    auto_rotate_creative: false, auto_rebalance_within_band: false,
    pacing_band_pct: 15, exploration_floor_mad: 20, exploration_floor_pct: 20,
    health_creative_weight_ctr: 60, health_creative_weight_freshness: 40,
    health_ops_weight_cpl: 60, health_ops_weight_delivery: 40,
  } })
  mocks.save.mockResolvedValue({ data: {} })
  mocks.guardUpdate.mockResolvedValue({ data: {} })
  // PACT112 — par défaut, aucune ligne CreativePolicy pour la société encore
  // (forme RÉELLE : ``policy-creative/`` renvoie une liste, DRF standard).
  mocks.policyList.mockResolvedValue({ data: [] })
  mocks.policyCreate.mockResolvedValue({ data: { id: 77, forbidden_rules: [], allowed_rules: [] } })
  mocks.policyUpdate.mockResolvedValue({ data: {} })
  // PUB129 — par défaut : autonomie OFF, 3 portes rouges (état réel d'une
  // société qui n'a encore rien tranché).
  mocks.autonomie.mockResolvedValue({ data: autonomyPayload() })
  mocks.activerAutonomie.mockResolvedValue({ data: autonomyPayload() })
  mocks.desactiverAutonomie.mockResolvedValue({ data: autonomyPayload() })
  mocks.acquitterSimulation.mockResolvedValue({ data: autonomyPayload() })
})

describe('ConnectionScreen (ENG22)', () => {
  it('les champs secrets partent vides et le serveur n\'en relit aucun', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    // Même avec un statut « connecté », le secret n'est jamais réaffiché.
    expect(screen.getByTestId('ae-conn-cred-app_secret').value).toBe('')
    expect(screen.getByTestId('ae-conn-cred-access_token').value).toBe('')
    // Le statut masqué s'affiche (jamais le secret complet).
    expect(await screen.findByText(/\*\*\*4321/)).toBeInTheDocument()
  })

  it('parcours setup complet : saisie → enregistrement (write-only)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('ae-conn-cred-app_id'),
      { target: { value: '123456' } })
    fireEvent.change(screen.getByTestId('ae-conn-cred-app_secret'),
      { target: { value: 's3cr3t' } })
    fireEvent.change(screen.getByTestId('ae-conn-cred-ad_account_id'),
      { target: { value: 'act_999' } })
    fireEvent.click(screen.getByTestId('ae-conn-cred-save'))
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith({
      app_id: '123456', app_secret: 's3cr3t', ad_account_id: 'act_999' }))
    // Après enregistrement, les champs sont RE-vidés (aucun secret en mémoire).
    await waitFor(() =>
      expect(screen.getByTestId('ae-conn-cred-app_secret').value).toBe(''))
    expect(await screen.findByTestId('ae-conn-msg')).toBeInTheDocument()
  })

  it('les statuts de câblage (ENG12) sont rendus avec OK / À configurer', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-conn-health-token')).toBeInTheDocument()
    const pixel = screen.getByTestId('ae-conn-health-pixel')
    expect(pixel).toHaveTextContent('À configurer')
    expect(pixel).toHaveTextContent('Non configuré')
    expect(screen.getByTestId('ae-conn-health-token')).toHaveTextContent('OK')
  })

  it('PUB9 — édition du plafond quotidien (alias historique) → guardrail.update', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.guardGet).toHaveBeenCalled())
    const daily = await screen.findByTestId('ae-conn-guard-max_daily_budget_mad')
    expect(daily.value).toBe('100')
    fireEvent.change(daily, { target: { value: '150' } })
    fireEvent.click(screen.getByTestId('ae-conn-guard-save'))
    await waitFor(() => expect(mocks.guardUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ max_daily_budget_mad: 150 })))
  })

  it('PUB9 — chaque champ exposé par le singleton est éditable (13 champs, groupés)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.guardGet).toHaveBeenCalled())
    const keys = [
      'max_daily_budget_mad', 'max_monthly_budget_mad', 'weekly_change_pct_max',
      'anomaly_window_hours', 'auto_rotate_creative', 'auto_rebalance_within_band',
      'pacing_band_pct', 'exploration_floor_mad', 'exploration_floor_pct',
      'health_creative_weight_ctr', 'health_creative_weight_freshness',
      'health_ops_weight_cpl', 'health_ops_weight_delivery',
    ]
    for (const key of keys) {
      expect(await screen.findByTestId(`ae-conn-guard-${key}`)).toBeInTheDocument()
    }
    // require_approval_above_mad reste un GAP documenté (aucun champ de
    // stockage) : jamais montré à l'édition (un champ qui n'enregistre
    // jamais rien serait trompeur).
    expect(screen.queryByTestId('ae-conn-guard-require_approval_above_mad')).toBeNull()
  })

  it('PUB9 — les bascules auto-application (ENG8) s\'éditent et s\'envoient explicitement', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.guardGet).toHaveBeenCalled())
    const autoRotate = await screen.findByTestId('ae-conn-guard-auto_rotate_creative')
    expect(autoRotate.checked).toBe(false)
    fireEvent.click(autoRotate)
    expect(autoRotate.checked).toBe(true)
    fireEvent.click(screen.getByTestId('ae-conn-guard-save'))
    await waitFor(() => expect(mocks.guardUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        auto_rotate_creative: true, auto_rebalance_within_band: false,
      })))
  })

  it('chaque champ de garde-fou porte une aide FR', async () => {
    renderScreen()
    await screen.findByTestId('ae-conn-guard-max_daily_budget_mad')
    expect(screen.getByText(/détecteur d'anomalie compare la dépense/)).toBeInTheDocument()
    expect(screen.getByText(/bande de pacing ci-dessous/)).toBeInTheDocument()
  })

  it('AUCUN toggle d\'activation de campagne n\'existe à l\'écran (par design)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    expect(screen.queryByRole('switch')).toBeNull()
    expect(screen.queryByText(/activer la campagne/i)).toBeNull()
    // Seules les 2 bascules d'auto-application (ENG8) existent — jamais une
    // activation de campagne Meta (interdite en dur côté service, pas un
    // réglage écran).
    expect(screen.getAllByRole('checkbox')).toHaveLength(2)
  })

  // ── PUB46 — Assistant de connexion guidé ─────────────────────────────────
  describe('PUB46 — assistant de connexion guidé', () => {
    it('affiche les 5 étapes du wizard, chacune avec un lien externe', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.health).toHaveBeenCalled())
      for (let n = 1; n <= 5; n++) {
        const step = screen.getByTestId(`ae-conn-wizard-step-${n}`)
        expect(step).toBeInTheDocument()
        const link = step.querySelector('a[target="_blank"]')
        expect(link).toBeTruthy()
        expect(link.getAttribute('href')).toMatch(/^https:\/\//)
      }
    })

    it('étape jeton VÉRIFIÉE quand le statut backend token est ok', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.health).toHaveBeenCalled())
      expect(screen.getByTestId('ae-conn-wizard-status-3')).toHaveTextContent('Vérifié')
    })

    it('étape sans statut backend dédié -> « à faire manuellement » (jamais fabriqué vert)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.health).toHaveBeenCalled())
      expect(screen.getByTestId('ae-conn-wizard-status-1')).toHaveTextContent('manuellement')
    })

    it('« Vérifier cette étape » redéclenche connection.health', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.health).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByTestId('ae-conn-wizard-verify-3'))
      await waitFor(() => expect(mocks.health).toHaveBeenCalledTimes(2))
    })

    it('remédiation affichée sous un item de câblage rouge (pixel), avec lien vers l’étape', async () => {
      renderScreen()
      const remediation = await screen.findByTestId('ae-conn-remediation-pixel')
      expect(remediation).toHaveTextContent('Aucun Pixel renseigné')
      const link = remediation.querySelector('a')
      expect(link.getAttribute('href')).toBe('#ae-conn-wizard-step-5')
    })

    it('aucune remédiation affichée pour un item déjà OK (token)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.health).toHaveBeenCalled())
      expect(screen.queryByTestId('ae-conn-remediation-token')).toBeNull()
    })
  })

  // ── PACT112 — Policy créative RÉELLE (CreativePolicy, jamais appelée avant) ──
  describe('PACT112 — policy créative', () => {
    it('aucune policy en base : listes vides (JAMAIS DEFAULT_POLICY_RULES fabriqué)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.policyList).toHaveBeenCalled())
      expect(await screen.findByTestId('ae-conn-policy-forbidden-list'))
        .toHaveTextContent('Aucune règle interdite.')
      expect(screen.getByTestId('ae-conn-policy-allowed-list'))
        .toHaveTextContent('Aucune règle permise.')
    })

    it('affiche la VRAIE policy existante (forbidden_rules/allowed_rules réels)', async () => {
      mocks.policyList.mockResolvedValue({ data: [
        { id: 12, forbidden_rules: [{ key: 'no_fake_sites', label: 'Aucun faux chantier' }],
          allowed_rules: [{ key: 'product_renders', label: 'Rendus produit (3D / studio)' }],
          created_at: '', updated_at: '' },
      ] })
      renderScreen()
      expect(await screen.findByTestId('ae-conn-policy-forbidden-no_fake_sites'))
        .toHaveTextContent('Aucun faux chantier')
      expect(screen.getByTestId('ae-conn-policy-allowed-product_renders'))
        .toHaveTextContent('Rendus produit (3D / studio)')
    })

    it('ajoute une règle interdite puis l\'enregistre : PATCH sur la policy existante', async () => {
      mocks.policyList.mockResolvedValue({ data: [
        { id: 12, forbidden_rules: [], allowed_rules: [], created_at: '', updated_at: '' },
      ] })
      renderScreen()
      await waitFor(() => expect(mocks.policyList).toHaveBeenCalled())
      fireEvent.change(screen.getByTestId('ae-conn-policy-forbidden-new'),
        { target: { value: 'Aucun prix sans TVA' } })
      fireEvent.click(screen.getByTestId('ae-conn-policy-forbidden-add'))
      // La règle apparaît immédiatement (état local), avant tout enregistrement.
      expect(await screen.findByText('Aucun prix sans TVA')).toBeInTheDocument()
      fireEvent.click(screen.getByTestId('ae-conn-policy-save'))
      await waitFor(() => expect(mocks.policyUpdate).toHaveBeenCalledWith(12, {
        forbidden_rules: [{ key: 'aucun_prix_sans_tva', label: 'Aucun prix sans TVA' }],
        allowed_rules: [],
      }))
      expect(await screen.findByTestId('ae-conn-policy-msg')).toBeInTheDocument()
    })

    it('retire une règle permise localement, puis enregistre la liste sans elle', async () => {
      mocks.policyList.mockResolvedValue({ data: [
        { id: 12, forbidden_rules: [],
          allowed_rules: [{ key: 'abstract_broll', label: 'B-roll abstrait' }],
          created_at: '', updated_at: '' },
      ] })
      renderScreen()
      await screen.findByTestId('ae-conn-policy-allowed-abstract_broll')
      fireEvent.click(screen.getByTestId('ae-conn-policy-allowed-remove-abstract_broll'))
      expect(screen.queryByTestId('ae-conn-policy-allowed-abstract_broll')).toBeNull()
      fireEvent.click(screen.getByTestId('ae-conn-policy-save'))
      await waitFor(() => expect(mocks.policyUpdate).toHaveBeenCalledWith(12, {
        forbidden_rules: [], allowed_rules: [],
      }))
    })

    it('première policy de la société : POST (jamais de PATCH sans id existant)', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.policyList).toHaveBeenCalled())
      fireEvent.change(screen.getByTestId('ae-conn-policy-allowed-new'),
        { target: { value: 'Explainers animés' } })
      fireEvent.click(screen.getByTestId('ae-conn-policy-allowed-add'))
      fireEvent.click(screen.getByTestId('ae-conn-policy-save'))
      await waitFor(() => expect(mocks.policyCreate).toHaveBeenCalledWith({
        forbidden_rules: [],
        allowed_rules: [{ key: 'explainers_animes', label: 'Explainers animés' }],
      }))
      expect(mocks.policyUpdate).not.toHaveBeenCalled()
    })
  })

  /* PUB129 — Cockpit d'autonomie : les portes de préflight AVEC leur
     remédiation cliquable, et la cérémonie d'activation/désactivation. */
  describe('cockpit d\'autonomie (PUB129)', () => {
    it('montre chaque porte avec son état et sa remédiation FR', async () => {
      renderScreen()
      await screen.findByTestId('ae-conn-autonomy')
      // Porte verte : badge Vert, aucune remédiation affichée.
      expect(await screen.findByTestId('ae-conn-autonomy-ok-loop')).toBeInTheDocument()
      expect(screen.queryByTestId('ae-conn-autonomy-fix-loop')).toBeNull()
      // Portes rouges : badge Rouge + détail serveur + lien de remédiation.
      expect(screen.getByTestId('ae-conn-autonomy-ko-field_tests')).toBeInTheDocument()
      expect(screen.getByText('Inconnues terrain non tranchées : FT1.')).toBeInTheDocument()
      expect(screen.getByTestId('ae-conn-autonomy-fix-field_tests'))
        .toHaveAttribute('href', '/publicite/tests-terrain')
      expect(screen.getByTestId('ae-conn-autonomy-fix-alerts'))
        .toHaveAttribute('href', '/publicite/regles')
      // Une remédiation par COMMANDE serveur est affichée, jamais déclenchée.
      expect(screen.getByTestId('ae-conn-autonomy-cmd-alerts'))
        .toHaveTextContent('python manage.py seed_adsengine')
      // État : autonomie OFF + nombre de portes à ouvrir (depuis le serveur).
      expect(screen.getByTestId('ae-conn-autonomy-etat'))
        .toHaveTextContent('Autonomie désactivée')
      expect(screen.getByTestId('ae-conn-autonomy-pret'))
        .toHaveTextContent('3 porte(s) à ouvrir')
    })

    it('activation refusée : le message du serveur est affiché TEL QUEL', async () => {
      const refus = "Autonomie non activable : Inconnues terrain non tranchées : FT1."
      mocks.activerAutonomie.mockRejectedValue({
        response: { data: { ...autonomyPayload(), detail: refus } },
      })
      renderScreen()
      await screen.findByTestId('ae-conn-autonomy')
      fireEvent.click(screen.getByTestId('ae-conn-autonomy-activer'))
      expect(await screen.findByTestId('ae-conn-autonomy-err')).toHaveTextContent(refus)
      expect(screen.getByTestId('ae-conn-autonomy-etat'))
        .toHaveTextContent('Autonomie désactivée')
    })

    it('le bouton Activer n\'est jamais pré-grisé par une porte rouge', async () => {
      renderScreen()
      await screen.findByTestId('ae-conn-autonomy')
      // Portes rouges au chargement : le bouton reste cliquable — c'est le
      // serveur qui refuse et DIT pourquoi.
      expect(screen.getByTestId('ae-conn-autonomy-activer')).not.toBeDisabled()
    })

    it('toutes les portes vertes : l\'activation passe et l\'état devient ACTIVE', async () => {
      mocks.activerAutonomie.mockResolvedValue({ data: {
        ...autonomyPayload({ pret: true, actif: true, manquantes: [] }),
        detail: 'Autonomie ACTIVÉE (toutes les portes sont vertes).',
      } })
      renderScreen()
      await screen.findByTestId('ae-conn-autonomy')
      fireEvent.click(screen.getByTestId('ae-conn-autonomy-activer'))
      await waitFor(() => expect(mocks.activerAutonomie).toHaveBeenCalled())
      expect(await screen.findByTestId('ae-conn-autonomy-msg'))
        .toHaveTextContent('Autonomie ACTIVÉE')
      expect(screen.getByTestId('ae-conn-autonomy-etat'))
        .toHaveTextContent('Autonomie ACTIVE.')
    })

    it('la désactivation est libre : un clic, aucune porte requise', async () => {
      mocks.autonomie.mockResolvedValue({ data: autonomyPayload({ actif: true }) })
      mocks.desactiverAutonomie.mockResolvedValue({ data: {
        ...autonomyPayload({ actif: false }), detail: 'Autonomie DÉSACTIVÉE.',
      } })
      renderScreen()
      await waitFor(() => expect(screen.getByTestId('ae-conn-autonomy-etat'))
        .toHaveTextContent('Autonomie ACTIVE.'))
      const bouton = screen.getByTestId('ae-conn-autonomy-desactiver')
      expect(bouton).not.toBeDisabled()
      fireEvent.click(bouton)
      await waitFor(() => expect(mocks.desactiverAutonomie).toHaveBeenCalledTimes(1))
      expect(await screen.findByTestId('ae-conn-autonomy-msg'))
        .toHaveTextContent('Autonomie DÉSACTIVÉE.')
    })

    it('la porte simulation s\'acquitte EN PLACE (remédiation cliquable)', async () => {
      mocks.acquitterSimulation.mockResolvedValue({ data: {
        ...autonomyPayload(), detail: 'Simulation acquittée.',
      } })
      renderScreen()
      await screen.findByTestId('ae-conn-autonomy')
      fireEvent.click(screen.getByTestId('ae-conn-autonomy-ack-simulation'))
      await waitFor(() => expect(mocks.acquitterSimulation).toHaveBeenCalledTimes(1))
      expect(await screen.findByTestId('ae-conn-autonomy-msg'))
        .toHaveTextContent('Simulation acquittée.')
      // Seule la porte qui porte l'action l'expose.
      expect(screen.queryByTestId('ae-conn-autonomy-ack-field_tests')).toBeNull()
    })

    it('cockpit indisponible : rien n\'est fabriqué à l\'écran', async () => {
      mocks.autonomie.mockRejectedValue(new Error('boom'))
      renderScreen()
      expect(await screen.findByTestId('ae-conn-autonomy-vide')).toBeInTheDocument()
      expect(screen.getByTestId('ae-conn-autonomy-etat'))
        .toHaveTextContent('Autonomie désactivée')
      // La coupure reste offerte même sans portes chargées (sécurité).
      expect(screen.getByTestId('ae-conn-autonomy-desactiver')).not.toBeDisabled()
    })
  })
})
