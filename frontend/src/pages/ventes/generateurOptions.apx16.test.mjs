// APX16 — Générateur : les DEUX options côte à côte + les modèles visibles
// dès la création.
//   1. le scénario « Les deux (Sans + Avec) » construisait deux options mais
//      le rail n'affichait qu'UN total : impossible de voir l'écart pendant
//      la construction ;
//   2. le panneau de modèles n'apparaissait qu'en ÉDITION (`{editDevis && …}`),
//      donc on ne pouvait pas PARTIR d'un modèle — le besoin le plus fréquent ;
//   3. un vert `text-green-600` codé en dur (invisible/faux en sombre).
// Les gardes du générateur (`noValidate`, `step="any"`) restent intactes.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const gen = readFileSync(path.join(__dirname, 'DevisGenerator.jsx'), 'utf8')
const panel = readFileSync(path.join(__dirname, 'DevisPresetPanel.jsx'), 'utf8')

test('le rail montre les DEUX totaux quand le scénario est double', () => {
  assert.match(gen, /\{showSans && showAvec \? \(/)
  assert.match(gen, /data-testid=\{avecRec \? 'gen-rail-total-sans' : 'gen-rail-total'\}/)
  assert.match(gen, /data-testid=\{avecRec \? 'gen-rail-total' : 'gen-rail-total-avec'\}/)
  assert.match(gen, /label="Total sans batterie · TTC"/)
  assert.match(gen, /label="Total avec batterie · TTC"/)
})

test('l’écart entre options est affiché en MAD ET en %', () => {
  assert.match(gen, /const ecartOptions = \(showSans && showAvec\)/)
  assert.match(gen, /const ecartOptionsPct =/)
  assert.match(gen, /data-testid="gen-rail-ecart"/)
  assert.match(gen, /Écart batterie/)
})

test('les modèles sont visibles DÈS LA CRÉATION (plus de garde editDevis)', () => {
  assert.match(gen, /<DevisPresetPanel devisId=\{editDevis\?\.id\} onApplied=\{handlePresetApplied\} \/>/)
  assert.doesNotMatch(gen, /\{editDevis && \(\s*\r?\n?\s*<DevisPresetPanel/)
  // Le panneau ne s'auto-annule plus quand l'id est absent.
  assert.doesNotMatch(panel, /if \(!devisId\) return null/)
})

test('un devis VIERGE applique le modèle localement, sans endpoint nouveau', () => {
  // Pas d'id serveur → on lit l'instantané de lignes DÉJÀ sérialisé.
  assert.match(panel, /if \(!devisId\) \{[\s\S]{0,400}?preset\.lignes_snapshot/)
  // La section « Enregistrer » dit honnêtement qu'elle attend le devis.
  assert.match(panel, /Disponible une fois le devis créé/)
  // Aucun nouvel appel d'API n'a été introduit.
  const calls = panel.match(/ventesApi\.\w+/g) ?? []
  assert.deepEqual(
    [...new Set(calls)].sort(),
    ['ventesApi.applyPreset', 'ventesApi.deletePreset', 'ventesApi.getPresets', 'ventesApi.savePreset'],
  )
})

test('plus aucune couleur codée en dur dans le panneau de modèles', () => {
  assert.doesNotMatch(panel, /text-green-600|text-red-600|#[0-9a-fA-F]{6}/)
  assert.match(panel, /text-success/)
})

test('les gardes de saisie du générateur sont intactes (jamais de valeur rejetée)', () => {
  assert.match(gen, /<form id="gen-form"[\s\S]{0,200}?noValidate/)
  assert.doesNotMatch(gen, /step="0\.\d+"/)
})
