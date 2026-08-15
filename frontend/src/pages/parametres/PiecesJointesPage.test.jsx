import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* WIR270/FG10 — l'endpoint `records/attachments/all/` était complet (scopé
   société, filtrable mime / mime_like / phase / model / since, paginé à 50) et
   `getAllAttachments` l'exposait déjà — mais AUCUN écran ne l'appelait.
   Arbitrage : on construit l'écran plutôt que de supprimer l'export.

   Charge utile alignée sur `AttachmentSerializer` (id, filename, size, mime,
   phase, uploaded_by, uploaded_by_nom, created_at, url) dans l'enveloppe
   paginée DRF — jamais une forme inventée. */

vi.mock('../../api/recordsApi', () => ({
  default: { getAllAttachments: vi.fn() },
}))

import recordsApi from '../../api/recordsApi'
import PiecesJointesPage from './PiecesJointesPage'

const PIECE = {
  id: 3, filename: 'devis.pdf', size: 2048, mime: 'application/pdf',
  phase: 'avant', uploaded_by: 1, uploaded_by_nom: 'reda',
  created_at: '2026-07-01T09:00:00Z',
  url: '/api/django/records/attachments/3/download/',
}

const pagine = (results, extra = {}) => ({
  data: { count: results.length, next: null, previous: null, results, ...extra },
})

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('PiecesJointesPage (WIR270)', () => {
  it('rend la première page et lie chaque fichier à son téléchargement', async () => {
    recordsApi.getAllAttachments.mockResolvedValue(pagine([PIECE]))
    render(<PiecesJointesPage />)

    await waitFor(() => expect(recordsApi.getAllAttachments)
      .toHaveBeenCalledWith({ page: 1 }))
    expect(await screen.findByRole('link', { name: 'devis.pdf' }))
      .toHaveAttribute('href', PIECE.url)
    expect(screen.getByText('2.0 ko')).toBeInTheDocument()
    expect(screen.getByText('reda')).toBeInTheDocument()
  })

  it('les filtres partent au serveur ; un filtre vide n’est pas envoyé', async () => {
    recordsApi.getAllAttachments.mockResolvedValue(pagine([]))
    render(<PiecesJointesPage />)
    await waitFor(() => expect(recordsApi.getAllAttachments).toHaveBeenCalledTimes(1))

    fireEvent.change(screen.getByLabelText(/Type \(contient\)/), { target: { value: 'image' } })
    fireEvent.change(screen.getByLabelText(/Enregistrement/), { target: { value: 'crm.lead' } })
    fireEvent.click(screen.getByRole('button', { name: 'Filtrer' }))

    await waitFor(() => expect(recordsApi.getAllAttachments).toHaveBeenCalledTimes(2))
    expect(recordsApi.getAllAttachments.mock.calls[1][0])
      .toEqual({ page: 1, mime_like: 'image', model: 'crm.lead' })
  })

  it('pagination serveur : « Suivant » demande la page 2', async () => {
    recordsApi.getAllAttachments.mockResolvedValue(
      pagine([PIECE], { next: 'http://x/?page=2' }))
    render(<PiecesJointesPage />)
    await waitFor(() => expect(recordsApi.getAllAttachments).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    await waitFor(() => expect(recordsApi.getAllAttachments)
      .toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })))
  })

  it('sans page suivante, « Suivant » est fermé', async () => {
    recordsApi.getAllAttachments.mockResolvedValue(pagine([PIECE]))
    render(<PiecesJointesPage />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Suivant' })).toBeDisabled())
    expect(screen.getByRole('button', { name: 'Précédent' })).toBeDisabled()
  })

  it('erreur serveur : message FR, jamais du JSON brut', async () => {
    recordsApi.getAllAttachments.mockRejectedValue({
      response: { status: 500, data: { detail: 'Erreur serveur.' } },
    })
    render(<PiecesJointesPage />)

    const alerte = await screen.findByRole('alert')
    expect(alerte.textContent).not.toMatch(/\{"detail"/)
  })
})
