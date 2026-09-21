import { describe, it, expect } from 'vitest'
import reducer, {
  setActiveConversation,
  clearConversationUnread,
  upsertConversation,
  toggleReaction,
  fetchConversations,
  fetchUnreadCount,
  fetchMessages,
  sendMessage,
  editMessage,
  deleteMessage,
} from './messagingSlice'

/* S12 — Tests du reducer du module Discuter (logique d'état, sans réseau).
   On dispatche les actions `.fulfilled` des thunks directement avec un payload
   simulé : aucun appel axios n'est effectué. */
describe('messagingSlice', () => {
  const init = reducer(undefined, { type: '@@INIT' })

  it('setActiveConversation réinitialise le fil quand l’id change', () => {
    let s = reducer(init, setActiveConversation(7))
    expect(s.activeId).toBe(7)
    s = { ...s, messages: [{ id: 1 }], nextOlder: 'x' }
    const same = reducer(s, setActiveConversation(7))
    expect(same.messages).toHaveLength(1) // même id → pas de reset
    const changed = reducer(s, setActiveConversation(8))
    expect(changed.messages).toHaveLength(0)
    expect(changed.nextOlder).toBeNull()
  })

  it('fetchConversations.fulfilled trie et calcule le total non-lu', () => {
    const s = reducer(init, {
      type: fetchConversations.fulfilled.type,
      payload: [
        { id: 1, unread_count: 0, last_message: { created_at: 'b' } },
        { id: 2, unread_count: 4, last_message: { created_at: 'a' } },
      ],
    })
    expect(s.conversations[0].id).toBe(2) // non-lue en tête
    expect(s.unreadTotal).toBe(4)
  })

  it('fetchUnreadCount.fulfilled pose le total du badge', () => {
    const s = reducer(init, { type: fetchUnreadCount.fulfilled.type, payload: 9 })
    expect(s.unreadTotal).toBe(9)
  })

  it('fetchMessages.fulfilled n’applique la page que pour la conversation active', () => {
    let s = reducer(init, setActiveConversation(5))
    s = reducer(s, { type: fetchMessages.pending.type, meta: { requestId: 'r1' } })
    s = reducer(s, {
      type: fetchMessages.fulfilled.type,
      meta: { requestId: 'r1' },
      payload: { conversationId: 5, page: { results: [{ id: 1, created_at: 'a' }] }, next: 'cursor' },
    })
    expect(s.messages).toHaveLength(1)
    expect(s.nextOlder).toBe('cursor')
    // page d'une AUTRE conversation : ignorée
    const other = reducer(s, {
      type: fetchMessages.fulfilled.type,
      meta: { requestId: 'r1' },
      payload: { conversationId: 99, page: { results: [{ id: 2 }] }, next: null },
    })
    expect(other.messages).toHaveLength(1)
  })

  it('fetchMessages.fulfilled ignore un tick PÉRIMÉ (VX164 — résolution inversée)', () => {
    let s = reducer(init, setActiveConversation(5))
    // Tick N-1 dispatché, PUIS tick N (le poll suivant, avant que N-1 réponde).
    s = reducer(s, { type: fetchMessages.pending.type, meta: { requestId: 'tickN-1' } })
    s = reducer(s, { type: fetchMessages.pending.type, meta: { requestId: 'tickN' } })
    // Tick N répond D'ABORD (plus rapide) — appliqué (c'est la DERNIÈRE requête).
    s = reducer(s, {
      type: fetchMessages.fulfilled.type,
      meta: { requestId: 'tickN' },
      payload: { conversationId: 5, page: { results: [{ id: 2, created_at: 'b' }] }, next: null },
    })
    expect(s.messages.map((m) => m.id)).toEqual([2])
    // Tick N-1 (lent) répond ENSUITE, en retard — ignoré : ne fait PAS
    // régresser l'écran vers une page plus ancienne.
    s = reducer(s, {
      type: fetchMessages.fulfilled.type,
      meta: { requestId: 'tickN-1' },
      payload: { conversationId: 5, page: { results: [{ id: 1, created_at: 'a' }] }, next: 'stale-cursor' },
    })
    expect(s.messages.map((m) => m.id)).toEqual([2])
    expect(s.nextOlder).toBeNull()
  })

  it('sendMessage.fulfilled ajoute le message au fil actif', () => {
    let s = reducer(init, setActiveConversation(3))
    s = reducer(s, {
      type: sendMessage.fulfilled.type,
      payload: { id: 10, conversation: 3, body: 'hello', created_at: 'z' },
    })
    expect(s.messages.map((m) => m.id)).toContain(10)
  })

  it('editMessage / deleteMessage mutent le fil', () => {
    let s = reducer(init, setActiveConversation(1))
    s = reducer(s, { type: sendMessage.fulfilled.type, payload: { id: 1, conversation: 1, body: 'a' } })
    s = reducer(s, { type: editMessage.fulfilled.type, payload: { id: 1, body: 'modifié' } })
    expect(s.messages[0].body).toBe('modifié')
    s = reducer(s, { type: deleteMessage.fulfilled.type, payload: 1 })
    expect(s.messages).toHaveLength(0)
  })

  it('clearConversationUnread remet le compteur d’une conversation à zéro', () => {
    let s = reducer(init, {
      type: fetchConversations.fulfilled.type,
      payload: [{ id: 1, unread_count: 5 }],
    })
    s = reducer(s, clearConversationUnread(1))
    expect(s.conversations[0].unread_count).toBe(0)
    expect(s.unreadTotal).toBe(0)
  })

  it('upsertConversation insère/maj une conversation', () => {
    let s = reducer(init, upsertConversation({ id: 42, unread_count: 1 }))
    expect(s.conversations).toHaveLength(1)
    s = reducer(s, upsertConversation({ id: 42, name: 'Canal' }))
    expect(s.conversations[0].name).toBe('Canal')
  })

  it('toggleReaction bascule la réaction du message actif', () => {
    let s = reducer(init, setActiveConversation(1))
    s = reducer(s, { type: sendMessage.fulfilled.type, payload: { id: 1, conversation: 1 } })
    s = reducer(s, toggleReaction({ messageId: 1, emoji: '👍', userId: 7 }))
    expect(s.messages[0].reactions[0].count).toBe(1)
  })
})
