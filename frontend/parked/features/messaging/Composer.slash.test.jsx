import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer, { setActiveConversation } from './store/messagingSlice'

// XKB31 — Composer : commandes / branchées sur le pipeline propose→confirm
// existant (S8/S19). Fichier séparé de Composer.test.jsx pour isoler les mocks
// iaApi/messagesApi propres à ce flux sans toucher aux tests existants.
vi.mock('../../api/messagesApi', () => ({
  default: {
    sendMessage: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    editMessage: vi.fn(),
    deleteMessage: vi.fn(),
    uploadAttachment: vi.fn(),
  },
}))

vi.mock('../../api/iaApi', () => ({
  default: {
    getAgentActions: vi.fn(() => Promise.resolve({
      data: { actions: [{ key: 'crm.lead.create' }] }, // ventes.devis.creer_auto absent -> indisponible
    })),
    queryAgent: vi.fn(),
    confirmAction: vi.fn(),
  },
}))

import messagesApi from '../../api/messagesApi'
import iaApi from '../../api/iaApi'
import Composer from './Composer'

function renderComposer(props = {}) {
  const store = configureStore({ reducer: { messaging: messagingReducer } })
  store.dispatch(setActiveConversation(1))
  return render(
    <Provider store={store}>
      <Composer members={[]} {...props} />
    </Provider>,
  )
}

describe('Composer — commandes / (XKB31)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('taper / affiche le picker de commandes filtré par le registre autorisé', async () => {
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), '/le')
    expect(await screen.findByRole('listbox', { name: 'Commandes' })).toBeInTheDocument()
    expect(screen.getByText('/lead')).toBeInTheDocument()
    await waitFor(() => expect(iaApi.getAgentActions).toHaveBeenCalled())
  })

  it('une commande dont l’action n’est pas dans le registre apparaît indisponible', async () => {
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), '/devis')
    const option = await screen.findByRole('option', { name: /devis/ })
    expect(option).toBeInTheDocument()
    const button = option.querySelector('button')
    expect(button).toBeDisabled()
    expect(screen.getByText(/indisponible pour votre rôle/)).toBeInTheDocument()
  })

  it('/lead propose la création via le pipeline propose→confirm existant', async () => {
    iaApi.queryAgent.mockResolvedValue({
      data: {
        answer: 'Je vais créer ce lead.',
        proposal: {
          type: 'proposal',
          action_key: 'crm.lead.create',
          human_preview: 'Créer un lead nommé Ahmed.',
          confirm_token: 'tok-123',
        },
      },
    })
    renderComposer()
    const input = screen.getByLabelText('Message')
    await userEvent.type(input, '/lead Ahmed')
    await userEvent.click(screen.getByLabelText('Envoyer'))

    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledWith('Crée un lead nommé Ahmed.'))
    expect(await screen.findByTestId('slash-proposal-card')).toBeInTheDocument()
    expect(screen.getByText('Créer un lead nommé Ahmed.')).toBeInTheDocument()
  })

  it('la confirmation exécute et poste la carte du lead créé — aucune exécution sans confirmation', async () => {
    iaApi.queryAgent.mockResolvedValue({
      data: {
        answer: '', proposal: {
          type: 'proposal', action_key: 'crm.lead.create',
          human_preview: 'Créer un lead nommé Ahmed.', confirm_token: 'tok-123',
        },
      },
    })
    iaApi.confirmAction.mockResolvedValue({
      data: {
        ok: true, detail: 'Lead créé avec succès.', action_key: 'crm.lead.create',
        data: { lead_id: 42 },
      },
    })
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), '/lead Ahmed')
    await userEvent.click(screen.getByLabelText('Envoyer'))
    await screen.findByTestId('slash-proposal-card')

    // Aucune exécution avant le clic Confirmer.
    expect(iaApi.confirmAction).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: /Confirmer/ }))

    await waitFor(() => expect(iaApi.confirmAction).toHaveBeenCalledWith('tok-123'))
    expect(await screen.findByTestId('slash-result-card')).toBeInTheDocument()
    await waitFor(() => expect(messagesApi.sendMessage).toHaveBeenCalled())
    expect(messagesApi.sendMessage.mock.calls[0][0]).toMatchObject({
      conversation: 1, record_type: 'lead', record_id: 42,
    })
  })

  it('Annuler écarte la proposition sans jamais appeler confirmAction', async () => {
    iaApi.queryAgent.mockResolvedValue({
      data: {
        answer: '', proposal: {
          type: 'proposal', action_key: 'crm.lead.create',
          human_preview: 'Créer un lead nommé Ahmed.', confirm_token: 'tok-999',
        },
      },
    })
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), '/lead Ahmed')
    await userEvent.click(screen.getByLabelText('Envoyer'))
    await screen.findByTestId('slash-proposal-card')

    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(iaApi.confirmAction).not.toHaveBeenCalled()
    expect(screen.queryByTestId('slash-proposal-card')).not.toBeInTheDocument()
  })

  it('/aide reste purement local (aucun appel à queryAgent)', async () => {
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), '/aide')
    await userEvent.click(screen.getByLabelText('Envoyer'))
    await screen.findByTestId('slash-result-card')
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
    expect(screen.getByText(/Commandes disponibles/)).toBeInTheDocument()
  })
})
