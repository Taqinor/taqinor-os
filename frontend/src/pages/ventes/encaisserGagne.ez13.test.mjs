// EZ13 — Le bouton dangereux dégradé : « ✓ Payée » ne gagne plus contre
// « ⚡ Encaisser ».
// État d'avant : les deux boutons étaient CÔTE À CÔTE dans la rangée, « Payée »
// en `variant="success"` (donc plus attirant). Or « Payée » est le bouton
// PAUVRE : marquage sec qui DÉTRUIT le mode, la date et la référence du
// règlement, quand « Encaisser » capture tout. Sur une liste chargée, le
// pauvre gagnait.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const src = readFileSync(path.join(__dirname, 'FactureList.jsx'), 'utf8')
const dialog = readFileSync(path.join(__dirname, 'PaiementDialog.jsx'), 'utf8')
const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')

test('« Payée » a quitté la rangée d’actions rapides', () => {
  // Plus aucun bouton de marquage sec dans la rangée.
  assert.doesNotMatch(code, /<Button size="sm" variant="success"[\s\S]{0,220}?marquerPayeeFacture/)
  assert.doesNotMatch(code, /<Check \/> Payée/)
})

test('« Encaisser » est l’unique action rapide d’encaissement', () => {
  // Une seule formulation, en action primaire (`variant="default"`).
  assert.doesNotMatch(code, /Enregistrer paiement/)
  const encaisser = code.match(/<Zap className="size-3\.5" aria-hidden="true" \/> Encaisser/g) || []
  assert.equal(encaisser.length, 2, 'action recommandée + repli, tous deux « Encaisser »')
})

test('le marquage sec vit dans le menu ⋯, derrière une confirmation qui EXPLIQUE', () => {
  assert.match(src, /data-testid="marquer-payee"/)
  assert.match(src, /Marquer payée \(sans détail\)/)
  assert.match(src, /<ConfirmDialog/)
  // La confirmation nomme ce qu'on perd — jamais « êtes-vous sûr ? ».
  assert.match(src, /Le MODE de règlement, la DATE et la RÉFÉRENCE ne seront pas enregistrés/)
  // Et elle propose l'échappatoire riche.
  assert.match(src, /Préférez « Encaisser »/)
})

test('le « paiement simple » existe DANS le dialogue, sans rien détruire', () => {
  assert.match(dialog, /data-testid="paiement-simple-hint"/)
  // Tout est réellement pré-rempli : reste dû, date du jour, dernier mode.
  assert.match(dialog, /setPayMontant\(facture\.montant_du \?\? ''\)/)
  assert.match(dialog, /setPayDate\(todayIso\(\)\)/)
  assert.match(dialog, /setPayMode\(lireDernierMode\(\)\)/)
})
