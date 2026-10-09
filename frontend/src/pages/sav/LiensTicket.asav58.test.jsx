import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// ASAV58 — chaque lien « ouvrir ce ticket » mène à /sav?id=<id> (ROUTE.ticket),
// jamais à la liste nue. URL lue après le clic dans un routeur mémoire.

vi.mock('../../api/savApi', () => ({
  default: new Proxy({
    getSavFileAction: () => Promise.resolve({ data: { buckets: { a_repondre: { count: 1, ids: [7] } } } }),
    getTickets: () => Promise.resolve({ data: [{ id: 7, reference: 'SAV-7', client_nom: 'C' }] }),
    getTicketsSimilaires: () => Promise.resolve({ data: { results: [
      { id: 42, reference: 'SAV-42', produit_nom: 'Onduleur' }] } }),
    createTicket: () => Promise.resolve({ data: { id: 321 } }),
  }, {
    get: (cible, nom) => cible[nom] ?? (() => Promise.resolve({ data: [] })),
  }),
}))
vi.mock('../../api/stockApi', () => ({ default: { getProduits: () => Promise.resolve({ data: [] }) } }))
vi.mock('../../api/installationsApi', () => ({ default: { getInstallations: () => Promise.resolve({ data: [] }) } }))
vi.mock('../../api/importApi', () => ({ default: {} }))

import SavActionBoardPage from './SavActionBoardPage'
import TicketAdvancedPanel from './TicketAdvancedPanel'
import { EquipementDetail } from './EquipementsPage'

afterEach(() => cleanup())

function Sonde() {
  const l = useLocation()
  return <div data-testid="url">{l.pathname + l.search}</div>
}
const store = () => configureStore({ reducer: {
  auth: (s = { role: 'admin', permissions: [] }) => s,
} })
const monter = (ui) => render(<Provider store={store()}><MemoryRouter initialEntries={['/depart']}>
  {ui}<Sonde /></MemoryRouter></Provider>)

describe('ASAV58 — liens vers LE ticket', () => {
  it('Action requise : le ticket du seau ouvre /sav?id=7', async () => {
    const user = userEvent.setup()
    monter(<SavActionBoardPage />)
    await user.click(await screen.findByRole('link', { name: /SAV-7/ }))
    expect(screen.getByTestId('url')).toHaveTextContent('/sav?id=7')
  })

  it('Résolutions similaires : le ticket ouvre /sav?id=42', async () => {
    const user = userEvent.setup()
    monter(<TicketAdvancedPanel ticket={{ id: 1, reference: 'SAV-1', statut: 'en_cours' }} />)
    await user.click(await screen.findByRole('link', { name: 'SAV-42' }))
    expect(screen.getByTestId('url')).toHaveTextContent('/sav?id=42')
  })

  it('« Créer un ticket SAV » depuis le parc ouvre le ticket créé', async () => {
    const user = userEvent.setup()
    monter(<EquipementDetail equipement={{ id: 9, numero_serie: 'SN', statut: 'en_service', nb_tickets_ouverts: 0 }}
                             onClose={() => {}} onSaved={() => {}} />)
    await user.click(await screen.findByRole('button', { name: /Créer un ticket SAV/ }))
    await waitFor(() => expect(screen.getByTestId('url')).toHaveTextContent('/sav?id=321'))
  }, 60000)
})
