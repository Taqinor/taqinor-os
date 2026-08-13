import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT97 — Acceptations de devis (portail) : écran de LECTURE SEULE, l'IP et
   la date affichées viennent telles quelles du serveur. portailApi mocké. */

vi.mock('../../../api/portailApi', () => ({
  default: { admin: { acceptationsDevis: { liste: vi.fn() } } },
}))

import portailApi from '../../../api/portailApi'
import AcceptationsDevisPortailAdmin from './AcceptationsDevisPortailAdmin'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('AcceptationsDevisPortailAdmin — PACT97', () => {
  it("affiche l'IP et le nom du signataire tels que renvoyés par le serveur", async () => {
    portailApi.admin.acceptationsDevis.liste.mockResolvedValue({
      data: [{
        id: 1, devis_id: 42, option_choisie: 'Autoconsommation 6kWc',
        nom_signataire: 'Karim Alaoui', signature_ip: '41.248.12.34',
        accepte: true, signe_le: '2026-08-01T09:12:00Z', date_creation: '2026-08-01T09:10:00Z',
      }],
    })
    renderPage(<AcceptationsDevisPortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('Karim Alaoui').length).toBeGreaterThan(0))
    expect(screen.getAllByText('41.248.12.34').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Devis #42').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Accepté').length).toBeGreaterThan(0)
  })

  it('affiche un état vide quand aucune acceptation', async () => {
    portailApi.admin.acceptationsDevis.liste.mockResolvedValue({ data: [] })
    renderPage(<AcceptationsDevisPortailAdmin />)
    expect((await screen.findAllByText('Aucune acceptation de devis')).length).toBeGreaterThan(0)
  })

  it("ne propose aucune action d'écriture (lecture seule)", async () => {
    portailApi.admin.acceptationsDevis.liste.mockResolvedValue({
      data: [{
        id: 2, devis_id: 8, option_choisie: '', nom_signataire: 'Sami Idrissi',
        signature_ip: '', accepte: false, signe_le: null, date_creation: '2026-08-02T08:00:00Z',
      }],
    })
    renderPage(<AcceptationsDevisPortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('Sami Idrissi').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /créer|ajouter|modifier|supprimer/i })).not.toBeInTheDocument()
    expect(screen.getAllByText('Non accepté').length).toBeGreaterThan(0)
  })
})
