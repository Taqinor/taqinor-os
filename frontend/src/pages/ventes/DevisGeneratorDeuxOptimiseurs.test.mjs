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

// U3COMPOSE (26/08/2026) — l'ancien corps de `handleAutoFill` a été extrait
// TEL QUEL dans `composeLocalement()` : c'est lui qui compose le chemin
// agricole/industriel/commercial ET le repli résidentiel quand le dry-run
// serveur est indisponible. Les épingles L-2OPT ci-dessous le suivent donc là
// où le comportement vit désormais — elles cassent toujours si ce
// comportement disparaît.
const COMPOSE_LOCALEMENT = 'const composeLocalement = () => {'
const HANDLE_AUTOFILL = 'const handleAutoFill = async () => {'

function corpsDe(needle, quoi) {
  const start = DG.indexOf(needle)
  assert.ok(start > -1, `${quoi} introuvable`)
  return extractBracedBlock(DG, start + needle.length - 1).body
}

// Options passées au PREMIER appel `autoFillLines(produits, { … })` d'un corps
// (la composition SANS) — bornées à cet appel, jamais à la fenêtre entière :
// une option perdue ici casse le test même si `composeAvec` la porte encore.
function premieresOptionsAutoFill(corps) {
  const needle = 'autoFillLines(produits, {'
  const i = corps.indexOf(needle)
  assert.ok(i > -1, 'appel autoFillLines introuvable')
  return extractBracedBlock(corps, i + needle.length - 1).body
}

test('composeLocalement : la PREMIÈRE composition (SANS) reste EXACTEMENT celle d\'avant L-2OPT', () => {
  const options = premieresOptionsAutoFill(corpsDe(COMPOSE_LOCALEMENT, 'composeLocalement'))
  // Contrat partagé avec DevisGeneratorOrdreLignes.test.mjs.
  assert.match(options, /marques:\s*marquesActives,/)
  assert.match(options, /ordreLignes:\s*gammesConfig\?\.ordre_lignes,/)
})

test('mono « Avec batterie » compose l\'optimum AVEC SEUL, sans fusion (repli local ET dry-run serveur)', () => {
  // 1. Repli local (ex-corps de handleAutoFill) : inchangé.
  const local = corpsDe(COMPOSE_LOCALEMENT, 'composeLocalement')
  assert.match(local, /scenario === SCENARIO_LES_DEUX \|\| scenario === SCENARIO_AVEC/)
  assert.match(local, /const kwpAvec = resolveKwcAvec\(\)/)
  assert.match(local, /if \(scenario === SCENARIO_AVEC\) \{\s*\n\s*\/\/ mono avec : compose l'optimum AVEC seul, aucune fusion\.\s*\n\s*generated = composeAvec\(\)/)
  // 2. Chemin dry-run serveur (U3COMPOSE) : même règle. Le serveur fusionne
  //    DEUX champs dès qu'il reçoit `dimensionnement_avec` — un mono « Avec »
  //    doit donc envoyer le kWc AVEC comme puissance UNIQUE, jamais
  //    `dimensionnement_avec`.
  const serveur = corpsDe(HANDLE_AUTOFILL, 'handleAutoFill')
  assert.match(serveur, /const kwpAvec = resolveKwcAvec\(\)/)
  assert.match(
    serveur,
    /if \(scenario === SCENARIO_AVEC\) \{[\s\S]{0,700}?body\.kwc = kwpAvec\s*\n\s*\} else \{\s*\n\s*body\.dimensionnement_avec = buildDimensionnementAvec\(kwpAvec\)/,
    'le mono « Avec » doit composer sur kwpAvec seul (pas de dimensionnement_avec, qui déclencherait la fusion serveur)')
})

test('« Les deux » fusionne (fusionnerVariantes) et déduplique les avertissements des DEUX compositions', () => {
  const local = corpsDe(COMPOSE_LOCALEMENT, 'composeLocalement')
  assert.match(local, /generated = fusionnerVariantes\(lignesSans, lignesAvec\)/)
  assert.match(local, /generated\.onduleursIncomplets = dedupeParCle\(/)
  assert.match(local, /generated\.marquesManquantes = dedupeParCle\(/)
  // Chemin serveur : la fusion à deux champs est demandée par
  // `dimensionnement_avec` (le serveur compose alors les deux variantes).
  const serveur = corpsDe(HANDLE_AUTOFILL, 'handleAutoFill')
  assert.match(serveur, /body\.dimensionnement_avec = buildDimensionnementAvec\(kwpAvec\)/)
})

test('handleAutoFill : industriel\\/commercial\\/agricole restent AVANT toute logique L-2OPT (zéro changement)', () => {
  const corps = corpsDe(HANDLE_AUTOFILL, 'handleAutoFill')
  const idxAgricole = corps.indexOf("if (modeInstallation === 'agricole')")
  const idxL2opt = corps.indexOf("modeInstallation === 'residentiel'")
  assert.ok(idxAgricole > -1 && idxL2opt > -1)
  assert.ok(idxAgricole < idxL2opt, 'le branchement agricole doit précéder (et donc `return` avant) toute logique L-2OPT')
  // Industriel/commercial : AUCUN dry-run serveur — ils tombent sur la
  // composition locale, en sortie de fonction, après le `return` résidentiel.
  const idxReplique = corps.lastIndexOf('composeLocalement()')
  assert.ok(idxReplique > idxL2opt, 'industriel/commercial doivent finir sur composeLocalement()')
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
  // F14 (26/08/2026) — le filtre par variante a été FACTORISÉ dans les deux
  // prédicats `appartientAuPanierSans/Avec` (miroir exact de builder.py
  // `_repartir_options`) : une ligne DÉCLARÉE tranche seule, une ligne SANS
  // `variante` retombe sur les mots-clés — le comportement legacy, mot pour
  // mot. L'épingle suit la factorisation ; elle casse toujours si l'un des
  // deux étages disparaît.
  // Portée = la fonction visée SEULE (de sa déclaration au prochain `export`
  // de premier niveau) : une assertion ne peut pas être satisfaite par une
  // autre fonction du fichier.
  const bloc = (needle, quoi) => {
    const i = SOLAR.indexOf(needle)
    assert.ok(i > -1, `${quoi} introuvable`)
    const fin = SOLAR.indexOf('\nexport ', i + needle.length)
    return SOLAR.slice(i, fin > -1 ? fin : SOLAR.length)
  }
  const panierSans = bloc('export function appartientAuPanierSans(l) {', 'appartientAuPanierSans')
  assert.match(panierSans, /if \(v === 'avec'\) return false/)
  assert.match(panierSans, /if \(v === 'sans'\) return true/)
  // Repli mot-clé pour une ligne SANS variante : comportement historique.
  assert.match(panierSans, /return !isBattery\(l\?\.designation\) && !isHybridInverter\(l\?\.designation\)/)
  const panierAvec = bloc('export function appartientAuPanierAvec(l) {', 'appartientAuPanierAvec')
  assert.match(panierAvec, /if \(v === 'sans'\) return false/)
  assert.match(panierAvec, /if \(v === 'avec'\) return true/)
  assert.match(panierAvec, /return !isReseauInverter\(l\?\.designation\)/)
  // Les DEUX consommateurs des paniers les utilisent RÉELLEMENT.
  const totaux = bloc('export function optionTotalsTTC(lines, discountPct) {', 'optionTotalsTTC')
  assert.match(totaux, /\.filter\(appartientAuPanierSans\)/)
  assert.match(totaux, /\.filter\(appartientAuPanierAvec\)/)
  const roi = bloc('export function computeROI({', 'computeROI')
  assert.match(roi, /const linesSans = lines\.filter\(l => appartientAuPanierSans\(l\)\)/)
  assert.match(roi, /const linesAvec = lines\.filter\(l => appartientAuPanierAvec\(l\)\)/)
  // batteryKwhFromLines / batteryCapaciteInconnue : une ligne taguée 'sans' ne
  // compte JAMAIS dans une capacité batterie.
  assert.match(SOLAR, /if \(l\.variante === 'sans'\) return sum/)
  assert.match(SOLAR, /isBattery\(l\.designation\) && l\.variante !== 'sans'/)
})
