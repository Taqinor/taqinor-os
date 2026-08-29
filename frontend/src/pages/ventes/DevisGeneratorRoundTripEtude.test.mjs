// QJR66 / ARBITRAGE ORCHESTRATEUR (29/08/2026) — LE CONTRAT DE ROUND-TRIP
// `?edit=` DE L'ÉTUDE, tenu des DEUX côtés et dans les DEUX langages.
//
// LE BUG DE CLASSE QUE CECI FERME. Rouvrir un brouillon (`?edit=`) réinjecte
// dans le formulaire des clés de TÊTE d'`etude_params` (`e.hmt_m`,
// `e.repartition_mt`, `e[q.key]` des réponses commerciales…). Tant que l'écran
// posait `etude_params` EN BLOC, ces clés voyageaient sans jamais avoir été
// déclarées nulle part. QJR62 a introduit un SCHÉMA serveur qui refuse en 400
// toute clé de tête inconnue : une clé relue par le mappeur mais absente du
// schéma casse le round-trip EN SILENCE (l'écran repose ses défauts, et
// l'enregistrement suivant les fige).
//
// TROIS PROPRIÉTÉS, vérifiées par LECTURE DES SOURCES (le mappeur est du JSX
// non exécutable sans node_modules ; `etude_schema.py` est du Python) :
//
//   1. TOUT ce que le mappeur RELIT est ÉCRIT par l'écran — ou figuré dans une
//      liste d'exemptions NOMMÉE (une clé dont un AUTRE propriétaire a la
//      charge). Pas d'oubli muet possible.
//   2. TOUT ce que l'écran ÉCRIT est DÉCLARÉ dans `domain/etude_schema.py` —
//      sinon la fusion QJR62 le refuse en 400.
//   3. Les réponses par catégorie commerciale (`COMMERCIAL_CATEGORY_QUESTIONS`)
//      sont déclarées au schéma, une par une : ajouter une question sans la
//      déclarer ferait rougir ici, pas en production.
//
// Run : node --test src/pages/ventes/DevisGeneratorRoundTripEtude.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { COMMERCIAL_CATEGORY_QUESTIONS } from '../../features/ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')
const SCHEMA_PY = readFileSync(
  join(HERE, '../../../../backend/django_core/apps/ventes/domain/etude_schema.py'),
  'utf8')

// ── Les clés déclarées côté serveur ─────────────────────────────────────────
const CLES_SCHEMA = new Set(
  [...SCHEMA_PY.matchAll(/^ {4}'([a-z0-9_]+)': _cle\(/gm)].map(m => m[1]))

// ── Ce que le mappeur `?edit=` RELIT ────────────────────────────────────────
function blocMappeur() {
  const start = DG.indexOf('const e = d.etude_params || {}')
  assert.ok(start > -1, 'le mappeur `?edit=` de l\'étude est introuvable')
  const end = DG.indexOf('}).catch(() => {', start)
  assert.ok(end > start, 'la fin du mappeur `?edit=` est introuvable')
  return DG.slice(start, end)
}

const CLES_RELUES = new Set(
  [...blocMappeur().matchAll(/\be\.([a-z0-9_]+)\b/g)].map(m => m[1]))

// Clés RELUES que l'écran n'écrit VOLONTAIREMENT pas : chacune a un AUTRE
// propriétaire déclaré. Toute nouvelle exemption doit être motivée ICI.
//
// `scenario` A ÉTÉ RETIRÉ DE CETTE LISTE (passe Fable pré-merge) : l'exempter
// était le bug. Sans écrivain, `etude_params['scenario']` disparaissait, et
// `quote_engine/builder.py` (`_stored_choice`) prenait la branche ARTEFACT —
// total = TOUTES les lignes (deux onduleurs + batterie) pendant que le total
// d'affichage montrait l'option choisie. L'assertion INVERSE est faite plus
// bas (`CHOIX_ECRITS`).
const EXEMPTIONS = {
  gamme: 'écrite par le serveur (`services._set_gamme`), jamais par l\'écran',
  recommended_choice: 'hors schéma ; l\'écran écrit `recommended_option`, la '
    + 'clé DÉCLARÉE — `recommended_choice` reste une lecture tolérante des '
    + 'devis d\'hier',
  injection_82_21: 'drapeau dérivé — le round-trip passe par `injection_dh_an`',
}

//: Les CHOIX du commercial : écrits pour TOUS les marchés (QF7), jamais null.
const CHOIX_ECRITS = new Set(
  [...DG.slice(DG.indexOf('const choixEcran = () => {'),
               DG.indexOf('const entreesReellesEcran ='))
      .matchAll(/choix\.([a-z0-9_]+) =/g)].map(m => m[1]))

// ── Ce que l'écran ÉCRIT, par marché ────────────────────────────────────────
// Toutes les découpes se font DANS `blocEtudeMarche` : `modeInstallation ===
// 'agricole'` apparaît une douzaine de fois ailleurs dans l'écran, un
// `indexOf` global attraperait le mauvais bloc (et le test passerait au vert
// sur les clés d'un autre morceau de code).
const BLOC_MARCHE = (() => {
  const start = DG.indexOf('const blocEtudeMarche = () => {')
  assert.ok(start > -1, 'blocEtudeMarche introuvable')
  const end = DG.indexOf('const persisterDevis', start)
  assert.ok(end > start, 'la fin de blocEtudeMarche est introuvable')
  return DG.slice(start, end)
})()

function clesDe(debut, fin) {
  const start = BLOC_MARCHE.indexOf(debut)
  assert.ok(start > -1, `bloc introuvable : ${debut}`)
  const end = BLOC_MARCHE.indexOf(fin, start)
  assert.ok(end > start, `fin de bloc introuvable : ${fin}`)
  return new Set([...BLOC_MARCHE.slice(start, end)
    .matchAll(/^ {8}([a-z0-9_]+): /gm)].map(m => m[1]))
}

const CLES_COMMUNES = new Set(
  [...DG.slice(DG.indexOf('const entreesReellesEcran = (consoDejaConnue) => {'),
               DG.indexOf('const repartitionMtSaisie = () => {'))
      .matchAll(/entrees\.([a-z0-9_]+) =/g)].map(m => m[1]))

const CLES_IC = clesDe(
  "if (modeInstallation === 'industriel' || modeInstallation === 'commercial') {",
  "if (modeInstallation === 'agricole') {")
const CLES_AGRI = clesDe(
  "if (modeInstallation === 'agricole') {", '// Résidentiel : le serveur')

// La catégorie commerciale est posée par affectation, pas en littéral.
CLES_IC.add('categorie_commerciale')

const CLES_ECRITES = new Set([
  ...CHOIX_ECRITS, ...CLES_COMMUNES, ...CLES_IC, ...CLES_AGRI,
  ...Object.values(COMMERCIAL_CATEGORY_QUESTIONS).flat().map(q => q.key),
])


test('les trois blocs de l\'écran sont bien peuplés (le test se protège de sa propre extraction)', () => {
  assert.ok(CLES_COMMUNES.size >= 3, [...CLES_COMMUNES].join(','))
  assert.ok(CLES_IC.size >= 8, [...CLES_IC].join(','))
  assert.ok(CLES_AGRI.size >= 15, [...CLES_AGRI].join(','))
  assert.ok(CLES_RELUES.size >= 20, [...CLES_RELUES].join(','))
  assert.ok(CLES_SCHEMA.size >= 50, `schéma trop petit : ${CLES_SCHEMA.size}`)
})

test('PROPRIÉTÉ 1 — chaque clé relue par `?edit=` est écrite par l\'écran, ou explicitement exemptée', () => {
  const orphelines = [...CLES_RELUES]
    .filter(cle => !CLES_ECRITES.has(cle) && !(cle in EXEMPTIONS))
  assert.deepEqual(orphelines, [],
    'clés relues au rechargement mais que plus personne n\'écrit — le '
    + 'formulaire reposera ses défauts par-dessus le choix du vendeur : '
    + orphelines.join(', '))
})

test('PROPRIÉTÉ 2 — chaque clé écrite par l\'écran est déclarée dans domain/etude_schema.py', () => {
  const inconnues = [...CLES_ECRITES].filter(cle => !CLES_SCHEMA.has(cle))
  assert.deepEqual(inconnues, [],
    'clés envoyées à la fusion mais absentes du schéma serveur (400 garanti) : '
    + inconnues.join(', '))
})

test('PROPRIÉTÉ 3 — chaque réponse de catégorie commerciale est déclarée au schéma', () => {
  for (const [categorie, questions] of Object.entries(COMMERCIAL_CATEGORY_QUESTIONS)) {
    for (const q of questions) {
      assert.ok(CLES_SCHEMA.has(q.key),
        `réponse « ${q.key} » (catégorie ${categorie}) absente du schéma serveur`)
    }
  }
})

test('AGRICOLE — le round-trip pompage + exploitation est complet des deux côtés', () => {
  for (const cle of ['pompe_cv', 'hmt_m', 'debit_souhaite_m3h', 'heures_pompage',
                     'type_pompe', 'alim', 'profondeur_m', 'distance_m',
                     'irrigation_method', 'region', 'crop', 'surface_ha',
                     'current_fuel', 'fuel_spend_current', 'hmt_static',
                     'hmt_drawdown']) {
    assert.ok(CLES_AGRI.has(cle), `l'écran n'écrit pas ${cle}`)
    assert.ok(CLES_SCHEMA.has(cle), `le schéma ne déclare pas ${cle}`)
  }
  // Et le mappeur les repose bien dans le formulaire.
  for (const cle of ['type_pompe', 'alim', 'distance_m']) {
    assert.ok(CLES_RELUES.has(cle), `le mappeur \`?edit=\` ne relit pas ${cle}`)
  }
})

test('INDUSTRIEL / COMMERCIAL — MT et catégorie font l\'aller-retour', () => {
  for (const cle of ['tension_raccordement', 'repartition_mt',
                     'categorie_commerciale']) {
    assert.ok(CLES_IC.has(cle), `l'écran n'écrit pas ${cle}`)
    assert.ok(CLES_RELUES.has(cle), `le mappeur ne relit pas ${cle}`)
    assert.ok(CLES_SCHEMA.has(cle), `le schéma ne déclare pas ${cle}`)
  }
  // Les réponses de la catégorie retenue partent bien, avec la MÊME coercition
  // de type qu'avant la bascule (nombre / booléen / texte).
  assert.match(BLOC_MARCHE,
    /bloc\[q\.key\] = q\.type === 'number'\s*\r?\n?\s*\? \(parseFloat\(brut\) \|\| 0\)/)
  // La répartition MT n'est envoyée QUE pour un site MT — sinon `null`, ce qui
  // la RETIRE (règle Z2 : jamais une répartition d'hier sur un devis BT).
  const start = DG.indexOf('const repartitionMtSaisie = () => {')
  assert.ok(start > -1, 'repartitionMtSaisie introuvable')
  const bloc = DG.slice(start, DG.indexOf('const blocEtudeMarche', start))
  assert.match(bloc, /if \(tensionRaccordement !== 'mt'\) return null/)
})

test('BLOQUANT FABLE — `scenario` et `recommended_option` ONT un écrivain, pour les QUATRE marchés', () => {
  // Sans `etude_params['scenario']`, `quote_engine/builder.py` prend la
  // branche ARTEFACT et totalise TOUTES les lignes (deux onduleurs +
  // batterie) pendant que le total d'affichage montre l'option choisie.
  for (const cle of ['scenario', 'recommended_option']) {
    assert.ok(CHOIX_ECRITS.has(cle), `l'écran n'écrit plus ${cle}`)
    assert.ok(CLES_SCHEMA.has(cle), `le schéma ne déclare pas ${cle}`)
    assert.ok(!(cle in EXEMPTIONS), `${cle} ne doit plus être exemptée`)
  }
  // Les trois branches de marché les fusionnent (QF7 : tous les modes).
  // On compte dans le CODE, pas dans les commentaires (le bloc en PARLE).
  const codeMarche = BLOC_MARCHE.split(/\r?\n/)
    .filter(l => !/^\s*\/\//.test(l)).join('\n')
  assert.equal((codeMarche.match(/choixEcran\(\)/g) || []).length, 3,
    'les quatre marchés doivent tous porter le choix de l\'écran')
  // JAMAIS `null` pour CES DEUX clés : elles ne sont posées que si l'écran les
  // possède (les envoyer à null les SUPPRIMERAIT et rouvrirait le bug).
  // `nombre_proprietes` est la seule exception assumée du bloc — son propre
  // test, plus bas, explique pourquoi.
  const bloc = DG.slice(DG.indexOf('const choixEcran = () => {'),
                        DG.indexOf('const entreesReellesEcran ='))
  assert.ok(!/choix\.(scenario|recommended_option) = null/.test(bloc),
    'un choix envoyé à null SUPPRIMERAIT la clé côté serveur')
  assert.match(bloc, /if \(scenario\) choix\.scenario = scenario/)
  assert.match(bloc, /if \(recommended\) choix\.recommended_option = recommended/)
})

test('BLOQUANT FABLE — `nombre_proprietes` (×N villas) est écrit, RETIRÉ à N=1, et relu par `?edit=`', () => {
  // `selectors.py` multiplie le total par cette clé (défaut 1) : sans
  // écrivain, un devis ×4 rendait le total d'UNE villa.
  assert.ok(CHOIX_ECRITS.has('nombre_proprietes'), 'clé plus écrite')
  assert.ok(CLES_SCHEMA.has('nombre_proprietes'), 'clé absente du schéma')
  const bloc = DG.slice(DG.indexOf('const choixEcran = () => {'),
                        DG.indexOf('const entreesReellesEcran ='))
  // Écrite avec sa valeur en mode ×N, RETIRÉE (null → règle Z2) sinon : le ×4
  // d'hier ne doit pas survivre à un retour en mono-système.
  assert.match(bloc, /multiMode === 'multiplier' \? parseInt\(nombreProprietes, 10\) : 1/)
  assert.match(bloc,
    /choix\.nombre_proprietes = \(Number\.isFinite\(n\) && n > 1\) \? n : null/)
  // Et le mappeur la relit — sans quoi rouvrir un devis ×4 enverrait `null`
  // au premier enregistrement et DÉTRUIRAIT le ×N en base.
  assert.ok(CLES_RELUES.has('nombre_proprietes'),
    'le mappeur `?edit=` ne relit pas nombre_proprietes')
  assert.match(blocMappeur(), /setMultiMode\('multiplier'\)/)
})

test('RÉSIDENTIEL — aucune clé de marché, seulement les choix et les entrées réelles', () => {
  const start = BLOC_MARCHE.indexOf('// Résidentiel : le serveur est propriétaire')
  assert.ok(start > -1, 'la branche résidentielle est introuvable')
  const bloc = BLOC_MARCHE.slice(start)
  assert.match(bloc, /\{ \.\.\.choixEcran\(\), \.\.\.entreesReellesEcran\(null\) \}/)
  assert.match(bloc, /Object\.keys\(entrees\)\.length \? entrees : null/)
})
