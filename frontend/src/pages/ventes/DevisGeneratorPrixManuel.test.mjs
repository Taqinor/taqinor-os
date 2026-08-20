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
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

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
  const body = DG.slice(start, start + 1200)
  // La mise à jour reste une fonction de MàJ (ls => ls.map(...)) — jamais un
  // `lines` fermé sur une valeur périmée — et vérifie `!l.prixManuel` avant
  // d'écraser le prix.
  assert.match(body, /setLines\(ls => ls\.map\(l =>\s*\n?\s*\(l\._key === key && !l\.prixManuel\) \? \{ \.\.\.l, prix_unit_ttc: String\(data\.prix\) \} : l\)\)/)
})

test('l\'effet [clientId, lines.length] appelle refreshTarif sur toutes les lignes à produit (déclencheur du bug — reste inchangé, la garde vit dans refreshTarif)', () => {
  assert.match(DG, /\[clientId, lines\.length\]/)
  const idx = DG.indexOf('lines.forEach(l => { if (l.produit) refreshTarif(l._key, l.produit, l.quantite) })')
  assert.ok(idx > -1, "l'effet listes-de-prix (déclencheur du bug N2) introuvable")
})
