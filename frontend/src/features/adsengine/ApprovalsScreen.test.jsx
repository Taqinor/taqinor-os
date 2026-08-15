import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG25 — la boîte d'approbation (écran-vaisseau-amiral) : cartes EngineAction
   avec artefact réel (préview créatif, diff budget avant→après) + reason_fr,
   approuver/rejeter en contrôles STRUCTURÉS (jamais du chat), batch avec toggle
   par item (partiel possible), une action appliquée quitte la boîte. */

const mocks = vi.hoisted(() => ({
  pending: vi.fn(),
  approve: vi.fn(),
  apply: vi.fn(),
  reject: vi.fn(),
  create: vi.fn(),
  // PUB10 — permissions effectives ; pleines par défaut (préserve le
  // comportement des tests existants), restreintes dans les tests dédiés.
  permissions: ['adsengine_approve', 'adsengine_manage'],
}))

vi.mock('./adsengineApi', () => ({
  default: {
    actions: {
      pending: mocks.pending, approve: mocks.approve, reject: mocks.reject,
      apply: mocks.apply, create: mocks.create,
    },
    // PUB48 — cloche de la console (AlertCenter), historique vide par défaut :
    // hors périmètre de ce fichier, mais montée sur l'écran (import réel).
    alerts: { history: () => Promise.resolve({ data: [] }) },
    // PUB51 — palette de commandes (CommandPalette), montée sur l'écran mais
    // ses données ne sont tirées qu'à l'ouverture (Ctrl-K, jamais pressé ici).
    campaigns: { list: () => Promise.resolve({ data: [] }) },
    metrics: { adsCockpit: () => Promise.resolve({ data: [] }) },
  },
}))

vi.mock('./useAdsPermissions', () => ({
  useAdsPermissions: () => ({
    loading: false,
    has: (code) => mocks.permissions.includes(code),
  }),
}))

import ApprovalsScreen from './ApprovalsScreen'

const renderScreen = () => render(
  <MemoryRouter><ApprovalsScreen /></MemoryRouter>)

const ACTIONS = [
  { id: 11, type: 'adjust_budget', reason_fr: 'CPL en baisse — augmenter la portée.',
    budget_avant: 80, budget_apres: 120 },
  { id: 12, type: 'swap_creative', reason_fr: 'Créatif fatigué (fréquence 3,2).',
    creative: { designation: 'Reel toiture v2', type: 'reel', preview_url: 'https://cdn/x.jpg' } },
  { id: 13, type: 'create_campaign', reason_fr: 'Nouvelle ville : Marrakech.' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.pending.mockResolvedValue({ data: ACTIONS })
  mocks.approve.mockResolvedValue({ data: { status: 'approuvee' } })
  mocks.apply.mockResolvedValue({ data: { status: 'appliquee' } })
  mocks.reject.mockResolvedValue({ data: {} })
  mocks.create.mockResolvedValue({ data: { id: 100 } })
  mocks.permissions = ['adsengine_approve', 'adsengine_manage']
})

describe('ApprovalsScreen (ENG25)', () => {
  it('montre les cartes avec reason_fr et l\'artefact réel (diff budget + créatif)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    expect(screen.getAllByTestId('ae-action-card')).toHaveLength(3)
    // reason_fr rendu.
    expect(screen.getByText('CPL en baisse — augmenter la portée.')).toBeInTheDocument()
    // Diff budget avant→après (artefact réel).
    const budget = screen.getByTestId('ae-artifact-budget')
    expect(budget).toHaveTextContent('80 MAD')
    expect(budget).toHaveTextContent('120 MAD')
    // Préview créatif (artefact réel) avec alt accessible.
    expect(screen.getByAltText('Reel toiture v2')).toBeInTheDocument()
  })

  it('WIR208 — approuver n\'applique RIEN : la carte reste, avec « Appliquer »', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-approve-11'))
    await waitFor(() => expect(mocks.approve).toHaveBeenCalledWith(11))
    // La carte NE quitte PAS la boîte : rien n'est encore parti chez Meta.
    await waitFor(() => expect(screen.getByTestId('ae-apply-11')).toBeInTheDocument())
    expect(screen.getAllByTestId('ae-action-card')).toHaveLength(3)
    expect(screen.queryByTestId('ae-approve-11')).toBeNull()
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('WIR208 — « Appliquer » POSTe apply/ et la carte quitte la boîte au statut appliquee', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-approve-11'))
    const apply = await screen.findByTestId('ae-apply-11')
    fireEvent.click(apply)
    await waitFor(() => expect(mocks.apply).toHaveBeenCalledWith(11))
    await waitFor(() => expect(screen.getAllByTestId('ae-action-card')).toHaveLength(2))
    expect(screen.queryByTestId('ae-apply-11')).toBeNull()
  })

  it('WIR208 — 502 Meta : message FR et l\'action NE disparaît PAS', async () => {
    mocks.apply.mockRejectedValue({ response: { status: 502 } })
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-approve-11'))
    fireEvent.click(await screen.findByTestId('ae-apply-11'))
    await waitFor(() => expect(mocks.apply).toHaveBeenCalledWith(11))
    expect(await screen.findByText(/Meta a refusé/)).toBeInTheDocument()
    expect(screen.getByTestId('ae-apply-11')).toBeInTheDocument()
    expect(screen.getAllByTestId('ae-action-card')).toHaveLength(3)
  })

  it('WIR208 — 409 non approuvée : message FR explicite, rien envoyé à Meta', async () => {
    mocks.apply.mockRejectedValue({ response: { status: 409 } })
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-approve-11'))
    fireEvent.click(await screen.findByTestId('ae-apply-11'))
    await waitFor(() => expect(mocks.apply).toHaveBeenCalledWith(11))
    expect(await screen.findByText(/n'est pas approuvée/)).toBeInTheDocument()
    expect(screen.getByTestId('ae-apply-11')).toBeInTheDocument()
  })

  it('rejeter est STRUCTURÉ (motif via select, jamais de chat) et retire l\'action', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    // Aucune zone de texte libre (chat) sur l'écran.
    expect(screen.queryByRole('textbox')).toBeNull()
    fireEvent.click(screen.getByTestId('ae-reject-12'))
    const reason = await screen.findByTestId('ae-reject-reason-12')
    // Le motif est un select (contrôle structuré), pas un textarea.
    expect(reason.tagName).toBe('SELECT')
    fireEvent.change(reason, { target: { value: 'creatif_non_conforme' } })
    fireEvent.click(screen.getByTestId('ae-reject-confirm-12'))
    await waitFor(() => expect(mocks.reject).toHaveBeenCalledWith(12, { reason: 'creatif_non_conforme' }))
    await waitFor(() => expect(screen.queryByTestId('ae-reject-12')).toBeNull())
  })

  it('batch PARTIEL : n\'approuve que les cases cochées', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    // Coche 2 des 3 actions.
    fireEvent.click(screen.getByTestId('ae-batch-toggle-11'))
    fireEvent.click(screen.getByTestId('ae-batch-toggle-13'))
    expect(screen.getByTestId('ae-batch-count')).toHaveTextContent('2')
    fireEvent.click(screen.getByTestId('ae-batch-approve'))
    await waitFor(() => expect(mocks.approve).toHaveBeenCalledTimes(2))
    expect(mocks.approve).toHaveBeenCalledWith(11)
    expect(mocks.approve).toHaveBeenCalledWith(13)
    expect(mocks.approve).not.toHaveBeenCalledWith(12)
    // WIR208 — les 2 approuvées attendent « Appliquer » ; seule 12 reste à approuver.
    await waitFor(() => expect(screen.getByTestId('ae-apply-11')).toBeInTheDocument())
    expect(screen.getByTestId('ae-apply-13')).toBeInTheDocument()
    expect(screen.getByTestId('ae-approve-12')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-apply-12')).toBeNull()
  })

  it('boîte vide → message dédié', async () => {
    mocks.pending.mockResolvedValue({ data: [] })
    renderScreen()
    expect(await screen.findByTestId('ae-approvals-empty')).toBeInTheDocument()
  })

  // ── PUB41 — Fraîcheur + panne visibles (sondage doux + état-erreur) ─────
  describe('PUB41 — sondage doux + état-erreur', () => {
    it('panne réseau -> message d’erreur, PAS « aucune action en attente »', async () => {
      mocks.pending.mockRejectedValue(new Error('network'))
      renderScreen()
      expect(await screen.findByTestId('ae-approvals-load-error')).toBeInTheDocument()
      expect(screen.queryByTestId('ae-approvals-empty')).toBeNull()
    })

    it('boîte réellement vide (succès) -> état-vide normal, pas d’erreur', async () => {
      mocks.pending.mockResolvedValue({ data: [] })
      renderScreen()
      await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
      expect(screen.getByTestId('ae-approvals-empty')).toBeInTheDocument()
      expect(screen.queryByTestId('ae-approvals-load-error')).toBeNull()
    })

    it('bouton « Actualiser » redéclenche un chargement immédiat', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.pending).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByTestId('ae-approvals-refresh'))
      await waitFor(() => expect(mocks.pending).toHaveBeenCalledTimes(2))
    })

    it('un échec puis un succès efface le message d’erreur', async () => {
      mocks.pending.mockRejectedValueOnce(new Error('network'))
      renderScreen()
      await screen.findByTestId('ae-approvals-load-error')
      mocks.pending.mockResolvedValue({ data: ACTIONS })
      fireEvent.click(screen.getByTestId('ae-approvals-refresh'))
      await waitFor(() => expect(screen.getAllByTestId('ae-action-card')).toHaveLength(3))
      expect(screen.queryByTestId('ae-approvals-load-error')).toBeNull()
    })
  })
})

describe('ApprovalsScreen — avertissements + composeur EDIT_COPY (ADSDEEP35)', () => {
  const EDIT_ACTIONS = [
    { id: 21, type: 'edit_copy', reason_fr: "Rafraîchir l'accroche.",
      payload: {
        warnings: ['Édition significative : réinitialise l’apprentissage.',
                    'Perte de preuve sociale.'],
        current_creative: { body: 'Ancien texte fatigué' },
        creative_spec: { title: 'Nouveau', body: 'Nouveau texte frais' },
      } },
  ]

  it('rend les avertissements du payload en chips ET le diff avant/après', async () => {
    mocks.pending.mockResolvedValue({ data: EDIT_ACTIONS })
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    const chips = screen.getAllByTestId('ae-warning-chip')
    expect(chips).toHaveLength(2)
    const diff = screen.getByTestId('ae-edit-copy-diff')
    expect(diff).toHaveTextContent('Ancien texte fatigué')
    expect(diff).toHaveTextContent('Nouveau texte frais')
  })

  it('le composeur EDIT_COPY se montre/masque et recharge la boîte après proposition', async () => {
    mocks.pending.mockResolvedValue({ data: [] })
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalledTimes(1))
    expect(screen.queryByTestId('ae-composer')).toBeNull()

    fireEvent.click(screen.getByTestId('ae-toggle-composer'))
    expect(screen.getByTestId('ae-composer')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('ae-composer-ad-id'), { target: { value: 'ad-7' } })
    fireEvent.change(screen.getByTestId('ae-composer-proposed-body'), { target: { value: 'Texte neuf' } })
    fireEvent.change(screen.getByTestId('ae-composer-reason'), { target: { value: 'Motif clair.' } })
    fireEvent.click(screen.getByTestId('ae-composer-submit'))

    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    // Recharge la boîte + referme le composeur.
    await waitFor(() => expect(mocks.pending).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByTestId('ae-composer')).toBeNull())
  })
})

/* WIR63 — DaypartingGrid (ADSDEEP36) était montée dans ManualActionComposer.jsx
   (composeur) mais jamais côté REVUE : une carte `set_schedule` n'affichait
   que le libellé générique. Miroir de `editCopyDiff` : avant (défaut Meta
   24/7, `emptyGrid()`, aucune donnée inventée) / après (grille proposée). */
describe('ApprovalsScreen — grille dayparting avant/après (WIR63, set_schedule)', () => {
  const SCHEDULE_ACTIONS = [
    { id: 31, type: 'set_schedule', reason_fr: 'Poser un horaire de diffusion.',
      payload: {
        adset_id: 'a1', mode: 'native',
        grid: { mon: Array.from({ length: 24 }, (_, h) => (h >= 8 && h < 20 ? 1 : 0)),
                tue: Array(24).fill(1), wed: Array(24).fill(1), thu: Array(24).fill(1),
                fri: Array(24).fill(1), sat: Array(24).fill(1), sun: Array(24).fill(1) },
      } },
  ]

  it('rend la grille avant (24/7 par défaut) et après (proposée), lecture seule', async () => {
    mocks.pending.mockResolvedValue({ data: SCHEDULE_ACTIONS })
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())

    const diff = screen.getByTestId('ae-dayparting-diff')
    expect(diff).toBeInTheDocument()

    const before = within(screen.getByTestId('ae-dayparting-before'))
    const after = within(screen.getByTestId('ae-dayparting-after'))
    // Avant : 24/7 (défaut Meta, aucune restriction) — lundi 3h autorisé.
    expect(before.getByTestId('dp-cell-mon-3')).toHaveAttribute('aria-pressed', 'true')
    // Après : la grille PROPOSÉE — lundi 3h bloqué, lundi 10h autorisé.
    expect(after.getByTestId('dp-cell-mon-3')).toHaveAttribute('aria-pressed', 'false')
    expect(after.getByTestId('dp-cell-mon-10')).toHaveAttribute('aria-pressed', 'true')
    // Lecture seule : les cellules sont désactivées (jamais éditables ici).
    expect(after.getByTestId('dp-cell-mon-10')).toBeDisabled()
  })

  it('n\'affiche aucune grille pour une action d\'un autre kind', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    expect(screen.queryByTestId('ae-dayparting-diff')).toBeNull()
  })
})

describe('PUB10 — parité permissions UI', () => {
  it('manage-sans-approve : Approuver/Rejeter/batch sont grisés, le composeur reste actif', async () => {
    mocks.permissions = ['adsengine_manage'] // pas adsengine_approve
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    expect(screen.getByTestId('ae-approve-11')).toBeDisabled()
    expect(screen.getByTestId('ae-reject-11')).toBeDisabled()
    // Cliquer un bouton désactivé n'appelle jamais l'API.
    fireEvent.click(screen.getByTestId('ae-approve-11'))
    expect(mocks.approve).not.toHaveBeenCalled()
    // Le composeur (adsengine_manage) reste utilisable.
    expect(screen.getByTestId('ae-toggle-composer')).not.toBeDisabled()

    // Batch : cocher une case puis le bouton de sélection reste grisé.
    fireEvent.click(screen.getByTestId('ae-batch-toggle-11'))
    expect(screen.getByTestId('ae-batch-approve')).toBeDisabled()
  })

  it('approve-sans-manage : le composeur est grisé, Approuver/Rejeter restent actifs', async () => {
    mocks.permissions = ['adsengine_approve'] // pas adsengine_manage
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    expect(screen.getByTestId('ae-toggle-composer')).toBeDisabled()
    expect(screen.getByTestId('ae-approve-11')).not.toBeDisabled()
    expect(screen.getByTestId('ae-reject-11')).not.toBeDisabled()
  })

  it('aucune permission : tous les contrôles protégés sont grisés', async () => {
    mocks.permissions = []
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    expect(screen.getByTestId('ae-approve-11')).toBeDisabled()
    expect(screen.getByTestId('ae-reject-11')).toBeDisabled()
    expect(screen.getByTestId('ae-toggle-composer')).toBeDisabled()
  })

  // PUB10/PUB51 — les raccourcis clavier A/R doivent respecter la même garde
  // de permission que les boutons : sans adsengine_approve, ni A ni R ne
  // doivent appeler l'API ou ouvrir le panneau de rejet.
  it('aucune permission : les raccourcis clavier A/R sont sans effet', async () => {
    mocks.permissions = []
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.keyDown(window, { key: 'a' })
    expect(mocks.approve).not.toHaveBeenCalled()
    fireEvent.keyDown(window, { key: 'r' })
    expect(screen.queryByTestId('ae-reject-panel-11')).toBeNull()
  })
})

describe('ApprovalsScreen — PUB51 raccourcis clavier (sans souris)', () => {
  it('la première carte est focalisée par défaut', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    const cards = screen.getAllByTestId('ae-action-card')
    expect(cards[0]).toHaveClass('ae-action-card-focused')
    expect(cards[1]).not.toHaveClass('ae-action-card-focused')
  })

  it('J avance le focus, K recule', async () => {
    renderScreen()
    // Attendre que les cartes soient RENDUES (pas seulement `pending` appelé) :
    // le gestionnaire clavier lit `actions` — tant qu'elles ne sont pas chargées,
    // `j` bornerait l'index à 0 (liste vide).
    await screen.findAllByTestId('ae-action-card')
    fireEvent.keyDown(window, { key: 'j' })
    let cards = screen.getAllByTestId('ae-action-card')
    expect(cards[1]).toHaveClass('ae-action-card-focused')
    fireEvent.keyDown(window, { key: 'j' })
    cards = screen.getAllByTestId('ae-action-card')
    expect(cards[2]).toHaveClass('ae-action-card-focused')
    fireEvent.keyDown(window, { key: 'k' })
    cards = screen.getAllByTestId('ae-action-card')
    expect(cards[1]).toHaveClass('ae-action-card-focused')
  })

  it('A approuve la carte focalisée', async () => {
    renderScreen()
    await screen.findAllByTestId('ae-action-card')
    fireEvent.keyDown(window, { key: 'j' }) // focus la 2e carte (id 12)
    fireEvent.keyDown(window, { key: 'a' })
    await waitFor(() => expect(mocks.approve).toHaveBeenCalledWith(12))
  })

  it('R ouvre le panneau de rejet STRUCTURÉ de la carte focalisée', async () => {
    renderScreen()
    await screen.findAllByTestId('ae-action-card')
    fireEvent.keyDown(window, { key: 'r' }) // carte 0 (id 11)
    expect(await screen.findByTestId('ae-reject-panel-11')).toBeInTheDocument()
  })

  it('jamais déclenché pendant qu\'un champ (select du motif) est focalisé', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-reject-12'))
    const select = await screen.findByTestId('ae-reject-reason-12')
    select.focus()
    fireEvent.keyDown(select, { key: 'a' })
    fireEvent.keyDown(select, { key: 'j' })
    expect(mocks.approve).not.toHaveBeenCalled()
    // Le focus visuel des cartes n'a pas bougé (toujours la 1re).
    const cards = screen.getAllByTestId('ae-action-card')
    expect(cards[0]).toHaveClass('ae-action-card-focused')
  })
})

describe('ApprovalsScreen — PUB56 cibles tactiles ≥44×44px', () => {
  it('Approuver/Rejeter ont une cible tactile d\'au moins 44×44px', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    const approve = screen.getByTestId('ae-approve-11')
    const reject = screen.getByTestId('ae-reject-11')
    expect(parseInt(approve.style.minHeight, 10)).toBeGreaterThanOrEqual(44)
    expect(parseInt(approve.style.minWidth, 10)).toBeGreaterThanOrEqual(44)
    expect(parseInt(reject.style.minHeight, 10)).toBeGreaterThanOrEqual(44)
    expect(parseInt(reject.style.minWidth, 10)).toBeGreaterThanOrEqual(44)
  })

  it('la case à cocher batch a une zone de tap ≥44×44px (label enveloppant)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    const checkbox = screen.getByTestId('ae-batch-toggle-11')
    const label = checkbox.closest('label')
    expect(label).not.toBeNull()
    expect(parseInt(label.style.minHeight, 10)).toBeGreaterThanOrEqual(44)
    expect(parseInt(label.style.minWidth, 10)).toBeGreaterThanOrEqual(44)
  })

  it('le panneau de rejet (confirmer/annuler/select) a des cibles ≥44px', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-reject-11'))
    const confirmBtn = await screen.findByTestId('ae-reject-confirm-11')
    const select = screen.getByTestId('ae-reject-reason-11')
    expect(parseInt(confirmBtn.style.minHeight, 10)).toBeGreaterThanOrEqual(44)
    expect(parseInt(select.style.minHeight, 10)).toBeGreaterThanOrEqual(44)
  })
})
