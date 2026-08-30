// N3 (audit apercu-issues) — un nombre de panneaux TAPÉ À LA MAIN était
// RE-FORCÉ par la frappe sur les factures : `syncBillEstimator` (déclenché à
// chaque frappe hiver/été, y compris via le collage nettoyé VX237) resynchronisait
// le nombre de panneaux SANS jamais consulter le garde-fou « nbPanneaux touché »
// déjà posé par la frappe directe — alors que le pré-remplissage depuis le lead
// et depuis le profil site, EUX, le respectaient déjà.
//
// QJR108 — CE FICHIER A CESSÉ DE LIRE LE SOURCE. Il épinglait le correctif par
// des expressions régulières sur `DevisGenerator.jsx` (position de la garde,
// forme du `dispatchSizing`, absence de `estimerPanneaux` dans le bloc) : des
// épingles qui rougissent au premier reformatage et qui restent VERTES si la
// garde est déplacée dans une branche morte. Depuis QJR87/QJR99 le garde-fou
// n'est plus un `useRef` caché dans le composant mais un ÉTAT du reducer PUR
// (`features/ventes/quote/sizingReducer.js`) — donc directement exécutable. Ce
// fichier rejoue maintenant LE SCÉNARIO N3 sur la machine à états, transition
// par transition : le bug d'origine le fait rougir, un reformatage non.
//
// Run : node --test src/pages/ventes/DevisGeneratorNbPanneauxTouched.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  sizingReducer, ETAT_INITIAL, DRAPEAUX_TOUCHE, drapeauxPoses,
} from '../../features/ventes/quote/sizingReducer.js'

/** Rejoue une suite d'actions depuis l'état initial (ou depuis `depart`). */
const rejouer = (actions, depart = ETAT_INITIAL) =>
  actions.reduce((etat, action) => sizingReducer(etat, action), depart)

/** La frappe directe du vendeur dans « Nombre de panneaux ». */
const TAPE_14_PANNEAUX = { type: 'SAISI', champ: 'nbPanneaux', valeur: '14' }

/**
 * Ce que `syncBillEstimator` dispatche à CHAQUE frappe sur une facture : la
 * transition du profil site, avec le balayage LOCAL déjà résolu par l'appelant
 * (le reducer ne va jamais chercher un chiffre lui-même).
 */
const frappeFacture = (mode, sizingLocal = null) => ({
  type: 'PROFIL_SITE_APPLIQUE',
  profil: { type_installation: mode, facture_hiver: 2400 },
  sizingLocal,
})

// ── LE GARDE-FOU EST POSÉ PAR LA FRAPPE DIRECTE ─────────────────────────────

test('la frappe dans « Nombre de panneaux » pose le garde-fou et garde la valeur EXACTE', () => {
  const etat = sizingReducer(ETAT_INITIAL, TAPE_14_PANNEAUX)
  assert.equal(etat.touche.nbPanneaux, true)
  assert.equal(etat.nbPanneaux, '14', 'la frappe ne doit jamais être « snappée »')
  assert.equal(etat.kwcCible, '9.94', 'la cible kWc suit la frappe')
  assert.equal(etat.sizingInfo, null, 'le « palier retenu » du balayage local ne décrit plus la taille')
})

test('la frappe dans « Puissance cible (kWc) » pose le MÊME garde-fou (champ bidirectionnel)', () => {
  const etat = sizingReducer(ETAT_INITIAL, { type: 'SAISI', champ: 'kwcCible', valeur: '7' })
  assert.equal(etat.touche.nbPanneaux, true)
  assert.equal(etat.kwcCible, '7')
  assert.ok(Number(etat.nbPanneaux) > 0, 'la cible lisible remplit le compte de panneaux')
})

test('une cible kWc encore ILLISIBLE ne pose aucun garde-fou (le vendeur tape « 7. »)', () => {
  const etat = sizingReducer(ETAT_INITIAL, { type: 'SAISI', champ: 'kwcCible', valeur: '' })
  assert.equal(etat.touche.nbPanneaux, false)
  assert.equal(etat.nbPanneaux, '')
})

// ── LE SCÉNARIO N3 LUI-MÊME ─────────────────────────────────────────────────

test('N3 — taper une facture APRÈS avoir tapé les panneaux ne re-force plus la taille (industriel)', () => {
  const etat = rejouer([
    TAPE_14_PANNEAUX,
    // Le balayage local proposerait 22 panneaux : c'est exactement ce qui
    // écrasait la frappe avant le correctif.
    frappeFacture('industriel', { nbPanneaux: 22, kwcOptimal: 15.6 }),
  ])
  assert.equal(etat.nbPanneaux, '14', 'régression N3 : la facture a re-forcé le nombre de panneaux')
  assert.equal(etat.touche.nbPanneaux, true, 'le garde-fou doit rester posé')
  assert.equal(etat.sizingInfo, null, 'aucun « palier retenu » ne doit justifier une taille qui n’a pas été retenue')
})

test('N3 — sans frappe préalable, la MÊME facture reprend bien la main (le garde-fou ne gèle pas l’écran)', () => {
  const etat = sizingReducer(
    ETAT_INITIAL, frappeFacture('industriel', { nbPanneaux: 22, kwcOptimal: 15.6 }))
  assert.equal(etat.nbPanneaux, '22')
  assert.equal(etat.touche.nbPanneaux, false, 'un pré-remplissage n’est pas une saisie')
  assert.deepEqual(etat.sizingInfo, { nbPanneaux: 22, kwcOptimal: 15.6 })
})

test('N3 — la TAILLE SOUHAITÉE d’un lead n’écrase pas non plus une frappe', () => {
  // OBSERVATION FAITE EN CONVERTISSANT (QJR108, hors scope de cette tâche —
  // une tâche corrige OU déplace, jamais les deux) : la reprise par la
  // FACTURE de `LEAD_APPLIQUE` (étape 8) ne consulte PAS `touche.nbPanneaux`
  // sur les marchés à balayage local, là où `PROFIL_SITE_APPLIQUE` — le
  // chemin de `syncBillEstimator`, donc le site du bug N3 — le consulte. Ce
  // test n'épingle donc QUE ce que le garde-fou couvre réellement
  // aujourd'hui : la taille souhaitée (étape 7).
  const etat = rejouer([
    TAPE_14_PANNEAUX,
    { type: 'LEAD_APPLIQUE',
      lead: { type_installation: 'industriel', taille_souhaitee_kwc: 30 } },
  ])
  assert.equal(etat.nbPanneaux, '14',
    'la taille souhaitée du lead ne doit pas écraser une frappe')
  assert.equal(etat.touche.nbPanneaux, true)
})

// ── U3-900 — AUCUNE TAILLE DEVINÉE À L’ÉCRAN EN RÉSIDENTIEL ─────────────────

test('U3-900 — en résidentiel une facture n’invente AUCUN nombre de panneaux : elle ATTEND le moteur serveur', () => {
  const etat = sizingReducer(ETAT_INITIAL, frappeFacture('residentiel'))
  assert.equal(etat.nbPanneaux, '', 'aucune taille ne doit être devinée depuis la facture à l’écran')
  assert.equal(etat.attenteMoteur, true)
  assert.equal(etat.sizingInfo, null)
  assert.equal(etat.motifMoteur, null)
})

test('U3-900 — un balayage local NON CHIFFRABLE ne pose rien plutôt que de supposer', () => {
  const etat = sizingReducer(ETAT_INITIAL, frappeFacture('industriel', null))
  assert.equal(etat.nbPanneaux, '', 'jamais un chiffre supposé')
  assert.equal(etat.sizingInfo, null)
})

// ── INVARIANT 1 — LA RÉPONSE DU MOTEUR N’ÉCRASE JAMAIS UNE FRAPPE ───────────

test('N3 — SAISI puis MOTEUR_A_REPONDU : la valeur TAPÉE reste, l’attente se referme', () => {
  const etat = rejouer([
    frappeFacture('residentiel'),          // ouvre l'attente du moteur
    TAPE_14_PANNEAUX,                      // le vendeur tape pendant l'aller-retour
    { type: 'MOTEUR_A_REPONDU',
      recommandation: { panneaux: 20, kwc: 14.2, panel_watt: 710 } },
  ])
  assert.equal(etat.nbPanneaux, '14', 'la recommandation serveur a écrasé une frappe')
  assert.equal(etat.kwcCible, '9.94', 'la cible affichée doit suivre la frappe, pas la réponse')
  assert.equal(etat.attenteMoteur, false, 'la réponse doit être CONSOMMÉE, pas laissée en attente')
  assert.equal(etat.touche.nbPanneaux, true)
})

test('N3 — SAISI puis MOTEUR_A_REFUSE : aucun motif de refus n’est épinglé sur une frappe', () => {
  const etat = rejouer([
    frappeFacture('residentiel'),
    TAPE_14_PANNEAUX,
    { type: 'MOTEUR_A_REFUSE', motif: 'Ville du lead absente.' },
  ])
  assert.equal(etat.motifMoteur, null,
    'refuser une taille que le vendeur a lui-même tapée n’a aucun sens')
  assert.equal(etat.attenteMoteur, false)
  assert.equal(etat.nbPanneaux, '14')
})

test('sans frappe, la recommandation du moteur est appliquée telle quelle', () => {
  const etat = rejouer([
    frappeFacture('residentiel'),
    { type: 'MOTEUR_A_REPONDU',
      recommandation: { panneaux: 20, kwc: 14.2, panel_watt: 710 } },
  ])
  assert.equal(etat.nbPanneaux, '20')
  assert.equal(etat.kwcCible, '14.2')
  assert.equal(etat.panelW, '710')
  assert.equal(etat.touche.nbPanneaux, false)
})

// ── CE QUE LE GARDE-FOU NE PEUT PAS BLOQUER, PAR CONSTRUCTION ───────────────

test('les FACTURES ne vivent pas dans la machine de dimensionnement — aucun garde-fou ne peut les geler', () => {
  // La contrepartie de N3 : `setMonthly` restait appelé INCONDITIONNELLEMENT,
  // hors du bloc protégé. L'épingle regex vérifiait sa POSITION dans le
  // source ; la vraie garantie est structurelle — le reducer n'a aucune clé
  // de facture, il ne peut donc rien empêcher de s'y mettre à jour.
  const cles = Object.keys(ETAT_INITIAL)
  for (const interdite of ['monthly', 'factures', 'fHiver', 'fEte']) {
    assert.equal(cles.includes(interdite), false,
      `« ${interdite} » n’a rien à faire dans la machine de dimensionnement`)
  }
  assert.deepEqual(DRAPEAUX_TOUCHE.filter(d => /facture|monthly/i.test(d)), [])
})

test('le garde-fou « nbPanneaux » est ÉNUMÉRABLE — c’est ce qu’un useRef interdisait', () => {
  assert.deepEqual(drapeauxPoses(ETAT_INITIAL), [])
  assert.deepEqual(drapeauxPoses(sizingReducer(ETAT_INITIAL, TAPE_14_PANNEAUX)),
                   ['nbPanneaux'])
})
