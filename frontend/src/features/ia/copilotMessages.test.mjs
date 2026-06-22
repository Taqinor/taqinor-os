// FG350 — Tests de la logique pure du Copilote in-app (node:test). Couvre la
// détection « clé API manquante » (dégradation gracieuse quand le backend
// no-op), le formatage du texte affiché, la normalisation d'erreur, et la garde
// d'envoi partagée par le bouton / Entrée / les suggestions.

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CONFIG_MISSING_FR,
  isConfigMissing,
  displayMessageText,
  formatAgentError,
  canSendQuestion,
} from './copilotMessages.js'

test('isConfigMissing reconnaît une réponse « clé API manquante »', () => {
  assert.ok(isConfigMissing('GROQ_API_KEY manquante dans le .env'))
  assert.ok(isConfigMissing('API key missing'))
  assert.ok(isConfigMissing('api_key absente'))
})

test('isConfigMissing rejette une réponse normale et les entrées vides', () => {
  assert.equal(isConfigMissing('Vous avez 3 produits en rupture.'), false)
  assert.equal(isConfigMissing(''), false)
  assert.equal(isConfigMissing(null), false)
  assert.equal(isConfigMissing(42), false)
})

test('displayMessageText remplace le dump technique par le libellé FR net', () => {
  const msg = { role: 'agent', content: 'Error: GROQ_API_KEY manquante (.env)' }
  assert.equal(displayMessageText(msg), CONFIG_MISSING_FR)
})

test('displayMessageText renvoie le contenu normal tel quel', () => {
  const msg = { role: 'agent', content: 'Chiffre d\'affaires : 12 000 MAD' }
  assert.equal(displayMessageText(msg), 'Chiffre d\'affaires : 12 000 MAD')
})

test('displayMessageText ne crash jamais sur un message dégénéré', () => {
  assert.equal(displayMessageText(null), '')
  assert.equal(displayMessageText({}), '')
  assert.equal(displayMessageText({ role: 'user', content: 'salut' }), 'salut')
})

test('formatAgentError gère chaîne, objet {detail} et clé manquante', () => {
  assert.equal(formatAgentError('boom'), 'Erreur : boom')
  assert.equal(formatAgentError({ detail: 'serveur indisponible' }), 'Erreur : serveur indisponible')
  assert.equal(formatAgentError('GROQ_API_KEY manquante'), CONFIG_MISSING_FR)
  assert.equal(formatAgentError(null), '')
})

test('canSendQuestion : seulement un texte non vide et hors chargement', () => {
  assert.equal(canSendQuestion('bonjour', false), true)
  assert.equal(canSendQuestion('   ', false), false)
  assert.equal(canSendQuestion('', false), false)
  assert.equal(canSendQuestion('bonjour', true), false) // requête déjà en vol
  assert.equal(canSendQuestion(null, false), false)
})
