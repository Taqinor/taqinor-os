import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* YHARD3 — « Historique à cette date » : depuis une ligne du Journal reliée à
   un objet (module + model + object_id connus), un bouton ouvre une
   reconstruction champ-par-champ à une date choisie (GET
   /api/django/audit/objets/<app_label.model>/<id>/as-of/). */

const { getStats, getEntries, getMeta, getObjectAsOf } = vi.hoisted(() => ({
  getStats: vi.fn(() => Promise.resolve({ data: { total: 1, buckets: [] } })),
  getEntries: vi.fn(() => Promise.resolve({
    data: {
      count: 1,
      results: [{
        id: 1, timestamp_local: '2026-07-01T10:00:00', utilisateur: 'sami',
        action_label: 'Modification', module: 'crm', model: 'client',
        object_id: 42, object_repr: 'Client Bennani', detail: 'nom modifié',
      }],
    },
  })),
  getMeta: vi.fn(() => Promise.resolve({ data: { users: [], actions: [], modules: [] } })),
  getObjectAsOf: vi.fn(() => Promise.resolve({
    data: {
      content_type: 'crm.client', object_id: '42', as_of: '2026-07-01T00:00:00Z',
      fields: { nom: 'Ancien Nom', email: 'client@x.ma' },
      covered_changes: 1,
    },
  })),
}))

vi.mock('../api/auditApi', () => ({
  default: { getStats, getEntries, getMeta, getObjectAsOf },
}))

import Journal from './Journal'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderJournal() {
  const store = configureStore({
    reducer: { auth: (state = { permissions: ['journal_activite_voir'] }) => state },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter><Journal /></MemoryRouter>
    </Provider>,
  )
}

describe('Journal — YHARD3 historique à cette date', () => {
  it('affiche le bouton historique pour une entrée reliée à un objet', async () => {
    renderJournal()
    expect(await screen.findByText('Client Bennani')).toBeInTheDocument()
    expect(screen.getByLabelText('Historique à cette date')).toBeInTheDocument()
  })

  it('ouvre la reconstruction as-of et affiche les champs', async () => {
    const user = userEvent.setup()
    renderJournal()
    await screen.findByText('Client Bennani')

    await user.click(screen.getByLabelText('Historique à cette date'))

    await waitFor(() => expect(getObjectAsOf).toHaveBeenCalledWith(
      'crm.client', 42, expect.any(String)))
    expect(await screen.findByText('Ancien Nom')).toBeInTheDocument()
    expect(screen.getByText('client@x.ma')).toBeInTheDocument()
  })
})
