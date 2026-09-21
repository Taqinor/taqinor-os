import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer from './store/messagingSlice'

vi.mock('../../api/messagesApi', () => ({
  default: {
    listCompanyMembers: vi.fn(() => Promise.resolve({ data: [
      { id: 2, username: 'sami', full_name: 'Sami T' },
      { id: 3, username: 'sara', full_name: 'Sara K' },
    ] })),
    createConversation: vi.fn(() => Promise.resolve({ data: { id: 50, kind: 'channel', name: 'Casa' } })),
  },
}))

import messagesApi from '../../api/messagesApi'
import NewConversation from './NewConversation'

function renderModal(props = {}) {
  const store = configureStore({ reducer: { messaging: messagingReducer } })
  render(
    <Provider store={store}>
      <NewConversation open onOpenChange={() => {}} {...props} />
    </Provider>,
  )
  return store
}

describe('NewConversation (S20)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('crée un canal nommé avec membres', async () => {
    const onCreated = vi.fn()
    renderModal({ onCreated })
    // Bascule sur "Canal"
    await userEvent.click(screen.getByRole('radio', { name: /Canal/ }))
    await userEvent.type(screen.getByLabelText('Nom du canal'), 'Casa')
    await waitFor(() => expect(messagesApi.listCompanyMembers).toHaveBeenCalled())
    await userEvent.click(screen.getByRole('button', { name: 'Créer le canal' }))
    await waitFor(() => expect(messagesApi.createConversation).toHaveBeenCalled())
    expect(messagesApi.createConversation.mock.calls[0][0]).toMatchObject({ kind: 'channel', name: 'Casa' })
    expect(onCreated).toHaveBeenCalledWith(50)
  })

  it('le bouton DM est désactivé sans destinataire', () => {
    renderModal()
    expect(screen.getByRole('button', { name: 'Démarrer' })).toBeDisabled()
  })
})
