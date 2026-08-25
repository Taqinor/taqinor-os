// PVORD (fondateur 19/08/2026) — persistance de l'ordre des lignes comme
// ordre par défaut des PROCHAINS devis (`ParametresGammes.ordre_lignes`).
// DevisGenerator.jsx/autoQuote.js sont du JSX/ESM non exécutable par
// `node --test` sans node_modules (React, Redux dispatch réel) : ce test lit
// donc le SOURCE, même patron que LeadDevisPanel.wiring.test.mjs.
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

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const DG = read('DevisGenerator.jsx')
const AQ = read('../../features/ventes/autoQuote.js')

test('DevisGenerator : importe deriveRoleOrderFromLines de solar.js', () => {
  assert.match(DG, /deriveRoleOrderFromLines,?\s*\n\s*\}\s*from\s*'\.\.\/\.\.\/features\/ventes\/solar'/)
})

test('DevisGenerator : handleSaveOrdreLignes dérive lines puis PATCH ordre_lignes', () => {
  assert.match(DG, /const handleSaveOrdreLignes = async \(\) => \{/)
  assert.match(DG, /const derived = deriveRoleOrderFromLines\(lines\)/)
  assert.match(DG, /ventesApi\.updateParametresGammes\(\{\s*ordre_lignes:\s*derived\s*\}\)/)
})

test('DevisGenerator : le bouton « Enregistrer cet ordre » appelle handleSaveOrdreLignes', () => {
  assert.match(DG, /onClick=\{handleSaveOrdreLignes\}/)
  assert.match(DG, /Enregistrer cet ordre comme ordre par défaut/)
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
