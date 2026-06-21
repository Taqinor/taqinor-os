// Run: node --test src/features/messaging/time.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { shortTime, bubbleTime, conversationTitle, displayName } from './time.js'

const now = new Date('2026-06-21T14:00:00')

test('shortTime : à l’instant / minutes / heure du jour', () => {
  assert.equal(shortTime(new Date('2026-06-21T13:59:40').toISOString(), now), "à l'instant")
  assert.equal(shortTime('2026-06-21T13:30:00', now), '30 min')
  assert.equal(shortTime('2026-06-21T09:05:00', now), '09:05')
})

test('shortTime : hier, jours, date', () => {
  assert.equal(shortTime('2026-06-20T10:00:00', now), 'Hier')
  assert.equal(shortTime('2026-06-18T10:00:00', now), '3 j')
  assert.equal(shortTime('2026-05-01T10:00:00', now), '01/05')
})

test('shortTime : entrée vide / invalide → chaîne vide', () => {
  assert.equal(shortTime('', now), '')
  assert.equal(shortTime('pas-une-date', now), '')
})

test('bubbleTime : HH:MM', () => {
  assert.equal(bubbleTime('2026-06-21T08:07:00'), '08:07')
  assert.equal(bubbleTime(''), '')
})

test('displayName : ordre de repli', () => {
  assert.equal(displayName({ full_name: 'A B' }), 'A B')
  assert.equal(displayName({ first_name: 'A', last_name: 'B' }), 'A B')
  assert.equal(displayName({ username: 'ab' }), 'ab')
  assert.equal(displayName(null), '')
})

test('conversationTitle : canal vs DM', () => {
  assert.equal(conversationTitle({ kind: 'channel', name: 'Général' }), 'Général')
  assert.equal(
    conversationTitle(
      { kind: 'dm', members: [{ id: 1, username: 'moi' }, { id: 2, username: 'autre' }] },
      1,
    ),
    'autre',
  )
})
