// FOUNDER 26/08/2026 — « ça ne recalcule pas le meilleur choix (nombre de
// panneaux) quand on change [la facture] — il devrait y avoir un BOUTON qui
// recalcule ». Causes RÉELLES (confirmées en lisant DevisGenerator.jsx —
// corrigé après une revue adversariale qui a prouvé que la toute première
// version de ce commentaire avait la cause #2 À L'ENVERS, voir plus bas) :
//   1. En ÉDITION (?edit=ID), `nbPanneaux` est posé UNE fois depuis les
//      lignes du brouillon rouvert (comptage des lignes « panneau »), mais
//      `fHiver`/`fEte` ne sont JAMAIS reposées depuis le devis serveur (aucun
//      champ `etude_params` ne les porte encore) — retaper une facture part
//      donc d'un champ vide, pas de la facture d'origine.
//   2. Le bouton « Auto-remplir » existant (`handleAutoFill`) ne fait que
//      RECOMPOSER le catalogue au `nbPanneaux`/`kwp` COURANT : il ne relit
//      jamais la facture pour redériver ce compte (jamais un appel à
//      `computeAutoSizing`).
//   3. `syncBillEstimator` (déclenché à chaque frappe hiver/été) respecte
//      DÉJÀ le garde-fou `nbPanneauxTouched` (N3) : une fois ce drapeau posé
//      — ce qui arrive dès qu'un nombre de panneaux a été touché À LA MAIN,
//      n'importe où dans la session — plus AUCUNE frappe sur la facture ne
//      recalcule quoi que ce soit. IMPORTANT (revue adversariale 26/08) :
//      CE N'EST PAS SPÉCIFIQUE À L'ÉDITION — rien dans l'effet de chargement
//      ?edit= (lignes ~1544-1640) ne touche ce ref ; il reste à sa valeur
//      `useRef(false)` par défaut juste après un chargement d'édition (donc
//      OUVERT, pas fermé). La version initiale de ce commentaire affirmait
//      le contraire — corrigée ici après preuve du reviewer.
// Correctif : un bouton EXPLICITE « Recalculer le dimensionnement »
// (`recalculerDimensionnement`) qui déverrouille temporairement le garde-fou,
// rejoue le MÊME balayage palier/payback que `computeAutoSizing` sur la
// facture ACTUELLE (sans ET avec batterie, L-2OPT), pose les deux résultats,
// puis relance la composition par le chemin EXACT du bouton « Auto-remplir »
// (`handleAutoFill`, jamais une seconde règle de composition) — et reverrouille
// le garde-fou à SON ÉTAT D'AVANT LE CLIC (capturé, jamais un `true` figé —
// F1 ci-dessous), dans la fenêtre SYNCHRONE la plus étroite possible (F2).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE,
// même patron que DevisGeneratorNbPanneauxTouched.test.mjs /
// DevisGeneratorDeuxOptimiseurs.test.mjs. Un test COMPORTEMENTAL (rendu
// React réel, vitest) complète ce fichier dans
// DevisGeneratorRecalculerDimensionnementGuard.test.jsx — lui seul aurait
// intercepté F1 (un test purement source-pattern passe même avec le
// reverrouillage mal placé, tant que du texte « nbPanneauxTouched.current »
// apparaît quelque part dans l'effet).
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
  // Revue adversariale 26/08 (corrige la cause #2 initiale, qui affirmait le
  // contraire) — CE MÊME chargement ne touche JAMAIS nbPanneauxTouched.current
  // non plus : le garde-fou reste à sa valeur useRef(false) par défaut, donc
  // OUVERT, juste après un chargement d'édition — la staleness ne vient pas
  // d'un garde-fou fermé par l'édition, mais de fHiver/fEte vides (ci-dessus)
  // + handleAutoFill qui ne redérive jamais depuis la facture (ROOT CAUSE 2).
  assert.doesNotMatch(bloc, /nbPanneauxTouched\.current = true/,
    'régression : un chargement d\'édition ne doit toujours PAS fermer nbPanneauxTouched — sinon ce commentaire redevient faux')
})

test('ROOT CAUSE 2 — la branche RÉSIDENTIELLE de handleAutoFill() ne redérive JAMAIS nbPanneaux depuis la facture : elle lit `kwp` (nbPanneaux COURANT), jamais computeAutoSizing', () => {
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

test('ROOT CAUSE 3 — syncBillEstimator() ne recompose JAMAIS les lignes (setLines/handleAutoFill absents), garde nbPanneauxTouched déjà en place (fermeture générale, pas spécifique à l\'édition)', () => {
  const bloc = corpsDe('const syncBillEstimator = (hiverVal, eteVal) => {', 'syncBillEstimator')
  assert.doesNotMatch(bloc, /setLines\(/)
  assert.doesNotMatch(bloc, /handleAutoFill/)
  assert.match(bloc, /if \(!nbPanneauxTouched\.current\) \{/)
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

test('F1 (BLOQUANT, revue adversariale) — recalculerDimensionnement() CAPTURE nbPanneauxTouched AVANT de le déverrouiller (jamais un `true` figé au reverrouillage)', () => {
  const bloc = corpsDe('const recalculerDimensionnement = () => {', 'recalculerDimensionnement')
  assert.match(bloc, /const sizing = computeAutoSizing\(fHiver, fEte\)/)
  const captureIdx = bloc.indexOf('recalcDimPriorTouched.current = nbPanneauxTouched.current')
  assert.ok(captureIdx > -1,
    'la valeur AVANT le clic doit être capturée — sinon le reverrouillage ne peut pas la restaurer (régression F1 : un `true` figé verrouille le garde-fou en PERMANENCE dès le premier clic, même en création où il partait FAUX)')
  const unlockIdx = bloc.indexOf('nbPanneauxTouched.current = false', captureIdx)
  assert.ok(unlockIdx > -1, 'le garde-fou doit être déverrouillé APRÈS la capture — sinon on capture déjà `false` et la capture est un no-op')
  assert.ok(captureIdx < unlockIdx, 'la capture doit précéder le déverrouillage (sinon on capture la valeur déjà déverrouillée)')
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

test('F1+F2 (revue adversariale) — l\'effet du recalcul reverrouille à recalcDimPriorTouched.current (jamais `true` figé), SYNCHRONE (jamais dans un .finally() après l\'aller-retour réseau)', () => {
  const idx = DG.indexOf('if (!recalcDimPending.current) return')
  assert.ok(idx > -1, 'effet du recalcul introuvable')
  const depsIdx = DG.indexOf('}, [recalcDimTick])', idx)
  assert.ok(depsIdx > -1)
  const bloc = DG.slice(idx, depsIdx)
  assert.match(bloc, /recalcDimPending\.current = false/)
  // F2 — appel SYNCHRONE de handleAutoFill (résultat capturé, jamais attendu
  // avant de reverrouiller) : une fonction async exécute tout son préfixe
  // synchrone (jusqu'à son premier `await`) avant de rendre la main — donc
  // `resolveKwcAvec()` (lu par handleAutoFill AVANT son `await
  // ventesApi.composerDevis`) a déjà lu le ref au moment où la ligne suivante
  // s'exécute. Reverrouiller ICI ferme la fenêtre de course AVANT que la
  // moindre frappe utilisateur n'ait la chance de s'y engouffrer.
  const pendingIdx = bloc.indexOf('const pending = handleAutoFill()')
  assert.ok(pendingIdx > -1,
    'handleAutoFill() doit être appelé de façon SYNCHRONE (résultat nommé, pas attendu) — un `await handleAutoFill()` ou un `.finally()` rouvrirait la fenêtre sur tout le round-trip réseau (régression F2)')
  const relockIdx = bloc.indexOf('nbPanneauxTouched.current = recalcDimPriorTouched.current')
  assert.ok(relockIdx > -1,
    'le reverrouillage doit restaurer recalcDimPriorTouched.current — un `nbPanneauxTouched.current = true` figé ici est exactement la régression F1')
  assert.ok(pendingIdx < relockIdx, 'le reverrouillage doit suivre IMMÉDIATEMENT l\'appel (jamais après un .finally()/.then() qui attendrait la réponse réseau)')
  // Aucun `.finally(` n'entoure le reverrouillage (l'ancienne régression F1/F2).
  assert.doesNotMatch(bloc, /\.finally\(\(\) => \{\s*nbPanneauxTouched\.current/,
    'reverrouiller dans un .finally() rouvre la fenêtre sur tout l\'aller-retour réseau (régression F2) — voir le correctif ci-dessus')
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

test('deuxValeursDim : jamais un chiffre inventé — computeAutoSizing n\'est jamais appelé pendant le rendu (react-hooks/refs), tout vient de sizingInfo (état) ou du serveur', () => {
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
})

test('F3 (revue adversariale) — deuxValeursDim n\'affiche la PAIRE que si sans/avec partagent la MÊME source (serveur+serveur ou local+local), jamais un mélange', () => {
  const bloc = corpsDe('const deuxValeursDim = (() => {', 'deuxValeursDim')
  assert.match(bloc, /const srvSansOk = Number\(srvSans\?\.panneaux\) > 0/)
  assert.match(bloc, /const srvAvecOk = Number\(srvAvec\?\.panneaux\) > 0/)
  assert.match(bloc, /const localSansOk = localSans\?\.nbPanneaux > 0/)
  assert.match(bloc, /const localAvecOk = localAvec\?\.nbPanneaux > 0/)
  // La PAIRE ne sort que d'un bloc qui exige les DEUX cases de la MÊME source.
  assert.match(bloc, /if \(srvSansOk && srvAvecOk\) return \{ sans: asSans\(\), avec: asAvec\(\) \}/)
  assert.match(bloc, /if \(localSansOk && localAvecOk\) return \{ sans: asSans\(\), avec: asAvec\(\) \}/)
  // Reproduit la logique EXACTE avec de vraies données pour prouver le
  // comportement (pas seulement sa présence textuelle) : une PAIRE cohérente
  // (même source pour les deux branches) prime toujours sur un repli
  // partiel — un repli « serveur sans + local avec » (le mélange que F3
  // interdit) ne doit JAMAIS sortir de cette fonction, quelle que soit la
  // combinaison de disponibilités.
  function dedup(srvSansOk, srvAvecOk, localSansOk, localAvecOk) {
    if (srvSansOk && srvAvecOk) return 'PAIRE_SERVEUR'
    if (localSansOk && localAvecOk) return 'PAIRE_LOCAL'
    if (srvSansOk) return 'SANS_SEUL_SERVEUR'
    if (localSansOk) return 'SANS_SEUL_LOCAL'
    if (srvAvecOk) return 'AVEC_SEUL_SERVEUR'
    if (localAvecOk) return 'AVEC_SEUL_LOCAL'
    return 'RIEN'
  }
  // Local a les DEUX branches prêtes → une paire COHÉRENTE (delta comparable,
  // même méthode des deux côtés) prime sur un repli partiel serveur-seul,
  // même si le serveur a AUSSI répondu pour une des deux branches : mélanger
  // « sans » serveur avec « avec » local romprait la comparabilité (F3) — la
  // paire locale cohérente est strictement meilleure qu'un repli à une seule
  // valeur ici.
  assert.equal(dedup(true, false, true, true), 'PAIRE_LOCAL',
    'local dispo des deux côtés : une paire cohérente prime sur un repli sans-seul-serveur')
  // Ni pair serveur ni pair local possible (sans=local seul dispo, avec=serveur
  // seul dispo) : JAMAIS le mélange local-sans/serveur-avec — repli sur UNE
  // seule valeur (sans, la première testée dans la cascade).
  assert.equal(dedup(false, true, true, false), 'SANS_SEUL_LOCAL',
    'aucune paire de même source possible : une seule valeur, jamais le mélange serveur-avec/local-sans')
  // Preuve directe du bug rapporté : sans serveur dispo, avec NI serveur NI
  // local dispo → jamais de valeur avec fabriquée, sans seul s'affiche.
  assert.equal(dedup(true, false, false, false), 'SANS_SEUL_SERVEUR')
  assert.equal(dedup(true, true, false, false), 'PAIRE_SERVEUR')
  assert.equal(dedup(false, false, true, true), 'PAIRE_LOCAL')
  assert.equal(dedup(false, false, false, false), 'RIEN')
})

test('affichage : le bloc « Recommandé sans/avec batterie » est résidentiel-only, respecte showSans/showAvec, ET son garde extérieur reflète EXACTEMENT ce qui va rendre (F4 — jamais un wrapper vide)', () => {
  const idx = DG.indexOf('data-testid="dimensionnement-deux-valeurs"')
  assert.ok(idx > -1, 'bloc deux-valeurs introuvable')
  const bloc = DG.slice(Math.max(0, idx - 1400), idx + 700)
  // F4 — le garde EXTÉRIEUR (celui qui décide si le <div> se monte DU TOUT)
  // reprend les DEUX conditions (source ET scénario), pas seulement la source :
  // sinon un wrapper vide (marge + data-testid orphelins) peut se monter en
  // mono-option quand seule la branche masquée est calculable.
  assert.match(bloc, /modeInstallation === 'residentiel'\s*\n\s*&& \(\(showSans && deuxValeursDim\.sans\) \|\| \(showAvec && deuxValeursDim\.avec\)\)/)
  assert.doesNotMatch(bloc, /&& \(deuxValeursDim\.sans \|\| deuxValeursDim\.avec\) &&/,
    'régression F4 : le garde extérieur ne doit plus ignorer showSans/showAvec')
  assert.match(bloc, /\{showSans && deuxValeursDim\.sans && \(/)
  assert.match(bloc, /\{showAvec && deuxValeursDim\.avec && \(/)
  // F5 — libellés de RECOMMANDATION (pas une description des lignes
  // composées : un nombre de panneaux tapé à la main peut diverger).
  assert.match(bloc, /Recommandé sans batterie : <strong>\{deuxValeursDim\.sans\.nbPanneaux\} panneaux<\/strong>/)
  assert.match(bloc, /Recommandé avec batterie : <strong>\{deuxValeursDim\.avec\.nbPanneaux\} panneaux<\/strong>/)
})

test('showSans\\/showAvec (contrat mono-option existant) restent la SEULE source de vérité pour ce qui est vendu sur le devis — non redéfinis par ce chantier', () => {
  assert.match(DG, /const showSans = scenario !== 'Avec batterie'/)
  assert.match(DG, /const showAvec = scenario !== 'Sans batterie'/)
})
