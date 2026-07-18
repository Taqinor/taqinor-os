// NTCRM9 — Org chart tab: contacts grouped by rôle d'achat.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn() },
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
})
