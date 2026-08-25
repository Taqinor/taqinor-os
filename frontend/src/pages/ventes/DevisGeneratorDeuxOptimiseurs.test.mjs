// L-2OPT (fondateur 24/08/2026) — « deux optimiseurs indépendants ». Un devis
// résidentiel « Les deux (Sans + Avec) » compose SANS et AVEC séparément
// (chacun son propre kWc payback-optimal) puis fusionne les deux tableaux de
// lignes en une seule table taguée `variante`. DevisGenerator.jsx est du
// JSX/ESM non exécutable par `node --test` sans node_modules (React, Redux
// dispatch réel) : ce test lit donc le SOURCE, même patron que
// DevisGeneratorOrdreLignes.test.mjs / DevisGeneratorNbPanneauxTouched.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorDeuxOptimiseurs.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')
const SOLAR = readFileSync(join(HERE, '../../features/ventes/solar.js'), 'utf8')
const LINE_ROW = readFileSync(join(HERE, 'DevisLineRow.jsx'), 'utf8')

// Extrait le contenu d'un bloc `{ ... }` en comptant les accolades (fiable
// même avec des accolades imbriquées) — même utilitaire que
// DevisGeneratorNbPanneauxTouched.test.mjs.
function extractBracedBlock(src, openBraceIdx) {
  assert.equal(src[openBraceIdx], '{', 'index ne pointe pas sur une accolade ouvrante')
  let depth = 0
  for (let i = openBraceIdx; i < src.length; i++) {
    if (src[i] === '{') depth++
    else if (src[i] === '}') {
      depth--
      if (depth === 0) return { body: src.slice(openBraceIdx + 1, i), endIdx: i }
    }
  }
  throw new Error('accolade fermante introuvable')
}

test('DevisGenerator : fusionnerVariantes est importé de solar.js', () => {
  assert.match(DG, /fusionnerVariantes,?\s*\n/)
  assert.match(DG, /\}\s*from\s*'\.\.\/\.\.\/features\/ventes\/solar'/)
})

test('computeAutoSizing : calcule les DEUX optima (sans + avec), le SANS reste au niveau plat (contrat NbPanneauxTouched)', () => {
  const needle = 'const computeAutoSizing = useCallback((hiverVal, eteVal) => {'
  const start = DG.indexOf(needle)
  assert.ok(start > -1, 'computeAutoSizing introuvable')
  const { body } = extractBracedBlock(DG, start + needle.length - 1)
  // Le premier balayage (SANS) est inchangé.
  assert.match(body, /const opt = optimalKwcByPayback\(\{/)
  // Le second balayage (AVEC) existe, avec avecBatterie: true — jamais utilisé
  // avant L-2OPT.
  assert.match(body, /const optAvec = optimalKwcByPayback\(\{/)
  assert.match(body, /avecBatterie:\s*true,/)
  // Le résultat plat reste le SANS (spread `sansPart`) — contrat gardé par
  // DevisGeneratorNbPanneauxTouched.test.mjs (`sizing.nbPanneaux`).
  assert.match(body, /result = \{ \.\.\.sansPart, avec: avecPart \}/)
  // Jamais de chiffre inventé : sans optimum AVEC exploitable, repli sur le SANS.
  assert.match(body, /avecPart = \(optAvec\.nbPanneaux > 0\) \? \{ besoinKwc, \.\.\.optAvec \} : sansPart/)
})

test('resolveKwcAvec : respecte nbPanneauxTouched, priorise le serveur (recommandation_avec), replie sur le local puis kwc_sans', () => {
  const needle = 'const resolveKwcAvec = () => {'
  const start = DG.indexOf(needle)
  assert.ok(start > -1, 'resolveKwcAvec introuvable')
  const { body } = extractBracedBlock(DG, start + needle.length - 1)
  // 1. touché → kwc_sans pour les deux branches (aucune divergence recomposée
  //    par-dessus un choix déjà fait par l'utilisateur).
  assert.match(body, /if \(nbPanneauxTouched\.current\) return kwp/)
  // 2. le moteur horaire serveur (source de vérité) prime dès qu'il a répondu.
  assert.match(body, /etudeHoraireDonnees\?\.dimensionnement\?\.recommandation_avec/)
  // 3. repli local (même balayage payback que computeAutoSizing, objectif avec).
  assert.match(body, /computeAutoSizing\(fHiver, fEte\)/)
  assert.match(body, /sizing\?\.avec\?\.kwcOptimal/)
  // 4. repli ultime : kwc_sans (jamais un chiffre inventé).
  const lastReturn = body.lastIndexOf('return kwp')
  assert.ok(lastReturn > -1)
})

test('handleAutoFill : la PREMIÈRE composition (SANS) reste EXACTEMENT celle d\'avant L-2OPT', () => {
  const idx = DG.indexOf('const handleAutoFill = ()')
  assert.ok(idx > -1, 'handleAutoFill introuvable')
  const bloc = DG.slice(idx, idx + 2200)
  // Contrat gardé par DevisGeneratorOrdreLignes.test.mjs — la fenêtre de 2200
  // caractères doit encore contenir ces deux lignes SANS décalage.
  assert.match(bloc, /marques:\s*marquesActives,/)
  assert.match(bloc, /ordreLignes:\s*gammesConfig\?\.ordre_lignes,/)
})

test('handleAutoFill : mono « Avec batterie » compose l\'optimum AVEC SEUL, sans fusion', () => {
  const idx = DG.indexOf('const handleAutoFill = ()')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx, idx + 3600)
  assert.match(bloc, /scenario === SCENARIO_LES_DEUX \|\| scenario === SCENARIO_AVEC/)
  assert.match(bloc, /const kwpAvec = resolveKwcAvec\(\)/)
  assert.match(bloc, /if \(scenario === SCENARIO_AVEC\) \{\s*\n\s*\/\/ mono avec : compose l'optimum AVEC seul, aucune fusion\.\s*\n\s*generated = composeAvec\(\)/)
})

test('handleAutoFill : « Les deux » fusionne (fusionnerVariantes) et déduplique les avertissements des DEUX compositions', () => {
  const idx = DG.indexOf('const handleAutoFill = ()')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx, idx + 3600)
  assert.match(bloc, /generated = fusionnerVariantes\(lignesSans, lignesAvec\)/)
  assert.match(bloc, /generated\.onduleursIncomplets = dedupeParCle\(/)
  assert.match(bloc, /generated\.marquesManquantes = dedupeParCle\(/)
})

test('handleAutoFill : industriel\\/commercial\\/agricole restent AVANT toute logique L-2OPT (zéro changement)', () => {
  const idx = DG.indexOf('const handleAutoFill = ()')
  const idxAgricole = DG.indexOf("if (modeInstallation === 'agricole')", idx)
  const idxL2opt = DG.indexOf("modeInstallation === 'residentiel'", idx)
  assert.ok(idxAgricole > -1 && idxL2opt > -1)
  assert.ok(idxAgricole < idxL2opt, 'le branchement agricole doit précéder (et donc `return` avant) toute logique L-2OPT')
})

test('withKeys\\/emptyLine\\/structureLine portent toutes `variante` (défaut \'\' — commun, comportement historique)', () => {
  assert.match(DG, /variante: r\.variante \?\? '',\s*\n\}\)\)/)
  const emptyIdx = DG.indexOf('const emptyLine = () => ({')
  assert.ok(emptyIdx > -1)
  const { body: emptyBody } = extractBracedBlock(DG, DG.indexOf('({', emptyIdx) + 1)
  assert.match(emptyBody, /variante: '',/)
})

test('persisterDevis : chaque ligne produit envoie `variante` au serveur', () => {
  assert.match(DG, /variante: l\.variante \|\| '',/)
})

test('DevisLineRow : badge de variante posé UNIQUEMENT quand `variante` est \'sans\'\\/\'avec\' (aucun bruit sur le cas commun)', () => {
  assert.match(LINE_ROW, /l\.variante === 'sans'/)
  assert.match(LINE_ROW, /l\.variante === 'avec'/)
  assert.match(LINE_ROW, /Option sans batterie/)
  assert.match(LINE_ROW, /Option avec batterie/)
})

test('tableau de dimensionnement : la ligne recommandation_avec est surlignée DISTINCTEMENT de la ligne recommandation (sans)', () => {
  assert.match(DG, /const estRecommandeeAvec = etudeHoraireDonnees\?\.dimensionnement\s*\n\s*\?\.recommandation_avec\?\.panneaux === ligne\.panneaux/)
})

test('solar.js : fusionnerVariantes est exporté (pure, testable sous node --test)', () => {
  assert.match(SOLAR, /export function fusionnerVariantes\(lignesSans, lignesAvec\)/)
})

test('solar.js : optionTotalsTTC\\/batteryKwhFromLines\\/computeROI filtrent `variante` — jamais de régression sur les lignes legacy', () => {
  assert.match(SOLAR, /l\.variante !== 'avec'/)
  assert.match(SOLAR, /l\.variante !== 'sans'/)
  assert.match(SOLAR, /if \(l\.variante === 'sans'\) return sum/)
})
