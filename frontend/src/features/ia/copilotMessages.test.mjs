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
  construireContexte,
  routeNormalisee,
  ditUnePanne,
  marquerNote,
  NOTE_NEGATIVE,
  NOTE_POSITIVE,
  COMMENTAIRE_MAX,
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

// AIC8 — réduction d'état « noté » (pure) : note + commentaire borné + merci.
test('marquerNote pose la note, borne le commentaire et passe à « merci »', () => {
  const msg = { role: 'agent', content: 'ok', evenement_id: 9001 }
  const note = marquerNote(msg, NOTE_NEGATIVE, `  ${'x'.repeat(250)}  `)
  assert.equal(note.note, -1)
  assert.equal(note.commentaire.length, COMMENTAIRE_MAX)
  assert.equal(note.noteEnvoyee, true)
  assert.equal(note.evenement_id, 9001)
  assert.equal(msg.note, undefined) // jamais de mutation
  // Idempotent : re-noter remplace la note ; commentaire vide => null.
  const renote = marquerNote(note, NOTE_POSITIVE, '   ')
  assert.equal(renote.note, 1)
  assert.equal(renote.commentaire, null)
})

// COP-F5 — le contexte est lu AU MOMENT de l'envoi, depuis la route courante.
test('construireContexte : route normalisée, fiche et devis lus dans la route', () => {
  assert.deepEqual(construireContexte({ chemin: '/crm/leads/123/' }), {
    ecran: '/crm/leads/123', lead_id: 123, devis_id: null, touche_id: null, diagnostic: null,
  })
  assert.deepEqual(construireContexte({ chemin: '/ventes/devis/45/design?x=1#haut' }), {
    ecran: '/ventes/devis/45/design', lead_id: null, devis_id: 45, touche_id: null, diagnostic: null,
  })
  assert.equal(construireContexte({ chemin: '/crm/relances' }).lead_id, null)
  assert.equal(construireContexte({ chemin: '/crm/leads/abc' }).lead_id, null)
})

test('construireContexte : le foyer et le tampon sont posés par l\'écran, l\'événement ne vaut que pour une question', () => {
  const ctx = construireContexte({
    chemin: '/crm/relances', foyer: 412, diagnostic: { requetes: [] },
    detail: { ecran: '/crm/leads/12', lead_id: 12 },
  })
  assert.deepEqual(ctx, {
    ecran: '/crm/leads/12', lead_id: 12, devis_id: null, touche_id: 412, diagnostic: { requetes: [] },
  })
  // Sans événement : la route courante, jamais l'ancien lead.
  assert.equal(construireContexte({ chemin: '/stock/produits' }).lead_id, null)
  assert.equal(construireContexte({ chemin: '/x', foyer: 'pas un id' }).touche_id, null)
  assert.equal(routeNormalisee(undefined), '/')
  assert.equal(routeNormalisee('/a'.repeat(300)).length, 255)
})

test('ditUnePanne reconnaît une panne dite en français courant, pas une question métier', () => {
  for (const phrase of ['ça ne marche pas', 'Le bouton Fait ne fonctionne pas', 'j\'ai une erreur', 'bug sur le devis',
    'c\'est bloqué', 'rien ne se passe quand je clique', 'la page a planté']) {
    assert.equal(ditUnePanne(phrase), true, phrase)
  }
  for (const phrase of ['Combien de leads aujourd\'hui ?', 'Prépare ma prochaine relance', '', null]) {
    assert.equal(ditUnePanne(phrase), false, String(phrase))
  }
})
