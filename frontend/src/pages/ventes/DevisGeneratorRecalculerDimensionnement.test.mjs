// FOUNDER 26/08/2026 — « ça ne recalcule pas le meilleur choix (nombre de
// panneaux) quand on change [la facture] — il devrait y avoir un BOUTON qui
// recalcule ». Cause racine (confirmée en lisant DevisGenerator.jsx) :
//   1. En ÉDITION (?edit=ID), `nbPanneaux` est posé UNE fois depuis les
//      lignes du brouillon rouvert (comptage des lignes « panneau »), mais
//      `fHiver`/`fEte` ne sont JAMAIS reposées depuis le devis serveur (aucun
//      champ `etude_params` ne les porte encore) — retaper une facture part
//      donc d'un champ vide, pas de la facture d'origine.
//   2. `syncBillEstimator` (déclenché à chaque frappe hiver/été) respecte
//      DÉJÀ le garde-fou `nbPanneauxTouched` (N3) : une fois ce drapeau posé
//      — ce qui arrive dès qu'un nombre de panneaux a été affiché/retouché —
//      plus AUCUNE frappe sur la facture ne recalcule quoi que ce soit.
//   3. Le bouton « Auto-remplir » existant (`handleAutoFill`) ne fait que
//      RECOMPOSER le catalogue au `nbPanneaux`/`kwp` COURANT : il ne relit
//      jamais la facture pour redériver ce compte.
// Correctif : un bouton EXPLICITE « Recalculer le dimensionnement »
// (`recalculerDimensionnement`) qui déverrouille temporairement le garde-fou,
// rejoue le MÊME balayage palier/payback que `computeAutoSizing` sur la
// facture ACTUELLE (sans ET avec batterie, L-2OPT), pose les deux résultats,
// puis relance la composition par le chemin EXACT du bouton « Auto-remplir »
// (`handleAutoFill`, jamais une seconde règle de composition) — et reverrouille
// le garde-fou ensuite, pour qu'une frappe seule reste silencieuse comme
// demandé par le fondateur.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE,
// même patron que DevisGeneratorNbPanneauxTouched.test.mjs /
// DevisGeneratorDeuxOptimiseurs.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorRecalculerDimensionnement.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

// Même utilitaire que les tests voisins : extrait le contenu d'un bloc `{ … }`
// en comptant les accolades (fiable même imbriqué).
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

function corpsDe(needle, quoi) {
  const start = DG.indexOf(needle)
  assert.ok(start > -1, `${quoi} introuvable`)
  return extractBracedBlock(DG, start + needle.length - 1).body
}

// ── Root cause : preuves lisibles dans le source ──

test('ROOT CAUSE 1 — le chargement d\'édition (?edit=ID) ne repose JAMAIS fHiver/fEte depuis le devis serveur', () => {
  const idx = DG.indexOf('if (!editId || editLoaded.current) return')
  assert.ok(idx > -1, 'effet de chargement édition introuvable')
  const end = DG.indexOf('}, [editId]) // eslint-disable-line react-hooks/exhaustive-deps', idx)
  assert.ok(end > -1)
  const bloc = DG.slice(idx, end)
  assert.doesNotMatch(bloc, /setFHiver\(/, 'régression : fHiver est désormais reposée en édition — ce test/le correctif doivent être revus')
  assert.doesNotMatch(bloc, /setFEte\(/, 'régression : fEte est désormais reposée en édition — ce test/le correctif doivent être revus')
  // Le nombre de panneaux, lui, EST posé (depuis le comptage des lignes) —
  // c'est ce compte qui reste figé sans le bouton de recalcul.
  assert.match(bloc, /if \(panneaux > 0\) setNbPanneaux\(String\(panneaux\)\)/)
})

test('ROOT CAUSE 2 — syncBillEstimator() ne recompose JAMAIS les lignes (setLines/handleAutoFill absents), garde nbPanneauxTouched déjà en place', () => {
  const bloc = corpsDe('const syncBillEstimator = (hiverVal, eteVal) => {', 'syncBillEstimator')
  assert.doesNotMatch(bloc, /setLines\(/)
  assert.doesNotMatch(bloc, /handleAutoFill/)
  assert.match(bloc, /if \(!nbPanneauxTouched\.current\) \{/)
})

test('ROOT CAUSE 3 — la branche RÉSIDENTIELLE de handleAutoFill() ne redérive JAMAIS nbPanneaux depuis la facture : elle lit `kwp` (nbPanneaux COURANT), jamais computeAutoSizing', () => {
  const bloc = corpsDe('const handleAutoFill = async () => {', 'handleAutoFill')
  assert.doesNotMatch(bloc, /computeAutoSizing/,
    'handleAutoFill ne doit pas redériver le dimensionnement lui-même : c\'est exactement le bug — il recompose au nbPanneaux courant, jamais depuis la facture')
  // Scope la branche résidentielle SEULE (de son `if` jusqu'au `composeLocalement()`
  // de fin de fonction, hors branche agricole ci-dessus qui pose bien nbPanneaux
  // depuis pompageSel — hors sujet ici, dimensionnement HMT/débit, pas facture).
  const residentielIdx = bloc.indexOf("if (modeInstallation === 'residentiel') {")
  assert.ok(residentielIdx > -1)
  const residentielBloc = bloc.slice(residentielIdx)
  assert.doesNotMatch(residentielBloc, /setNbPanneaux/,
    'la branche résidentielle ne pose jamais nbPanneaux — recomposer avec le compte courant est le comportement historique, inchangé')
})

// ── Le correctif : bouton + fonction ──

test('recalculerDimensionnement() : sans facture hiver exploitable, pose une erreur et ne touche RIEN d\'autre', () => {
  const bloc = corpsDe('const recalculerDimensionnement = () => {', 'recalculerDimensionnement')
  const idxNull = bloc.indexOf('if (!sizing) {')
  assert.ok(idxNull > -1)
  const { body: guardBody } = extractBracedBlock(bloc, idxNull + 'if (!sizing) {'.length - 1)
  assert.match(guardBody, /recalcDim:/)
  assert.match(guardBody, /return/)
})

test('recalculerDimensionnement() : déverrouille nbPanneauxTouched AVANT de poser sizingInfo/kwcCible/nbPanneaux, jamais un chiffre inventé (computeAutoSizing réel)', () => {
  const bloc = corpsDe('const recalculerDimensionnement = () => {', 'recalculerDimensionnement')
  assert.match(bloc, /const sizing = computeAutoSizing\(fHiver, fEte\)/)
  const unlockIdx = bloc.indexOf('nbPanneauxTouched.current = false')
  assert.ok(unlockIdx > -1, 'le garde-fou doit être déverrouillé — sinon resolveKwcAvec() court-circuite sur kwp et les deux optimiseurs ne divergent plus jamais')
  const setNbIdx = bloc.indexOf('setNbPanneaux(String(retenu.nbPanneaux))')
  assert.ok(setNbIdx > -1)
  assert.ok(unlockIdx < setNbIdx, 'le déverrouillage doit précéder la pose du nombre de panneaux')
  // Choix sans/avec : même patron que applyLead/applySiteProfile/syncBillEstimator.
  assert.match(bloc, /const retenu = \(modeInstallation === 'residentiel' && scenario === SCENARIO_AVEC\)\s*\n\s*\? sizing\.avec : sizing/)
  assert.match(bloc, /setSizingInfo\(retenu\)/)
  assert.match(bloc, /setKwcCible\(retenu\.kwcOptimal/)
})

test('recalculerDimensionnement() : déclenche la recomposition via un COMPTEUR dédié (jamais un effet calé sur nbPanneaux qui pourrait ne pas se redéclencher à compte inchangé)', () => {
  const bloc = corpsDe('const recalculerDimensionnement = () => {', 'recalculerDimensionnement')
  assert.match(bloc, /recalcDimPending\.current = true/)
  assert.match(bloc, /setRecalcDimTick\(t => t \+ 1\)/)
})

test('l\'effet du recalcul appelle EXACTEMENT handleAutoFill() (même chemin que le bouton « Auto-remplir » — dry-run serveur + repli composeLocalement, aucune règle de composition dupliquée), puis reverrouille nbPanneauxTouched', () => {
  const idx = DG.indexOf('if (!recalcDimPending.current) return')
  assert.ok(idx > -1, 'effet du recalcul introuvable')
  const depsIdx = DG.indexOf('}, [recalcDimTick])', idx)
  assert.ok(depsIdx > -1)
  const bloc = DG.slice(idx, depsIdx)
  assert.match(bloc, /recalcDimPending\.current = false/)
  assert.match(bloc, /handleAutoFill\(\)/)
  assert.match(bloc, /nbPanneauxTouched\.current = true/)
})

// ── Le bouton (JSX) ──

test('bouton « Recalculer le dimensionnement » : visible en création ET en édition (aucune condition editId), désactivé sans facture ni en agricole', () => {
  const idx = DG.indexOf('data-testid="btn-recalculer-dimensionnement"')
  assert.ok(idx > -1, 'bouton introuvable')
  const bloc = DG.slice(Math.max(0, idx - 400), idx + 400)
  assert.match(bloc, /onClick=\{recalculerDimensionnement\}/)
  assert.match(bloc, /disabled=\{!\(parseFloat\(fHiver\) > 0\) \|\| modeInstallation === 'agricole'\}/)
  assert.match(bloc, /Recalculer le dimensionnement/)
  // Aucune garde `editId`/`embedded` autour du bouton : même bouton dans les
  // deux modes (le composant DevisGenerator sert les deux routes).
  assert.doesNotMatch(bloc, /editId &&[\s\S]{0,60}btn-recalculer/i)
})

// ── Les DEUX valeurs affichées (L-2OPT) ──

test('deuxValeursDim : résidentiel UNIQUEMENT — agricole (pompage) et industriel/commercial ne fabriquent jamais de valeur « avec »', () => {
  const bloc = corpsDe('const deuxValeursDim = (() => {', 'deuxValeursDim')
  assert.match(bloc, /if \(modeInstallation !== 'residentiel'\) return \{ sans: null, avec: null \}/)
})

test('deuxValeursDim : le serveur horaire (recommandation\\/recommandation_avec) prime, repli sur sizingInfo (ÉTAT, jamais recalculé pendant le rendu — react-hooks/refs) — jamais un chiffre inventé si rien n\'est calculable (null)', () => {
  const bloc = corpsDe('const deuxValeursDim = (() => {', 'deuxValeursDim')
  assert.match(bloc, /etudeHoraireDonnees\?\.dimensionnement\?\.recommandation\b/)
  assert.match(bloc, /etudeHoraireDonnees\?\.dimensionnement\?\.recommandation_avec/)
  // Jamais un appel à computeAutoSizing ICI : il lirait sizingCacheRef.current
  // PENDANT le rendu (deuxValeursDim est une const calculée en ligne dans le
  // corps du composant, pas dans un effet/gestionnaire) — interdit par la
  // règle ESLint react-hooks/refs, vérifiée en CI (backend-lint côté frontend).
  assert.doesNotMatch(bloc, /computeAutoSizing/)
  assert.match(bloc, /const localSans = \(scenario === SCENARIO_AVEC\) \? null : sizingInfo/)
  assert.match(bloc, /const localAvec = \(scenario === SCENARIO_AVEC\) \? sizingInfo : sizingInfo\?\.avec/)
  assert.match(bloc, /: null\)/)
})

test('affichage : le bloc « Sans batterie / Avec batterie » est résidentiel-only ET respecte showSans\\/showAvec (mono-option = une seule valeur, jamais les deux fabriquées)', () => {
  const idx = DG.indexOf('data-testid="dimensionnement-deux-valeurs"')
  assert.ok(idx > -1, 'bloc deux-valeurs introuvable')
  const bloc = DG.slice(Math.max(0, idx - 400), idx + 700)
  assert.match(bloc, /modeInstallation === 'residentiel'/)
  assert.match(bloc, /\{showSans && deuxValeursDim\.sans && \(/)
  assert.match(bloc, /\{showAvec && deuxValeursDim\.avec && \(/)
  assert.match(bloc, /Sans batterie : <strong>\{deuxValeursDim\.sans\.nbPanneaux\} panneaux<\/strong>/)
  assert.match(bloc, /Avec batterie : <strong>\{deuxValeursDim\.avec\.nbPanneaux\} panneaux<\/strong>/)
})

test('showSans\\/showAvec (contrat mono-option existant) restent la SEULE source de vérité pour ce qui est vendu sur le devis — non redéfinis par ce chantier', () => {
  assert.match(DG, /const showSans = scenario !== 'Avec batterie'/)
  assert.match(DG, /const showAvec = scenario !== 'Sans batterie'/)
})
