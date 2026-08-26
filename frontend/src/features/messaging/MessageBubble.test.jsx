import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import MessageBubble from './MessageBubble'
import messagingReducer from './store/messagingSlice'
import messagesApi from '../../api/messagesApi'

// VoiceMessage tire le binaire via messagesApi : on le neutralise. WIR155 —
// mock complet des nouveaux endpoints (fils/rappels/favoris/sondages) pour
// les tests ci-dessous.
vi.mock('../../api/messagesApi', () => ({
  default: {
    getAttachment: vi.fn(() => Promise.resolve({ data: new Blob() })),
    threads: {
      list: vi.fn(() => Promise.resolve({ data: [] })),
      reply: vi.fn(() => Promise.resolve({ data: { id: 42, body: 'réponse', conversation: 1 } })),
    },
    remindMe: vi.fn(() => Promise.resolve({ data: {} })),
    toggleBookmark: vi.fn(() => Promise.resolve({ data: { status: 'added' } })),
    poll: {
      results: vi.fn(() => Promise.resolve({
        data: {
          poll_id: 1, question: 'Réunion mardi ?', allow_multiple: false,
          is_anonymous: false, closed_at: null, my_vote_option_ids: [],
          options: [{ id: 1, label: 'Oui', vote_count: 2 }, { id: 2, label: 'Non', vote_count: 1 }],
        },
      })),
      vote: vi.fn(() => Promise.resolve({ data: {} })),
    },
  },
}))

// Store minimal portant l'utilisateur courant (pour le repli `state.auth.user`)
// + le reducer messaging réel (nécessaire à ThreadPanel qui dispatche
// `sendMessage.fulfilled`).
function makeStore(userId = 99) {
  return configureStore({
    reducer: {
      auth: (s = { user: { id: userId } }) => s,
      messaging: messagingReducer,
    },
  })
}

// WIR259 — la carte d'enregistrement partagé est désormais le VRAI
// `./RecordCard` (S19), qui navigue en SPA via `useNavigate` : la bulle doit
// donc être rendue dans un Router.
function renderBubble(props) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/chat']}>
        <Routes>
          <Route path="/chat" element={<MessageBubble {...props} />} />
          <Route path="/ventes/devis/7" element={<div>Écran devis 7</div>} />
        </Routes>
      </MemoryRouter>
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

  // ── WIR155 ──────────────────────────────────────────────────────────────
  it('rend les options/vote/résultats d’un sondage (kind=poll)', async () => {
    renderBubble({
      message: { id: 5, body: 'Réunion mardi ?', kind: 'poll', created_at: 'x', sender: { id: 2 } },
      own: false,
    })
    expect(await screen.findByText('Réunion mardi ?')).toBeInTheDocument()
    expect(screen.getByText('Oui')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Oui'))
    expect(messagesApi.poll.vote).toHaveBeenCalledWith(5, [1])
  })

  it('« Répondre en fil » ouvre le panneau et poste une réponse', async () => {
    renderBubble({
      message: { id: 1, body: 'Racine', created_at: 'x', sender: { id: 2 } },
    })
    await userEvent.click(screen.getByText('Répondre en fil'))
    const input = await screen.findByLabelText('Répondre en fil')
    await userEvent.type(input, 'ma réponse')
    await userEvent.click(screen.getByLabelText('Envoyer la réponse'))
    expect(messagesApi.threads.reply).toHaveBeenCalledWith(1, { body: 'ma réponse' })
  })

  it('« Me rappeler » et « favori » appellent le backend depuis le menu', async () => {
    renderBubble({ message: { id: 1, body: 'x', created_at: 'x', sender: { id: 2 } } })
    await userEvent.click(screen.getByLabelText('Actions du message'))
    await userEvent.click(await screen.findByText('Me rappeler dans 1 h'))
    expect(messagesApi.remindMe).toHaveBeenCalledWith(1, expect.any(String))

    await userEvent.click(screen.getByLabelText('Actions du message'))
    await userEvent.click(await screen.findByText('Ajouter aux favoris'))
    expect(messagesApi.toggleBookmark).toHaveBeenCalledWith(1)
  })

  // ── WIR259 — vraie carte d'enregistrement (SPA + icône par type) ─────────
  it('rend un devis partagé en carte cliquable qui navigue en SPA', async () => {
    renderBubble({
      message: {
        id: 8, body: '', created_at: 'x', sender: { id: 2 },
        shared_label: 'Devis DV-2026-004', shared_url: '/ventes/devis/7',
      },
    })
    const card = screen.getByTestId('record-card')
    expect(card).toHaveAttribute('href', '/ventes/devis/7')
    expect(screen.getByText('Devis DV-2026-004')).toBeInTheDocument()
    // Navigation SPA : le clic ne suit pas le lien, il route en interne.
    await userEvent.click(card)
    expect(await screen.findByText('Écran devis 7')).toBeInTheDocument()
  })

  it('ne monte aucune carte quand le message ne partage rien', () => {
    renderBubble({
      message: { id: 9, body: 'texte simple', created_at: 'x', sender: { id: 2 } },
    })
    expect(screen.queryByTestId('record-card')).toBeNull()
  })

  it('rend un mémo vocal via VoiceMessage (pièce jointe kind=voice)', () => {
    renderBubble({
      message: {
        id: 10, body: '', created_at: 'x', sender: { id: 2 },
        attachments: [{ id: 3, kind: 'voice', mime: 'audio/webm', duration_s: 4 }],
      },
    })
    expect(screen.getByTestId('voice-message')).toBeInTheDocument()
  })
})
