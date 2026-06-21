import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer, { fetchUnreadCount } from '../../features/messaging/store/messagingSlice'

vi.mock('../../api/messagesApi', () => ({
  default: { unreadCount: vi.fn(() => Promise.resolve({ data: { unread: 0 } })) },
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => navigateMock,
}))

import ChatBell from './ChatBell'

function renderBell(unread) {
  const store = configureStore({ reducer: { messaging: messagingReducer } })
  if (unread != null) {
    store.dispatch({ type: fetchUnreadCount.fulfilled.type, payload: unread })
  }
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ChatBell />
      </MemoryRouter>
    </Provider>,
  )
  return store
}

describe('ChatBell (S13)', () => {
  it('affiche le badge du total de non-lus', () => {
    renderBell(4)
    expect(screen.getByText('4')).toBeInTheDocument()
  })

  it('plafonne le badge à 99+', () => {
    renderBell(150)
    expect(screen.getByText('99+')).toBeInTheDocument()
  })

  it('clique → navigue vers /messages', async () => {
    renderBell(0)
    await userEvent.click(screen.getByLabelText(/Messages/))
    expect(navigateMock).toHaveBeenCalledWith('/messages')
  })
})
