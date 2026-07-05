// Run: node --test src/features/kb/aiWriting.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { isKeyMissing, textForAction, applyAiResult, AI_ACTIONS } from './aiWriting.js'

test('AI_ACTIONS déclare les 6 actions attendues', () => {
  const keys = AI_ACTIONS.map((a) => a.action)
  assert.deepEqual(keys, ['generer', 'reformuler', 'corriger', 'traduire_fr_ar', 'traduire_ar_fr', 'resumer'])
})

test('isKeyMissing : reconnaît un message de clé LLM manquante', () => {
  assert.equal(isKeyMissing('GROQ_API_KEY manquante dans .env'), true)
  assert.equal(isKeyMissing('api_key absente'), true)
})

test('isKeyMissing : faux pour une autre erreur ou une entrée vide', () => {
  assert.equal(isKeyMissing('Erreur serveur 500'), false)
  assert.equal(isKeyMissing(''), false)
  assert.equal(isKeyMissing(null), false)
})

test('textForAction : reformuler/corriger/traduire utilisent la sélection si non vide', () => {
  const ctx = { corps: 'Bonjour le monde', selectionStart: 8, selectionEnd: 10 }
  assert.equal(textForAction('reformuler', ctx), 'le')
  assert.equal(textForAction('corriger', ctx), 'le')
  assert.equal(textForAction('traduire_fr_ar', ctx), 'le')
})

test('textForAction : reformuler sans sélection utilise tout le corps', () => {
  const ctx = { corps: 'Bonjour le monde', selectionStart: 5, selectionEnd: 5 }
  assert.equal(textForAction('reformuler', ctx), 'Bonjour le monde')
})

test('textForAction : générer/résumer utilisent toujours tout le corps', () => {
  const ctx = { corps: 'Un long article...', selectionStart: 2, selectionEnd: 5 }
  assert.equal(textForAction('generer', ctx), 'Un long article...')
  assert.equal(textForAction('resumer', ctx), 'Un long article...')
})

test('applyAiResult : resumer préfixe un chapeau sans toucher au reste', () => {
  const next = applyAiResult('resumer', 'Résumé court.', { corps: 'Corps original.', selectionStart: 0, selectionEnd: 0 })
  assert.equal(next, 'Résumé court.\n\nCorps original.')
})

test('applyAiResult : resumer avec un résultat vide ne modifie rien', () => {
  const next = applyAiResult('resumer', '', { corps: 'Corps original.', selectionStart: 0, selectionEnd: 0 })
  assert.equal(next, 'Corps original.')
})

test('applyAiResult : reformuler remplace la sélection', () => {
  const next = applyAiResult('reformuler', 'joli monde', { corps: 'Bonjour le monde', selectionStart: 8, selectionEnd: 16 })
  assert.equal(next, 'Bonjour joli monde')
})

test('applyAiResult : reformuler sans sélection remplace tout le corps', () => {
  const next = applyAiResult('reformuler', 'Nouveau texte.', { corps: 'Ancien texte.', selectionStart: 3, selectionEnd: 3 })
  assert.equal(next, 'Nouveau texte.')
})

test('applyAiResult : generer ajoute à la suite si du contenu existe déjà', () => {
  const next = applyAiResult('generer', 'Suite générée.', { corps: 'Début existant.', selectionStart: 0, selectionEnd: 0 })
  assert.equal(next, 'Début existant.\n\nSuite générée.')
})

test('applyAiResult : generer remplace une page vierge', () => {
  const next = applyAiResult('generer', 'Contenu généré.', { corps: '', selectionStart: 0, selectionEnd: 0 })
  assert.equal(next, 'Contenu généré.')
})
