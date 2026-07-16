import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG41 — Gestionnaire de backlog : file par campagne, runway, diversité hooks,
   approbation par LOT des recombinaisons (CreativeGenerationBatch), dépôt
   d'asset. Chiffres = API ENG27 mockée. Cœur du test : approbation par lot
   bout-en-bout. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  approveLot: vi.fn(),
  dropAsset: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    backlog: { list: mocks.list, approveLot: mocks.approveLot, dropAsset: mocks.dropAsset },
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
  mocks.dropAsset.mockResolvedValue({ data: { id: 99 } })
})

describe('BacklogScreen (ENG41)', () => {
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
    // Le lot est maintenant marqué Approuvé et son bouton disparaît.
    await waitFor(() =>
      expect(screen.getByTestId('ae-backlog-lot-status-51')).toHaveTextContent('Approuvé'))
    expect(screen.queryByTestId('ae-backlog-approve-lot-51')).toBeNull()
    // L'autre lot reste en attente et approuvable.
    expect(screen.getByTestId('ae-backlog-approve-lot-52')).toBeInTheDocument()
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
})
