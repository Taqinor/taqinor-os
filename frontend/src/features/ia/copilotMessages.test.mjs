// FG350 — Tests de la logique pure du Copilote in-app (node:test). Couvre la
// détection « clé API manquante » (dégradation gracieuse quand le backend
// no-op), le formatage du texte affiché, la normalisation d'erreur, et la garde
// d'envoi partagée par le bouton / Entrée / les suggestions.

import test from 'node:test'
import { exempleContrat } from '../../test/fixtures/contractSamples.js'
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
  DEMANDES_PRETES_TACHES,
  PHRASE_PLAN_PROPOSE,
  demandePreteTaches,
  estEcranTaches,
  lancerDemandePrete,
  nomEcranTaches,
  conversationLibreAbsente,
  phrasePlanPropose,
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

// TCH118 — les quatre demandes prêtes de /taches : route déterministe, carte rendue, aucun modèle.
const client = () => {
  const appels = []
  const rep = (nom, charge) => (...args) => { appels.push([nom, ...args]); return Promise.resolve({ data: charge }) }
  return {
    appels,
    proposerJournee: rep('proposerJournee', exempleContrat('taches', 'journee_proposition')),
    lirePriorites: rep('lirePriorites', exempleContrat('taches', 'priorites')),
    lirePoint: rep('lirePoint', exempleContrat('taches', 'point')),
    saisieRapide: rep('saisieRapide', exempleContrat('taches', 'saisie_apercu')),
  }
}

test('les quatre demandes prêtes sont exactement celles de textes.md §5.2', () => {
  assert.deepEqual(DEMANDES_PRETES_TACHES.map((d) => d.question),
    ['Planifie ma journée', 'Aide-moi à prioriser', 'Range ma liste', 'Où j\'en suis ?'])
  assert.deepEqual(DEMANDES_PRETES_TACHES.map((d) => d.carte), ['plan_propose', 'priorites', 'capture_apercu', 'point'])
  assert.equal(demandePreteTaches('  Où j\'en suis ?  ').carte, 'point')
  assert.equal(demandePreteTaches('Combien de leads ?'), null)
  assert.equal(estEcranTaches('/taches/aujourdhui'), true)
  assert.equal(estEcranTaches('/taches'), true)
  assert.equal(estEcranTaches('/tachesx'), false)
  assert.equal(estEcranTaches('/crm/leads'), false)
})

test('sans clé d\'IA, chaque demande prête appelle SA route et rend SA carte (aucun appel à l\'assistant)', async () => {
  const c = client()
  for (const [question, appel, carte, donnees] of [
    ['Planifie ma journée', 'proposerJournee', 'plan_propose', 'journee_proposition'],
    ['Aide-moi à prioriser', 'lirePriorites', 'priorites', 'priorites'],
    ['Où j\'en suis ?', 'lirePoint', 'point', 'point'],
    ['Range ma liste', 'saisieRapide', 'capture_apercu', 'saisie_apercu'],
  ]) {
    const msg = await lancerDemandePrete(question, { client: c, ids: [41, 42] })
    assert.equal(msg.role, 'agent', question)
    assert.equal(msg.cartes.length, 1, question)
    assert.equal(msg.cartes[0].type, 'resultat')
    assert.equal(msg.cartes[0].carte, carte)
    assert.deepEqual(msg.cartes[0].donnees, exempleContrat('taches', donnees))
    assert.equal(c.appels.at(-1)[0], appel)
  }
  assert.deepEqual(c.appels.at(-1).slice(1), [{ ids: [41, 42], apercu: true }])
  assert.equal((await lancerDemandePrete('Planifie ma journée', { client: c })).content, PHRASE_PLAN_PROPOSE)
})

test('« Range ma liste » sans tâche À trier, ou une question libre : rien n\'est appelé', async () => {
  const c = client()
  assert.equal(await lancerDemandePrete('Range ma liste', { client: c, ids: [] }), null)
  assert.equal(await lancerDemandePrete('Dis-moi bonjour', { client: c }), null)
  assert.equal(c.appels.length, 0)
})

// F3 acceptation ERR 3 — textes du panneau ouvert depuis Tâches (textes.md §5.2).
test('ERR 3 — « Planifie ma journée » : les deux phrases de §5.2, accordées, et la phrase seule sans nombre', () => {
  const proposition = exempleContrat('taches', 'journee_proposition') // objectif 5, 2 lignes
  const journee = (e) => ({ progression: { essentiel_prevues: e } })
  const fin = 'Rien ne change tant que tu ne gardes pas.'
  assert.equal(phrasePlanPropose(proposition, journee(2)),
    `Tu as gardé 2 essentielles. Pour atteindre 5, voici 2 tâches de plus, dans cet ordre. ${fin}`)
  assert.equal(phrasePlanPropose(proposition, journee(0)), `Pour atteindre 5, voici 2 tâches, dans cet ordre. ${fin}`)
  const une = { ...proposition, proposition: proposition.proposition.slice(0, 1) }
  assert.equal(phrasePlanPropose(une, journee(1)),
    `Tu as gardé 1 essentielle. Pour atteindre 5, voici 1 tâche de plus, dans cet ordre. ${fin}`)
  assert.equal(phrasePlanPropose({ ...proposition, objectif: { nb: null, mode: 'libre' } }, journee(1)), PHRASE_PLAN_PROPOSE)
  assert.equal(phrasePlanPropose(proposition, null), PHRASE_PLAN_PROPOSE)
})

test('ERR 3 — nom de l\'écran Tâches et conversation libre absente', () => {
  assert.equal(nomEcranTaches('/taches/aujourdhui'), 'Aujourd\'hui')
  assert.equal(nomEcranTaches('/taches/projets/12'), 'Projets')
  assert.equal(nomEcranTaches('/taches'), 'Tâches')
  assert.equal(conversationLibreAbsente([{ role: 'agent', content: 'Voici.' }]), false)
  assert.equal(conversationLibreAbsente([{ role: 'agent',
    content: 'L\'assistant n\'est pas disponible pour le moment (réglage du serveur). Réessaie.' }]), true)
  assert.equal(conversationLibreAbsente([{ role: 'agent', content: 'GROQ_API_KEY manquante dans le .env' }]), true)
  assert.equal(conversationLibreAbsente([{ role: 'user', content: 'GROQ_API_KEY manquante' }]), false)
})
