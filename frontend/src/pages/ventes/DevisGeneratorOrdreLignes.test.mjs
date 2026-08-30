// PVORD (fondateur 19/08/2026) — persistance de l'ordre des lignes comme
// ordre par défaut des PROCHAINS devis (`ParametresGammes.ordre_lignes`).
//
// QJR109 — CONVERSION PARTIELLE, ET LA RAISON EST DITE ICI EN CLAIR.
// La cible annoncée était « un test RTL de `LigneTable` ». Deux faits
// VÉRIFIÉS l'interdisent dans ce fichier :
//   1. `generator/LigneTable.jsx` n'exporte QUE son composant par défaut —
//      aucune logique pure à importer et appeler ;
//   2. `autoQuote.js` n'est PAS chargeable sous `node --test` : un
//      `import()` échoue à la première dépendance
//      (« Cannot find module …/features/ventes/store/ventesSlice » — imports
//      sans extension, puis `import.meta.env` via le client axios). C'est
//      exactement pourquoi ces épingles lisent le source.
// La moitié CÂBLAGE (bouton, PATCH, transmission de `ordreLignes` par
// `runAutoQuote`/`createAutoQuote`, absence de `ordre_lignes` dans le corps du
// dry-run) reste donc lue au source — la RETIRER sans rien mettre à la place
// DESSERRERAIT la garde, ce qui est interdit. Elle appelle une spec RTL
// (`render(<LigneTable …/>)`), qui est un travail à part entière et n'a pas sa
// place dans une tâche de conversion de tests.
// Ce qui EST exécutable — la règle que le bouton persiste et que le composeur
// applique — est ajouté en fin de fichier, par appel réel.
//
// Verrouille :
//  1. le bouton « Enregistrer cet ordre comme ordre par défaut » PATCH
//     ParametresGammes.ordre_lignes via deriveRoleOrderFromLines(lines) ;
//  2. les DEUX chemins d'auto-composition (auto-remplir manuel, devis auto)
//     appliquent la préférence société (ordreLignes: gammesConfig?.ordre_lignes) ;
//  3. autoQuote.js accepte + transmet ordreLignes à autoFillLines (même
//     patron que `marques`, déjà verrouillé par solar.marques.test.mjs).
//
// Run : node --test src/pages/ventes/DevisGeneratorOrdreLignes.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
// QJR109 — la moitié EXÉCUTABLE : les deux fonctions PURES que le bouton et le
// composeur utilisent réellement (voir la section en fin de fichier).
import {
  deriveRoleOrderFromLines, orderLinesByRolePreference,
} from '../../features/ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const DG = read('DevisGenerator.jsx')
const AQ = read('../../features/ventes/autoQuote.js')
// QJR100 — la table des lignes (et son bouton « Enregistrer cet ordre ») est
// extraite dans `generator/LigneTable.jsx` ; la DÉRIVATION et l'appel réseau,
// eux, restent dans l'écran. Les épingles suivent chaque moitié chez elle.
const LT = read('generator/LigneTable.jsx')

test('DevisGenerator : importe deriveRoleOrderFromLines de solar.js', () => {
  assert.match(DG, /deriveRoleOrderFromLines,?\s*\n\s*\}\s*from\s*'\.\.\/\.\.\/features\/ventes\/solar'/)
})

test('DevisGenerator : handleSaveOrdreLignes dérive lines puis PATCH ordre_lignes', () => {
  assert.match(DG, /const handleSaveOrdreLignes = async \(\) => \{/)
  assert.match(DG, /const derived = deriveRoleOrderFromLines\(lines\)/)
  assert.match(DG, /ventesApi\.updateParametresGammes\(\{\s*ordre_lignes:\s*derived\s*\}\)/)
})

test('LigneTable : le bouton « Enregistrer cet ordre » appelle handleSaveOrdreLignes', () => {
  assert.match(LT, /onClick=\{handleSaveOrdreLignes\}/)
  assert.match(LT, /Enregistrer cet ordre comme ordre par défaut/)
  // …et l'écran le lui passe bien (le cablage complet, pas seulement le bouton).
  assert.match(DG, /handleSaveOrdreLignes=\{handleSaveOrdreLignes\}/)
  assert.match(DG, /savingOrdreLignes=\{savingOrdreLignes\}/)
})

test('DevisGenerator : la composition locale (auto-remplir manuel) transmet ordreLignes de gammesConfig', () => {
  // U3COMPOSE (26/08/2026) — l'ancien corps de `handleAutoFill` vit désormais
  // dans `composeLocalement()` : c'est lui qui compose l'agricole,
  // l'industriel, le commercial ET le repli résidentiel quand le dry-run
  // serveur est injoignable. La préférence société doit y être transmise
  // EXACTEMENT comme avant — sur le chemin résidentiel nominal, c'est le
  // serveur qui lit `ordre_lignes_societe` (jamais accepté du corps de la
  // requête), verrouillé côté Django.
  const idx = DG.indexOf('const composeLocalement = () => {')
  assert.ok(idx > -1, 'composeLocalement introuvable')
  // Fenêtre bornée à la PREMIÈRE composition (l'appel `composeAvec` suivant
  // est au-delà) : une option perdue ici casse le test.
  const bloc = DG.slice(idx, idx + 1200)
  assert.match(bloc, /marques:\s*marquesActives,/)
  assert.match(bloc, /ordreLignes:\s*gammesConfig\?\.ordre_lignes,/)
})

test('DevisGenerator : le dry-run serveur n\'envoie JAMAIS l\'ordre des lignes dans le corps (lu société-side)', () => {
  const idx = DG.indexOf('const handleAutoFill = async () => {')
  assert.ok(idx > -1, 'handleAutoFill introuvable')
  const debutBody = DG.indexOf('const body = {', idx)
  const appel = DG.indexOf('ventesApi.composerDevis(body)', idx)
  assert.ok(debutBody > -1 && appel > debutBody, 'construction du corps du dry-run introuvable')
  const bloc = DG.slice(debutBody, appel)
  assert.doesNotMatch(bloc, /ordre_lignes/,
    'l\'ordre des lignes est un réglage société lu par le serveur — jamais accepté du corps')
})

test('DevisGenerator : runAutoQuote (devis auto) transmet ordreLignes à createAutoQuote', () => {
  const idx = DG.indexOf('const runAutoQuote = async')
  assert.ok(idx > -1, 'runAutoQuote introuvable')
  const bloc = DG.slice(idx, idx + 1600)
  assert.match(bloc, /marques:\s*marquesActives,/)
  assert.match(bloc, /ordreLignes:\s*gammesConfig\?\.ordre_lignes,/)
})

test('autoQuote.js : createAutoQuote accepte ordreLignes et le transmet à autoFillLines', () => {
  assert.match(AQ, /targetKwc,\s*marques,\s*ordreLignes\s*\}\)\s*\{/)
  const idx = AQ.indexOf('rows = autoFillLines(produits, {')
  assert.ok(idx > -1, 'appel autoFillLines introuvable dans autoQuote.js')
  const bloc = AQ.slice(idx, idx + 400)
  assert.match(bloc, /marques,/)
  assert.match(bloc, /ordreLignes,/)
})

// ── LA MOITIÉ EXÉCUTABLE (QJR109) ──────────────────────────────────────────
// Ce que le bouton PERSISTE et ce que le composeur EN FAIT sont deux fonctions
// PURES de `solar.js` : elles sont ici APPELÉES, pas décrites. Le round-trip
// complet — lignes à l'écran → préférence enregistrée → composition suivante —
// est ainsi prouvé sans React.

test('PVORD — round-trip : l’ordre TAPÉ à l’écran devient la préférence, et la préférence réordonne la composition suivante', () => {
  const lignesEcran = [
    { designation: 'Batterie Deye 16 kWh' },
    { designation: 'Onduleur hybride Deye SG05LP3' },
    { designation: 'Panneau JA Solar 710W' },
  ]
  const preference = deriveRoleOrderFromLines(lignesEcran)
  assert.deepEqual(preference, ['batterie', 'onduleur_hybride', 'panneau'],
    'la préférence enregistrée est l’ordre RÉEL de l’écran')

  // La composition suivante arrive dans l'ordre canonique du catalogue…
  const composition = [
    ['panneau', { designation: 'Panneau JA Solar 710W' }],
    ['onduleur_hybride', { designation: 'Onduleur hybride Deye SG05LP3' }],
    ['batterie', { designation: 'Batterie Deye 16 kWh' }],
  ]
  const rendu = orderLinesByRolePreference(composition, preference)
  assert.deepEqual(rendu.map(l => l.designation), [
    'Batterie Deye 16 kWh',
    'Onduleur hybride Deye SG05LP3',
    'Panneau JA Solar 710W',
  ], '…et ressort dans l’ordre que le commercial avait enregistré')
})

test('PVORD — sans préférence enregistrée, l’ordre canonique est rendu INCHANGÉ', () => {
  const composition = [
    ['panneau', { designation: 'Panneau' }],
    ['batterie', { designation: 'Batterie' }],
  ]
  for (const vide of [null, undefined, []]) {
    assert.deepEqual(
      orderLinesByRolePreference(composition, vide).map(l => l.designation),
      ['Panneau', 'Batterie'], `préférence ${JSON.stringify(vide)}`)
  }
})

test('PVORD — un rôle absent de la préférence garde son rang canonique, TOUJOURS après les rôles préférés', () => {
  const composition = [
    ['panneau', { designation: 'Panneau' }],
    ['cable', { designation: 'Câble solaire DC' }],
    ['batterie', { designation: 'Batterie' }],
  ]
  assert.deepEqual(
    orderLinesByRolePreference(composition, ['batterie']).map(l => l.designation),
    ['Batterie', 'Panneau', 'Câble solaire DC'])
})

test('PVORD — la dérivation déduplique et ignore ce qu’elle ne sait pas classer (jamais un rôle inventé)', () => {
  const preference = deriveRoleOrderFromLines([
    { designation: 'Batterie Deye 16 kWh' },
    { designation: 'Batterie Deye 8 kWh' },
    { designation: '— Prestations —' },
    { designation: '' },
    { designation: 'Panneau JA Solar 710W' },
  ])
  assert.deepEqual(preference, ['batterie', 'panneau'],
    'deux batteries ne comptent que pour UN rang, une section n’en vaut aucun')
  assert.deepEqual(deriveRoleOrderFromLines(null), [])
})

test('PVORD — acier et aluminium sont deux rangs DISTINCTS (une structure n’est pas l’autre)', () => {
  assert.deepEqual(
    deriveRoleOrderFromLines([{ designation: 'Structure aluminium tuiles' }]),
    ['structure_alu'])
  assert.deepEqual(
    deriveRoleOrderFromLines([{ designation: 'Structure acier galvanisé' }]),
    ['structure_acier'])
})
