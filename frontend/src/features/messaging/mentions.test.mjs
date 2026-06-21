// Run: node --test src/features/messaging/mentions.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { activeMention, insertMention, filterMembers, extractMentions } from './mentions.js'

test('activeMention : détecte un @token en fin de saisie', () => {
  assert.deepEqual(activeMention('bonjour @sa', 11), { query: 'sa', start: 8 })
  assert.deepEqual(activeMention('@a', 2), { query: 'a', start: 0 })
})

test('activeMention : pas de token si pas d’@ ou si suivi d’un espace', () => {
  assert.equal(activeMention('bonjour sa', 10), null)
  assert.equal(activeMention('@sami ', 6), null)
  assert.equal(activeMention('email@x', 7), null) // @ collé à un mot → non précédé d'espace
})

test('insertMention : remplace le token par @label et place le curseur', () => {
  const { text, caret } = insertMention('salut @sa', 6, 2, 'Sami')
  assert.equal(text, 'salut @Sami ')
  assert.equal(caret, 12)
})

test('filterMembers : filtre insensible aux accents/casse, tronqué', () => {
  const members = [
    { id: 1, label: 'Réda', username: 'reda' },
    { id: 2, label: 'Sami', username: 'sami' },
    { id: 3, label: 'Sara', username: 'sara' },
  ]
  assert.deepEqual(filterMembers(members, 'red').map((m) => m.id), [1])
  assert.deepEqual(filterMembers(members, 'sa').map((m) => m.id), [2, 3])
  assert.equal(filterMembers(members, '', 2).length, 2)
})

test('extractMentions : retrouve les ids mentionnés par étiquette', () => {
  const members = [{ id: 1, label: 'Sami' }, { id: 2, label: 'Réda' }]
  assert.deepEqual(extractMentions('cc @Sami merci', members), [1])
  assert.deepEqual(extractMentions('@Sami et @Réda', members), [1, 2])
  assert.deepEqual(extractMentions('rien', members), [])
})
