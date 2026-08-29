// QJR87 — tests de la machine à états du dimensionnement. `node --test`
// uniquement (le reducer n'importe que `solar.js`, lui-même sans node_modules).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  sizingReducer, ETAT_INITIAL, DRAPEAUX_TOUCHE, drapeauxPoses,
  toucheNbPanneauxPourComposition,
  SCENARIO_LES_DEUX, SCENARIO_SANS, SCENARIO_AVEC,
} from './sizingReducer.js'

const red = (etat, ...actions) => actions.reduce(sizingReducer, etat)

test('état initial : les six ex-refs sont de l’ÉTAT, énumérable', () => {
  assert.deepEqual(DRAPEAUX_TOUCHE,
    ['mode', 'structure', 'tension', 'pompeAlim', 'nbPanneaux', 'scenario'])
  assert.deepEqual(Object.keys(ETAT_INITIAL.touche).sort(), [...DRAPEAUX_TOUCHE].sort())
  assert.deepEqual(drapeauxPoses(ETAT_INITIAL), [])
  assert.equal(ETAT_INITIAL.scenario, SCENARIO_LES_DEUX)
  assert.equal(ETAT_INITIAL.modeInstallation, 'residentiel')
})

test('une action inconnue rend l’état INCHANGÉ (un écran ne casse pas)', () => {
  assert.equal(sizingReducer(ETAT_INITIAL, { type: 'INEXISTANT' }), ETAT_INITIAL)
})

// ── SAISI ────────────────────────────────────────────────────────────────────

test('SAISI nbPanneaux : garde EXACTEMENT ce qui est tapé, dérive la cible', () => {
  const s = red(ETAT_INITIAL, { type: 'SAISI', champ: 'nbPanneaux', valeur: '12' })
  assert.equal(s.nbPanneaux, '12')
  assert.equal(s.kwcCible, '8.52')            // 12 × 710 W
  assert.equal(s.touche.nbPanneaux, true)
  assert.equal(s.sizingInfo, null)
})

test('SAISI kwcCible : bidirectionnel, jamais « snappé »', () => {
  const s = red(ETAT_INITIAL, { type: 'SAISI', champ: 'kwcCible', valeur: '8.5' })
  assert.equal(s.kwcCible, '8.5')             // le champ garde la frappe
  assert.equal(s.nbPanneaux, '12')            // ceil(8500/710)
  assert.equal(s.touche.nbPanneaux, true)
  // Une frappe encore illisible ne pose RIEN.
  const p = red(ETAT_INITIAL, { type: 'SAISI', champ: 'kwcCible', valeur: '0,' })
  assert.equal(p.kwcCible, '0,')
  assert.equal(p.nbPanneaux, '')
  assert.equal(p.touche.nbPanneaux, false)
})

test('SAISI pose le drapeau du champ concerné, et lui seul', () => {
  for (const [champ, valeur] of [['structure', 'aluminium'], ['tension', 'mt'],
    ['pompeAlim', 'mono'], ['scenario', SCENARIO_AVEC]]) {
    const s = red(ETAT_INITIAL, { type: 'SAISI', champ, valeur })
    assert.deepEqual(drapeauxPoses(s), [champ])
    assert.equal(s[champ], valeur)
  }
})

// ── INVARIANT 1 — une frappe n'est JAMAIS écrasée par le moteur ──────────────

test('INVARIANT 1 : MOTEUR_A_REPONDU n’écrase JAMAIS un nbPanneaux SAISI', () => {
  const attente = { ...ETAT_INITIAL, attenteMoteur: true }
  const s = red(attente,
    { type: 'SAISI', champ: 'nbPanneaux', valeur: '9' },
    { type: 'MOTEUR_A_REPONDU', recommandation: { panneaux: 21, kwc: 14.91, panel_watt: 710 } })
  assert.equal(s.nbPanneaux, '9')             // la frappe gagne
  assert.equal(s.attenteMoteur, false)        // l’attente est refermée
  assert.equal(s.motifMoteur, null)
})

test('INVARIANT 1 (bis) : MOTEUR_A_REFUSE n’épingle aucun motif sur une frappe', () => {
  const attente = { ...ETAT_INITIAL, attenteMoteur: true }
  const s = red(attente,
    { type: 'SAISI', champ: 'nbPanneaux', valeur: '9' },
    { type: 'MOTEUR_A_REFUSE', motif: 'Ville manquante.' })
  assert.equal(s.nbPanneaux, '9')
  assert.equal(s.attenteMoteur, false)
  assert.equal(s.motifMoteur, null)
})

test('sans frappe, la recommandation SERVEUR est appliquée telle quelle', () => {
  const s = sizingReducer({ ...ETAT_INITIAL, attenteMoteur: true },
    { type: 'MOTEUR_A_REPONDU', recommandation: { panneaux: 21, kwc: 14.91, panel_watt: 550 } })
  assert.equal(s.nbPanneaux, '21')
  assert.equal(s.panelW, '550')
  assert.equal(s.kwcCible, '14.91')
  assert.equal(s.attenteMoteur, false)
  assert.equal(s.touche.nbPanneaux, false)    // le serveur ne « touche » rien
})

test('un refus du moteur porte le motif FR VERBATIM, et aucun chiffre', () => {
  const motif = 'Dimensionnement impossible : ville du client manquante.'
  const s = sizingReducer({ ...ETAT_INITIAL, attenteMoteur: true },
    { type: 'MOTEUR_A_REFUSE', motif })
  assert.equal(s.motifMoteur, motif)
  assert.equal(s.nbPanneaux, '')
  assert.equal(s.attenteMoteur, false)
})

test('une réponse moteur hors attente ne touche à RIEN', () => {
  const s = sizingReducer(ETAT_INITIAL,
    { type: 'MOTEUR_A_REPONDU', recommandation: { panneaux: 21 } })
  assert.equal(s, ETAT_INITIAL)
})

// ── INVARIANT 2 — MARCHE_CHANGE consulte scenarioTouched ─────────────────────

test('INVARIANT 2 : MARCHE_CHANGE consulte touche.scenario (choix préservé)', () => {
  const choisi = red(ETAT_INITIAL,
    { type: 'SAISI', champ: 'scenario', valeur: SCENARIO_AVEC },
    { type: 'MARCHE_CHANGE', mode: 'industriel' })
  assert.equal(choisi.modeInstallation, 'industriel')
  assert.equal(choisi.scenario, SCENARIO_AVEC)   // JAMAIS jeté en silence
})

test('INVARIANT 2 (bis) : un scénario INTACT prend bien le défaut du marché', () => {
  const inact = red(ETAT_INITIAL, { type: 'MARCHE_CHANGE', mode: 'industriel' })
  assert.equal(inact.scenario, SCENARIO_SANS)
  const retour = red(inact, { type: 'MARCHE_CHANGE', mode: 'residentiel' })
  assert.equal(retour.scenario, SCENARIO_LES_DEUX)
  // Pompage : le scénario n'est PAS touché (ni batterie ni onduleur).
  const agri = red(ETAT_INITIAL, { type: 'MARCHE_CHANGE', mode: 'agricole' })
  assert.equal(agri.scenario, SCENARIO_LES_DEUX)
})

test('MARCHE_CHANGE : même marché = aucune transition ; mode inconnu ignoré', () => {
  const s = red(ETAT_INITIAL, { type: 'SAISI', champ: 'scenario', valeur: SCENARIO_AVEC })
  assert.equal(sizingReducer(s, { type: 'MARCHE_CHANGE', mode: 'residentiel' }).scenario,
    SCENARIO_AVEC)
  assert.equal(sizingReducer(ETAT_INITIAL, { type: 'MARCHE_CHANGE', mode: 'spatial' }),
    ETAT_INITIAL)
})

test('MARCHE_CHANGE marque touche.mode seulement pour un choix UTILISATEUR', () => {
  assert.equal(red(ETAT_INITIAL,
    { type: 'MARCHE_CHANGE', mode: 'agricole' }).touche.mode, true)
  assert.equal(red(ETAT_INITIAL,
    { type: 'MARCHE_CHANGE', mode: 'agricole', origine: 'lead' }).touche.mode, false)
})

// ── INVARIANT 3 — RECALCUL_DEMANDE : rouvrir ET restaurer, même transition ───

test('INVARIANT 3 : RECALCUL_DEMANDE restaure le drapeau ANTÉRIEUR (true)', () => {
  const tape = red(ETAT_INITIAL, { type: 'SAISI', champ: 'nbPanneaux', valeur: '9' })
  assert.equal(tape.touche.nbPanneaux, true)
  const s = sizingReducer(tape,
    { type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 21, kwcOptimal: 14.91 } })
  // Rouvert POUR LA COMPOSITION…
  assert.equal(toucheNbPanneauxPourComposition(s), false)
  // …et restauré dans la MÊME transition : aucune fenêtre intermédiaire.
  assert.equal(s.touche.nbPanneaux, true)
  assert.equal(s.nbPanneaux, '21')
  assert.equal(s.kwcCible, '14.91')
  assert.equal(s.compositionSeq, tape.compositionSeq + 1)
})

test('INVARIANT 3 (bis) : un drapeau ANTÉRIEUR faux n’est pas verrouillé à true', () => {
  const s = sizingReducer(ETAT_INITIAL,
    { type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 21, kwcOptimal: 14.91 } })
  assert.equal(s.touche.nbPanneaux, false)
  assert.equal(toucheNbPanneauxPourComposition(s), false)
})

test('la fenêtre de recalcul dure UNE transition et se referme', () => {
  const tape = red(ETAT_INITIAL, { type: 'SAISI', champ: 'nbPanneaux', valeur: '9' })
  const s = sizingReducer(tape,
    { type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 21, kwcOptimal: 14.91 } })
  const apres = sizingReducer(s, { type: 'INEXISTANT' })
  assert.equal(apres.recalcul, null)
  assert.equal(toucheNbPanneauxPourComposition(apres), true)   // le vrai drapeau reprend
})

test('RECALCUL_DEMANDE en résidentiel n’épingle AUCUN « palier retenu »', () => {
  const s = sizingReducer(ETAT_INITIAL,
    { type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 21, kwcOptimal: 14.91 } })
  assert.equal(s.sizingInfo, null)
  const indus = sizingReducer({ ...ETAT_INITIAL, modeInstallation: 'industriel' },
    { type: 'RECALCUL_DEMANDE', retenu: { nbPanneaux: 21, kwcOptimal: 14.91 } })
  assert.deepEqual(indus.sizingInfo, { nbPanneaux: 21, kwcOptimal: 14.91 })
})

test('RECALCUL_DEMANDE sans valeur retenue ne pose RIEN (jamais un chiffre supposé)', () => {
  assert.equal(sizingReducer(ETAT_INITIAL, { type: 'RECALCUL_DEMANDE', retenu: null }),
    ETAT_INITIAL)
})

// ── LEAD_APPLIQUE ────────────────────────────────────────────────────────────

const LEAD = {
  type_installation: 'industriel',
  batterie_souhaitee: 'avec',
  structure_pref: 'aluminium',
  web_questionnaire: { tension_raccordement: 'MT' },
  facture_hiver: '3000',
}

test('LEAD_APPLIQUE : mode/scénario/structure/tension du lead sur des champs INTACTS', () => {
  const s = sizingReducer(ETAT_INITIAL, { type: 'LEAD_APPLIQUE', lead: LEAD, sizingLocal: null })
  assert.equal(s.modeInstallation, 'industriel')
  assert.equal(s.scenario, SCENARIO_AVEC)     // le choix du tunnel bat le défaut du marché
  assert.equal(s.structure, 'aluminium')
  assert.equal(s.tension, 'mt')
  assert.deepEqual(drapeauxPoses(s), [])      // un pré-remplissage ne « touche » rien
})

test('LEAD_APPLIQUE : aucun champ DÉJÀ TOUCHÉ n’est écrasé', () => {
  const touche = red(ETAT_INITIAL,
    { type: 'MARCHE_CHANGE', mode: 'residentiel' },              // pose touche.mode
    { type: 'SAISI', champ: 'scenario', valeur: SCENARIO_SANS },
    { type: 'SAISI', champ: 'structure', valeur: 'acier' },
    { type: 'SAISI', champ: 'tension', valeur: 'bt' })
  const s = sizingReducer(touche, { type: 'LEAD_APPLIQUE', lead: LEAD })
  assert.equal(s.modeInstallation, 'residentiel')
  assert.equal(s.scenario, SCENARIO_SANS)
  assert.equal(s.structure, 'acier')
  assert.equal(s.tension, 'bt')
})

test('LEAD_APPLIQUE : jamais de scénario en POMPAGE (ni batterie ni onduleur)', () => {
  const s = sizingReducer(ETAT_INITIAL, {
    type: 'LEAD_APPLIQUE',
    lead: { type_installation: 'agricole', batterie_souhaitee: 'avec', raccordement: 'monophase' },
  })
  assert.equal(s.modeInstallation, 'agricole')
  assert.equal(s.scenario, SCENARIO_LES_DEUX)   // le défaut initial, inchangé
  assert.equal(s.pompeAlim, 'mono')
})

test('LEAD_APPLIQUE : la taille souhaitée est PRIORITAIRE sur la facture', () => {
  const s = sizingReducer(ETAT_INITIAL, {
    type: 'LEAD_APPLIQUE',
    lead: { type_installation: 'residentiel', taille_souhaitee_kwc: '8', facture_hiver: '3000' },
  })
  assert.equal(s.nbPanneaux, '12')            // ceil(8000/710)
  assert.equal(s.attenteMoteur, false)        // aucune attente : la taille suffit
  assert.equal(s.touche.nbPanneaux, false)
})

test('LEAD_APPLIQUE résidentiel avec facture : ATTEND le moteur serveur (U3-900)', () => {
  const s = sizingReducer(ETAT_INITIAL, {
    type: 'LEAD_APPLIQUE',
    lead: { type_installation: 'residentiel', facture_hiver: '3000' },
  })
  assert.equal(s.attenteMoteur, true)
  assert.equal(s.nbPanneaux, '')              // RIEN n’est préremplié localement
  assert.equal(s.sizingInfo, null)
})

test('LEAD_APPLIQUE industriel avec facture : balayage LOCAL fourni par l’appelant', () => {
  const sizingLocal = { nbPanneaux: 30, kwcOptimal: 21.3 }
  const s = sizingReducer(ETAT_INITIAL,
    { type: 'LEAD_APPLIQUE', lead: LEAD, sizingLocal })
  assert.equal(s.attenteMoteur, false)        // aucun moteur serveur pour ce marché
  assert.equal(s.nbPanneaux, '30')
  assert.deepEqual(s.sizingInfo, sizingLocal)
  // Rien de chiffrable : aucun compte posé, aucun justificatif inventé.
  const rien = sizingReducer(ETAT_INITIAL,
    { type: 'LEAD_APPLIQUE', lead: LEAD, sizingLocal: null })
  assert.equal(rien.nbPanneaux, '')
  assert.equal(rien.sizingInfo, null)
})

test('LEAD_APPLIQUE : une frappe antérieure bloque la reprise par la facture', () => {
  const tape = red(ETAT_INITIAL, { type: 'SAISI', champ: 'nbPanneaux', valeur: '9' })
  const s = sizingReducer(tape, {
    type: 'LEAD_APPLIQUE',
    lead: { type_installation: 'residentiel', taille_souhaitee_kwc: '8', facture_hiver: '3000' },
  })
  assert.equal(s.nbPanneaux, '9')
  // La facture arme quand même l’attente moteur, mais l’invariant 1 la neutralise.
  assert.equal(sizingReducer(s, {
    type: 'MOTEUR_A_REPONDU', recommandation: { panneaux: 21 },
  }).nbPanneaux, '9')
})

// ── PROFIL_SITE_APPLIQUE (QJR38 : le mode VISÉ, pas celui du rendu précédent) ─

test('PROFIL_SITE_APPLIQUE industriel : chemin INDUSTRIEL, aucune attente serveur', () => {
  const s = sizingReducer(ETAT_INITIAL, {
    type: 'PROFIL_SITE_APPLIQUE',
    profil: { type_installation: 'industriel', facture_hiver: '3000' },
    sizingLocal: { nbPanneaux: 30, kwcOptimal: 21.3 },
  })
  assert.equal(s.modeInstallation, 'industriel')
  assert.equal(s.attenteMoteur, false)        // le bug QJR38 armait une attente ici
  assert.equal(s.nbPanneaux, '30')
})

test('PROFIL_SITE_APPLIQUE résidentiel : attend le moteur ; profil vide = no-op', () => {
  const s = sizingReducer(ETAT_INITIAL, {
    type: 'PROFIL_SITE_APPLIQUE',
    profil: { type_installation: 'residentiel', facture_hiver: '3000' },
  })
  assert.equal(s.attenteMoteur, true)
  assert.equal(sizingReducer(ETAT_INITIAL,
    { type: 'PROFIL_SITE_APPLIQUE', profil: null }), ETAT_INITIAL)
})

// ── TAILLE_APPLIQUEE / REOUVERTURE ───────────────────────────────────────────

test('TAILLE_APPLIQUEE : pose la ligne choisie, ferme le drapeau, relance la composition', () => {
  const s = sizingReducer(ETAT_INITIAL, {
    type: 'TAILLE_APPLIQUEE',
    ligne: { panneaux: 18, kwc: 12.78, panel_watt: 710 },
  })
  assert.equal(s.nbPanneaux, '18')
  assert.equal(s.kwcCible, '12.78')
  assert.equal(s.touche.nbPanneaux, true)
  assert.equal(s.sizingInfo, null)
  assert.equal(s.compositionSeq, 1)
  // Une ligne sans panneaux ne fait RIEN.
  assert.equal(sizingReducer(ETAT_INITIAL, { type: 'TAILLE_APPLIQUEE', ligne: { panneaux: 0 } }),
    ETAT_INITIAL)
})

test('REOUVERTURE : mode et scénario du devis ferment leurs drapeaux', () => {
  const s = sizingReducer(ETAT_INITIAL, {
    type: 'REOUVERTURE',
    devis: { mode_installation: 'industriel', scenario: SCENARIO_LES_DEUX, panneaux: 24 },
  })
  assert.equal(s.modeInstallation, 'industriel')
  assert.equal(s.scenario, SCENARIO_LES_DEUX)  // le choix du devis, PAS le défaut du marché
  assert.deepEqual(drapeauxPoses(s).sort(), ['mode', 'scenario'])
  assert.equal(s.nbPanneaux, '24')
  assert.equal(s.touche.nbPanneaux, false)     // relire les lignes n’est pas une saisie
})

test('REOUVERTURE : un scénario hors contrat du moteur PDF est IGNORÉ', () => {
  const s = sizingReducer(ETAT_INITIAL, {
    type: 'REOUVERTURE', devis: { scenario: 'Avec panneaux magiques' },
  })
  assert.equal(s.scenario, SCENARIO_LES_DEUX)
  assert.equal(s.touche.scenario, false)
})
