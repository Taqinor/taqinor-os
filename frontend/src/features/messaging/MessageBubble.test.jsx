import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import MessageBubble from './MessageBubble'

// VoiceMessage tire le binaire via messagesApi : on le neutralise.
vi.mock('../../api/messagesApi', () => ({
  default: { getAttachment: vi.fn(() => Promise.resolve({ data: new Blob() })) },
}))

// Store minimal portant l'utilisateur courant (pour le repli `state.auth.user`).
function makeStore(userId = 99) {
  return configureStore({
    reducer: { auth: (s = { user: { id: userId } }) => s },
  })
}

function renderBubble(props) {
  return render(
    <Provider store={makeStore()}>
      <MessageBubble {...props} />
    </Provider>,
  )
}

describe('MessageBubble (S15/S17/S18)', () => {
  it('rend le corps, l’auteur et l’heure pour un message d’un autre', () => {
    renderBubble({
      message: { id: 1, body: 'Bonjour', created_at: '2026-06-21T08:07:00', sender: { id: 2, username: 'sami' } },
      own: false,
    })
    expect(screen.getByText('Bonjour')).toBeInTheDocument()
    expect(screen.getByText('sami')).toBeInTheDocument()
    expect(screen.getByText('08:07')).toBeInTheDocument()
  })

  it('affiche le slot pièce jointe (fichier)', () => {
    renderBubble({
      message: { id: 1, body: '', created_at: 'x', sender: { id: 2 },
        attachments: [{ id: 7, filename: 'devis.pdf', mime: 'application/pdf', url: '/f/7' }] },
      own: true,
    })
    expect(screen.getByText('devis.pdf')).toBeInTheDocument()
  })

  it('rend une pièce jointe vocale via VoiceMessage', () => {
    renderBubble({
      message: { id: 1, created_at: 'x', sender: { id: 2 },
        attachments: [{ id: 3, kind: 'voice', url: '/f/3', transcript_status: 'disabled' }] },
      own: true,
    })
    expect(screen.getByTestId('voice-message')).toBeInTheDocument()
  })

  it('un message supprimé affiche un placeholder', () => {
    renderBubble({ message: { id: 1, deleted: true, created_at: 'x' }, own: true })
    expect(screen.getByText('Message supprimé')).toBeInTheDocument()
  })

  it('lit is_pinned (pas pinned) pour l’indicateur d’épingle', () => {
    renderBubble({ message: { id: 1, body: 'x', created_at: 'x', sender: { id: 2 }, is_pinned: true } })
    expect(screen.getByLabelText('Épinglé')).toBeInTheDocument()
  })

  it('édition / suppression via le menu, pour ses propres messages', async () => {
    const onEdit = vi.fn(); const onDelete = vi.fn()
    renderBubble({
      message: { id: 1, body: 'à moi', created_at: 'x', sender: { id: 2 } },
      own: true, onEdit, onDelete,
    })
    await userEvent.click(screen.getByLabelText('Actions du message'))
    await userEvent.click(await screen.findByText('Modifier'))
    await userEvent.click(screen.getByLabelText('Actions du message'))
    await userEvent.click(await screen.findByText('Supprimer'))
    expect(onEdit).toHaveBeenCalled()
    expect(onDelete).toHaveBeenCalled()
  })

  it('agrège les réactions plates en puces avec count + état mine', () => {
    const onReact = vi.fn()
    renderBubble({
      message: {
        id: 1, body: 'x', created_at: 'x', sender: { id: 2 },
        reactions: [
          { id: 1, user: 99, emoji: '👍' },
          { id: 2, user: 5, emoji: '👍' },
          { id: 3, user: 5, emoji: '❤️' },
        ],
      },
      currentUserId: 99,
      onReact,
    })
    // 👍 a 2 réactions dont la mienne ; ❤️ en a 1.
    expect(screen.getByLabelText('👍 2 (vous avez réagi)')).toBeInTheDocument()
    expect(screen.getByLabelText('❤️ 1')).toBeInTheDocument()
  })

  it('cliquer une puce de réaction bascule l’emoji', async () => {
    const onReact = vi.fn()
    renderBubble({
      message: { id: 1, body: 'x', created_at: 'x', sender: { id: 2 },
        reactions: [{ id: 1, user: 99, emoji: '👍' }] },
      currentUserId: 99, onReact,
    })
    await userEvent.click(screen.getByLabelText('👍 1 (vous avez réagi)'))
    expect(onReact).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }), '👍')
  })

  it('épingler / désépingler via le menu', async () => {
    const onTogglePin = vi.fn()
    renderBubble({
      message: { id: 1, body: 'x', created_at: 'x', sender: { id: 2 }, is_pinned: false },
      onTogglePin,
    })
    await userEvent.click(screen.getByLabelText('Actions du message'))
    await userEvent.click(await screen.findByText('Épingler'))
    expect(onTogglePin).toHaveBeenCalled()
  })
})
