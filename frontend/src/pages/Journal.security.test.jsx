import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* WIR18 — onglet « Sécurité » du Journal (FG23) : évènements de connexion/
   déconnexion/échec/alerte via GET /audit/security/, + bouton « Exporter
   CSV » sur GET /audit/security/export/ (NTSEC15), réservé aux rôles admin
   (le backend re-vérifie via IsAdminRole ; le front cache juste l'affordance). */

const {
  getStats, getEntries, getMeta, getSecurityEvents, exportSecurityEvents,
} = vi.hoisted(() => ({
  getStats: vi.fn(() => Promise.resolve({ data: { total: 0, buckets: [] } })),
  getEntries: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  getMeta: vi.fn(() => Promise.resolve({ data: { users: [], actions: [], modules: [] } })),
  getSecurityEvents: vi.fn(() => Promise.resolve({
    data: {
      count: 1,
      results: [{
        id: 9, timestamp_local: '2026-07-01T08:00:00', utilisateur: 'sami',
        action_label: 'Échec de connexion', detail: 'mot de passe invalide',
      }],
    },
  })),
  exportSecurityEvents: vi.fn(() => Promise.resolve({ data: 'csv,data' })),
}))

vi.mock('../api/auditApi', () => ({
  default: { getStats, getEntries, getMeta, getSecurityEvents, exportSecurityEvents },
}))
vi.mock('../api/reportingApi', () => ({
  default: {
    auditAnalytics: vi.fn(() => Promise.resolve({
      data: { top_users: [], action_mix: [], daily_counts: [], failed_logins: [] },
    })),
  },
}))
// downloadBlobInGesture() touche window.matchMedia/URL.createObjectURL/DOM —
// hors périmètre de ce test (déjà couvert par downloadBlob.test.mjs) : on ne
// vérifie ici que l'appel API déclenché par le bouton.
vi.mock('../utils/downloadBlob', () => ({
  downloadBlobInGesture: () => ({ win: null, deliver: () => true }),
  stampedFilename: (base, ext) => `${base}.${ext}`,
}))

import Journal from './Journal'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderJournal(authOverrides) {
  const store = configureStore({
    reducer: {
      auth: (state = {
        permissions: ['journal_activite_voir'], role: null, ...authOverrides,
      }) => state,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter><Journal /></MemoryRouter>
    </Provider>,
  )
}

describe('Journal — WIR18 onglet Sécurité', () => {
  it("affiche les évènements de sécurité au clic sur l'onglet", async () => {
    const user = userEvent.setup()
    renderJournal()
    await screen.findByText("Journal d'activité")

    await user.click(screen.getByRole('tab', { name: 'Sécurité' }))

    await waitFor(() => expect(getSecurityEvents).toHaveBeenCalled())
    expect(await screen.findByText('sami')).toBeInTheDocument()
    expect(screen.getByText('Échec de connexion')).toBeInTheDocument()
  })

  it('cache le bouton Exporter CSV pour un rôle non-admin', async () => {
    const user = userEvent.setup()
    renderJournal({ role: 'responsable' })
    await screen.findByText("Journal d'activité")

    await user.click(screen.getByRole('tab', { name: 'Sécurité' }))
    await waitFor(() => expect(getSecurityEvents).toHaveBeenCalled())

    expect(screen.queryByRole('button', { name: /Exporter CSV/ })).not.toBeInTheDocument()
  })

  it("un admin voit le bouton Exporter CSV et il déclenche l'export", async () => {
    const user = userEvent.setup()
    renderJournal({ role: 'admin' })
    await screen.findByText("Journal d'activité")

    await user.click(screen.getByRole('tab', { name: 'Sécurité' }))
    const exportBtn = await screen.findByRole('button', { name: /Exporter CSV/ })
    await user.click(exportBtn)

    await waitFor(() => expect(exportSecurityEvents).toHaveBeenCalled())
  })
})
