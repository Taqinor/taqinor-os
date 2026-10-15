// WIR16 — la fiche client monte l'écran Plan de compte (PlanComptePage,
// NTCRM11) dans un onglet dédié, sans URL tapée.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import api from '../../api/axios'
import ClientDetailPanel from './ClientDetailPanel'
import { renderAvecAuth } from '../../test/renderAvecAuth'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPanel(client, { documents = { devis: [], factures: [], chantiers: [] }, plans = [] } = {}) {
  api.get.mockImplementation((url) => {
    if (url.includes('/documents/')) return Promise.resolve({ data: documents })
    if (url.includes('/consolidation/')) return Promise.resolve({ data: { filiales: [] } })
    if (url.includes('/contacts/contacts-client/')) return Promise.resolve({ data: { results: [] } })
    if (url.includes('/plans-compte/')) return Promise.resolve({ data: { results: plans } })
    return Promise.resolve({ data: {} })
  })
  return renderAvecAuth(<ClientDetailPanel client={client} onClose={() => {}} onNewDevis={() => {}} onChanged={() => {}} />, { role: 'admin' })
}

const client = { id: 11, nom: 'Benali', prenom: 'Sara' }

describe('ClientDetailPanel — WIR16 : onglet Plan de compte', () => {
  it('monte PlanComptePage avec le clientId de la fiche, sans URL tapée', async () => {
    renderPanel(client, {
      plans: [{
        id: 3, objectifs_strategiques: 'Grandir', revues: [],
        swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
      }],
    })
    await userEvent.click(screen.getByRole('tab', { name: 'Plan de compte' }))
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      '/crm/plans-compte/', { params: { client: 11 } },
    ))
    expect(await screen.findByTestId('plan-compte-screen')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Grandir')).toBeInTheDocument()
  })

  it('crée un plan de compte depuis la fiche client (POST /crm/plans-compte/)', async () => {
    renderPanel(client, { plans: [] })
    await userEvent.click(screen.getByRole('tab', { name: 'Plan de compte' }))
    await screen.findByTestId('plan-compte-screen')

    api.post.mockResolvedValue({ data: { id: 9 } })
    await userEvent.type(screen.getByPlaceholderText('Objectifs stratégiques'), 'Grandir')
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer le plan de compte/i }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/crm/plans-compte/',
      expect.objectContaining({ client: 11, objectifs_strategiques: 'Grandir' }),
    ))
  })
})
