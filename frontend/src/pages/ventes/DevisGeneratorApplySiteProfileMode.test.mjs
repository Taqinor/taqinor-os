// QJR38 (audit L3 29/08/2026, origine QJF7) — `applySiteProfile` lisait
// `modeInstallation` (l'état du rendu PRÉCÉDENT) au lieu du mode qu'il venait
// de poser via `onModeChange` : `setState` ne rafraîchit jamais la constante
// fermée dans la MÊME passe de la fonction (piège React classique). Un profil
// de site industriel ou commercial prenait donc le chemin résidentiel, armait
// `attenteSizingServeur` — que le moteur résidentiel-only ne satisfera
// JAMAIS — et laissait le vendeur sans compte de panneaux ET sans explication.
//
// Correctif : même patron qu'`applyLead` (déjà correct, voir `modeCible`
// dans cette fonction) — calculer le mode RÉELLEMENT visé dans une variable
// locale et brancher dessus, jamais sur `modeInstallation` après un
// `onModeChange` dans la même fonction.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE, même patron que les autres
// tests QJR de ce fichier.
//
// Run : node --test src/pages/ventes/DevisGeneratorApplySiteProfileMode.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

// QJR99 — la BASCULE a déplacé les écritures gardées d'`applySiteProfile` dans
// la transition `PROFIL_SITE_APPLIQUE` du reducer (le garde-fou `touche.mode`
// et le choix résidentiel-attend-le-moteur y vivent, testés dans
// sizingReducer.test.mjs). Ce qui reste ICI — et que ce fichier garde — est le
// point EXACT du bug QJR38 : la résolution LOCALE du mode visé, qui décide du
// dimensionneur (balayage local ou moteur serveur) et du type d'installation.
// Les épingles suivent donc le code là où il vit ; aucune n'est relâchée.
test('QJR38 — applySiteProfile calcule modeCible localement (mode fraîchement résolu, jamais modeInstallation du rendu précédent)', () => {
  const idx = DG.indexOf('const applySiteProfile = (p) => {')
  assert.ok(idx > -1, 'applySiteProfile introuvable')
  const bloc = DG.slice(idx, idx + 1400)
  // Le mode du profil n'est retenu QUE si le vendeur n'a pas déjà choisi le
  // sien (`touche.mode`, ex-`modeTouched`).
  assert.match(bloc,
    /const modeLead = !sizing\.touche\.mode\s*\n\s*&& p\.type_installation && LEAD_TYPE_TO_MODE\[p\.type_installation\]\s*\n\s*\? LEAD_TYPE_TO_MODE\[p\.type_installation\] : null/)
  // Le mode RÉELLEMENT visé est calculé en variable locale — jamais relu
  // depuis modeInstallation seul.
  assert.match(bloc, /const modeCible = modeLead \|\| modeInstallation/)
})

test('QJR38 — la résolution du dimensionneur d\'applySiteProfile branche sur modeCible, plus jamais sur modeInstallation directement', () => {
  const idx = DG.indexOf('const applySiteProfile = (p) => {')
  assert.ok(idx > -1)
  const endIdx = DG.indexOf('const applyClient = (v) => {')
  assert.ok(endIdx > idx, 'fin de applySiteProfile introuvable (avant applyClient)')
  const bloc = DG.slice(idx, endIdx)
  // Le balayage LOCAL n'est résolu que pour un marché NON résidentiel — le
  // résidentiel attend le moteur horaire serveur (transition du reducer).
  assert.match(bloc,
    /const sizingLocal = \(hiver > 0 && !sizing\.touche\.nbPanneaux && modeCible !== 'residentiel'\)\s*\n\s*\? computeAutoSizing\(hiver, ete\) : null/,
    'le choix du dimensionneur doit brancher sur modeCible')
  assert.match(bloc, /dispatchSizing\(\{ type: 'PROFIL_SITE_APPLIQUE', profil: p, sizingLocal \}\)/,
    'le pré-remplissage doit passer par la transition unique du reducer')
  // Plus aucune lecture nue de `modeInstallation === 'residentiel'` dans TOUT
  // le corps de la fonction (l'ancien bug) — la seule comparaison au mode
  // porte sur modeCible.
  assert.doesNotMatch(bloc, /modeInstallation === 'residentiel'/,
    'applySiteProfile ne doit plus jamais comparer modeInstallation directement')
})

test('QJR38 — le patron reproduit exactement celui, déjà correct, d\'applyLead (modeCible = modeLead || modeInstallation)', () => {
  // applyLead sert de référence : ce test échouerait si applyLead lui-même
  // régressait, ce qui prouve que les deux fonctions restent alignées.
  const idxLead = DG.indexOf('const applyLead = (id) => {')
  assert.ok(idxLead > -1)
  // Fenêtre élargie (1800→3000) : QJR99 a ajouté le commentaire de bascule en
  // tête de fonction ; le contenu vérifié, lui, est inchangé.
  const blocLead = DG.slice(idxLead, idxLead + 3000)
  assert.match(blocLead, /const modeCible = modeLead \|\| modeInstallation/)
  assert.match(blocLead, /modeCible !== 'residentiel'/,
    'applyLead doit lui aussi choisir son dimensionneur sur modeCible')
})

test('QJR38 — rejoué : un profil industriel/commercial résout modeCible sur ce mode, jamais résidentiel, quand le vendeur n\'a pas déjà choisi de mode', () => {
  // Reproduit la résolution verrouillée par le 1er test.
  const LEAD_TYPE_TO_MODE = { residentiel: 'residentiel', industriel: 'industriel', commercial: 'commercial' }
  const resoudreModeCible = (modeTouched, typeInstallation, modeInstallationCourant) => {
    const modeLead = !modeTouched && typeInstallation && LEAD_TYPE_TO_MODE[typeInstallation]
      ? LEAD_TYPE_TO_MODE[typeInstallation] : null
    return modeLead || modeInstallationCourant
  }
  // Écran par défaut en résidentiel, profil de site industriel, mode NON touché.
  assert.equal(resoudreModeCible(false, 'industriel', 'residentiel'), 'industriel',
    'un profil industriel doit résoudre modeCible sur industriel, jamais residentiel')
  assert.equal(resoudreModeCible(false, 'commercial', 'residentiel'), 'commercial')
  // Vendeur ayant déjà choisi un mode à la main : le profil ne le change pas,
  // modeCible retombe sur le mode COURANT (comportement inchangé).
  assert.equal(resoudreModeCible(true, 'industriel', 'residentiel'), 'residentiel',
    'un mode déjà choisi par le vendeur ne doit jamais être écrasé')
})
