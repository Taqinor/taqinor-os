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
  // AUD148 (b) — le serveur ne publie plus l'URL brute du FileField
  // (`/media/…`, morte par construction) : la colonne lit `lien_ged`, le
  // téléchargement GED authentifié.
  it('affiche la liste avec type, libellé et statut de traitement', async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({
      data: [{
        id: 1, client_id: 12, lead_id: null, type_document: 'facture_onee',
        libelle: 'Facture ONEE juillet', fichier_present: true,
        lien_ged: '/api/django/ged/versions/77/apercu/', document_ged: 55,
        traite: false, date_depot: '2026-08-01T08:00:00Z',
      }],
    })
    const { container } = renderPage(<DocumentsClientPortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('Facture ONEE juillet').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Facture ONEE').length).toBeGreaterThan(0)
    expect(screen.getAllByText('À traiter').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Voir le fichier').length).toBeGreaterThan(0)
    // Aucun lien /media/ rendu : c'est le critère AUD148 (b).
    expect(container.querySelector('a[href^="/media/"]')).toBeNull()
  })

  it("ne rend aucun lien quand la GED n'a pas (encore) le document", async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({
      data: [{
        id: 2, client_id: 12, lead_id: null, type_document: 'plan',
        libelle: 'Plan sans GED', fichier_present: true, lien_ged: null,
        document_ged: null, traite: false, date_depot: '2026-08-01T08:00:00Z',
      }],
    })
    const { container } = renderPage(<DocumentsClientPortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('Plan sans GED').length).toBeGreaterThan(0))
    expect(screen.queryByText('Voir le fichier')).not.toBeInTheDocument()
    expect(container.querySelector('a[href^="/media/"]')).toBeNull()
  })

  it('affiche un état vide quand aucun document', async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({ data: [] })
    renderPage(<DocumentsClientPortailAdmin />)
    expect((await screen.findAllByText('Aucun document')).length).toBeGreaterThan(0)
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
