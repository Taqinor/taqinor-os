import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT100 — Jalons de chantier (portail) : création + marquer_atteint (date
   posée côté serveur uniquement si absente). portailApi/installationsApi mockés. */

vi.mock('../../../api/portailApi', () => ({
  default: { admin: { jalonsChantier: { liste: vi.fn(), creer: vi.fn(), marquerAtteint: vi.fn() } } },
}))
vi.mock('../../../api/installationsApi', () => ({
  default: { getInstallations: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import portailApi from '../../../api/portailApi'
import installationsApi from '../../../api/installationsApi'
import JalonsChantierPortailAdmin from './JalonsChantierPortailAdmin'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('JalonsChantierPortailAdmin — PACT100', () => {
  it('affiche la timeline avec statut atteint/non atteint', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: [{ id: 1, chantier_id: 21, libelle: 'Étude', ordre: 1, atteint: true, date_jalon: '2026-07-01' }],
    })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Étude').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Atteint').length).toBeGreaterThan(0)
    expect(screen.getAllByText('#21').length).toBeGreaterThan(0)
  })

  it('crée un jalon pour le chantier choisi', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({ data: [] })
    installationsApi.getInstallations.mockResolvedValue({
      data: [{ id: 8, client_nom: 'Ferme Bennani' }],
    })
    portailApi.admin.jalonsChantier.creer.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    renderPage(<JalonsChantierPortailAdmin />)
    await user.click(await screen.findByRole('combobox', { name: 'Chantier' }))
    await user.click(await screen.findByRole('option', { name: '#8 — Ferme Bennani' }))
    await user.type(screen.getByLabelText('Jalon'), 'Livraison matériel')
    await user.click(screen.getAllByRole('button', { name: /Créer le jalon/ })[0])
    await waitFor(() => expect(portailApi.admin.jalonsChantier.creer).toHaveBeenCalledWith({
      chantier_id: '8', libelle: 'Livraison matériel', ordre: 0,
    }))
  })

  it('marque un jalon non atteint comme atteint', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: [{ id: 4, chantier_id: 21, libelle: 'Installation', ordre: 4, atteint: false, date_jalon: null }],
    })
    portailApi.admin.jalonsChantier.marquerAtteint.mockResolvedValue({ data: {} })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Installation').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: /Marquer atteint/ })[0])
    await waitFor(() => expect(portailApi.admin.jalonsChantier.marquerAtteint).toHaveBeenCalledWith(4))
  })

  it("n'affiche aucune action pour un jalon déjà atteint", async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: [{ id: 6, chantier_id: 21, libelle: 'Réception', ordre: 6, atteint: true, date_jalon: '2026-07-20' }],
    })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Réception').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Marquer atteint/ })).not.toBeInTheDocument()
  })
})
