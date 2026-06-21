import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer, { setActiveConversation } from './store/messagingSlice'

// Mock du client API pour ne déclencher aucun réseau.
vi.mock('../../api/messagesApi', () => ({
  default: {
    sendMessage: vi.fn(() => Promise.resolve({ data: { id: 99, conversation: 1, body: 'envoyé' } })),
    editMessage: vi.fn(() => Promise.resolve({ data: { id: 5, body: 'corrigé' } })),
    deleteMessage: vi.fn(() => Promise.resolve({ data: {} })),
    uploadAttachment: vi.fn(() => Promise.resolve({ data: { id: 1, name: 'f.png' } })),
  },
}))

import messagesApi from '../../api/messagesApi'
import Composer from './Composer'

const members = [
  { id: 2, value: '2', label: 'Sami', username: 'sami' },
  { id: 3, value: '3', label: 'Sara', username: 'sara' },
]

function renderComposer(props = {}) {
  const store = configureStore({ reducer: { messaging: messagingReducer } })
  store.dispatch(setActiveConversation(1))
  const utils = render(
    <Provider store={store}>
      <Composer members={members} {...props} />
    </Provider>,
  )
  return { store, ...utils }
}

describe('Composer (S16)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('taper @ affiche le sélecteur de membres', async () => {
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), 'cc @sa')
    expect(await screen.findByRole('listbox', { name: 'Membres à mentionner' })).toBeInTheDocument()
    expect(screen.getByText('Sami')).toBeInTheDocument()
    expect(screen.getByText('Sara')).toBeInTheDocument()
  })

  it('envoyer appelle l’API avec le corps', async () => {
    renderComposer()
    const input = screen.getByLabelText('Message')
    await userEvent.type(input, 'bonjour')
    await userEvent.click(screen.getByLabelText('Envoyer'))
    await waitFor(() => expect(messagesApi.sendMessage).toHaveBeenCalled())
    expect(messagesApi.sendMessage.mock.calls[0][0]).toMatchObject({ conversation: 1, body: 'bonjour' })
  })

  it('en mode édition, enregistre via editMessage', async () => {
    const onEditDone = vi.fn()
    renderComposer({ editing: { id: 5, body: 'avant' }, onEditDone })
    const input = screen.getByLabelText('Message')
    expect(input).toHaveValue('avant')
    await userEvent.clear(input)
    await userEvent.type(input, 'corrigé')
    await userEvent.click(screen.getByLabelText('Enregistrer'))
    await waitFor(() => expect(messagesApi.editMessage).toHaveBeenCalledWith(5, { body: 'corrigé' }))
    expect(onEditDone).toHaveBeenCalled()
  })

  it('confirme la suppression via AlertDialog', async () => {
    const onDeleteResolved = vi.fn()
    renderComposer({ pendingDelete: { id: 7 }, onDeleteResolved })
    expect(screen.getByText('Supprimer ce message ?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(messagesApi.deleteMessage).toHaveBeenCalledWith(7))
    expect(onDeleteResolved).toHaveBeenCalled()
  })
})
