// S12 — Tests PURS des helpers du module Discuter.
// Run: node --test src/features/messaging/store/messagingUtils.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  sortConversations,
  upsertConversation,
  totalUnread,
  mergeOlderMessages,
  mergeNewerMessages,
  upsertMessage,
  removeMessage,
  toAsc,
  dedupeById,
  toggleReactionLocal,
} from './messagingUtils.js'

test('sortConversations : non-lues d’abord, puis dernier message le plus récent', () => {
  const list = [
    { id: 1, unread_count: 0, last_message: { created_at: '2026-06-21T10:00:00Z' } },
    { id: 2, unread_count: 3, last_message: { created_at: '2026-06-20T10:00:00Z' } },
    { id: 3, unread_count: 0, last_message: { created_at: '2026-06-21T12:00:00Z' } },
  ]
  const sorted = sortConversations(list)
  assert.equal(sorted[0].id, 2) // non-lue en tête
  assert.equal(sorted[1].id, 3) // puis la plus récente des lues
  assert.equal(sorted[2].id, 1)
})

test('upsertConversation : insère puis met à jour par id, et re-trie', () => {
  let list = []
  list = upsertConversation(list, { id: 1, unread_count: 0, updated_at: 'a' })
  assert.equal(list.length, 1)
  list = upsertConversation(list, { id: 1, unread_count: 5, updated_at: 'b' })
  assert.equal(list.length, 1)
  assert.equal(list[0].unread_count, 5)
})

test('totalUnread : somme des compteurs', () => {
  assert.equal(totalUnread([{ unread_count: 2 }, { unread_count: 3 }, {}]), 5)
  assert.equal(totalUnread([]), 0)
  assert.equal(totalUnread(null), 0)
})

test('toAsc : normalise une page DRF (newest-first) en ordre croissant', () => {
  const page = { results: [
    { id: 3, created_at: '2026-06-21T12:00:00Z' },
    { id: 1, created_at: '2026-06-21T10:00:00Z' },
    { id: 2, created_at: '2026-06-21T11:00:00Z' },
  ] }
  assert.deepEqual(toAsc(page).map((m) => m.id), [1, 2, 3])
})

test('mergeOlderMessages : préfixe les anciens sans doublon', () => {
  const existing = [
    { id: 2, created_at: '2026-06-21T11:00:00Z' },
    { id: 3, created_at: '2026-06-21T12:00:00Z' },
  ]
  const older = { results: [{ id: 1, created_at: '2026-06-21T10:00:00Z' }, { id: 2, created_at: '2026-06-21T11:00:00Z' }] }
  const merged = mergeOlderMessages(existing, older)
  assert.deepEqual(merged.map((m) => m.id), [1, 2, 3])
})

test('mergeNewerMessages : ajoute en fin, dédupe', () => {
  const existing = [{ id: 1, created_at: 'a' }]
  const merged = mergeNewerMessages(existing, [{ id: 1, created_at: 'a' }, { id: 2, created_at: 'b' }])
  assert.deepEqual(merged.map((m) => m.id), [1, 2])
})

test('upsertMessage : remplace une édition, insère un nouveau', () => {
  let msgs = [{ id: 1, body: 'a' }]
  msgs = upsertMessage(msgs, { id: 1, body: 'modifié' })
  assert.equal(msgs[0].body, 'modifié')
  msgs = upsertMessage(msgs, { id: 2, body: 'b' })
  assert.equal(msgs.length, 2)
})

test('removeMessage : retire par id', () => {
  assert.deepEqual(removeMessage([{ id: 1 }, { id: 2 }], 1).map((m) => m.id), [2])
})

test('dedupeById : fusionne la version la plus récente', () => {
  const out = dedupeById([{ id: 1, a: 1 }, { id: 1, a: 2, b: 3 }])
  assert.equal(out.length, 1)
  assert.deepEqual(out[0], { id: 1, a: 2, b: 3 })
})

test('toggleReactionLocal : ajoute puis retire la réaction de l’utilisateur', () => {
  const msg = { id: 1, reactions: [] }
  const added = toggleReactionLocal(msg, '👍', 42)
  assert.equal(added.reactions[0].count, 1)
  assert.deepEqual(added.reactions[0].user_ids, [42])
  const removed = toggleReactionLocal(added, '👍', 42)
  assert.equal(removed.reactions.length, 0)
})

test('toggleReactionLocal : un autre user incrémente le même emoji', () => {
  let msg = { id: 1, reactions: [] }
  msg = toggleReactionLocal(msg, '🔥', 1)
  msg = toggleReactionLocal(msg, '🔥', 2)
  assert.equal(msg.reactions[0].count, 2)
})
