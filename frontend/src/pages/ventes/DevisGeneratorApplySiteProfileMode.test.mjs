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
// CIQ126 — le dimensionneur LOCAL (balayage C&I `computeAutoSizing`) est
// SUPPRIMÉ : plus aucun pré-remplissage (lead, profil site, frappe facture) ne
// choisit de dimensionneur à l'écran. Le bug QJR38 (brancher sur le mode du
// rendu précédent) ne peut donc plus revenir : il n'y a plus de branche.
const blocDe = (debut, fin) => {
  const i = DG.indexOf(debut)
  assert.ok(i > -1, `${debut} introuvable`)
  return DG.slice(i, DG.indexOf(fin, i))
}

test('CIQ126 — applySiteProfile ne choisit plus aucun dimensionneur local (sizingLocal nul)', () => {
  const bloc = blocDe('const applySiteProfile = (p) => {', '  // ── Factures')
  assert.match(bloc, /const sizingLocal = null\n/)
  assert.match(bloc, /dispatchSizing\(\{ type: 'PROFIL_SITE_APPLIQUE', profil: p, sizingLocal \}\)/)
  assert.doesNotMatch(bloc, /computeAutoSizing/)
})

test('CIQ126 — applyLead et la frappe facture non plus ; computeAutoSizing n’existe plus', () => {
  const blocLead = blocDe('const applyLead = ', 'const applySiteProfile = (p) => {')
  assert.match(blocLead, /const sizingLocal = null\n/)
  assert.doesNotMatch(DG, /computeAutoSizing\(|const computeAutoSizing/)
  assert.doesNotMatch(DG, /optimalKwcByPayback\(|parametresBalayageCI\(/)
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
