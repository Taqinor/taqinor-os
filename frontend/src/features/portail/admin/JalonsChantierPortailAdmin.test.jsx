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
  default: { getInstallations: vi.fn(() => Promise.resolve({ data: { count: 0, next: null, previous: null, results: [] } })) },
}))

import portailApi from '../../../api/portailApi'
import installationsApi from '../../../api/installationsApi'
import JalonsChantierPortailAdmin from './JalonsChantierPortailAdmin'

// ADOC32 — l'API sert l'enveloppe DRF réelle {count, next, results} (jamais un
// tableau nu) ; `pagine` simule une liste de `total` lignes servie par pages de 50.
const enveloppe = (results) => ({ count: results.length, next: null, previous: null, results })
const pagine = (total, ligne, taille = 50) => (params) => {
  const page = params?.page ?? 1
  const debut = (page - 1) * taille
  const fin = Math.min(total, debut + taille)
  return Promise.resolve({
    data: {
      count: total,
      next: fin < total ? `/api/django/portail/x/?page=${page + 1}` : null,
      previous: page > 1 ? `/api/django/portail/x/?page=${page - 1}` : null,
      results: Array.from({ length: Math.max(0, fin - debut) }, (_, i) => ligne(debut + i + 1)),
    },
  })
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('JalonsChantierPortailAdmin — PACT100', () => {
  it('affiche la timeline avec statut atteint/non atteint', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: enveloppe([{ id: 1, chantier_id: 21, libelle: 'Étude', ordre: 1, atteint: true, date_jalon: '2026-07-01' }]),
    })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Étude').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Atteint').length).toBeGreaterThan(0)
    expect(screen.getAllByText('#21').length).toBeGreaterThan(0)
  })

  it('crée un jalon pour le chantier choisi', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({ data: enveloppe([]) })
    installationsApi.getInstallations.mockResolvedValue({
      data: enveloppe([{ id: 8, client_nom: 'Ferme Bennani' }]),
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
      data: enveloppe([{ id: 4, chantier_id: 21, libelle: 'Installation', ordre: 4, atteint: false, date_jalon: null }]),
    })
    portailApi.admin.jalonsChantier.marquerAtteint.mockResolvedValue({ data: {} })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Installation').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: /Marquer atteint/ })[0])
    await waitFor(() => expect(portailApi.admin.jalonsChantier.marquerAtteint).toHaveBeenCalledWith(4))
  })

  it("n'affiche aucune action pour un jalon déjà atteint", async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({
      data: enveloppe([{ id: 6, chantier_id: 21, libelle: 'Réception', ordre: 6, atteint: true, date_jalon: '2026-07-20' }]),
    })
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('Réception').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Marquer atteint/ })).not.toBeInTheDocument()
  })

  it("ERR-QAH-PORTAIL-JALON-ERREUR-TOAST — l'erreur 400 sur « Ordre » s'affiche sous le champ", async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({ data: enveloppe([]) })
    installationsApi.getInstallations.mockResolvedValue({
      data: enveloppe([{ id: 8, client_nom: 'Ferme Bennani' }]),
    })
    portailApi.admin.jalonsChantier.creer.mockRejectedValue({
      response: { data: { ordre: ['Un nombre entier valide est requis.'] } },
    })
    const user = userEvent.setup()
    renderPage(<JalonsChantierPortailAdmin />)
    await user.click(await screen.findByRole('combobox', { name: 'Chantier' }))
    await user.click(await screen.findByRole('option', { name: '#8 — Ferme Bennani' }))
    await user.type(screen.getByLabelText('Jalon'), 'Livraison')
    await user.click(screen.getAllByRole('button', { name: /Créer le jalon/ })[0])
    expect(await screen.findByText('Un nombre entier valide est requis.')).toBeInTheDocument()
  })
})

describe('ADOC32 — toutes les pages (jalons)', () => {
  it('60 lignes sur deux pages', async () => {
    portailApi.admin.jalonsChantier.liste.mockImplementation(pagine(60, (n) => ({ id: n, chantier_id: 21, libelle: `Jalon ${n}`, ordre: n, atteint: false, date_jalon: null })))
    renderPage(<JalonsChantierPortailAdmin />)
    expect((await screen.findAllByText('1–25 sur 60')).length).toBeGreaterThan(0)
    expect(portailApi.admin.jalonsChantier.liste).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })
})

describe('ADOC32 — sélecteur de chantiers complet', () => {
  it('propose les 60 chantiers (deux pages)', async () => {
    portailApi.admin.jalonsChantier.liste.mockResolvedValue({ data: enveloppe([]) })
    installationsApi.getInstallations.mockImplementation(
      pagine(60, (n) => ({ id: n, client_nom: `Client ${n}` })),
    )
    const user = userEvent.setup()
    renderPage(<JalonsChantierPortailAdmin />)
    await waitFor(() => expect(installationsApi.getInstallations).toHaveBeenCalledWith({ page: 2 }))
    await user.click(await screen.findByRole('combobox', { name: 'Chantier' }))
    expect(await screen.findByRole('option', { name: '#60 — Client 60' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '#1 — Client 1' })).toBeInTheDocument()
  })
})
