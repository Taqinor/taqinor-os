import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT96 — Comptes portail (accès client) : liste + création + bascule Actif
   (révocation) + provisionnement d'accès. portailApi/crmApi mockés. */

vi.mock('../../../api/portailApi', () => ({
  default: {
    admin: {
      comptes: {
        liste: vi.fn(),
        creer: vi.fn(),
        patch: vi.fn(),
        provisionnerAcces: vi.fn(),
      },
    },
  },
}))
vi.mock('../../../api/crmApi', () => ({
  default: { getClients: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import portailApi from '../../../api/portailApi'
import crmApi from '../../../api/crmApi'
import ComptesPortailAdmin from './ComptesPortailAdmin'

afterEach(() => { cleanup(); vi.clearAllMocks() })

// DataTable lit la densité via useDensity → <ThemeProvider> et persiste ses
// filtres via useSearchParams → <Router> (même patron que WarrantyClaimsPage.test.jsx).
function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('ComptesPortailAdmin — PACT96', () => {
  it('affiche la liste des comptes avec email, jeton et statut actif', async () => {
    portailApi.admin.comptes.liste.mockResolvedValue({
      data: [{
        id: 1, client: 12, email: 'client@exemple.ma', token_acces: 'tok-abc123',
        actif: true, derniere_connexion: null, date_creation: '2026-08-01T10:00:00Z',
      }],
    })
    renderPage(<ComptesPortailAdmin />)
    await waitFor(() => expect(
      screen.getAllByText('client@exemple.ma').length).toBeGreaterThan(0))
    expect(screen.getAllByText('tok-abc123').length).toBeGreaterThan(0)
    expect(screen.getAllByText('#12').length).toBeGreaterThan(0)
  })

  it('affiche un état vide quand aucun compte', async () => {
    portailApi.admin.comptes.liste.mockResolvedValue({ data: [] })
    renderPage(<ComptesPortailAdmin />)
    expect((await screen.findAllByText('Aucun compte portail')).length).toBeGreaterThan(0)
  })

  it('crée un compte pour le client choisi', async () => {
    portailApi.admin.comptes.liste.mockResolvedValue({ data: [] })
    crmApi.getClients.mockResolvedValue({ data: [{ id: 5, nom: 'ACME Solaire' }] })
    portailApi.admin.comptes.creer.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    renderPage(<ComptesPortailAdmin />)
    await user.click(await screen.findByRole('combobox', { name: 'Client' }))
    await user.click(await screen.findByRole('option', { name: 'ACME Solaire' }))
    await user.click(screen.getAllByRole('button', { name: /Créer un compte/ })[0])
    await waitFor(() => expect(portailApi.admin.comptes.creer)
      .toHaveBeenCalledWith({ client: '5' }))
  })

  it('révoque un compte actif via la bascule (jamais de filtrage client)', async () => {
    portailApi.admin.comptes.liste.mockResolvedValue({
      data: [{
        id: 3, client: 9, email: 'a@b.ma', token_acces: 'tok-xyz',
        actif: true, derniere_connexion: null, date_creation: '2026-08-01T10:00:00Z',
      }],
    })
    portailApi.admin.comptes.patch.mockResolvedValue({ data: {} })
    renderPage(<ComptesPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('a@b.ma').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('switch')[0])
    await waitFor(() => expect(portailApi.admin.comptes.patch)
      .toHaveBeenCalledWith(3, { actif: false }))
  })

  it('provisionne un accès et affiche le message renvoyé par le serveur', async () => {
    portailApi.admin.comptes.liste.mockResolvedValue({
      data: [{
        id: 7, client: 4, email: 'c@d.ma', token_acces: 'tok-777',
        actif: true, derniere_connexion: null, date_creation: '2026-08-01T10:00:00Z',
      }],
    })
    portailApi.admin.comptes.provisionnerAcces.mockResolvedValue({
      data: { detail: 'Accès portail créé — mot de passe temporaire envoyé par email.' },
    })
    renderPage(<ComptesPortailAdmin />)
    await waitFor(() => expect(screen.getAllByText('c@d.ma').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: /Provisionner l'accès/ })[0])
    await waitFor(() => expect(portailApi.admin.comptes.provisionnerAcces).toHaveBeenCalledWith(7))
  })
})
