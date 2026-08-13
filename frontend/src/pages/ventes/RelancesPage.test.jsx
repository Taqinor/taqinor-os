import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const ROWS = [
  {
    id: 1, reference: 'FAC-001', client_id: 42, client_nom: 'ACME SARL',
    montant_du: 1000, niveau: null,
  },
  {
    id: 2, reference: 'FAC-002', client_id: 99, client_nom: 'Globex',
    montant_du: 2000, niveau: null,
  },
]

vi.mock('../../api/ventesApi', () => ({
  default: {
    getRelances: vi.fn(() => Promise.resolve({ data: ROWS })),
  },
}))
// PACT44/PACT45 — le paramétrage de relance client et les promesses de paiement
// sont lus/écrits sur leurs endpoints REST directs.
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({
    confirm: () => Promise.resolve(true),
    confirmDelete: () => Promise.resolve(true),
  }),
}))

import api from '../../api/axios'
import RelancesPage from './RelancesPage'

// Réponses par défaut : aucun paramétrage, aucune promesse.
const defaultGet = (url) => {
  if (url === '/users/') {
    return Promise.resolve({ data: [{ id: 5, username: 'meryem' }] })
  }
  if (url === '/ventes/relances/') return Promise.resolve({ data: ROWS })
  return Promise.resolve({ data: [] })
}

beforeEach(() => { api.get.mockImplementation(defaultGet) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPage = (entry = '/ventes/relances') => render(
  <MemoryRouter initialEntries={[entry]}>
    <RelancesPage />
  </MemoryRouter>,
)

/* VX112 — la page /ventes/relances lit ?client=<id> (posé par le drill-down
   de la balance âgée) et pré-filtre la liste sur ce client, sans appel API
   supplémentaire (filtrage d'affichage, miroir du niveauFilter existant). */
describe('RelancesPage (VX112 — pré-filtre client via ?client=)', () => {
  it('sans ?client=, affiche toutes les factures', async () => {
    renderPage()
    expect(await screen.findByText('ACME SARL')).toBeInTheDocument()
    expect(screen.getByText('Globex')).toBeInTheDocument()
  })

  it('avec ?client=42, ne montre que les factures de ce client', async () => {
    renderPage('/ventes/relances?client=42')
    expect(await screen.findByText('ACME SARL')).toBeInTheDocument()
    expect(screen.queryByText('Globex')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /effacer/ })).toHaveAttribute('href', '/ventes/relances')
  })
})

/* PACT44 — le serveur renvoyait déjà `relance_mode`/`relance_responsable_id`
   sans que rien ne les affiche : tout client était silencieusement en mode
   automatique sans responsable. L'écran les montre et les règle. */
describe('RelancesPage (PACT44 — paramétrage des relances par client)', () => {
  it('affiche le mode de relance et le responsable de chaque client', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/ventes/parametrages-relance-client/') {
        return Promise.resolve({
          data: [{
            id: 3, client: 42, mode: 'manuel', responsable: 5,
            responsable_username: 'meryem', prochaine_relance_manuelle: null,
          }],
        })
      }
      return defaultGet(url)
    })
    renderPage()
    await screen.findByText('ACME SARL')
    expect(await screen.findByText('Manuelle')).toBeInTheDocument()
    expect(screen.getByText('meryem')).toBeInTheDocument()
    // L'autre client reste en automatique, sans responsable.
    expect(screen.getAllByText('Automatique').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Sans responsable').length).toBeGreaterThan(0)
  })

  it('« Mes relances » délègue le filtrage au serveur (?mes_relances=1)', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('ACME SARL')

    await user.click(screen.getByRole('combobox', { name: 'Filtrer la file de relance' }))
    await user.click(await screen.findByRole('option', { name: 'Mes relances' }))

    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      '/ventes/relances/', { params: { mes_relances: 1 } }))
  })

  it('passe un client en relance manuelle assignée', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValue({ data: { id: 8 } })
    renderPage()
    await screen.findByText('ACME SARL')

    await user.click(screen.getByRole('button', { name: /Plus d'actions — FAC-001/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Paramétrer les relances/ }))

    await user.click(await screen.findByRole('combobox', { name: 'Mode de relance' }))
    await user.click(await screen.findByRole('option', { name: 'Manuel (assigné)' }))
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/ventes/parametrages-relance-client/',
      expect.objectContaining({ client: 42, mode: 'manuel' })))
    // `company` n'est JAMAIS envoyée depuis le client (imposée serveur).
    expect(api.post.mock.calls[0][1]).not.toHaveProperty('company')
  })
})
