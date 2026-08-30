// FOUNDER 26/08/2026 — « ça ne recalcule pas le meilleur choix (nombre de
// panneaux) quand on change [la facture] — il devrait y avoir un BOUTON qui
// recalcule ». Causes RÉELLES d'alors :
//   1. En ÉDITION (?edit=ID), `nbPanneaux` est reposé depuis les lignes du
//      brouillon, mais `fHiver`/`fEte` ne le sont JAMAIS — retaper une facture
//      part d'un champ vide, pas de la facture d'origine.
//   2. « Auto-remplir » ne fait que RECOMPOSER au `nbPanneaux` COURANT : il ne
//      relit jamais la facture pour redériver ce compte.
//   3. Le garde-fou « nbPanneaux touché » (N3), une fois posé n'importe où
//      dans la session, empêche toute frappe sur la facture de recalculer.
// Correctif : un bouton EXPLICITE « Recalculer le dimensionnement » qui
// déverrouille temporairement le garde-fou, pose la taille RETENUE (la
// recommandation SERVEUR en résidentiel, le balayage local ailleurs — résolue
// par l'appelant, jamais par le reducer), relance la composition, puis
// RESTAURE le garde-fou à SON ÉTAT D'AVANT LE CLIC.
//
// QJR108 — CE FICHIER A CESSÉ DE LIRE LE SOURCE. Il faisait de l'archéologie
// par expression régulière sur `DevisGenerator.jsx` : « `setFHiver(` n'apparaît
// pas dans ce bloc », « `PriorTouched` n'apparaît plus », « le texte
// `if (estFait(mSans) && estFait(mAvec))` est présent », et — le pire — une
// fonction `dedup()` RÉÉCRITE DANS LE TEST pour « prouver le comportement »
// d'une fonction de production qu'il ne pouvait pas appeler : elle prouvait le
// comportement de sa propre copie.
//
// LE CORRECTIF LUI-MÊME EST DEVENU UNE TRANSITION. `RECALCUL_DEMANDE`
// (sizingReducer, invariant 3) fait EN UNE FOIS ce que l'écran faisait en
// trois instructions — donc avec une FENÊTRE dans laquelle une frappe pouvait
// s'engouffrer (régression F1). Cette transition est pure : elle est ici
// EXÉCUTÉE, avec le lecteur qui l'accompagne
// (`toucheNbPanneauxPourComposition`) et le sélecteur `deuxValeursDim`,
// devenu importable en QJR108.
//
// CE QUI RESTE HORS DE PORTÉE D'UN TEST PUR, et n'est donc PAS revendiqué ici :
// tout ce qui exige un rendu React — l'absence de `setFHiver` dans l'effet
// `?edit=`, l'appel SYNCHRONE `Promise.resolve(handleAutoFill()).catch(…)` de
// l'effet de composition (F2), le bouton lui-même et sa désactivation, le
// garde d'affichage du bloc « Recommandé sans/avec batterie » (F4). Ces
// comportements ont déjà leur spec RTL —
// `DevisGeneratorRecalculerDimensionnementGuard.test.jsx` — qui, elle, monte
// vraiment le composant : c'est elle, et non les regex retirées ici, qui a
// intercepté F1.
//
// Run : node --test src/pages/ventes/DevisGeneratorRecalculerDimensionnement.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  sizingReducer, ETAT_INITIAL, toucheNbPanneauxPourComposition,
  SCENARIO_LES_DEUX,
} from '../../features/ventes/quote/sizingReducer.js'
import { deuxValeursDim } from '../../features/ventes/quote/paireDimensionnement.js'

const rejouer = (actions, depart = ETAT_INITIAL) =>
  actions.reduce((etat, action) => sizingReducer(etat, action), depart)

const TAPE = (valeur) => ({ type: 'SAISI', champ: 'nbPanneaux', valeur })
const RETENU = { nbPanneaux: 18, kwcOptimal: 12.78 }
const RECALCUL = { type: 'RECALCUL_DEMANDE', retenu: RETENU }

// ── CE QUE LE BOUTON POSE ───────────────────────────────────────────────────

test('le recalcul pose la taille RETENUE et sa cible kWc', () => {
  const etat = sizingReducer(ETAT_INITIAL, RECALCUL)
  assert.equal(etat.nbPanneaux, '18')
  assert.equal(etat.kwcCible, '12.78')
})

test('le recalcul referme l’attente moteur et efface un refus précédent', () => {
  const avant = rejouer([
    { type: 'PROFIL_SITE_APPLIQUE',
      profil: { type_installation: 'residentiel', facture_hiver: 3000 } },
    { type: 'MOTEUR_A_REFUSE', motif: 'Ville du lead absente.' },
  ])
  assert.equal(avant.motifMoteur, 'Ville du lead absente.')
  const etat = sizingReducer(avant, RECALCUL)
  assert.equal(etat.attenteMoteur, false)
  assert.equal(etat.motifMoteur, null)
})

test('le reducer NE DÉRIVE RIEN de la facture : il pose ce que l’appelant a résolu', () => {
  // C'est le partage de responsabilité U3-MOTEUR : en résidentiel l'appelant
  // relit la recommandation SERVEUR, ailleurs il fait tourner le balayage
  // local. Le reducer, lui, ne va jamais chercher un chiffre.
  const etat = sizingReducer(ETAT_INITIAL, { type: 'RECALCUL_DEMANDE',
    retenu: { nbPanneaux: 7, kwcOptimal: 4.97 } })
  assert.equal(etat.nbPanneaux, '7')
  assert.equal(etat.kwcCible, '4.97')
})

test('sans valeur retenue, le recalcul ne pose RIEN (jamais un chiffre supposé)', () => {
  assert.equal(sizingReducer(ETAT_INITIAL, { type: 'RECALCUL_DEMANDE' }), ETAT_INITIAL)
  assert.equal(sizingReducer(ETAT_INITIAL,
    { type: 'RECALCUL_DEMANDE', retenu: null }), ETAT_INITIAL)
  assert.equal(sizingReducer(ETAT_INITIAL,
    { type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 0 } }), ETAT_INITIAL)
  const texte = sizingReducer(ETAT_INITIAL,
    { type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 'beaucoup' } })
  assert.equal(texte, ETAT_INITIAL, 'un compte illisible n’est pas un compte')
})

test('une cible kWc absente laisse le champ VIDE plutôt que d’inventer une conversion', () => {
  const etat = sizingReducer(ETAT_INITIAL,
    { type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 18 } })
  assert.equal(etat.nbPanneaux, '18')
  assert.equal(etat.kwcCible, '')
})

test('le recalcul ne touche QUE la taille : marché, scénario et options techniques sont intacts', () => {
  const configure = rejouer([
    { type: 'SAISI', champ: 'scenario', valeur: 'Avec batterie' },
    { type: 'SAISI', champ: 'structure', valeur: 'aluminium' },
    { type: 'SAISI', champ: 'tension', valeur: 'mt' },
    { type: 'SAISI', champ: 'panelW', valeur: '600' },
  ])
  const etat = sizingReducer(configure, RECALCUL)
  assert.equal(etat.scenario, 'Avec batterie')
  assert.equal(etat.structure, 'aluminium')
  assert.equal(etat.tension, 'mt')
  assert.equal(etat.panelW, '600', 'la puissance panneau du vendeur n’est pas redéfinie')
  assert.equal(etat.modeInstallation, 'residentiel')
})

test('le recalcul préserve TOUS les autres drapeaux « touché »', () => {
  const configure = rejouer([
    { type: 'SAISI', champ: 'scenario', valeur: 'Avec batterie' },
    { type: 'SAISI', champ: 'structure', valeur: 'aluminium' },
    { type: 'SAISI', champ: 'pompeAlim', valeur: 'mono' },
  ])
  const etat = sizingReducer(configure, RECALCUL)
  assert.equal(etat.touche.scenario, true)
  assert.equal(etat.touche.structure, true)
  assert.equal(etat.touche.pompeAlim, true)
  assert.equal(etat.touche.tension, false)
})

// ── U3-MOTEUR — LE « PALIER RETENU » NE DÉCRIT PAS LE MOTEUR ────────────────

test('en résidentiel le recalcul n’épingle AUCUN « palier retenu » (notion du balayage local)', () => {
  const etat = sizingReducer(ETAT_INITIAL, RECALCUL)
  assert.equal(etat.modeInstallation, 'residentiel')
  assert.equal(etat.sizingInfo, null,
    'l’encart « palier retenu / besoin lu sur la facture » ne décrit pas ce que le moteur a fait')
})

test('sur un marché SANS moteur, le justificatif du balayage local est bien conservé', () => {
  const industriel = sizingReducer(ETAT_INITIAL,
    { type: 'MARCHE_CHANGE', mode: 'industriel' })
  const etat = sizingReducer(industriel, RECALCUL)
  assert.equal(etat.modeInstallation, 'industriel')
  assert.deepEqual(etat.sizingInfo, RETENU)
})

// ── INVARIANT 3 — ROUVRIR ET RESTAURER DANS LA MÊME TRANSITION ──────────────
// F1 (revue adversariale 26/08/2026, BLOQUANT) : l'écran CAPTURAIT le
// garde-fou, le déverrouillait, puis le restaurait dans un effet — trois
// instructions, donc une fenêtre où une frappe pouvait s'engouffrer et se
// faire écraser. La transition fait les trois EN UNE FOIS : le drapeau RÉEL
// n'est jamais écrit, seul le LECTEUR de composition le voit ouvert.

test('F1 — un garde-fou POSÉ reste posé : le recalcul ne l’écrit jamais', () => {
  const tape = sizingReducer(ETAT_INITIAL, TAPE('14'))
  assert.equal(tape.touche.nbPanneaux, true)
  const etat = sizingReducer(tape, RECALCUL)
  assert.equal(etat.touche.nbPanneaux, true,
    'le drapeau réel doit être INCHANGÉ — pas restauré après coup, jamais écrit')
})

test('F1 — un garde-fou INTACT n’est pas verrouillé à `true` par le recalcul', () => {
  const etat = sizingReducer(ETAT_INITIAL, RECALCUL)
  assert.equal(etat.touche.nbPanneaux, false,
    'un `true` figé ferait de tout recalcul une « saisie » et gèlerait l’écran ensuite')
})

test('F1 — pendant la fenêtre, la COMPOSITION voit le garde-fou OUVERT (et lui seul)', () => {
  const tape = sizingReducer(ETAT_INITIAL, TAPE('14'))
  const etat = sizingReducer(tape, RECALCUL)
  assert.equal(toucheNbPanneauxPourComposition(etat), false,
    'c’est le déverrouillage explicite demandé par le fondateur')
  assert.equal(etat.touche.nbPanneaux, true,
    'l’état, lui, conserve la vérité — les deux lectures diffèrent, et c’est le point')
})

test('F1 — hors fenêtre, les deux lectures redisent la MÊME chose', () => {
  const tape = sizingReducer(ETAT_INITIAL, TAPE('14'))
  assert.equal(toucheNbPanneauxPourComposition(tape), true)
  assert.equal(toucheNbPanneauxPourComposition(ETAT_INITIAL), false)
})

test('F2 — la fenêtre dure EXACTEMENT une transition : la moindre action suivante la referme', () => {
  const ouverte = rejouer([TAPE('14'), RECALCUL])
  assert.notEqual(ouverte.recalcul, null)
  for (const suite of [
    { type: 'SAISI', champ: 'panelW', valeur: '600' },
    { type: 'MARCHE_CHANGE', mode: 'industriel' },
    { type: 'MOTEUR_A_REPONDU', recommandation: { panneaux: 30 } },
    { type: 'UNE_ACTION_DE_TROP' },
    {},
  ]) {
    const apres = sizingReducer(ouverte, suite)
    assert.equal(apres.recalcul, null, `action ${suite.type ?? '(sans type)'}`)
    assert.equal(toucheNbPanneauxPourComposition(apres), apres.touche.nbPanneaux,
      'refermée, la lecture de composition redit l’état réel')
  }
})

test('F2 — une frappe pendant la fenêtre la referme ET garde la valeur tapée', () => {
  const ouverte = rejouer([TAPE('14'), RECALCUL])
  assert.equal(ouverte.nbPanneaux, '18')
  const frappe = sizingReducer(ouverte, TAPE('9'))
  assert.equal(frappe.nbPanneaux, '9', 'la frappe la plus récente gagne')
  assert.equal(frappe.recalcul, null)
  assert.equal(frappe.touche.nbPanneaux, true)
})

test('la fenêtre porte le NUMÉRO de la composition qu’elle autorise', () => {
  const etat = sizingReducer(ETAT_INITIAL, RECALCUL)
  assert.equal(etat.recalcul.seq, etat.compositionSeq)
  assert.equal(etat.recalcul.ignorerToucheNbPanneaux, true)
  assert.equal(Object.isFrozen(etat.recalcul), true, 'la fenêtre ne se retouche pas')
})

test('F2 — refermer la fenêtre rend un état NEUF : l’état ouvert n’est jamais muté sur place', () => {
  const ouverte = sizingReducer(ETAT_INITIAL, RECALCUL)
  const refermee = sizingReducer(ouverte, { type: 'UNE_ACTION_DE_TROP' })
  assert.notEqual(refermee, ouverte)
  assert.notEqual(ouverte.recalcul, null, 'l’état d’origine garde sa fenêtre — aucune mutation')
  assert.equal(refermee.recalcul, null)
  assert.equal(refermee.nbPanneaux, ouverte.nbPanneaux, 'refermer ne défait pas le recalcul')
})

test('le lecteur de composition tolère un état SANS fenêtre (aucune exception sur un état ancien)', () => {
  assert.equal(toucheNbPanneauxPourComposition({ touche: { nbPanneaux: true } }), true)
  assert.equal(toucheNbPanneauxPourComposition({ touche: { nbPanneaux: false } }), false)
})

// ── LE COMPTEUR DE COMPOSITION ─────────────────────────────────────────────
// Le correctif ne pouvait PAS caler la recomposition sur `nbPanneaux` : un
// recalcul qui retombe sur le MÊME compte n'aurait rien redéclenché.

test('un recalcul relance la composition MÊME si le compte ne bouge pas', () => {
  const premier = sizingReducer(ETAT_INITIAL, RECALCUL)
  assert.equal(premier.compositionSeq, 1)
  const second = sizingReducer(premier, RECALCUL)
  assert.equal(second.nbPanneaux, premier.nbPanneaux, 'même compte…')
  assert.equal(second.compositionSeq, 2, '…et pourtant une nouvelle composition')
})

test('deux recalculs successifs gardent la fenêtre ouverte, chacun avec SON numéro', () => {
  const premier = sizingReducer(ETAT_INITIAL, RECALCUL)
  const second = sizingReducer(premier, RECALCUL)
  assert.equal(premier.recalcul.seq, 1)
  assert.equal(second.recalcul.seq, 2)
  assert.equal(toucheNbPanneauxPourComposition(second), false)
})

test('le compteur ne bouge QUE pour les transitions qui relancent la composition', () => {
  assert.equal(sizingReducer(ETAT_INITIAL, TAPE('14')).compositionSeq, 0,
    'taper un nombre ne recompose pas à chaque frappe')
  assert.equal(sizingReducer(ETAT_INITIAL,
    { type: 'MARCHE_CHANGE', mode: 'industriel' }).compositionSeq, 0)
  assert.equal(sizingReducer(ETAT_INITIAL,
    { type: 'TAILLE_APPLIQUEE', ligne: { panneaux: 12 } }).compositionSeq, 1,
    '« Appliquer cette taille » recompose, comme le recalcul')
})

// ── ROOT CAUSE 3, EXPRIMÉE PAR LE COMPORTEMENT ─────────────────────────────

test('ROOT CAUSE 3 — sans le bouton, une frappe sur la facture ne recalcule plus rien une fois le garde-fou posé', () => {
  const bloque = rejouer([
    TAPE('14'),
    { type: 'PROFIL_SITE_APPLIQUE',
      profil: { type_installation: 'industriel', facture_hiver: 4800 },
      sizingLocal: { nbPanneaux: 40, kwcOptimal: 28.4 } },
  ])
  assert.equal(bloque.nbPanneaux, '14', 'c’est exactement le blocage rapporté par le fondateur')
  // Le BOUTON est la sortie explicite : il passe outre, une fois, sans jamais
  // effacer le fait que le vendeur avait touché le champ.
  const recalcule = sizingReducer(bloque, {
    type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 40, kwcOptimal: 28.4 } })
  assert.equal(recalcule.nbPanneaux, '40')
  assert.equal(recalcule.touche.nbPanneaux, true)
  assert.equal(toucheNbPanneauxPourComposition(recalcule), false)
})

test('ROOT CAUSE 1 — la réouverture d’un brouillon ne FERME pas le garde-fou (il reste ouvert après un ?edit=)', () => {
  const etat = sizingReducer(ETAT_INITIAL, {
    type: 'REOUVERTURE',
    devis: { mode_installation: 'residentiel', panneaux: 20, scenario: SCENARIO_LES_DEUX },
  })
  assert.equal(etat.nbPanneaux, '20', 'le compte vient des lignes du devis')
  assert.equal(etat.touche.nbPanneaux, false,
    'la staleness ne venait pas d’un garde-fou fermé par l’édition — c’était la cause #2 initiale, corrigée')
  assert.equal(etat.touche.scenario, true, 'le SCÉNARIO, lui, est un choix déjà posé')
  assert.equal(etat.touche.mode, true)
})

// ── LES DEUX VALEURS AFFICHÉES APRÈS UN RECALCUL ───────────────────────────

test('les deux valeurs affichées viennent du MOTEUR, jamais du recalcul local', () => {
  const paire = deuxValeursDim('residentiel', {
    dimensionnement: {
      recommandation: { panneaux: 12, kwc: 8.52 },
      recommandation_avec: { panneaux: 16, kwc: 11.36 },
    },
  })
  assert.deepEqual(paire.sans, { nbPanneaux: 12, kwc: 8.52 })
  assert.deepEqual(paire.avec, { nbPanneaux: 16, kwc: 11.36 })
})

test('F3 — le serveur n’a chiffré que le SANS : aucune valeur « avec » n’est fabriquée pour compléter la paire', () => {
  const paire = deuxValeursDim('residentiel',
    { dimensionnement: { recommandation: { panneaux: 12, kwc: 8.52 } } })
  assert.deepEqual(paire.sans, { nbPanneaux: 12, kwc: 8.52 })
  assert.equal(paire.avec, null, 'c’était le bug rapporté')
})

test('F3 — et l’inverse : le SANS ne se fabrique pas non plus depuis l’AVEC', () => {
  const paire = deuxValeursDim('residentiel',
    { dimensionnement: { recommandation_avec: { panneaux: 16, kwc: 11.36 } } })
  assert.equal(paire.sans, null)
  assert.deepEqual(paire.avec, { nbPanneaux: 16, kwc: 11.36 })
})

test('F3 — hors résidentiel, aucune des deux valeurs n’est affichée', () => {
  for (const marche of ['industriel', 'commercial', 'agricole']) {
    assert.deepEqual(
      deuxValeursDim(marche, {
        dimensionnement: {
          recommandation: { panneaux: 12, kwc: 8.52 },
          recommandation_avec: { panneaux: 16, kwc: 11.36 },
        },
      }),
      { sans: null, avec: null }, `marché ${marche}`)
  }
})

test('un recalcul ne change PAS les deux valeurs affichées : elles décrivent la RECOMMANDATION, pas ce qui est composé', () => {
  // F5 — un nombre de panneaux tapé (ou recalculé) peut diverger de la
  // recommandation : le bloc reste un rappel de ce que le moteur conseille.
  const donnees = { dimensionnement: { recommandation: { panneaux: 12, kwc: 8.52 } } }
  const avant = deuxValeursDim('residentiel', donnees)
  const apres = deuxValeursDim('residentiel', donnees)
  assert.deepEqual(avant, apres)
  assert.equal(sizingReducer(ETAT_INITIAL, RECALCUL).nbPanneaux, '18')
  assert.equal(avant.sans.nbPanneaux, 12,
    'la recommandation affichée n’est pas réécrite par la taille retenue')
})
