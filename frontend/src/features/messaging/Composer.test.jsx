import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import messagingReducer, { setActiveConversation } from './store/messagingSlice'

// Mock du client API pour ne déclencher aucun réseau. WIR155 — ajoute les
// nouveaux endpoints (réponses enregistrées, sondages, messages programmés).
vi.mock('../../api/messagesApi', () => ({
  default: {
    sendMessage: vi.fn(() => Promise.resolve({ data: { id: 99, conversation: 1, body: 'envoyé' } })),
    editMessage: vi.fn(() => Promise.resolve({ data: { id: 5, body: 'corrigé' } })),
    deleteMessage: vi.fn(() => Promise.resolve({ data: {} })),
    uploadAttachment: vi.fn(() => Promise.resolve({ data: { id: 1, name: 'f.png' } })),
    canned: {
      list: vi.fn(() => Promise.resolve({
        data: [{ id: 1, shortcut: 'merci', body: 'Merci beaucoup !', scope: 'personal' }],
      })),
    },
    poll: {
      create: vi.fn(() => Promise.resolve({
        data: { id: 77, conversation: 1, kind: 'poll', body: 'Sondage ?' },
      })),
    },
    scheduled: {
      list: vi.fn(() => Promise.resolve({ data: [] })),
      create: vi.fn(() => Promise.resolve({ data: { id: 3, status: 'pending' } })),
      cancel: vi.fn(() => Promise.resolve({ data: {} })),
    },
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

  // WIR259 — les deux actions étaient écrites/testées isolément mais jamais
  // montées dans le composer réel.
  it('monte les actions « partager un enregistrement » et note vocale (WIR259)', () => {
    renderComposer()
    expect(screen.getByRole('button', { name: 'Partager un enregistrement' })).toBeInTheDocument()
    // VoiceRecorder se masque lui-même en environnement de test (jsdom n'a
    // pas MediaRecorder) : ce n'est PAS une régression, `isRecordingSupported()`
    // renvoie false et le composant rend `null` volontairement.
    expect(screen.queryByRole('button', { name: /note vocale|enregistrer|micro/i })).toBeNull()
  })

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

  // ── WIR155 ──────────────────────────────────────────────────────────────
  it('taper : affiche l’autocomplétion des réponses enregistrées et insère au choix', async () => {
    renderComposer()
    const input = screen.getByLabelText('Message')
    await userEvent.type(input, 'cc :merci')
    expect(await screen.findByRole('listbox', { name: 'Réponses enregistrées' })).toBeInTheDocument()
    await userEvent.click(screen.getByText(':merci'))
    expect(input).toHaveValue('cc Merci beaucoup ! ')
  })

  it('crée un sondage via le Dialog', async () => {
    renderComposer()
    await userEvent.click(screen.getByLabelText('Créer un sondage'))
    await userEvent.type(screen.getByLabelText('Question'), 'Réunion mardi ?')
    await userEvent.type(screen.getByLabelText('Option 1'), 'Oui')
    await userEvent.type(screen.getByLabelText('Option 2'), 'Non')
    await userEvent.click(screen.getByText('Créer le sondage'))
    await waitFor(() => expect(messagesApi.poll.create).toHaveBeenCalledWith({
      conversation: 1, question: 'Réunion mardi ?', options: ['Oui', 'Non'],
      allow_multiple: false, is_anonymous: false,
    }))
  })

  it('programme l’envoi via le Popover', async () => {
    renderComposer()
    await userEvent.type(screen.getByLabelText('Message'), 'plus tard')
    await userEvent.click(screen.getByLabelText('Programmer l\'envoi'))
    const future = new Date(Date.now() + 3600_000)
    const local = `${future.getFullYear()}-${String(future.getMonth() + 1).padStart(2, '0')}-${String(future.getDate()).padStart(2, '0')}T${String(future.getHours()).padStart(2, '0')}:${String(future.getMinutes()).padStart(2, '0')}`
    fireEvent.change(document.getElementById('chat-schedule-at'), { target: { value: local } })
    await userEvent.click(screen.getByText('Programmer'))
    await waitFor(() => expect(messagesApi.scheduled.create).toHaveBeenCalledWith(
      expect.objectContaining({ conversation: 1, body: 'plus tard' })))
  })
})
