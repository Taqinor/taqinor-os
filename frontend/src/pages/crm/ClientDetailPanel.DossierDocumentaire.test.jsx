// WIR17(b) — bouton « Voir dossier documentaire » sur la fiche client, même
// motif que le bouton dossier chantier d'InstallationDetail.jsx:883 (route
// /reporting/archive/client/:id déjà enregistrée, N32).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const navigateSpy = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => navigateSpy,
}))

import api from '../../api/axios'
import ClientDetailPanel from './ClientDetailPanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPanel(client) {
  api.get.mockImplementation((url) => {
    if (url.includes('/documents/')) return Promise.resolve({ data: { devis: [], factures: [], chantiers: [] } })
    if (url.includes('/consolidation/')) return Promise.resolve({ data: { filiales: [] } })
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

const client = { id: 21, nom: 'Tazi', prenom: 'Nabil' }

describe('ClientDetailPanel — WIR17(b) : dossier documentaire', () => {
  it('navigue vers /reporting/archive/client/<id> au clic', async () => {
    renderPanel(client)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    await userEvent.click(screen.getByRole('button', { name: 'Voir dossier documentaire' }))
    expect(navigateSpy).toHaveBeenCalledWith('/reporting/archive/client/21')
  })
})
