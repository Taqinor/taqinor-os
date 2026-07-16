import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* VX204 — `getMeta().catch(() => {})` rendait les menus de filtre (utilisateurs/
   actions/modules) vides SANS dire qu'ils sont cassés : indiscernable de
   « aucune valeur possible ». Un échec doit afficher un message + Réessayer. */

const { getStats, getEntries, getMeta } = vi.hoisted(() => ({
  getStats: vi.fn(() => Promise.resolve({ data: { total: 0, buckets: [] } })),
  getEntries: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  getMeta: vi.fn(),
}))

vi.mock('../api/auditApi', () => ({
  default: { getStats, getEntries, getMeta },
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

describe('Journal — VX204 échec de getMeta()', () => {
  it('affiche un message + Réessayer quand les métadonnées de filtre échouent', async () => {
    getMeta.mockRejectedValueOnce(new Error('boom'))
    renderJournal()
    expect(await screen.findByRole('alert')).toHaveTextContent('Filtres indisponibles')
  })

  it('Réessayer relance getMeta et efface le message en cas de succès', async () => {
    getMeta.mockRejectedValueOnce(new Error('boom'))
    renderJournal()
    await screen.findByRole('alert')

    getMeta.mockResolvedValueOnce({ data: { users: [], actions: [], modules: [] } })
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })

  it('aucun message quand getMeta réussit', async () => {
    getMeta.mockResolvedValueOnce({ data: { users: [], actions: [], modules: [] } })
    renderJournal()
    await screen.findByText("Journal d'activité")
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
