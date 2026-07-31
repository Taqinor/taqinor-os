import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer from './store/messagingSlice'

// WIR157 — ajoute alias e-mail du canal + export intégral (admin).
vi.mock('../../api/messagesApi', () => ({
  default: {
    listCompanyMembers: vi.fn(() => Promise.resolve({ data: [] })),
    getConversation: vi.fn(() => Promise.resolve({ data: { id: 1, members: [] } })),
    removeMember: vi.fn(() => Promise.resolve({ data: {} })),
    leaveConversation: vi.fn(() => Promise.resolve({ data: {} })),
    updateConversation: vi.fn(() => Promise.resolve({ data: {} })),
    addMembers: vi.fn(() => Promise.resolve({ data: {} })),
    setChannelAlias: vi.fn(() => Promise.resolve({ data: {} })),
    exportConversation: vi.fn(() => Promise.resolve({ data: new Blob(['{}'], { type: 'application/json' }) })),
  },
}))

// downloadBlob touche le DOM (createObjectURL/<a download>) : neutralisé pour
// le test, on vérifie juste qu'il est appelé avec le bon nom de fichier.
vi.mock('../../utils/downloadBlob', () => ({
  downloadBlob: vi.fn(),
  stampedFilename: (base, ext) => `${base}.${ext}`,
}))

import messagesApi from '../../api/messagesApi'
import { downloadBlob } from '../../utils/downloadBlob'
import ManageMembers from './ManageMembers'

const conversation = {
  id: 1, kind: 'channel', name: 'Général',
  members: [
    { id: 9, username: 'reda', full_name: 'Réda', is_admin: true },
    { id: 2, username: 'sami', full_name: 'Sami' },
  ],
}

function renderSheet(props = {}) {
  const store = configureStore({ reducer: { messaging: messagingReducer } })
  render(
    <Provider store={store}>
      <ManageMembers open onOpenChange={() => {}} conversation={conversation}
                     currentUserId={9} isAdmin {...props} />
    </Provider>,
  )
  return store
}

describe('ManageMembers (S20)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('liste les membres et permet à un admin d’en retirer', async () => {
    renderSheet()
    expect(screen.getByText('Sami')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Retirer Sami'))
    await waitFor(() => expect(messagesApi.removeMember).toHaveBeenCalledWith(1, 2))
  })

  it('un membre peut quitter le canal (avec confirmation)', async () => {
    const onLeft = vi.fn()
    renderSheet({ isAdmin: false, onLeft })
    await userEvent.click(screen.getByRole('button', { name: /Quitter le canal/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Quitter' }))
    await waitFor(() => expect(messagesApi.leaveConversation).toHaveBeenCalledWith(1))
  })

  // ── WIR157 ──────────────────────────────────────────────────────────────
  it('un admin pose l’alias e-mail entrant du canal', async () => {
    renderSheet()
    await userEvent.type(screen.getByLabelText(/Alias e-mail entrant/), 'ventes@taqinor.ma')
    await userEvent.click(screen.getByLabelText('Enregistrer l’alias'))
    await waitFor(() => expect(messagesApi.setChannelAlias)
      .toHaveBeenCalledWith(1, 'ventes@taqinor.ma'))
  })

  it('un admin exporte la conversation en JSON puis CSV', async () => {
    renderSheet()
    await userEvent.click(screen.getByRole('button', { name: /JSON/ }))
    await waitFor(() => expect(messagesApi.exportConversation).toHaveBeenCalledWith(1, 'json'))
    await userEvent.click(screen.getByRole('button', { name: /CSV/ }))
    await waitFor(() => expect(messagesApi.exportConversation).toHaveBeenCalledWith(1, 'csv'))
    expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'conversation-1.csv')
  })

  it('un non-admin ne voit ni l’alias ni l’export', () => {
    renderSheet({ isAdmin: false })
    expect(screen.queryByLabelText(/Alias e-mail entrant/)).not.toBeInTheDocument()
    expect(screen.queryByText('Exporter la conversation')).not.toBeInTheDocument()
  })
})
