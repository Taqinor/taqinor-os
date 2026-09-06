import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer, { fetchConversations } from '../../features/messaging/store/messagingSlice'

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

vi.mock('../../api/messagesApi', () => ({
  default: {
    listConversations: vi.fn(() => Promise.resolve({ data: [] })),
    listMessages: vi.fn(() => Promise.resolve({ data: { results: [], next: null } })),
    listPinned: vi.fn(() => Promise.resolve({ data: [] })),
    markRead: vi.fn(() => Promise.resolve({ data: {} })),
    unreadCount: vi.fn(() => Promise.resolve({ data: { unread: 0 } })),
    listCompanyMembers: vi.fn(() => Promise.resolve({ data: [] })),
    // AUDV28 — durée de conservation affichée dans l'en-tête de conversation.
    getConversationRetention: vi.fn(() => Promise.resolve({
      data: { conversation_kind: 'channel', retention_months: null, applicable: false },
    })),
  },
}))

const authReducer = (state = { user: { id: 9, username: 'reda' } }) => state

import ChatPage from './ChatPage'
import messagesApi from '../../api/messagesApi'

function renderPage(conversations = [], route = '/messages') {
  const store = configureStore({
    reducer: { messaging: messagingReducer, auth: authReducer },
  })
  if (conversations.length) {
    store.dispatch({ type: fetchConversations.fulfilled.type, payload: conversations })
  }
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <ChatPage />
      </MemoryRouter>
    </Provider>,
  )
  return store
}

describe('ChatPage (S13)', () => {
  it('rend le shell deux-panneaux avec le placeholder sans conversation active', () => {
    renderPage()
    expect(screen.getByTestId('chat-page')).toBeInTheDocument()
    expect(screen.getByTestId('conversation-list')).toBeInTheDocument()
    expect(screen.getByText('Sélectionnez une conversation')).toBeInTheDocument()
  })

  it('liste les conversations chargées', () => {
    renderPage([
      { id: 1, kind: 'channel', name: 'Général', unread_count: 0, last_message: null },
    ])
    expect(screen.getByText('Général')).toBeInTheDocument()
  })

  /* AUDV28 (DRAFT165-8) — durée de conservation affichée dans l'en-tête
     UNIQUEMENT quand une politique est réellement applicable (jamais un
     défaut inventé). */
  it('affiche la durée de conservation quand une politique est applicable', async () => {
    messagesApi.getConversationRetention.mockResolvedValueOnce({
      data: { conversation_kind: 'channel', retention_months: 6, applicable: true },
    })
    renderPage(
      [{ id: 1, kind: 'channel', name: 'Général', unread_count: 0, last_message: null }],
      '/messages?c=1',
    )
    expect(await screen.findByText('Conservation : 6 mois')).toBeInTheDocument()
  })

  it('n’affiche rien quand aucune politique n’est posée', async () => {
    renderPage(
      [{ id: 1, kind: 'channel', name: 'Général', unread_count: 0, last_message: null }],
      '/messages?c=1',
    )
    await waitFor(() => expect(messagesApi.getConversationRetention).toHaveBeenCalledWith(1))
    expect(screen.queryByText(/Conservation :/)).not.toBeInTheDocument()
  })
})
