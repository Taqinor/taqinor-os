// VX216(c) — la fiche client montre la chaîne Devis · Chantier UNIQUEMENT
// quand elle est sans ambiguïté (exactement un devis + un chantier) ; ni lead
// ni ticket SAV ne sont exposés par cet endpoint, donc jamais inventés.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn() },
}))

import api from '../../api/axios'
import ClientDetailPanel from './ClientDetailPanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderPanel(client, { documents, consolidation = { filiales: [] } } = {}) {
  api.get.mockImplementation((url) => {
    if (url.includes('/documents/')) return Promise.resolve({ data: documents })
    if (url.includes('/consolidation/')) return Promise.resolve({ data: consolidation })
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

describe('ClientDetailPanel — VX216(c) : OwnerChain (Devis · Chantier)', () => {
  it('affiche la chaîne quand il y a exactement un devis et un chantier', async () => {
    renderPanel(client, {
      documents: {
        devis: [{ id: 20, reference: 'DEV-2026-07-0020', statut: 'accepte', total_ttc: '15000', date: '2026-07-01' }],
        factures: [],
        chantiers: [{ id: 30, reference: 'CH-2026-07-0030', statut: 'en_cours' }],
      },
    })
    await waitFor(() => expect(screen.getByRole('link', { name: /DEV-2026-07-0020/ })).toBeInTheDocument())
    expect(screen.getByRole('link', { name: /DEV-2026-07-0020/ })).toHaveAttribute('href', '/ventes/devis?devis=20')
    expect(screen.getByRole('link', { name: /CH-2026-07-0030/ })).toHaveAttribute('href', '/chantiers?id=30')
  })

  it('n\'affiche aucune chaîne quand il y a plusieurs devis (ambiguïté)', async () => {
    renderPanel(client, {
      documents: {
        devis: [
          { id: 20, reference: 'DEV-A', statut: 'accepte', total_ttc: '1000', date: '2026-07-01' },
          { id: 21, reference: 'DEV-B', statut: 'brouillon', total_ttc: '2000', date: '2026-07-02' },
        ],
        factures: [],
        chantiers: [{ id: 30, reference: 'CH-2026-07-0030', statut: 'en_cours' }],
      },
    })
    await waitFor(() => expect(screen.getByText('DEV-A')).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: /CH-2026-07-0030/ })).not.toBeInTheDocument()
  })
})
