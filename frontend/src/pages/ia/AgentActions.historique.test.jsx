import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* YHARD2 — onglet « Historique / annuler » (admin/Directeur) : liste les
   actions IA confirmées (GET /api/django/agent/logs/) et permet d'annuler
   celles qui sont réversibles (POST …/logs/<id>/annuler/). */

const { getAgentActions, getAgentActionLogs, undoAgentAction } = vi.hoisted(() => ({
  getAgentActions: vi.fn(() => Promise.resolve({ data: { count: 0, actions: [] } })),
  getAgentActionLogs: vi.fn(() => Promise.resolve({
    data: {
      count: 2,
      results: [
        {
          id: 1, action_key: 'ventes.devis.send_whatsapp', risk_level: 'outward',
          user: 'sami', confirmed_at: '2026-07-01T10:00:00Z', executed_at: '2026-07-01T10:00:01Z',
          object_repr: 'Devis DEV-0007', undone_at: null, is_undoable: true,
        },
        {
          id: 2, action_key: 'stock.produit.archive', risk_level: 'irreversible',
          user: 'reda', confirmed_at: '2026-07-02T09:00:00Z', executed_at: '2026-07-02T09:00:01Z',
          object_repr: 'Produit PAN-450', undone_at: null, is_undoable: false,
        },
      ],
    },
  })),
  undoAgentAction: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/iaApi', () => ({
  default: { getAgentActions, getAgentActionLogs, undoAgentAction },
}))

import AgentActions from './AgentActions'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderAsAdmin() {
  const store = configureStore({
    reducer: { auth: (state = { role: 'admin', role_nom: 'Directeur' }) => state },
  })
  return render(<Provider store={store}><AgentActions /></Provider>)
}

describe('AgentActions — YHARD2 historique / annuler (admin)', () => {
  it('affiche l\'onglet Historique pour un admin et liste le journal', async () => {
    const user = userEvent.setup()
    renderAsAdmin()

    const tab = await screen.findByRole('tab', { name: 'Historique / annuler' })
    await user.click(tab)

    expect(await screen.findByText('Devis DEV-0007')).toBeInTheDocument()
    expect(screen.getByText('Produit PAN-450')).toBeInTheDocument()
    expect(getAgentActionLogs).toHaveBeenCalled()
  })

  it('permet d\'annuler une action réversible', async () => {
    const user = userEvent.setup()
    renderAsAdmin()

    await user.click(await screen.findByRole('tab', { name: 'Historique / annuler' }))
    await screen.findByText('Devis DEV-0007')

    const rows = screen.getAllByTestId('action-log-row')
    const undoBtn = rows[0].querySelector('button')
    await user.click(undoBtn)

    await waitFor(() => expect(undoAgentAction).toHaveBeenCalledWith(1))
  })

  it('désactive l\'annulation pour une action non réversible', async () => {
    const user = userEvent.setup()
    renderAsAdmin()

    await user.click(await screen.findByRole('tab', { name: 'Historique / annuler' }))
    await screen.findByText('Produit PAN-450')

    const rows = screen.getAllByTestId('action-log-row')
    const undoBtn = rows[1].querySelector('button')
    expect(undoBtn).toBeDisabled()
  })
})
