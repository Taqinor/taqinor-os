// WIR12 — la fiche client monte l'onglet Organigramme (ContactClient, NTCRM9)
// et permet de créer un contact sans appel API manuel.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import api from '../../api/axios'
import ClientDetailPanel from './ClientDetailPanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPanel(client, { documents = { devis: [], factures: [], chantiers: [] }, contacts = [] } = {}) {
  api.get.mockImplementation((url) => {
    if (url.includes('/documents/')) return Promise.resolve({ data: documents })
    if (url.includes('/consolidation/')) return Promise.resolve({ data: { filiales: [] } })
    if (url.includes('/contacts/contacts-client/')) return Promise.resolve({ data: { results: contacts } })
    return Promise.resolve({ data: {} })
  })
  const store = configureStore({ reducer: { auth: (state = { role: 'admin' }) => state } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ClientDetailPanel client={client} onClose={() => {}} onNewDevis={() => {}} onChanged={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

const client = { id: 9, nom: 'Benali', prenom: 'Sara' }

describe('ClientDetailPanel — WIR12 : onglet Organigramme', () => {
  it('montre l\'onglet Organigramme groupé par rôle d\'achat', async () => {
    renderPanel(client, {
      contacts: [
        { id: 1, nom: 'Alaoui', prenom: 'Sami', role_achat: 'decideur', contact_principal: true },
      ],
    })
    await userEvent.click(screen.getByRole('tab', { name: 'Organigramme' }))
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      '/contacts/contacts-client/', { params: { client: 9 } },
    ))
    expect(await screen.findByText(/Alaoui/)).toBeInTheDocument()
    expect(screen.getByText('Décideur')).toBeInTheDocument()
  })

  it('crée un contact depuis la fiche client (POST /contacts/contacts-client/)', async () => {
    renderPanel(client, { contacts: [] })
    await userEvent.click(screen.getByRole('tab', { name: 'Organigramme' }))
    expect(await screen.findByText(/Aucun contact/)).toBeInTheDocument()

    api.post.mockResolvedValue({ data: { id: 42 } })
    await userEvent.click(screen.getAllByRole('button', { name: /Ajouter un contact/ })[0])
    await userEvent.type(screen.getByLabelText('Nom'), 'Zahra')
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/contacts/contacts-client/',
      expect.objectContaining({ client: 9, nom: 'Zahra' }),
    ))
  })
})
