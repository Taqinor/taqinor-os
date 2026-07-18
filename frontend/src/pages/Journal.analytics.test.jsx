import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* WIR20 — corrige le préfixe d'URL cassé d'`auditAnalytics()`
   (`/reporting/audit/analytics/` → 404 ; corrigé en `/audit/analytics/`,
   FG97) ET ajoute un vrai consommateur : un onglet « Analytiques » sur
   Journal.jsx affiche top_users/action_mix/daily_counts/failed_logins. */

const { getStats, getEntries, getMeta, auditAnalytics } = vi.hoisted(() => ({
  getStats: vi.fn(() => Promise.resolve({ data: { total: 0, buckets: [] } })),
  getEntries: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  getMeta: vi.fn(() => Promise.resolve({ data: { users: [], actions: [], modules: [] } })),
  auditAnalytics: vi.fn(() => Promise.resolve({
    data: {
      window_days: 30,
      from: '2026-06-01',
      to: '2026-06-30',
      total_entries: 42,
      top_users: [{ actor_username: 'sami', count: 12 }],
      action_mix: [{ action: 'update', label: 'Modification', count: 20, pct: 47.6 }],
      daily_counts: [{ date: '2026-06-30', count: 5 }],
      failed_logins: [{ date: '2026-06-30', count: 2 }],
    },
  })),
}))

vi.mock('../api/auditApi', () => ({
  default: { getStats, getEntries, getMeta },
}))
vi.mock('../api/reportingApi', () => ({
  default: { auditAnalytics },
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

describe('Journal — WIR20 onglet Analytiques', () => {
  it('appelle /audit/analytics/ (via reportingApi.auditAnalytics) et affiche les données', async () => {
    const user = userEvent.setup()
    renderJournal()
    await screen.findByText("Journal d'activité")

    await user.click(screen.getByRole('tab', { name: 'Analytiques' }))

    await waitFor(() => expect(auditAnalytics).toHaveBeenCalled())
    expect(await screen.findByText(/Le plus actif : sami/)).toBeInTheDocument()
    expect(screen.getByText(/Action la plus fréquente : Modification/)).toBeInTheDocument()
    expect(screen.getByText('42', { exact: false })).toBeInTheDocument()
  })

  it("affiche un message d'erreur si l'appel échoue", async () => {
    auditAnalytics.mockRejectedValueOnce(new Error('boom'))
    const user = userEvent.setup()
    renderJournal()
    await screen.findByText("Journal d'activité")

    await user.click(screen.getByRole('tab', { name: 'Analytiques' }))

    expect(await screen.findByText('Impossible de charger les analytiques du Journal.'))
      .toBeInTheDocument()
  })
})
