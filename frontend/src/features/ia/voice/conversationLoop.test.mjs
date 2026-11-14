// AG12 — Tests de la machine à états du « Mode conversation » (logique pure,
// node:test). Couvre : la boucle écoute↔réponse, le barge-in, l'arrêt immédiat,
// et SURTOUT le garde-fou de sécurité (COP-F6) : AUCUNE confirmation à la voix —
// une proposition se confirme d'un doigt, rien de ce qui se dit ne la confirme.

import test from 'node:test'
import assert from 'node:assert/strict'
import * as moduleBoucle from './conversationLoop.js'

const { createConversationLoop, LOOP_STATES, PHRASE_CONFIRMER_AU_DOIGT } = moduleBoucle

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
      // Un `confirm` branché ne doit JAMAIS être appelé : la boucle n'en connaît plus.
      confirm: rec('confirm'),
      onState: rec('onState'),
    },
    names: () => calls.map((c) => c[0]),
  }
}

test('COP-F6 : le module n\'exporte plus aucun chemin de confirmation vocale', () => {
  assert.equal(moduleBoucle.isConfirmUtterance, undefined)
  assert.equal(moduleBoucle.isCancelUtterance, undefined)
  assert.equal(LOOP_STATES.AWAITING_CONFIRM, undefined)
  const loop = createConversationLoop({})
  assert.equal(loop.confirmByTap, undefined)
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

test('SÉCURITÉ : une proposition est lue, dit d\'appuyer au doigt, et ne confirme RIEN', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  loop.onTranscript('envoie le devis par whatsapp')
  loop.onAnswer({ role: 'agent', content: 'Voilà.', proposition: true, apercu: 'Envoyer le devis DEV-7 ?' })
  assert.equal(spy.names().filter((n) => n === 'confirm').length, 0)
  const parle = spy.calls.find((c) => c[0] === 'speak')
  assert.match(parle[1], /Envoyer le devis DEV-7/)
  assert.ok(parle[1].endsWith(PHRASE_CONFIRMER_AU_DOIGT))
  // La lecture finie, le micro se ré-ouvre : il ne reste jamais bloqué.
  loop.onSpeechSpoken()
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
})

test('SÉCURITÉ : « non je ne confirme pas » (et « confirmer ») n\'est qu\'une question', () => {
  for (const phrase of ['non je ne confirme pas', 'confirmer', 'valide', 'oui']) {
    const spy = makeSpyHandlers()
    const loop = createConversationLoop(spy.handlers)
    loop.start()
    loop.onSpeechEnd()
    loop.onTranscript('envoie le devis')
    loop.onAnswer({ role: 'agent', content: '', proposition: true, apercu: 'X' })
    loop.onSpeechSpoken()
    loop.onSpeechEnd()
    loop.onTranscript(phrase)
    assert.equal(spy.names().filter((n) => n === 'confirm').length, 0, phrase)
    assert.deepEqual(spy.calls.filter((c) => c[0] === 'ask').at(-1), ['ask', phrase])
    assert.equal(loop.getState(), LOOP_STATES.THINKING)
  }
})

test('une action confirmée au doigt : accusé lu puis ré-écoute', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  loop.onSpeechEnd()
  loop.onTranscript('accepte le devis')
  loop.onAnswer({ role: 'agent', content: '', proposition: true, apercu: 'Accepter ?' })
  loop.onSpeechSpoken()
  loop.onActionDone({ content: 'Devis accepté.' })
  assert.equal(loop.getState(), LOOP_STATES.SPEAKING)
  loop.onSpeechSpoken()
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
})

test('confirmée au doigt PENDANT l\'écoute : micro fermé, accusé lu, clip en cours ignoré, puis ré-écoute', () => {
  const spy = makeSpyHandlers()
  const loop = createConversationLoop(spy.handlers)
  loop.start()
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
  loop.onActionDone({ content: 'C’est fait : remise.' })
  assert.equal(loop.getState(), LOOP_STATES.SPEAKING)
  // Le micro se ferme AVANT la lecture : jamais deux captures ouvertes.
  const noms = spy.names()
  assert.ok(noms.indexOf('stopListening') !== -1 && noms.indexOf('stopListening') < noms.indexOf('speak'))
  // Le clip coupé revient transcrit : il ne pose aucune question et ne rouvre rien.
  loop.onSpeechEnd()
  loop.onTranscript('bruit capté pendant la confirmation')
  assert.equal(loop.getState(), LOOP_STATES.SPEAKING)
  assert.equal(spy.names().filter((n) => n === 'ask').length, 0)
  assert.equal(spy.names().filter((n) => n === 'startListening').length, 1)
  loop.onSpeechSpoken()
  assert.equal(loop.getState(), LOOP_STATES.LISTENING)
  assert.equal(spy.names().filter((n) => n === 'startListening').length, 2)
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
  const avant = spy.calls.length
  loop.onTranscript('confirmer')
  loop.onAnswer({ proposition: true })
  assert.equal(spy.calls.length, avant)
})
