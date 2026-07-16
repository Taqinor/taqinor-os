import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
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

  // VX134(d) — pulse UNIQUEMENT quand le total AUGMENTE (jamais à chaque
  // poll qui ne change rien, jamais à la baisse après lecture).
  it('le badge pulse quand le total augmente', () => {
    const store = renderBell(2)
    expect(screen.getByText('2')).not.toHaveClass('nb-badge-pulse')
    act(() => {
      store.dispatch({ type: fetchUnreadCount.fulfilled.type, payload: 5 })
    })
    expect(screen.getByText('5')).toHaveClass('nb-badge-pulse')
  })

  it('le badge ne pulse pas si le total ne change pas (poll sans changement)', () => {
    const store = renderBell(3)
    act(() => {
      store.dispatch({ type: fetchUnreadCount.fulfilled.type, payload: 3 })
    })
    expect(screen.getByText('3')).not.toHaveClass('nb-badge-pulse')
  })

  it('le badge ne pulse pas quand le total BAISSE (lecture des messages)', () => {
    const store = renderBell(5)
    act(() => {
      store.dispatch({ type: fetchUnreadCount.fulfilled.type, payload: 1 })
    })
    expect(screen.getByText('1')).not.toHaveClass('nb-badge-pulse')
  })
})
