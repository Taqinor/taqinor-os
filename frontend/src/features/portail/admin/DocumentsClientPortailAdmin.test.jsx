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
  // (`/media/…`, morte par construction). SOLMVP16 — le miroir GED (et son
  // lien de consultation authentifié) a été retiré : la colonne « Fichier »
  // affiche seulement une présence, jamais une URL.
  it('affiche la liste avec type, libellé et statut de traitement', async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({
      data: [{
        id: 1, client_id: 12, lead_id: null, type_document: 'facture_onee',
        libelle: 'Facture ONEE juillet', fichier_present: true,
        traite: false, date_depot: '2026-08-01T08:00:00Z',
      }],
    })
    const { container } = renderPage(<DocumentsClientPortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('Facture ONEE juillet').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Facture ONEE').length).toBeGreaterThan(0)
    expect(screen.getAllByText('À traiter').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Déposé').length).toBeGreaterThan(0)
    // Aucun lien /media/ rendu : c'est le critère AUD148 (b).
    expect(container.querySelector('a[href^="/media/"]')).toBeNull()
  })

  it("n'affiche aucune mention de dépôt sans fichier", async () => {
    portailApi.admin.documentsClient.liste.mockResolvedValue({
      data: [{
        id: 2, client_id: 12, lead_id: null, type_document: 'plan',
        libelle: 'Plan sans fichier', fichier_present: false,
        traite: false, date_depot: '2026-08-01T08:00:00Z',
      }],
    })
    const { container } = renderPage(<DocumentsClientPortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('Plan sans fichier').length).toBeGreaterThan(0))
    expect(screen.queryByText('Déposé')).not.toBeInTheDocument()
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
        libelle: 'Plan toiture', fichier: '',
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
        libelle: 'Justificatif', fichier: '',
        traite: true, date_depot: '2026-08-01T08:00:00Z',
      }],
    })
    renderPage(<DocumentsClientPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Justificatif').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Marquer traité/ })).not.toBeInTheDocument()
  })
})
