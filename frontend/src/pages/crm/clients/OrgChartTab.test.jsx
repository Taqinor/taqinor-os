// NTCRM9 — Org chart tab: contacts grouped by rôle d'achat.
// WIR12 — création/édition d'un ContactClient (POST/PATCH), sans appel API manuel.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))
vi.mock('../../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import api from '../../../api/axios'
import OrgChartTab from './OrgChartTab'

describe('OrgChartTab (NTCRM9)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('groups contacts by rôle d\'achat', async () => {
    api.get.mockResolvedValue({
      data: {
        results: [
          { id: 1, nom: 'Alaoui', prenom: 'Sami', role_achat: 'decideur', contact_principal: true },
          { id: 2, nom: 'Bennani', prenom: 'Nadia', role_achat: 'influenceur', contact_principal: false },
          { id: 3, nom: 'Chraibi', prenom: 'Omar', role_achat: 'decideur', contact_principal: false },
        ],
      },
    })
    render(<OrgChartTab clientId={7} />)
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      '/contacts/contacts-client/', { params: { client: 7 } },
    ))
    expect(await screen.findByText('Décideur')).toBeInTheDocument()
    expect(screen.getByText('Influenceur')).toBeInTheDocument()
    expect(screen.getByText(/Alaoui/)).toBeInTheDocument()
    expect(screen.getByText(/Chraibi/)).toBeInTheDocument()
  })

  it('shows an empty state when the client has no contacts', async () => {
    api.get.mockResolvedValue({ data: { results: [] } })
    render(<OrgChartTab clientId={8} />)
    expect(await screen.findByText(/Aucun contact/i)).toBeInTheDocument()
  })

  it('creates a ContactClient via POST /contacts/contacts-client/', async () => {
    api.get.mockResolvedValue({ data: { results: [] } })
    api.post.mockResolvedValue({ data: { id: 99 } })
    render(<OrgChartTab clientId={8} />)
    await screen.findByText(/Aucun contact/i)

    await userEvent.click(screen.getAllByRole('button', { name: /Ajouter un contact/ })[0])
    await userEvent.type(screen.getByLabelText('Nom'), 'Kabbaj')
    await userEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/contacts/contacts-client/',
      expect.objectContaining({ client: 8, nom: 'Kabbaj', role_achat: 'autre' }),
    ))
  })

  it('edits an existing ContactClient via PATCH /contacts/contacts-client/<id>/', async () => {
    api.get.mockResolvedValue({
      data: {
        results: [{ id: 5, nom: 'Idrissi', prenom: 'Yasmine', role_achat: 'sponsor', contact_principal: false }],
      },
    })
    api.patch.mockResolvedValue({ data: { id: 5 } })
    render(<OrgChartTab clientId={8} />)
    await screen.findByText(/Idrissi/)

    await userEvent.click(screen.getByRole('button', { name: /Éditer Idrissi/ }))
    const nomInput = screen.getByLabelText('Nom')
    await userEvent.clear(nomInput)
    await userEvent.type(nomInput, 'Idrissi-Alami')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(api.patch).toHaveBeenCalledWith(
      '/contacts/contacts-client/5/',
      expect.objectContaining({ nom: 'Idrissi-Alami' }),
    ))
  })
})
