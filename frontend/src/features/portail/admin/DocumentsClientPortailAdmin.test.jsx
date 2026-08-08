import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT99 — Documents clients (portail) : consultation + marquer_traite,
   jamais de formulaire de dépôt (hors périmètre, dépôt déjà automatique). */

vi.mock('../../../api/portailApi', () => ({
  default: { admin: { documentsClient: { liste: vi.fn(), marquerTraite: vi.fn() } } },
}))

import portailApi from '../../../api/portailApi'
import DocumentsClientPortailAdmin from './DocumentsClientPortailAdmin'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('DocumentsClientPortailAdmin — PACT99', () => {
  it('affiche la liste avec type, libellé et statut de traitement', async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({
      data: [{
        id: 1, client_id: 12, lead_id: null, type_document: 'facture_onee',
        libelle: 'Facture ONEE juillet', fichier: '/media/doc.pdf', document_ged: 55,
        traite: false, date_depot: '2026-08-01T08:00:00Z',
      }],
    })
    renderPage(<DocumentsClientPortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('Facture ONEE juillet').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Facture ONEE').length).toBeGreaterThan(0)
    expect(screen.getAllByText('À traiter').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Voir le fichier').length).toBeGreaterThan(0)
  })

  it('affiche un état vide quand aucun document', async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({ data: [] })
    renderPage(<DocumentsClientPortailAdmin />)
    expect(await screen.findByText('Aucun document')).toBeInTheDocument()
  })

  it('marque un document traité sans dupliquer le fichier déjà déposé', async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({
      data: [{
        id: 3, client_id: 9, lead_id: null, type_document: 'plan',
        libelle: 'Plan toiture', fichier: '', document_ged: null,
        traite: false, date_depot: '2026-08-01T08:00:00Z',
      }],
    })
    portailApi.admin.documentsClient.marquerTraite.mockResolvedValue({ data: {} })
    renderPage(<DocumentsClientPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Plan toiture').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: /Marquer traité/ })[0])
    await waitFor(() => expect(portailApi.admin.documentsClient.marquerTraite).toHaveBeenCalledWith(3))
    // Une seule liste rechargée : jamais un second appel de dépôt.
    expect(portailApi.admin.documentsClient.liste).toHaveBeenCalledTimes(2)
  })

  it("n'affiche aucune action pour un document déjà traité", async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({
      data: [{
        id: 5, client_id: 2, lead_id: null, type_document: 'autre',
        libelle: 'Justificatif', fichier: '', document_ged: null,
        traite: true, date_depot: '2026-08-01T08:00:00Z',
      }],
    })
    renderPage(<DocumentsClientPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Justificatif').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Marquer traité/ })).not.toBeInTheDocument()
  })
})
