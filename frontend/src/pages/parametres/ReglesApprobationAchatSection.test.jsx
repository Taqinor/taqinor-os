import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTP2P32 — Paramètres → Achats → Règles d'approbation des demandes d'achat.
   CRUD complet sur l'endpoint EXISTANT `regles-approbation-achat/` (NTP2P2) :
   créer une règle à seuil 20 000 MAD avec 2 approbateurs, la désactiver, la
   supprimer. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}

      unobserve() {}

      disconnect() {}
    }
  }
})

const getReglesApprobationAchat = vi.fn()
const saveRegleApprobationAchat = vi.fn()
const deleteRegleApprobationAchat = vi.fn()
const getInstallations = vi.fn()

vi.mock('../../api/installationsApi', () => ({
  default: {
    getReglesApprobationAchat: (...a) => getReglesApprobationAchat(...a),
    saveRegleApprobationAchat: (...a) => saveRegleApprobationAchat(...a),
    deleteRegleApprobationAchat: (...a) => deleteRegleApprobationAchat(...a),
    getInstallations: (...a) => getInstallations(...a),
  },
}))

import ReglesApprobationAchatSection from './ReglesApprobationAchatSection'

const REGLE_EXISTANTE = {
  id: 1, libelle: 'Règle générique', montant_min: null, montant_max: null,
  chantier: null, niveau_approbation: 'responsable',
  niveau_approbation_display: 'Responsable', nombre_approbateurs: 1,
  priorite: 0, actif: true,
}

beforeEach(() => {
  getReglesApprobationAchat.mockReset()
  saveRegleApprobationAchat.mockReset()
  deleteRegleApprobationAchat.mockReset()
  getInstallations.mockReset()
  getInstallations.mockResolvedValue({ data: [] })
})

describe('ReglesApprobationAchatSection (NTP2P32)', () => {
  it('liste les règles existantes avec leur seuil et leur niveau', async () => {
    getReglesApprobationAchat.mockResolvedValue({ data: [REGLE_EXISTANTE] })
    render(<ReglesApprobationAchatSection />)

    const ligne = await screen.findByTestId('regle-achat-1')
    expect(within(ligne).getByText('Règle générique')).toBeInTheDocument()
    expect(within(ligne).getByText('Active')).toBeInTheDocument()
    expect(within(ligne).getByText(/Tout montant/)).toBeInTheDocument()
  })

  it("crée une règle à seuil 20 000 MAD avec 2 approbateurs (critère d'acceptation)", async () => {
    const user = userEvent.setup()
    getReglesApprobationAchat.mockResolvedValue({ data: [] })
    saveRegleApprobationAchat.mockResolvedValue({ data: { id: 2 } })
    render(<ReglesApprobationAchatSection />)

    await screen.findByText("Aucune règle pour l'instant.")
    await user.click(screen.getByRole('button', { name: /Nouvelle règle/ }))
    await user.type(screen.getByLabelText(/^Libellé/), 'Seuil élevé')
    await user.type(screen.getByLabelText('Seuil minimum (MAD)'), '20000')
    const champNbApprobateurs = screen.getByLabelText("Nombre d'approbateurs")
    await user.clear(champNbApprobateurs)
    await user.type(champNbApprobateurs, '2')
    await user.click(screen.getByRole('button', { name: 'Créer la règle' }))

    await waitFor(() => expect(saveRegleApprobationAchat).toHaveBeenCalledWith(
      undefined,
      expect.objectContaining({
        libelle: 'Seuil élevé', montant_min: 20000, nombre_approbateurs: 2,
      }),
    ))
  })

  it('désactive une règle active (Switch) sans passer par un dialogue', async () => {
    const user = userEvent.setup()
    getReglesApprobationAchat.mockResolvedValue({ data: [REGLE_EXISTANTE] })
    saveRegleApprobationAchat.mockResolvedValue({ data: { ...REGLE_EXISTANTE, actif: false } })
    render(<ReglesApprobationAchatSection />)

    const ligne = await screen.findByTestId('regle-achat-1')
    await user.click(within(ligne).getByRole('switch'))

    await waitFor(() => expect(saveRegleApprobationAchat)
      .toHaveBeenCalledWith(1, { actif: false }))
  })

  it('supprime une règle après confirmation', async () => {
    const user = userEvent.setup()
    getReglesApprobationAchat.mockResolvedValue({ data: [REGLE_EXISTANTE] })
    deleteRegleApprobationAchat.mockResolvedValue({})
    render(<ReglesApprobationAchatSection />)

    const ligne = await screen.findByTestId('regle-achat-1')
    await user.click(within(ligne).getByRole('button', { name: 'Supprimer Règle générique' }))
    await user.click(await screen.findByRole('button', { name: 'Supprimer' }))

    await waitFor(() => expect(deleteRegleApprobationAchat).toHaveBeenCalledWith(1))
  })
})
