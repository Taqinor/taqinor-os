import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT72 — pièces FOURNIES du dossier de dépôt (AOF115/AOF149).
   Preuve centrale : marquer une pièce présente est TOUJOURS accompagné d'un
   fichier — jamais un état « présente » sans preuve — et le fichier part en
   `records.Attachment` GÉNÉRIQUE (cible `ao.piecedossierao`), jamais un
   FileField local. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  update: vi.fn(),
  uploadAttachment: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  default: { piecesDossierAo: { list: mocks.list, update: mocks.update } },
}))
vi.mock('../../../api/recordsApi', () => ({
  default: { uploadAttachment: mocks.uploadAttachment },
}))

import PiecesFournies from './PiecesFournies'

const PIECE_MANQUANTE = {
  id: 21, dossier: 7, code: 'acte_engagement', libelle: "Acte d'engagement (modèle acheteur)",
  type_piece: 'fournie', obligatoire: true, presente: false, visibilite: 'client', controlee: 'fabriquee',
}
const PIECE_PRESENTE = {
  id: 22, dossier: 7, code: 'caution_bancaire', libelle: 'Caution bancaire scannée',
  type_piece: 'fournie', obligatoire: true, presente: true, visibilite: 'client', controlee: 'hors_controle',
}

const renderEcran = (props) => render(<PiecesFournies dossierId={7} {...props} />)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [PIECE_MANQUANTE, PIECE_PRESENTE] })
  mocks.uploadAttachment.mockResolvedValue({ data: { id: 555 } })
  mocks.update.mockResolvedValue({ data: {} })
})

describe('PiecesFournies (PACT72)', () => {
  it('charge SEULEMENT les pièces FOURNIES du dossier (jamais les générées)', async () => {
    renderEcran()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ dossier: 7, type_piece: 'fournie' }))
    expect(await screen.findByText("Acte d'engagement (modèle acheteur)")).toBeInTheDocument()
    expect(screen.getByText('Caution bancaire scannée')).toBeInTheDocument()
  })

  it('une pièce manquante affiche le badge « Manquante », une présente le badge « Présente »', async () => {
    renderEcran()
    await screen.findByText("Acte d'engagement (modèle acheteur)")
    expect(screen.getByText('Manquante')).toBeInTheDocument()
    expect(screen.getByText('Présente')).toBeInTheDocument()
  })

  it('une pièce hors contrôle porte son badge — jamais présumée verte', async () => {
    renderEcran()
    expect(await screen.findByText('Hors contrôle')).toBeInTheDocument()
  })

  it('joindre un fichier UPLOAD le fichier PUIS marque la pièce présente avec cet attachement', async () => {
    renderEcran()
    const input = await screen.findByLabelText("Fichier — Acte d'engagement (modèle acheteur)")
    const fichier = new File(['contenu'], 'acte.pdf', { type: 'application/pdf' })
    await userEvent.upload(input, fichier)

    await waitFor(() => expect(mocks.uploadAttachment).toHaveBeenCalledWith('ao.piecedossierao', 21, fichier))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(21, { attachment: 555, presente: true }))
    // L'ordre compte : jamais de PATCH avant que le fichier ne soit envoyé.
    const ordreUpload = mocks.uploadAttachment.mock.invocationCallOrder[0]
    const ordreUpdate = mocks.update.mock.invocationCallOrder[0]
    expect(ordreUpload).toBeLessThan(ordreUpdate)
  })

  it('aucune pièce fournie : le panneau ne s’affiche pas (rien à inventer)', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    const { container } = renderEcran()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
