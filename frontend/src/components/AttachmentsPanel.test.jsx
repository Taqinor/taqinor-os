import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../api/recordsApi', () => ({
  default: {
    getAttachments: vi.fn(),
    uploadAttachment: vi.fn(),
    deleteAttachment: vi.fn(),
  },
}))
vi.mock('../hooks/useHasPermission', () => ({ useIsAdmin: () => true }))

import recordsApi from '../api/recordsApi'
import AttachmentsPanel from './AttachmentsPanel'
import { ConfirmProvider } from '../providers/ConfirmProvider'

beforeEach(() => { vi.clearAllMocks() })

/* AERR61 — un premier chargement rejeté disait « Aucune pièce jointe. » :
   l'utilisateur croyait le dossier vide et re-téléversait. */
describe('AttachmentsPanel (AERR61)', () => {
  it('lecture rejetée : avis + Réessayer, jamais « Aucune pièce jointe »', async () => {
    recordsApi.getAttachments.mockRejectedValueOnce(new Error('boom'))
    render(<AttachmentsPanel model="crm.lead" id={1} />)

    expect(await screen.findByText(/Pièces jointes non chargées/)).toBeInTheDocument()
    expect(screen.queryByText('Aucune pièce jointe.')).not.toBeInTheDocument()

    recordsApi.getAttachments.mockResolvedValueOnce({
      data: [{ id: 7, filename: 'devis-signe.pdf', mime: 'application/pdf', size: 10, url: '/x' }],
    })
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))

    expect(await screen.findByText('devis-signe.pdf')).toBeInTheDocument()
    expect(screen.queryByText(/Pièces jointes non chargées/)).not.toBeInTheDocument()
  })
})

describe('AttachmentsPanel (AERR68)', () => {
  it('la boîte de suppression nomme le fichier ; Annuler ne supprime rien', async () => {
    recordsApi.getAttachments.mockResolvedValueOnce({
      data: [{ id: 7, filename: 'devis-signe.pdf', mime: 'application/pdf', size: 10, url: '/x' }],
    })
    render(<ConfirmProvider><AttachmentsPanel model="crm.lead" id={1} /></ConfirmProvider>)
    fireEvent.click(await screen.findByLabelText('Supprimer devis-signe.pdf'))
    expect(await screen.findByText(/devis-signe\.pdf sera supprimé/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByText('Supprimer cette pièce jointe ?')).not.toBeInTheDocument())
    expect(recordsApi.deleteAttachment).not.toHaveBeenCalled()
  })
})
