// AG12 — Tests de la machine à états du « Mode conversation » (logique pure,
// node:test). Couvre : la boucle écoute↔réponse, le barge-in, l'arrêt immédiat,
// et SURTOUT le garde-fou de sécurité : la boucle NE confirme JAMAIS
// automatiquement une action sensible — elle attend un « confirmer » explicite.

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createConversationLoop,
  LOOP_STATES,
  normalizeUtterance,
  isConfirmUtterance,
  isCancelUtterance,
} from './conversationLoop.js'

// Petit harnais : enregistre tous les appels de handlers.
function makeSpyHandlers() {
  const calls = []
  const rec = (name) => (...args) => calls.push([name, ...args])
  return {
    calls,
    handlers: {
      startListening: rec('startListening'),
      stopListening: rec('stopListening'),
      ask: rec('ask'),
      speak: rec('speak'),
      stopSpeaking: rec('stopSpeaking'),
      confirm: rec('confirm'),
      onState: rec('onState'),
    },
    names: () => calls.map((c) => c[0]),
  }
}

test('normalizeUtterance retire accents/casse/espaces', () => {
  assert.equal(normalizeUtterance('  Confirmér  '), 'confirmer')
  assert.equal(normalizeUtterance('OUI   Confirme'), 'oui confirme')
  assert.equal(normalizeUtterance(null), '')
})

test('isConfirmUtterance reconnaît « confirmer » et variantes, rejette le reste', () => {
  assert.ok(isConfirmUtterance('confirmer'))
  assert.ok(isConfirmUtterance('Confirmé'))
  assert.ok(isConfirmUtterance('oui confirme'))
  assert.ok(isConfirmUtterance('valider'))
  assert.equal(isConfirmUtterance('quel est le stock ?'), false)
  assert.equal(isConfirmUtterance('oui'), false) // « oui » seul ne confirme PAS
  assert.equal(isConfirmUtterance(''), false)
})

test('isCancelUtterance reconnaît « annuler » / « non »', () => {
  assert.ok(isCancelUtterance('annuler'))
  assert.ok(isCancelUtterance('non'))
  assert.equal(isCancelUtterance('confirmer'), false)
})

test('start() ouvre le micro et passe en LISTENING', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
  assert.ok(spy.names().includes('startListening'))
  assert.ok(loop.isRunning())
})

test('tour normal : parole → transcription → question → réponse lue → ré-écoute', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  assert.equal(loop.getState(), LOOP_STATES.TRANSCRIBING)
  loop.onTranscript('combien de clients ?')
  assert.equal(loop.getState(), LOOP_STATES.THINKING)
  assert.deepEqual(spy.calls.find((c) => c[0] === 'ask'), ['ask', 'combien de clients ?'])
  // L'agent répond (texte simple) → lecture vocale.
  loop.onAnswer({ role: 'agent', content: 'Vous avez 12 clients.' })
  assert.equal(loop.getState(), LOOP_STATES.SPEAKING)
  assert.deepEqual(spy.calls.find((c) => c[0] === 'speak'), ['speak', 'Vous avez 12 clients.'])
  // Fin de lecture → on ré-ouvre le micro.
  loop.onSpeechSpoken()
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
})

test('transcript vide ne pose PAS de question et ré-ouvre le micro', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  loop.onTranscript('   ')
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
  assert.equal(spy.names().filter((n) => n === 'ask').length, 0)
})

test('SÉCURITÉ : une proposition NE déclenche JAMAIS confirm() automatiquement', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  loop.onTranscript('envoie le devis par whatsapp')
  // L'agent répond par une PROPOSITION (action sensible).
  loop.onAnswer({
    role: 'agent', kind: 'proposal',
    human_preview: 'Envoyer le devis DEV-7 par WhatsApp ?',
    confirm_token: 'tok-9',
  })
  // → AWAITING_CONFIRM, l'aperçu est lu, mais AUCUN confirm() émis.
  assert.equal(loop.getState(), LOOP_STATES.AWAITING_CONFIRM)
  assert.equal(spy.names().filter((n) => n === 'confirm').length, 0)
  const speakCall = spy.calls.find((c) => c[0] === 'speak')
  assert.match(speakCall[1], /confirmer/i)
})

test('SÉCURITÉ : un énoncé NON reconnu pendant l\'attente ne confirme pas (nouvelle question)', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  loop.onTranscript('envoie le devis')
  loop.onAnswer({ role: 'agent', kind: 'proposal', human_preview: 'X', confirm_token: 'tok-9' })
  assert.equal(loop.getState(), LOOP_STATES.AWAITING_CONFIRM)
  // L'utilisateur dit autre chose → traité comme une question, JAMAIS confirmé.
  loop.onSpeechEnd?.() // pas requis mais on reste cohérent
  loop.onTranscript('quel est le total ?')
  assert.equal(spy.names().filter((n) => n === 'confirm').length, 0)
  assert.equal(loop.getState(), LOOP_STATES.THINKING)
  assert.ok(spy.calls.some((c) => c[0] === 'ask' && c[1] === 'quel est le total ?'))
})

test('confirmation : « confirmer » explicite exécute confirm() avec le token', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  loop.onTranscript('envoie le devis')
  loop.onAnswer({ role: 'agent', kind: 'proposal', human_preview: 'X', confirm_token: 'tok-9' })
  loop.onTranscript('confirmer')
  assert.deepEqual(spy.calls.find((c) => c[0] === 'confirm'), ['confirm', 'tok-9'])
  assert.equal(loop.getState(), LOOP_STATES.THINKING)
})

test('confirmByTap exécute uniquement en AWAITING_CONFIRM', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  // Pas en attente → le tap ne fait rien.
  loop.confirmByTap()
  assert.equal(spy.names().filter((n) => n === 'confirm').length, 0)
  // En attente → le tap confirme.
  loop.onSpeechEnd()
  loop.onTranscript('envoie le devis')
  loop.onAnswer({ role: 'agent', kind: 'proposal', human_preview: 'X', confirm_token: 'tok-1' })
  loop.confirmByTap()
  assert.deepEqual(spy.calls.find((c) => c[0] === 'confirm'), ['confirm', 'tok-1'])
})

test('« annuler » pendant l\'attente écarte sans confirmer et ré-écoute', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  loop.onTranscript('envoie le devis')
  loop.onAnswer({ role: 'agent', kind: 'proposal', human_preview: 'X', confirm_token: 'tok-9' })
  loop.onTranscript('annuler')
  assert.equal(spy.names().filter((n) => n === 'confirm').length, 0)
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
})

test('barge-in : parler pendant la lecture coupe la synthèse et ré-ouvre le micro', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  loop.onTranscript('bonjour')
  loop.onAnswer({ role: 'agent', content: 'Bonjour, comment puis-je aider ?' })
  assert.equal(loop.getState(), LOOP_STATES.SPEAKING)
  loop.onBargeIn()
  assert.ok(spy.names().includes('stopSpeaking'))
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
})

test('stop() arrête tout immédiatement et revient à IDLE', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.stop()
  assert.equal(loop.getState(), LOOP_STATES.IDLE)
  assert.equal(loop.isRunning(), false)
  assert.ok(spy.names().includes('stopListening'))
  assert.ok(spy.names().includes('stopSpeaking'))
  // Après stop, plus aucune transition ne réagit.
  const before = spy.calls.length
  loop.onTranscript('confirmer')
  loop.onAnswer({ kind: 'proposal', confirm_token: 't' })
  assert.equal(spy.calls.length, before)
})
