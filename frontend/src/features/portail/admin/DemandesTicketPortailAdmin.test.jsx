import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT101 — Demandes de ticket (portail) : prendre_en_charge lie un ticket
   SAV EXISTANT (le serveur n'en crée jamais un lui-même) ; le lien affiché
   vient de la réponse serveur, jamais un ticket fictif côté client. */

vi.mock('../../../api/portailApi', () => ({
  default: { admin: { demandesTicket: { liste: vi.fn(), prendreEnCharge: vi.fn() } } },
}))

import portailApi from '../../../api/portailApi'
import DemandesTicketPortailAdmin from './DemandesTicketPortailAdmin'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('DemandesTicketPortailAdmin — PACT101', () => {
  it('affiche la liste avec sujet et statut', async () => {
    portailApi.admin.demandesTicket.liste.mockResolvedValue({
      data: [{
        id: 1, client_id: 5, chantier_id: null, sujet: 'Onduleur en panne',
        statut: 'soumise', ticket_id: null, date_creation: '2026-08-01T08:00:00Z',
      }],
    })
    renderPage(<DemandesTicketPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Onduleur en panne').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Soumise').length).toBeGreaterThan(0)
  })

  it('affiche un état vide quand aucune demande', async () => {
    portailApi.admin.demandesTicket.liste.mockResolvedValue({ data: [] })
    renderPage(<DemandesTicketPortailAdmin />)
    expect((await screen.findAllByText('Aucune demande')).length).toBeGreaterThan(0)
  })

  it("prend en charge une demande soumise en liant un ticket SAV existant", async () => {
    portailApi.admin.demandesTicket.liste.mockResolvedValue({
      data: [{
        id: 3, client_id: 9, chantier_id: 21, sujet: 'Fuite au toit',
        statut: 'soumise', ticket_id: null, date_creation: '2026-08-01T08:00:00Z',
      }],
    })
    portailApi.admin.demandesTicket.prendreEnCharge.mockResolvedValue({
      data: {
        id: 3, client_id: 9, chantier_id: 21, sujet: 'Fuite au toit',
        statut: 'prise_en_charge', ticket_id: 77, date_creation: '2026-08-01T08:00:00Z',
      },
    })
    renderPage(<DemandesTicketPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Fuite au toit').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: /Prendre en charge/ })[0])
    // DataTable rend simultanément table (desktop) et cartes (mobile) : l'état
    // `edit` étant partagé, les DEUX vues basculent en édition (même patron
    // que WarrantyClaimsPage.test.jsx) — on agit sur la première occurrence.
    const champ = screen.getAllByLabelText(/N° de ticket SAV existant/)[0]
    fireEvent.change(champ, { target: { value: '77' } })
    fireEvent.click(screen.getAllByRole('button', { name: /Confirmer/ })[0])
    await waitFor(() => expect(portailApi.admin.demandesTicket.prendreEnCharge)
      .toHaveBeenCalledWith(3, { ticket_id: 77 }))
  })

  it("affiche le lien vers le ticket SAV réellement lié par le serveur", async () => {
    portailApi.admin.demandesTicket.liste.mockResolvedValue({
      data: [{
        id: 4, client_id: 2, chantier_id: null, sujet: 'Coupure onduleur',
        statut: 'prise_en_charge', ticket_id: 55, date_creation: '2026-08-01T08:00:00Z',
      }],
    })
    renderPage(<DemandesTicketPortailAdmin />)
    const liens = await screen.findAllByRole('link', { name: /Voir le ticket SAV #55/ })
    expect(liens[0]).toHaveAttribute('href', '/sav?id=55')
  })
})
