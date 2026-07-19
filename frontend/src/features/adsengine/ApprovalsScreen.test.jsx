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
  reject: vi.fn(),
  create: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    actions: {
      pending: mocks.pending, approve: mocks.approve, reject: mocks.reject,
      create: mocks.create,
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
  mocks.approve.mockResolvedValue({ data: {} })
  mocks.reject.mockResolvedValue({ data: {} })
  mocks.create.mockResolvedValue({ data: { id: 100 } })
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

  it('approuver appelle l\'API et l\'action QUITTE la boîte', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-approve-11'))
    await waitFor(() => expect(mocks.approve).toHaveBeenCalledWith(11))
    await waitFor(() => expect(screen.getAllByTestId('ae-action-card')).toHaveLength(2))
    expect(screen.queryByTestId('ae-approve-11')).toBeNull()
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
    // Seule l'action non cochée (12) reste dans la boîte.
    await waitFor(() => expect(screen.getAllByTestId('ae-action-card')).toHaveLength(1))
    expect(within(screen.getByTestId('ae-action-card')).getByTestId('ae-approve-12')).toBeInTheDocument()
  })

  it('boîte vide → message dédié', async () => {
    mocks.pending.mockResolvedValue({ data: [] })
    renderScreen()
    expect(await screen.findByTestId('ae-approvals-empty')).toBeInTheDocument()
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
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
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
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
    fireEvent.keyDown(window, { key: 'j' }) // focus la 2e carte (id 12)
    fireEvent.keyDown(window, { key: 'a' })
    await waitFor(() => expect(mocks.approve).toHaveBeenCalledWith(12))
  })

  it('R ouvre le panneau de rejet STRUCTURÉ de la carte focalisée', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.pending).toHaveBeenCalled())
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
