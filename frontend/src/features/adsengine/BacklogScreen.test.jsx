import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG41/PACT111 — Gestionnaire de backlog : file par campagne, runway,
   diversité hooks, approbation ET rejet par LOT des recombinaisons
   (CreativeGenerationBatch), dépôt d'asset, déclencheur du pipeline RÉEL de
   génération ancrée aux faits, et une vue séparée des items SANS lot (que la
   vue groupée ignore silencieusement). Les mocks de ``backlog.list`` (une
   VUE agrégée maison, ``BacklogListView``) reproduisent le dict construit par
   ``views.py`` ; ceux de ``backlog.rawItems`` reproduisent EXACTEMENT
   ``CreativeBacklogItemSerializer`` (id/asset/batch/target_campaign/source/
   status/...) — aucun champ inventé (PACT13). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  approveLot: vi.fn(),
  rejectLot: vi.fn(),
  dropAsset: vi.fn(),
  rawItems: vi.fn(),
  generateGroundedVariants: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    backlog: {
      list: mocks.list, approveLot: mocks.approveLot, rejectLot: mocks.rejectLot,
      dropAsset: mocks.dropAsset, rawItems: mocks.rawItems,
      generateGroundedVariants: mocks.generateGroundedVariants,
    },
  },
}))

import BacklogScreen from './BacklogScreen'

const renderScreen = () => render(<MemoryRouter><BacklogScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [
    { id: 5, campagne: 'Résidentiel Casablanca', runway_jours: 6, runway_cible: 14,
      diversite_hooks: 0.45, lots: [
        { id: 51, nom: 'Recombinaison A', statut: 'en_attente', nb_hooks: 3,
          assets: [{ id: 1, designation: 'Reel toiture' }, { id: 2, designation: 'Statique prix' }] },
        { id: 52, nom: 'Recombinaison B', statut: 'en_attente', nb_hooks: 2, assets: [] },
      ] },
  ] })
  mocks.approveLot.mockResolvedValue({ data: { id: 51, statut: 'approuve' } })
  mocks.rejectLot.mockResolvedValue({ data: { id: 52, status: 'rejetee' } })
  mocks.dropAsset.mockResolvedValue({ data: { id: 99 } })
  // Forme RÉELLE de CreativeBacklogItemSerializer : un item AVEC lot (filtré
  // par cette vue, déjà visible ci-dessus dans le groupé) et un item SANS lot
  // (batch: null — celui que la vue groupée ignore silencieusement).
  mocks.rawItems.mockResolvedValue({ data: [
    { id: 900, asset: 12, batch: 51, target_campaign: 5, source: 'recombinaison',
      earliest_date: null, seasonal_tag: '', status: 'en_file',
      created_at: '', updated_at: '' },
    { id: 901, asset: 34, batch: null, target_campaign: 5, source: 'manuel',
      earliest_date: null, seasonal_tag: '', status: 'en_file',
      created_at: '', updated_at: '' },
  ] })
  mocks.generateGroundedVariants.mockResolvedValue({ data: {
    enabled: true,
    detail: 'Génération lancée : le lot de variantes ancrées apparaîtra dans le backlog pour approbation.',
  } })
})

describe('BacklogScreen (ENG41/PACT111)', () => {
  it('affiche le runway et la diversité de hooks avec les chiffres de l\'API', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-backlog-runway-val-5')).toHaveTextContent('6 j sur 14 j')
    expect(screen.getByTestId('ae-backlog-diversity-val-5')).toHaveTextContent('45 %')
  })

  it('approuve un lot bout-en-bout (le lot passe « Approuvé »)', async () => {
    renderScreen()
    const approveBtn = await screen.findByTestId('ae-backlog-approve-lot-51')
    fireEvent.click(approveBtn)
    await waitFor(() => expect(mocks.approveLot).toHaveBeenCalledWith(51))
    // Le lot est maintenant marqué Approuvé et ses boutons disparaissent.
    await waitFor(() =>
      expect(screen.getByTestId('ae-backlog-lot-status-51')).toHaveTextContent('Approuvé'))
    expect(screen.queryByTestId('ae-backlog-approve-lot-51')).toBeNull()
    expect(screen.queryByTestId('ae-backlog-reject-lot-51')).toBeNull()
    // L'autre lot reste en attente et approuvable/rejetable.
    expect(screen.getByTestId('ae-backlog-approve-lot-52')).toBeInTheDocument()
    expect(screen.getByTestId('ae-backlog-reject-lot-52')).toBeInTheDocument()
  })

  it('rejette un lot bout-en-bout (PACT111 — bouton manquant, le lot passe « Rejeté »)', async () => {
    renderScreen()
    const rejectBtn = await screen.findByTestId('ae-backlog-reject-lot-52')
    fireEvent.click(rejectBtn)
    await waitFor(() => expect(mocks.rejectLot).toHaveBeenCalledWith(52))
    await waitFor(() =>
      expect(screen.getByTestId('ae-backlog-lot-status-52')).toHaveTextContent('Rejeté'))
    expect(screen.queryByTestId('ae-backlog-reject-lot-52')).toBeNull()
    expect(screen.queryByTestId('ae-backlog-approve-lot-52')).toBeNull()
    // Le lot 51 reste inchangé.
    expect(screen.getByTestId('ae-backlog-approve-lot-51')).toBeInTheDocument()
  })

  it('dépose un asset dans le backlog d\'une campagne', async () => {
    renderScreen()
    const input = await screen.findByTestId('ae-backlog-drop-5')
    const file = new File(['x'], 'toiture.jpg', { type: 'image/jpeg' })
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(mocks.dropAsset).toHaveBeenCalled())
    expect(mocks.dropAsset.mock.calls[0][0]).toBe(5)
  })

  it('affiche un état vide sans campagne', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    renderScreen()
    expect(await screen.findByTestId('ae-backlog-empty')).toBeInTheDocument()
  })

  it('PACT111 — affiche les items SANS lot (collection brute), sans toucher la vue groupée', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.rawItems).toHaveBeenCalled())
    const rows = await screen.findAllByTestId('ae-backlog-sans-lot-item')
    // Seul l'item 901 (batch: null) apparaît — pas le 900 (déjà dans un lot).
    expect(rows.length).toBe(1)
    expect(rows[0]).toHaveTextContent('Asset #34')
    // La vue groupée existante n'a pas changé : toujours ses 2 lots.
    expect(await screen.findAllByTestId('ae-backlog-lot')).toHaveLength(2)
  })

  it('PACT111 — déclenche le pipeline RÉEL de génération ancrée aux faits', async () => {
    renderScreen()
    fireEvent.change(screen.getByTestId('ae-backlog-seed-brief'),
      { target: { value: 'Accroche pompage agricole HMT 40m' } })
    fireEvent.click(screen.getByTestId('ae-backlog-generate-submit'))
    await waitFor(() => expect(mocks.generateGroundedVariants).toHaveBeenCalledWith(
      { seed_brief: 'Accroche pompage agricole HMT 40m' }))
    expect(await screen.findByTestId('ae-backlog-generate-msg'))
      .toHaveTextContent('Génération lancée')
  })

  it('PACT111 — génération désactivée (clé absente) : message clair, jamais un crash', async () => {
    mocks.generateGroundedVariants.mockResolvedValue({ data: {
      enabled: false,
      detail: "Génération IA désactivée : la clé ADSENGINE_GEN_API_KEY n'est pas configurée. Aucun lot créé.",
    } })
    renderScreen()
    fireEvent.change(screen.getByTestId('ae-backlog-seed-brief'), { target: { value: 'Brief test' } })
    fireEvent.click(screen.getByTestId('ae-backlog-generate-submit'))
    expect(await screen.findByTestId('ae-backlog-generate-msg'))
      .toHaveTextContent('désactivée')
  })
})
