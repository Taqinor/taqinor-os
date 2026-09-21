import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer, { setActiveConversation, fetchMessages, fetchPinned } from './store/messagingSlice'
import MessageThread from './MessageThread'

// jsdom n'implémente pas scrollIntoView.
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

function storeWithThread() {
  const store = configureStore({ reducer: { messaging: messagingReducer } })
  store.dispatch(setActiveConversation(1))
  store.dispatch({
    type: fetchMessages.fulfilled.type,
    payload: {
      conversationId: 1,
      page: { results: [
        { id: 1, body: 'premier', created_at: '2026-06-21T09:00:00', sender: { id: 2 } },
        { id: 2, body: 'à moi', created_at: '2026-06-21T09:01:00', sender: { id: 9 } },
      ] },
      next: 'cursor-older',
    },
  })
  store.dispatch({
    type: fetchPinned.fulfilled.type,
    payload: { conversationId: 1, items: [{ id: 1, body: 'premier', created_at: '2026-06-21T09:00:00' }] },
  })
  return store
}

describe('MessageThread (S15)', () => {
  it('rend les bulles et la barre des épingles', () => {
    render(
      <Provider store={storeWithThread()}>
        <MessageThread currentUserId={9} nextOlder="cursor-older" />
      </Provider>,
    )
    expect(screen.getByText('à moi')).toBeInTheDocument()
    expect(screen.getByLabelText('Messages épinglés')).toBeInTheDocument()
  })

  it('propose de charger les anciens messages quand un curseur existe', () => {
    render(
      <Provider store={storeWithThread()}>
        <MessageThread currentUserId={9} nextOlder="cursor-older" />
      </Provider>,
    )
    expect(screen.getByText('Charger les anciens messages')).toBeInTheDocument()
  })

  it('VX196 — le fil est un log annoncé (polite/additions) et défilable au clavier', () => {
    render(
      <Provider store={storeWithThread()}>
        <MessageThread currentUserId={9} nextOlder="cursor-older" />
      </Provider>,
    )
    const scrollEl = screen.getByText('à moi').closest('[role="log"]')
    expect(scrollEl).not.toBeNull()
    expect(scrollEl).toHaveAttribute('aria-live', 'polite')
    expect(scrollEl).toHaveAttribute('aria-relevant', 'additions')
    expect(scrollEl).toHaveAttribute('tabIndex', '0')
  })
})
