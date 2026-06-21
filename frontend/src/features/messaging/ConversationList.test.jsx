import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer, { fetchConversations } from './store/messagingSlice'
import ConversationList from './ConversationList'

function storeWith(conversations) {
  const store = configureStore({ reducer: { messaging: messagingReducer } })
  store.dispatch({ type: fetchConversations.fulfilled.type, payload: conversations })
  return store
}

const convs = [
  { id: 1, kind: 'channel', name: 'Général', unread_count: 2,
    last_message: { body: 'Salut tout le monde', created_at: '2026-06-21T10:00:00Z', sender: { username: 'sami' } } },
  { id: 2, kind: 'dm', muted: true,
    members: [{ id: 9, username: 'reda' }, { id: 5, username: 'autre' }],
    unread_count: 0,
    last_message: { body: 'ok', created_at: '2026-06-20T10:00:00Z' } },
]

describe('ConversationList (S14)', () => {
  it('rend canaux et DMs avec aperçu et badge de non-lus', () => {
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    expect(screen.getByText('Général')).toBeInTheDocument()
    expect(screen.getByText('autre')).toBeInTheDocument() // nom de l'autre membre du DM
    expect(screen.getByText('2')).toBeInTheDocument() // badge de non-lus
    expect(screen.getByLabelText('Notifications coupées')).toBeInTheDocument() // muet
  })

  it('filtre via la recherche', async () => {
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    await userEvent.type(screen.getByLabelText('Rechercher une conversation'), 'général')
    expect(screen.getByText('Général')).toBeInTheDocument()
    expect(screen.queryByText('autre')).not.toBeInTheDocument()
  })

  it('le "+" déclenche le flux de création', async () => {
    const onNew = vi.fn()
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} onNew={onNew} />
      </Provider>,
    )
    await userEvent.click(screen.getByLabelText('Nouvelle conversation'))
    expect(onNew).toHaveBeenCalledTimes(1)
  })

  it('sélectionner une conversation remonte son id', async () => {
    const onSelect = vi.fn()
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} onSelect={onSelect} />
      </Provider>,
    )
    await userEvent.click(screen.getByText('Général'))
    expect(onSelect).toHaveBeenCalledWith(1)
  })
})
