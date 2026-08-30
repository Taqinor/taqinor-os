// QJR88 — tests du registre d'overrides côté écran. `node --test` uniquement.
// Le test LIT le contrat QJR1 sur disque : c'est ce qui rend le registre
// « aligné sur le backend » vérifiable au lieu d'être affirmé en commentaire.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  CHEMINS_AUTORISES, CHEMIN_PAR_DRAPEAU, ORIGINES,
  cheminAutorise, cheminsRefuses, serialiser, hydrater, fusionner,
} from './overrides.js'
import {
  sizingReducer, ETAT_INITIAL, DRAPEAUX_TOUCHE, SCENARIO_AVEC,
} from './sizingReducer.js'

const CONTRAT = JSON.parse(readFileSync(new URL(
  '../../../../../backend/django_core/apps/ventes/contract_samples/devis_overrides.json',
  import.meta.url), 'utf8'))

// ── Conformité au contrat QJR1 ───────────────────────────────────────────────

test('les chemins sont RECOPIÉS À L’IDENTIQUE du contrat QJR1 (ordre compris)', () => {
  assert.deepEqual([...CHEMINS_AUTORISES], CONTRAT.notes.chemins_autorises)
})

test('les origines sont celles du contrat, jamais une quatrième', () => {
  assert.deepEqual([...ORIGINES], ['manuel', 'import', 'api'])
  for (const o of ORIGINES) assert.ok(CONTRAT.notes.origine_valeurs.includes(o))
  assert.throws(() => serialiser(ETAT_INITIAL, { origine: 'devinette' }), TypeError)
})

test('tout chemin d’exemple du contrat est accepté par la liste blanche', () => {
  for (const chemin of Object.keys(CONTRAT.exemple.overrides)) {
    assert.equal(cheminAutorise(chemin), true, chemin)
  }
  for (const chemin of Object.keys(CONTRAT.exemple.effectif)) {
    assert.equal(cheminAutorise(chemin), true, chemin)
  }
})

test('`profil.equipements.<clef>` est le SEUL motif dynamique', () => {
  assert.equal(cheminAutorise('profil.equipements.piscine'), true)
  assert.equal(cheminAutorise('profil.equipements.vehicule_electrique'), true)
  assert.equal(cheminAutorise('profil.equipements.<clef>'), false) // le motif lui-même
  assert.equal(cheminAutorise('profil.equipements.piscine.puissance_kw'), false)
  // Aucune clé de ligne indexée par POSITION (interdit explicite du contrat).
  assert.equal(cheminAutorise('lignes[3].prix_manuel'), false)
  assert.equal(cheminAutorise('total_ttc'), false)   // champ DÉRIVÉ → 400
  assert.equal(cheminAutorise(''), false)
  assert.equal(cheminAutorise(null), false)
})

// ── EXHAUSTIVITÉ drapeaux ↔ registre ─────────────────────────────────────────

test('EXHAUSTIVITÉ : chaque drapeau « touché » du reducer a SON chemin', () => {
  for (const drapeau of Object.keys(ETAT_INITIAL.touche)) {
    const def = CHEMIN_PAR_DRAPEAU[drapeau]
    assert.ok(def, `drapeau « ${drapeau} » sans chemin dans le registre`)
    assert.equal(cheminAutorise(def.chemin), true, def.chemin)
    assert.ok(def.champ in ETAT_INITIAL, `champ « ${def.champ}» absent de l'état`)
  }
  assert.deepEqual(Object.keys(CHEMIN_PAR_DRAPEAU).sort(), [...DRAPEAUX_TOUCHE].sort())
})

test('EXHAUSTIVITÉ : un drapeau ajouté SANS son chemin rend ROUGE', () => {
  // Simule le reducer de demain : un septième drapeau apparaît dans l'état.
  const etatDemain = {
    ...ETAT_INITIAL,
    orientationToit: 'sud',
    touche: { ...ETAT_INITIAL.touche, orientationToit: true },
  }
  const manquants = Object.keys(etatDemain.touche)
    .filter((d) => !CHEMIN_PAR_DRAPEAU[d])
  assert.deepEqual(manquants, ['orientationToit'])   // détecté, donc ROUGE
  // Et la sérialisation REFUSE l'état plutôt que d'oublier le drapeau en
  // silence (c'est la taxe « chaque champ invente son propre drapeau » qui
  // devient impossible) — il faut le déclarer dans DRAPEAUX_TOUCHE + ici.
  assert.throws(() => serialiser({
    ...etatDemain,
    touche: { ...etatDemain.touche },
    // le reducer énumère DRAPEAUX_TOUCHE : on simule son extension.
  }, {}), (err) => err instanceof TypeError || err instanceof Error)
})

// ── serialiser / hydrater ────────────────────────────────────────────────────

test('serialiser n’émet QUE les chemins réellement touchés', () => {
  assert.deepEqual(serialiser(ETAT_INITIAL), {})
  const etat = [
    { type: 'SAISI', champ: 'nbPanneaux', valeur: '14' },
    { type: 'SAISI', champ: 'scenario', valeur: SCENARIO_AVEC },
  ].reduce(sizingReducer, ETAT_INITIAL)
  const payload = serialiser(etat, {
    pose_le: '2026-08-20T09:14:00+00:00', pose_par: 'sami@taqinor.ma',
  })
  assert.deepEqual(Object.keys(payload).sort(), ['scenario', 'taille.nb_panneaux'])
  assert.deepEqual(payload['taille.nb_panneaux'], {
    valeur: 14, pose_le: '2026-08-20T09:14:00+00:00',
    pose_par: 'sami@taqinor.ma', origine: 'manuel',
  })
  assert.equal(payload.scenario.valeur, SCENARIO_AVEC)
  // La MÊME forme que l'exemple du contrat.
  assert.deepEqual(Object.keys(payload['taille.nb_panneaux']).sort(),
    Object.keys(CONTRAT.exemple.overrides['taille.nb_panneaux']).sort())
  assert.equal(payload['taille.nb_panneaux'].valeur,
    CONTRAT.exemple.overrides['taille.nb_panneaux'].valeur)
})

test('serialiser n’invente aucune clé d’audit absente', () => {
  const etat = sizingReducer(ETAT_INITIAL,
    { type: 'SAISI', champ: 'tension', valeur: 'mt' })
  assert.deepEqual(serialiser(etat), { tension: { valeur: 'mt', origine: 'manuel' } })
})

test('serialiser ne produit JAMAIS un chemin hors liste blanche', () => {
  const etat = DRAPEAUX_TOUCHE.reduce((s, d) => ({
    ...s, touche: { ...s.touche, [d]: true },
  }), ETAT_INITIAL)
  assert.deepEqual(cheminsRefuses(serialiser(etat)), [])
  assert.equal(Object.keys(serialiser(etat)).length, DRAPEAUX_TOUCHE.length)
})

test('hydrater est l’inverse : il repose la valeur ET son drapeau', () => {
  const etat = [
    { type: 'SAISI', champ: 'nbPanneaux', valeur: '14' },
    { type: 'SAISI', champ: 'pompeAlim', valeur: 'mono' },
  ].reduce(sizingReducer, ETAT_INITIAL)
  const partiel = hydrater(serialiser(etat))
  assert.equal(partiel.nbPanneaux, '14')
  assert.equal(partiel.pompeAlim, 'mono')
  assert.deepEqual(partiel.touche, { nbPanneaux: true, pompeAlim: true })
  // Un état RÉHYDRATÉ ne se fait plus écraser par un pré-remplissage.
  const rejoue = sizingReducer(
    { ...ETAT_INITIAL, ...partiel, touche: { ...ETAT_INITIAL.touche, ...partiel.touche } },
    { type: 'LEAD_APPLIQUE', lead: { type_installation: 'residentiel', taille_souhaitee_kwc: '8' } })
  assert.equal(rejoue.nbPanneaux, '14')
})

test('hydrater ignore les chemins inconnus, vides ou nuls', () => {
  assert.deepEqual(hydrater({}), {})
  assert.deepEqual(hydrater(null), {})
  assert.deepEqual(hydrater({ 'tarif.distributeur': { valeur: 'ONEE' } }), {})  // pas d'écran
  assert.deepEqual(hydrater({ scenario: { valeur: null } }), {})
  assert.deepEqual(hydrater({ scenario: 'Avec batterie' }), {})                 // pas signé
})

// ── PATCH = FUSION ───────────────────────────────────────────────────────────

test('PATCH est une FUSION : les autres chemins posés restent intacts', () => {
  const registre = {
    'tarif.distributeur': { valeur: 'ONEE', origine: 'import' },
    'taille.nb_panneaux': { valeur: 12, origine: 'manuel' },
  }
  const fusionne = fusionner(registre, { 'taille.nb_panneaux': { valeur: 14, origine: 'manuel' } })
  assert.deepEqual(fusionne['tarif.distributeur'], registre['tarif.distributeur'])
  assert.equal(fusionne['taille.nb_panneaux'].valeur, 14)
  assert.equal(Object.keys(fusionne).length, 2)
  // Le registre d'origine n'est pas muté.
  assert.equal(registre['taille.nb_panneaux'].valeur, 12)
})

test('fusionner REFUSE un chemin hors liste blanche (miroir du 400 serveur)', () => {
  assert.throws(() => fusionner({}, { total_ttc: { valeur: 42000 } }), TypeError)
  assert.throws(() => fusionner({}, { 'lignes[3].prix_manuel': { valeur: true } }), TypeError)
  assert.deepEqual(fusionner({}, {}), {})
})
