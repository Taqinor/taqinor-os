import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// WIR156 — la liste interroge maintenant messagesApi.status (mon statut +
// statuts des collègues) au montage : on le stub pour éviter tout réseau.
// WIR155 — ajoute les onglets Fils/Favoris (threads.listFollowed / listBookmarks).
const {
  statusMe, statusColleagues, setStatus, clearStatus, setDnd,
  listFollowed, listBookmarks,
  // WIR260 — mute/archive/recherche plein-texte : bouchons par défaut pour
  // que TAPER dans la recherche (déclenche `search` après 300 ms) ne parte
  // jamais sur un `undefined` non-fonction dans un test qui n'a rien à voir
  // avec WIR260.
  search, muteConversation, archiveConversation,
} = vi.hoisted(() => ({
  statusMe: vi.fn(() => Promise.resolve({ data: { status_emoji: '', status_text: '', is_dnd: false } })),
  statusColleagues: vi.fn(() => Promise.resolve({ data: [] })),
  setStatus: vi.fn((d) => Promise.resolve({ data: { ...d, is_dnd: false } })),
  clearStatus: vi.fn(() => Promise.resolve({ data: { status_emoji: '', status_text: '', is_dnd: false } })),
  setDnd: vi.fn(() => Promise.resolve({ data: { is_dnd: true } })),
  listFollowed: vi.fn(() => Promise.resolve({ data: [] })),
  listBookmarks: vi.fn(() => Promise.resolve({ data: [] })),
  search: vi.fn(() => Promise.resolve({ data: [] })),
  muteConversation: vi.fn(() => Promise.resolve({ data: {} })),
  archiveConversation: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/messagesApi', () => ({
  default: {
    status: {
      me: statusMe, colleagues: statusColleagues,
      setStatus, clear: clearStatus, setDnd,
    },
    threads: { listFollowed },
    listBookmarks,
    search, muteConversation, archiveConversation,
  },
}))

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

describe('ConversationList — WIR156 (statut + DND + présence collègues)', () => {
  it('définit un statut personnalisé', async () => {
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    await waitFor(() => expect(statusMe).toHaveBeenCalled())
    await userEvent.click(screen.getByLabelText('Définir mon statut'))
    await userEvent.type(screen.getByLabelText('Texte de statut'), 'En réunion')
    await userEvent.click(screen.getByLabelText('Enregistrer le statut'))
    await waitFor(() => expect(setStatus).toHaveBeenCalledWith(
      expect.objectContaining({ status_text: 'En réunion' })))
  })

  it('bascule Ne pas déranger', async () => {
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    await userEvent.click(screen.getByLabelText('Activer Ne pas déranger'))
    await waitFor(() => expect(setDnd).toHaveBeenCalled())
  })

  it('affiche le statut d’un collègue dans la liste (DM)', async () => {
    // Le collègue « autre » (id 5) est en DND avec un emoji de statut.
    statusColleagues.mockResolvedValueOnce({
      data: [{ user_id: 5, status_emoji: '🌴', status_text: 'Congés', is_dnd: true }],
    })
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    expect(await screen.findByLabelText('Statut du collègue')).toHaveTextContent('🌴')
    expect(screen.getAllByLabelText('Ne pas déranger').length).toBeGreaterThan(0)
  })
})

describe('ConversationList — WIR155 (onglets Fils / Favoris)', () => {
  it('l’onglet Fils liste les fils suivis et ouvre leur conversation', async () => {
    listFollowed.mockResolvedValueOnce({
      data: [{ root_message_id: 1, conversation_id: 1, root_preview: 'Question du fil', reply_count: 3, unread: 2 }],
    })
    const onSelect = vi.fn()
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} onSelect={onSelect} />
      </Provider>,
    )
    await userEvent.click(screen.getByRole('tab', { name: /Fils/ }))
    await userEvent.click(await screen.findByText('Question du fil'))
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it('l’onglet Fils affiche un état vide sans fil suivi', async () => {
    listFollowed.mockResolvedValueOnce({ data: [] })
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    await userEvent.click(screen.getByRole('tab', { name: /Fils/ }))
    expect(await screen.findByText('Aucun fil suivi')).toBeInTheDocument()
  })

  it('l’onglet Favoris liste les messages enregistrés et ouvre leur conversation', async () => {
    listBookmarks.mockResolvedValueOnce({
      data: [{ id: 1, message_detail: { conversation: 2, body: 'À relire', created_at: '2026-06-21T10:00:00Z' } }],
    })
    const onSelect = vi.fn()
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} onSelect={onSelect} />
      </Provider>,
    )
    await userEvent.click(screen.getByRole('tab', { name: /Favoris/ }))
    await userEvent.click(await screen.findByText('À relire'))
    expect(onSelect).toHaveBeenCalledWith(2)
  })
})

describe('ConversationList — mute/archive/recherche plein-texte (WIR260)', () => {
  it('« Sourdine » allume l’icône BellOff sur la conversation cliquée', async () => {
    muteConversation.mockResolvedValueOnce({ data: {} })
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    // Conversation 1 (« Général ») n'est pas sourdine au départ.
    const general = screen.getByRole('button', { name: 'Actions — Général' })
    await userEvent.click(general)
    await userEvent.click(await screen.findByText('Sourdine'))
    await waitFor(() => expect(muteConversation).toHaveBeenCalledWith(1, true))
    await waitFor(() => {
      expect(within(screen.getByText('Général').closest('button')).getByLabelText('Notifications coupées')).toBeInTheDocument()
    })
  })

  it('« Archiver » retire la ligne de la liste', async () => {
    archiveConversation.mockResolvedValueOnce({ data: {} })
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Actions — Général' }))
    await userEvent.click(await screen.findByText('Archiver'))
    await waitFor(() => expect(archiveConversation).toHaveBeenCalledWith(1))
    await waitFor(() => expect(screen.queryByText('Général')).not.toBeInTheDocument())
  })

  it('taper ≥ 2 caractères déclenche messagesApi.search et affiche les résultats serveur', async () => {
    search.mockResolvedValueOnce({
      data: [{ message_id: 5, conversation: 2, conversation_name: 'Reda / Autre', snippet: '…devis à confirmer…' }],
    })
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    await userEvent.type(screen.getByLabelText('Rechercher une conversation'), 'devis')
    await waitFor(() => expect(search).toHaveBeenCalledWith('devis'))
    expect(await screen.findByText('…devis à confirmer…')).toBeInTheDocument()
  })

  it('une erreur réseau sur la recherche laisse le filtre local intact (aucun plantage)', async () => {
    search.mockRejectedValueOnce(new Error('réseau'))
    render(
      <Provider store={storeWith(convs)}>
        <ConversationList currentUserId={9} />
      </Provider>,
    )
    await userEvent.type(screen.getByLabelText('Rechercher une conversation'), 'général')
    await waitFor(() => expect(search).toHaveBeenCalled())
    // Le filtre LOCAL (titre/aperçu) continue de fonctionner : « Général »
    // matche la saisie, la conversation reste affichée.
    expect(await screen.findByText('Général')).toBeInTheDocument()
  })
})
