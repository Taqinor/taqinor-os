import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT98 — Paiements de facture (portail) : rapprochement, jamais de bouton
   « Rejeter » (aucun service serveur ne pose le statut echoue). */

vi.mock('../../../api/portailApi', () => ({
  default: { admin: { paiementsFacture: { liste: vi.fn(), rapprocher: vi.fn() } } },
}))

import portailApi from '../../../api/portailApi'
import PaiementsFacturePortailAdmin from './PaiementsFacturePortailAdmin'
import { enveloppe, pagine } from './paginationTest'


afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('PaiementsFacturePortailAdmin — PACT98', () => {
  it('charge par défaut la file « à rapprocher » (statut=initie)', async () => {
    portailApi.admin.paiementsFacture.liste.mockResolvedValue({ data: enveloppe([]) })
    renderPage(<PaiementsFacturePortailAdmin />)
    await waitFor(() => expect(portailApi.admin.paiementsFacture.liste)
      .toHaveBeenCalledWith({ statut: 'initie', page: 1 }))
  })

  it('affiche le montant formaté et le statut', async () => {
    portailApi.admin.paiementsFacture.liste.mockResolvedValue({
      data: enveloppe([{
        id: 1, facture_id: 77, montant: '150.00', methode: 'virement',
        statut: 'initie', reference: '', paye_le: null, date_creation: '2026-08-01T08:00:00Z',
      }]),
    })
    renderPage(<PaiementsFacturePortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('Facture #77').length).toBeGreaterThan(0))
    // Pas de séparateur de milliers en jeu ici (montant < 1000) : évite toute
    // dépendance à l'espace fine insécable rendue par Intl.NumberFormat('fr-FR').
    expect(screen.getAllByText('150,00 MAD').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Initié').length).toBeGreaterThan(0)
  })

  it('propose Rapprocher pour un paiement initié, jamais de bouton Rejeter', async () => {
    portailApi.admin.paiementsFacture.liste.mockResolvedValue({
      data: enveloppe([{
        id: 5, facture_id: 3, montant: '900.00', methode: 'virement',
        statut: 'initie', reference: '', paye_le: null, date_creation: '2026-08-01T08:00:00Z',
      }]),
    })
    portailApi.admin.paiementsFacture.rapprocher.mockResolvedValue({ data: {} })
    renderPage(<PaiementsFacturePortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Facture #3').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /rejeter/i })).not.toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: /Rapprocher/ })[0])
    await waitFor(() => expect(portailApi.admin.paiementsFacture.rapprocher).toHaveBeenCalledWith(5))
  })

  it("n'affiche aucune action pour un paiement déjà payé", async () => {
    portailApi.admin.paiementsFacture.liste.mockResolvedValue({
      data: enveloppe([{
        id: 9, facture_id: 4, montant: '400.00', methode: 'carte',
        statut: 'paye', reference: 'CMI-1', paye_le: '2026-08-01T10:00:00Z',
        date_creation: '2026-08-01T08:00:00Z',
      }]),
    })
    renderPage(<PaiementsFacturePortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Facture #4').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Rapprocher/ })).not.toBeInTheDocument()
  })
})

describe('ADOC32 — toutes les pages (paiements)', () => {
  it('60 lignes sur deux pages', async () => {
    portailApi.admin.paiementsFacture.liste.mockImplementation(pagine(60, (n) => ({ id: n, facture_id: 1000 + n, montant: '150.00', methode: 'virement', statut: 'initie', reference: '', paye_le: null, date_creation: '2026-08-01T08:00:00Z' })))
    renderPage(<PaiementsFacturePortailAdmin />)
    expect((await screen.findAllByText('1–25 sur 60')).length).toBeGreaterThan(0)
    expect(portailApi.admin.paiementsFacture.liste).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })
})
