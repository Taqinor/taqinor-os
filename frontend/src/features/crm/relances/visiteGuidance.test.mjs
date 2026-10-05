import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  phaseVisite, PHASE_GUIDANCE, SIGNAUX_ACHAT, REGLE_OBJECTION, visitePassee,
  REGLE_VRAI_CLIENT, guidanceVisite,
} from './visiteGuidance.js'

// VISCAD — table ordre -> jour du gabarit apres_devis par défaut
// (`apps/parametres/models_relance.py CADENCE_APRES_DEVIS_DEFAUT`) :
// ordre 1 -> J1, ordre 2-5 -> J2/J3/J4/J6, ordre 6-10 -> J7/J9/J11/J13/J14.

test('phaseVisite : ordre 1 (J1) -> phase 1 (pas encore)', () => {
  assert.equal(phaseVisite({ ordre: 1 }), 1)
})

test('phaseVisite : ordre 2 à 5 (J2-J6) -> phase 2 (semez la visite)', () => {
  assert.equal(phaseVisite({ ordre: 2 }), 2)
  assert.equal(phaseVisite({ ordre: 3 }), 2)
  assert.equal(phaseVisite({ ordre: 4 }), 2)
  assert.equal(phaseVisite({ ordre: 5 }), 2)
})

test('phaseVisite : ordre 6 et au-delà (J7+) -> phase 3 (choix alternatif)', () => {
  assert.equal(phaseVisite({ ordre: 6 }), 3)
  assert.equal(phaseVisite({ ordre: 7 }), 3)
  assert.equal(phaseVisite({ ordre: 10 }), 3)
})

test('phaseVisite : ordre hors gabarit par défaut (cadence personnalisée) -> repli ordinal', () => {
  // 11e barreau : au-delà de la table par défaut (max ordre 10) — reste
  // phase 3 (repli ordinal, jamais un jour halluciné).
  assert.equal(phaseVisite({ ordre: 11 }), 3)
})

test('phaseVisite : étape absente/ordre absent -> phase 1 (jamais une erreur)', () => {
  assert.equal(phaseVisite(null), 1)
  assert.equal(phaseVisite({}), 1)
})

test('PHASE_GUIDANCE : les trois phases portent les textes fondateur exacts', () => {
  assert.equal(PHASE_GUIDANCE[1].texte, 'Pas encore — laissez le devis vivre. Répondez, écoutez.')
  assert.match(PHASE_GUIDANCE[2].script, /orientation du toit et la charpente/)
  assert.match(PHASE_GUIDANCE[3].script, /créneau mardi matin ou jeudi après-midi/)
})

test('SIGNAUX_ACHAT : la checklist porte les 6 signaux', () => {
  assert.equal(SIGNAUX_ACHAT.length, 6)
})

test('REGLE_OBJECTION : la règle « jamais un débat au téléphone » est présente', () => {
  assert.match(REGLE_OBJECTION, /jamais par un débat au téléphone/)
})

test('visitePassee : terminee/validee sont passées, le reste ne l\'est pas', () => {
  assert.equal(visitePassee({ statut: 'terminee' }), true)
  assert.equal(visitePassee({ statut: 'validee' }), true)
  assert.equal(visitePassee({ statut: 'brouillon' }), false)
  assert.equal(visitePassee({ statut: 'en_cours' }), false)
  assert.equal(visitePassee({ statut: 'a_refaire' }), false)
  assert.equal(visitePassee(null), false)
})

// AGR532 — consignes agricoles AJOUTÉES à côté des textes du fondateur.

test('AGR532 — les textes du fondateur restent identiques octet pour octet', () => {
  // Copie « or » volontairement ÉCRITE AUTREMENT que dans visiteGuidance.js
  // (une ligne par clé, pas de recopie ligne à ligne : garde ACAL345).
  const OR_SCRIPT_2 = "Le chiffrage est basé sur vos factures et photos ; quand le technicien passe, "
    + "il confirme juste l'orientation du toit et la charpente pour verrouiller le prix, pas pour le changer."
  const OR_SCRIPT_3 = 'On a un créneau mardi matin ou jeudi après-midi — lequel vous arrange ?'
  const OR_JAMAIS = 'jamais « voulez-vous qu\'on passe ? »'
  assert.deepEqual(PHASE_GUIDANCE[1], { titre: 'Pas encore', texte: 'Pas encore — laissez le devis vivre. Répondez, écoutez.', script: null })
  assert.deepEqual(PHASE_GUIDANCE[2], { titre: 'Semez la visite', texte: 'Semez la visite.', script: OR_SCRIPT_2 })
  assert.deepEqual(PHASE_GUIDANCE[3], {
    titre: 'Proposez activement, en choix alternatif', texte: 'Proposez activement, en choix alternatif.',
    script: OR_SCRIPT_3, jamais: OR_JAMAIS,
  })
  assert.deepEqual(Object.keys(PHASE_GUIDANCE), ['1', '2', '3'])
  assert.deepEqual(SIGNAUX_ACHAT, [
    "Questions sur le délai d'installation", 'Questions sur les garanties',
    'Questions sur le financement', 'Questions sur SA toiture / sa maison',
    'Demande de références ou de témoignages',
    'Toute question « comment ça se passe quand… » (installation, entretien, panne)',
  ])
  assert.equal(REGLE_VRAI_CLIENT,
    'La visite se fait avec le client lui-même — jamais le gardien ni la bonne. '
    + 'Confirmez sa présence au créneau choisi.')
})

test('AGR532 — guidanceVisite("agricole") : ni toit, ni charpente, ni bonne', () => {
  const g = guidanceVisite('agricole')
  const texte = JSON.stringify(g).toLowerCase()
  for (const mot of ['toit', 'charpente', 'bonne']) {
    assert.ok(!texte.includes(mot), mot)
  }
  assert.match(g.phases[2].script, /niveau et le débit de l'eau/)
  assert.match(g.regleVraiClient, /jamais le gardien ni l'ouvrier/)
  // Aucun chiffre dans les TEXTES (les clés de phase 1/2/3 n'en sont pas).
  const textes = [
    ...Object.values(g.phases).flatMap((p) => [p.titre, p.texte, p.script, p.jamais]),
    ...g.signaux, g.regleObjection, g.regleVraiClient,
  ].filter(Boolean).join(' ')
  assert.ok(!/\d/.test(textes))
})

test('AGR532 — tout autre segment rend exactement les textes actuels', () => {
  for (const segment of ['residentiel', 'commercial', 'industriel', '', undefined, null]) {
    const g = guidanceVisite(segment)
    assert.equal(g.phases, PHASE_GUIDANCE)
    assert.equal(g.signaux, SIGNAUX_ACHAT)
    assert.equal(g.regleObjection, REGLE_OBJECTION)
    assert.equal(g.regleVraiClient, REGLE_VRAI_CLIENT)
  }
})
