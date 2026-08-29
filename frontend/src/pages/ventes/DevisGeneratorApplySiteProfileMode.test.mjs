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

test('QJR38 — applySiteProfile calcule modeCible localement (mode fraîchement résolu, jamais modeInstallation après onModeChange)', () => {
  const idx = DG.indexOf('const applySiteProfile = (p) => {')
  assert.ok(idx > -1, 'applySiteProfile introuvable')
  const bloc = DG.slice(idx, idx + 1100)
  // onModeChange n'est appelé QUE si le mode calculé depuis le profil existe.
  assert.match(bloc,
    /const modeLead = !modeTouched\.current\s*\n\s*&& p\.type_installation && LEAD_TYPE_TO_MODE\[p\.type_installation\]\s*\n\s*\? LEAD_TYPE_TO_MODE\[p\.type_installation\] : null/)
  assert.match(bloc, /if \(modeLead\) onModeChange\(modeLead\)/)
  // Le mode RÉELLEMENT visé est calculé APRÈS l'appel onModeChange, en
  // variable locale — jamais relu depuis modeInstallation seul.
  assert.match(bloc, /const modeCible = modeLead \|\| modeInstallation/)
})

test('QJR38 — la branche attenteSizingServeur d\'applySiteProfile branche sur modeCible, plus jamais sur modeInstallation directement', () => {
  const idx = DG.indexOf('const applySiteProfile = (p) => {')
  assert.ok(idx > -1)
  const endIdx = DG.indexOf('const applyClient = (v) => {')
  assert.ok(endIdx > idx, 'fin de applySiteProfile introuvable (avant applyClient)')
  const bloc = DG.slice(idx, endIdx)
  assert.match(bloc,
    /if \(modeCible === 'residentiel'\) \{\s*\n(?:[^\n]*\n){0,4}?\s*setSizingInfo\(null\)\s*\n\s*attenteSizingServeur\.current = true\s*\n\s*\} else \{/,
    'la branche résidentiel/attente-serveur doit brancher sur modeCible')
  // Plus aucune lecture nue de `modeInstallation === \'residentiel\'` dans TOUT
  // le corps de la fonction (l'ancien bug) — la seule comparaison au mode
  // porte sur modeCible.
  assert.doesNotMatch(bloc, /if \(modeInstallation === 'residentiel'\)/,
    'applySiteProfile ne doit plus jamais comparer modeInstallation directement')
})

test('QJR38 — le patron reproduit exactement celui, déjà correct, d\'applyLead (modeCible = modeLead || modeInstallation)', () => {
  // applyLead sert de référence : ce test échouerait si applyLead lui-même
  // régressait, ce qui prouve que les deux fonctions restent alignées.
  const idxLead = DG.indexOf('const applyLead = (id) => {')
  assert.ok(idxLead > -1)
  const blocLead = DG.slice(idxLead, idxLead + 900)
  assert.match(blocLead, /const modeCible = modeLead \|\| modeInstallation/)
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
