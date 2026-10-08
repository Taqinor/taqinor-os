// N2 (audit apercu-issues) — un prix TAPÉ À LA MAIN sur une ligne était
// RE-FORCÉ par l'effet listes-de-prix (dépendances [clientId, lines.length]) :
// changer le client ou ajouter une ligne relançait `refreshTarif` sur TOUTES
// les lignes portant un produit, et sa résolution de liste de prix (XSAL1/2)
// écrasait sans condition `prix_unit_ttc` — y compris une ligne où le vendeur
// venait de taper un prix négocié à la main. Correctif : un drapeau
// `prixManuel` posé par `setLine()` à la frappe du prix, lu par
// `refreshTarif()` au moment de l'écriture (jamais un `lines` capturé au
// lancement de l'appel réseau, obsolète), et levé par `onProduitChange()`
// quand le vendeur RESÉLECTIONNE explicitement un produit.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE,
// même patron que DevisGeneratorOrdreLignes.test.mjs /
// DevisGeneratorVX249Suggested.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorPrixManuel.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { lireSourceGenerateur } from './DevisGeneratorSource.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = lireSourceGenerateur()

test('withKeys()/emptyLine()/structureLine() portent toutes un prixManuel (False par défaut, préservé au restore de brouillon)', () => {
  const wkStart = DG.indexOf('const withKeys = (rows) => rows.map(r => ({')
  const wkEnd = DG.indexOf('}))', wkStart)
  assert.ok(wkStart > -1 && wkEnd > wkStart, 'withKeys() introuvable')
  assert.match(DG.slice(wkStart, wkEnd), /prixManuel:\s*!!r\.prixManuel/)

  const elStart = DG.indexOf('const emptyLine = () => ({')
  assert.ok(elStart > -1, 'emptyLine() introuvable')
  assert.match(DG.slice(elStart, elStart + 900), /prixManuel:\s*false/)

  const slStart = DG.indexOf('const structureLine = (typeLigne) => ({')
  assert.ok(slStart > -1, 'structureLine() introuvable')
  assert.match(DG.slice(slStart, slStart + 500), /prixManuel:\s*false/)
})

test('setLine() pose prixManuel=true UNIQUEMENT quand la clé modifiée est prix_unit_ttc', () => {
  const start = DG.indexOf('const setLine = useCallback((key, k, v) => {')
  assert.ok(start > -1, 'setLine introuvable')
  const body = DG.slice(start, start + 900)
  assert.match(body, /k === 'prix_unit_ttc' \? \{ prixManuel: true \} : \{\}/)
})

test('onProduitChange() lève le verrou prixManuel à la resélection explicite du produit', () => {
  const start = DG.indexOf('const onProduitChange = useCallback((key, produitId) => {')
  assert.ok(start > -1, 'onProduitChange introuvable')
  const body = DG.slice(start, start + 900)
  assert.match(body, /prixManuel:\s*false,/)
})

test('refreshTarif() ne réécrit prix_unit_ttc que si !l.prixManuel (lu au moment de l\'écriture, jamais l\'état capturé au lancement du réseau)', () => {
  const start = DG.indexOf('const refreshTarif = useCallback(async (key, produitId, quantite) => {')
  assert.ok(start > -1, 'refreshTarif introuvable')
  const body = DG.slice(start, start + 2000)
  // La mise à jour reste une fonction de MàJ (ls => ls.map(...)) — jamais un
  // `lines` fermé sur une valeur périmée — et vérifie `!l.prixManuel` avant
  // d'écraser le prix. AGNR15 — le prix servi (HT) est converti au taux de la
  // ligne (`ttcExactFromHt`), jamais écrit tel quel dans le champ TTC.
  // ATOT28 — le HT servi est en plus PORTÉ (`prixHtOrigine`), renvoyé tel quel.
  assert.match(body, /setLines\(ls => ls\.map\(l =>\s*\(l\._key === key && !l\.prixManuel\)\s*\? \{ \.\.\.l, prix_unit_ttc: String\(ttcExactFromHt\(data\.prix, l\.taux_tva\)\),\s*prixHtOrigine: \(parseFloat\(data\.prix\) \|\| 0\)\.toFixed\(2\) \}\s*: l\)\)/)
  assert.doesNotMatch(body, /prix_unit_ttc: String\(data\.prix\)/)
})

test('l\'effet [clientId, lines.length] ne résout que les lignes NOUVELLES (ou toutes au changement de client), jamais un prix relu (AGNR16)', () => {
  assert.match(DG, /\[clientId, lines\.length\]/)
  // AGNR16 — l'ancien effet rappelait refreshTarif sur TOUTES les lignes à
  // produit (rouvrir ?edit= réécrivait 1 200,00 en 818,18 HT sans geste).
  assert.equal(DG.indexOf('lines.forEach(l => { if (l.produit) refreshTarif(l._key, l.produit, l.quantite) })'), -1,
    "l'effet ne doit plus résoudre toutes les lignes sans condition")
  const idx = DG.indexOf('const clesTarifVues = useRef(new Set())')
  assert.ok(idx > -1, "l'effet listes-de-prix (AGNR16) introuvable")
  const bloc = DG.slice(idx, idx + 700)
  assert.match(bloc, /if \(!l\.produit \|\| l\.prixRelu\) return/)
  assert.match(bloc, /if \(nouvelle \|\| clientChange\) refreshTarif\(l\._key, l\.produit, l\.quantite\)/)
})
