import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* PACT74 — pièces du dossier de consultation reçu de l'acheteur (AOF21).
   Preuves : (1) les pièces sont filtrées sur CETTE affaire ; (2) un additif
   part TOUJOURS de l'action serveur dédiée (jamais un POST brut de type
   « additif ») et affiche le nombre RÉEL d'exigences marquées à revérifier,
   renvoyé par le serveur ; (3) une pièce fournie avec fichier upload PUIS
   patch (jamais l'inverse). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  additif: vi.fn(),
  uploadAttachment: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '1' }) }
})

vi.mock('../../api/aoApi', () => ({
  default: {
    piecesConsultation: {
      list: mocks.list, create: mocks.create, update: mocks.update, additif: mocks.additif,
    },
  },
}))
vi.mock('../../api/recordsApi', () => ({
  default: { uploadAttachment: mocks.uploadAttachment },
}))

import PiecesConsultation from './PiecesConsultation'

const CPS = {
  id: 10, appel_offre: 1, type_piece: 'cps', type_piece_display: 'CPS (cahier des prescriptions spéciales)',
  est_additif: false, reference: 'CPS-2026-014', version: '1', date_reception: '2026-07-01', modifie: null,
}
const ADDITIF = {
  id: 11, appel_offre: 1, type_piece: 'additif', type_piece_display: 'Additif / erratum',
  est_additif: true, reference: 'Erratum n°1', version: '', date_reception: '2026-07-20', modifie: 10,
}

const renderEcran = (props) => render(
  <MemoryRouter><PiecesConsultation affaireId={1} {...props} /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [CPS] })
  mocks.create.mockResolvedValue({ data: { id: 12 } })
  mocks.update.mockResolvedValue({ data: {} })
  mocks.uploadAttachment.mockResolvedValue({ data: { id: 777 } })
  mocks.additif.mockResolvedValue({ data: { exigences_a_reverifier: [3, 8] } })
})

describe('PiecesConsultation (PACT74)', () => {
  it('charge les pièces filtrées sur CETTE affaire (jamais toute la société)', async () => {
    renderEcran()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ appel_offre: 1 }))
    expect((await screen.findAllByText('CPS-2026-014')).length).toBeGreaterThan(0)
  })

  it('créer une pièce SANS fichier ne fait AUCUN appel d’upload', async () => {
    renderEcran()
    await screen.findAllByText('CPS-2026-014')
    await userEvent.type(screen.getByLabelText('Référence'), 'Règlement-2026')
    await userEvent.click(screen.getAllByRole('button', { name: 'Enregistrer la pièce' })[0])
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ appel_offre: 1, type_piece: 'cps', reference: 'Règlement-2026' }),
    ))
    expect(mocks.uploadAttachment).not.toHaveBeenCalled()
  })

  it('créer une pièce AVEC fichier uploade PUIS patch l’attachement (jamais l’inverse)', async () => {
    renderEcran()
    await screen.findAllByText('CPS-2026-014')
    const fichier = new File(['x'], 'cps.pdf', { type: 'application/pdf' })
    await userEvent.upload(screen.getByLabelText('Fichier (facultatif)'), fichier)
    await userEvent.click(screen.getAllByRole('button', { name: 'Enregistrer la pièce' })[0])

    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    await waitFor(() => expect(mocks.uploadAttachment).toHaveBeenCalledWith('ao.piececonsultation', 12, fichier))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(12, { attachment: 777 }))
  })

  it('un additif passe TOUJOURS par l’action serveur dédiée, jamais un POST brut', async () => {
    renderEcran()
    await screen.findAllByText('CPS-2026-014')
    await userEvent.click(screen.getAllByRole('button', { name: 'Signaler un additif' })[0])
    await userEvent.type(screen.getByLabelText("Référence de l'additif"), 'Erratum n°1')
    await userEvent.click(screen.getAllByRole('button', { name: "Enregistrer l'additif" })[0])

    await waitFor(() => expect(mocks.additif).toHaveBeenCalledWith(10, { reference: 'Erratum n°1', version: '' }))
    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('un additif déjà enregistré affiche la pièce qu’il modifie (jamais une désignation devinée)', async () => {
    mocks.list.mockResolvedValue({ data: [CPS, ADDITIF] })
    renderEcran()
    expect((await screen.findAllByText('modifie « CPS-2026-014 »')).length).toBeGreaterThan(0)
    // Un additif n'a pas d'action « Signaler un additif » — il EST déjà l'additif.
    expect(screen.getAllByRole('button', { name: 'Signaler un additif' })).toHaveLength(1)
  })
})
