import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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
  },
}))

const authReducer = (state = { user: { id: 9, username: 'reda' } }) => state

import ChatPage from './ChatPage'

function renderPage(conversations = []) {
  const store = configureStore({
    reducer: { messaging: messagingReducer, auth: authReducer },
  })
  if (conversations.length) {
    store.dispatch({ type: fetchConversations.fulfilled.type, payload: conversations })
  }
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/messages']}>
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
})
