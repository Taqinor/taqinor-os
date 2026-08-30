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
  // c'est ce compte qui reste figé sans le bouton de recalcul. QJR99 — il est
  // posé par la transition `REOUVERTURE`, qui pose le compte SANS marquer le
  // champ « touché » (`poserPanneaux`, cf. sizingReducer.test.mjs).
  assert.match(bloc, /dispatchSizing\(\{\s*\n\s*type: 'REOUVERTURE',\s*\n\s*devis: \{[\s\S]{0,200}panneaux,/)
  // Revue adversariale 26/08 (corrige la cause #2 initiale, qui affirmait le
  // contraire) — CE MÊME chargement ne ferme JAMAIS le garde-fou
  // « nbPanneaux touché » : il reste OUVERT juste après un chargement
  // d'édition — la staleness ne vient pas d'un garde-fou fermé par l'édition,
  // mais de fHiver/fEte vides (ci-dessus) + handleAutoFill qui ne redérive
  // jamais depuis la facture (ROOT CAUSE 2).
  assert.doesNotMatch(bloc, /champ: 'nbPanneaux'/,
    'régression : un chargement d\'édition ne doit toujours PAS fermer le drapeau « nbPanneaux touché »')
  assert.doesNotMatch(bloc, /champ: 'kwcCible'/,
    'régression : un chargement d\'édition ne doit pas non plus passer par la frappe kWc (qui ferme le même drapeau)')
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
  assert.doesNotMatch(residentielBloc, /'nbPanneaux'|'REOUVERTURE'/,
    'la branche résidentielle ne pose jamais nbPanneaux — recomposer avec le compte courant est le comportement historique, inchangé')
})

test('ROOT CAUSE 3 — syncBillEstimator() ne recompose JAMAIS les lignes (setLines/handleAutoFill absents), garde « nbPanneaux touché » déjà en place (fermeture générale, pas spécifique à l\'édition)', () => {
  const bloc = corpsDe('const syncBillEstimator = (hiverVal, eteVal) => {', 'syncBillEstimator')
  assert.doesNotMatch(bloc, /setLines\(/)
  assert.doesNotMatch(bloc, /handleAutoFill/)
  assert.match(bloc, /if \(!sizing\.touche\.nbPanneaux\) \{/)
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

// QJR99 — F1 exigeait de CAPTURER le garde-fou avant de le déverrouiller, puis
// de le restaurer dans un effet : trois instructions, donc une FENÊTRE. La
// transition `RECALCUL_DEMANDE` fait les trois EN UNE FOIS (invariant 3 du
// reducer, testé dans sizingReducer.test.mjs : le drapeau réel est INCHANGÉ, et
// seul `toucheNbPanneauxPourComposition` le voit ouvert, sur cette unique
// transition). L'épingle vérifie donc que l'écran n'a plus AUCUNE manœuvre de
// verrouillage à lui — c'est plus fort que l'ancienne, pas plus faible.
test('F1 (BLOQUANT, revue adversariale) — recalculerDimensionnement() ne manipule PLUS le garde-fou à la main : une seule transition le rouvre et le restaure', () => {
  const bloc = corpsDe('const recalculerDimensionnement = () => {', 'recalculerDimensionnement')
  assert.match(bloc, /const sizing = computeAutoSizing\(fHiver, fEte\)/)
  // Aucune écriture manuelle du drapeau, dans aucun sens : ni capture, ni
  // déverrouillage, ni restauration — c'est ce qui supprime la fenêtre de course.
  assert.doesNotMatch(bloc, /touche\.nbPanneaux\s*=/,
    'plus aucune écriture manuelle du garde-fou : `RECALCUL_DEMANDE` le rouvre et le restaure dans la MÊME transition (régression F1 si elle revient)')
  assert.doesNotMatch(bloc, /PriorTouched/,
    'la capture/restauration manuelle (et sa fenêtre) doit avoir disparu')
  // La taille retenue part par la transition, avec sa cible kWc. U3-MOTEUR —
  // en résidentiel `sizingInfo` reste NUL (le reducer le décide : son encart
  // décrit le balayage local, « palier retenu / besoin lu sur la facture »,
  // deux notions qui ne décrivent pas ce que le moteur a fait).
  assert.match(bloc, /dispatchSizing\(\{ type: 'RECALCUL_DEMANDE', retenu \}\)/)
  assert.match(bloc, /kwcOptimal: source\.kwc != null \? Number\(source\.kwc\) : null/)
})

// U3-MOTEUR (fondateur 29/08/2026, « ALL sizing goes through the new sizing
// tool ») — le bouton « Recalculer le dimensionnement » était le DERNIER
// endroit où un nombre de panneaux chiffré à l'écran (balayage par paliers de
// 5 kWc) pouvait encore écraser celui du moteur horaire, quelle que soit la
// facture. En résidentiel il relit désormais la recommandation SERVEUR (déjà
// obtenue par le dry-run d'aperçu — aucun appel réseau supplémentaire).
test("U3-MOTEUR — recalculerDimensionnement() : en résidentiel la taille vient du MOTEUR SERVEUR, le balayage local ne sert plus qu'aux marchés sans moteur", () => {
  const bloc = corpsDe('const recalculerDimensionnement = () => {', 'recalculerDimensionnement')
  const residIdx = bloc.indexOf("if (modeInstallation === 'residentiel') {")
  assert.ok(residIdx > -1, 'la branche résidentielle du recalcul est introuvable')
  const elseIdx = bloc.indexOf('} else {', residIdx)
  assert.ok(elseIdx > -1, 'la branche des autres marchés est introuvable')
  const brancheResid = bloc.slice(residIdx, elseIdx)
  // Résidentiel : uniquement la recommandation du moteur, jamais un palier local.
  assert.match(brancheResid, /etudeHoraireDonnees\?\.dimensionnement/)
  assert.match(brancheResid, /recommandation_avec/)
  assert.ok(!/computeAutoSizing\(/.test(brancheResid),
    "la branche résidentielle ne doit plus chiffrer de palier localement")
  // Refus : message FRANÇAIS du serveur (motivation/avertissements) en priorité.
  assert.match(brancheResid, /recalcDim: dim\?\.motivation/)
  assert.match(brancheResid, /etudeHoraireDonnees\?\.avertissements\?\.\[0\]/)
  // Aucun chiffre posé sans recommandation exploitable.
  assert.match(brancheResid, /if \(!\(Number\(source\?\.panneaux\) > 0\)\) \{/)
  // Les autres marchés (aucun moteur serveur pour eux) gardent le balayage.
  const brancheAutres = bloc.slice(elseIdx)
  assert.match(brancheAutres, /const sizing = computeAutoSizing\(fHiver, fEte\)/)
})

test('recalculerDimensionnement() : déclenche la recomposition via un COMPTEUR dédié (jamais un effet calé sur nbPanneaux qui pourrait ne pas se redéclencher à compte inchangé)', () => {
  const bloc = corpsDe('const recalculerDimensionnement = () => {', 'recalculerDimensionnement')
  // QJR99 — le compteur est `compositionSeq`, incrémenté PAR la transition
  // (`RECALCUL_DEMANDE`), donc impossible à oublier côté écran ; l'effet de
  // composition est calé dessus (`recalcDimTick`), jamais sur `nbPanneaux`.
  assert.match(bloc, /dispatchSizing\(\{ type: 'RECALCUL_DEMANDE', retenu \}\)/)
  assert.match(DG, /compositionSeq: recalcDimTick,/)
  assert.match(DG, /\}, \[recalcDimTick\]\)/)
})

test('F2 (revue adversariale) — l\'effet de composition appelle handleAutoFill de façon SYNCHRONE (jamais un await/.finally qui rouvrirait la fenêtre sur tout l\'aller-retour réseau)', () => {
  const idx = DG.indexOf('    if (!recalcDimTick) return')
  assert.ok(idx > -1, 'effet de composition introuvable')
  const depsIdx = DG.indexOf('}, [recalcDimTick])', idx)
  assert.ok(depsIdx > -1)
  const bloc = DG.slice(idx, depsIdx)
  // F2 — une fonction async exécute tout son préfixe synchrone (jusqu'à son
  // premier `await`) avant de rendre la main : `resolveKwcAvec()` (lu par
  // handleAutoFill AVANT son `await ventesApi.composerDevis`) voit donc la
  // fenêtre `recalcul` ouverte par la transition, et RIEN d'autre ne peut
  // s'intercaler — le reducer la referme à l'action suivante.
  assert.match(bloc, /Promise\.resolve\(handleAutoFill\(\)\)\.catch\(\(\) => \{\}\)/,
    'handleAutoFill() doit être appelé de façon SYNCHRONE (promesse capturée, jamais attendue) — un `await handleAutoFill()` rouvrirait la fenêtre sur tout le round-trip réseau (régression F2)')
  assert.doesNotMatch(bloc, /await /,
    'aucun await dans cet effet : il bornerait la fenêtre au round-trip réseau (régression F2)')
  // Plus AUCUNE manœuvre de verrouillage manuelle dans l'effet (régression F1).
  assert.doesNotMatch(bloc, /touche\.nbPanneaux\s*=|PriorTouched/,
    'le reverrouillage manuel doit avoir disparu : il vit dans la transition `RECALCUL_DEMANDE`')
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
  assert.match(bloc, /const dim = etudeHoraireDonnees\?\.dimensionnement/)
  assert.match(bloc, /dim\?\.recommandation, dim\?\.recommandation_avec/)
  // Jamais un appel à computeAutoSizing ICI : il lirait sizingCacheRef.current
  // PENDANT le rendu (deuxValeursDim est une const calculée en ligne dans le
  // corps du composant, pas dans un effet/gestionnaire) — interdit par la
  // règle ESLint react-hooks/refs, vérifiée en CI (backend-lint côté frontend).
  assert.doesNotMatch(bloc, /computeAutoSizing/)
  assert.match(bloc, /const localSans = \(scenario === SCENARIO_AVEC\) \? null : sizingInfo/)
  assert.match(bloc, /const localAvec = \(scenario === SCENARIO_AVEC\) \? sizingInfo : sizingInfo\?\.avec/)
})

// QJR99 — la chaîne de ternaires est remplacée par `paireDimensionnement`, qui
// SIGNE chaque branche (`moteur` / `apercu` / `absent`, QJR86) au lieu de la
// deviner : la règle F3 devient une comparaison de sources explicite. Les
// épingles suivent la fonction ; la PREUVE par les données ci-dessous est
// inchangée, et c'est elle qui garde le comportement.
test('F3 (revue adversariale) — deuxValeursDim n\'affiche la PAIRE que si sans/avec partagent la MÊME source (serveur+serveur ou local+local), jamais un mélange', () => {
  const idx = DG.indexOf('const paireDimensionnement = (srvSans, srvAvec, localSans, localAvec) => {')
  assert.ok(idx > -1, 'paireDimensionnement introuvable')
  const bloc = DG.slice(idx, idx + 1300)
  // Chaque branche est SIGNÉE de sa source — jamais un nombre nu.
  assert.match(bloc, /const mSans = valeurMoteurDim\(srvSans\)/)
  assert.match(bloc, /const mAvec = valeurMoteurDim\(srvAvec\)/)
  assert.match(bloc, /const aSans = valeurApercuDim\(localSans\)/)
  assert.match(bloc, /const aAvec = valeurApercuDim\(localAvec\)/)
  // La PAIRE ne sort que d'un bloc qui exige les DEUX cases de la MÊME source.
  assert.match(bloc, /if \(estFait\(mSans\) && estFait\(mAvec\)\) return \{ sans: mSans\.valeur, avec: mAvec\.valeur \}/)
  assert.match(bloc, /if \(estFait\(aSans\) && estFait\(aAvec\)\) return \{ sans: aSans\.valeur, avec: aAvec\.valeur \}/)
  // Et les replis à UNE valeur ne mélangent jamais deux sources.
  assert.match(bloc, /if \(estFait\(mSans\)\) return \{ sans: mSans\.valeur, avec: null \}/)
  assert.match(bloc, /if \(estFait\(aSans\)\) return \{ sans: aSans\.valeur, avec: null \}/)
  assert.match(bloc, /if \(estFait\(mAvec\)\) return \{ sans: null, avec: mAvec\.valeur \}/)
  assert.match(bloc, /if \(estFait\(aAvec\)\) return \{ sans: null, avec: aAvec\.valeur \}/)
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
