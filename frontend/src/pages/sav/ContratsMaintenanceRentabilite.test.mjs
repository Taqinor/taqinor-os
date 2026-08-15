// WIR231/XSAV18 — 5e vue « Rentabilité » de ContratsMaintenance : P&L (revenu/
// coût/marge) par contrat, réservé à la permission prix d'achat côté serveur
// — un 403 affiche SEULEMENT le message FR du serveur, jamais une valeur de
// coût/marge dans le DOM. Vérification de SOURCE (JSX, pas de node_modules
// installés dans ce lane — cf. SigneDialog.test.mjs).
//   node --test src/pages/sav/ContratsMaintenanceRentabilite.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ContratsMaintenance.jsx'), 'utf8')
const API_SRC = readFileSync(join(HERE, '..', '..', 'api', 'savApi.js'), 'utf8')

test('savApi expose getRentabiliteContrats (WIR231)', () => {
  assert.match(API_SRC, /getRentabiliteContrats: \(\) => api\.get\('\/sav\/contrats-maintenance\/rentabilite\/'\)/)
})

test('la vue "rentabilite" existe dans le segmenté', () => {
  assert.match(SRC, /value: 'rentabilite', label: 'Rentabilité'/)
})

test('le tableau de rentabilité ne se rend QUE si `rentabilite` est non-null (succès serveur)', () => {
  assert.match(SRC, /\{!rentabiliteLoading && rentabilite != null && \(/)
  // Jamais une condition qui masque juste en CSS (ex. `hidden`/`display:none`
  // sur le tableau) : la ligne conditionnelle contrôle le RENDU JSX lui-même.
  const tableBlock = SRC.slice(SRC.indexOf('data-testid="rentabilite-table"'), SRC.indexOf('</table>'))
  assert.doesNotMatch(tableBlock, /display:\s*none/)
  assert.doesNotMatch(tableBlock, /\bhidden\b/)
})

test("l'erreur 403 (ou autre) est affichée en FR via frenchError, jamais un texte générique brut", () => {
  assert.match(SRC, /setRentabiliteError\(frenchError\(err, 'Impossible de charger la rentabilité\.'\)\)/)
  assert.match(SRC, /setRentabilite\(null\)/)
})

test("le tri (marge croissante) vient du SERVEUR, jamais retrié côté écran", () => {
  const tableBlock = SRC.slice(SRC.indexOf('data-testid="rentabilite-table"'), SRC.indexOf('</table>'))
  assert.doesNotMatch(tableBlock, /\.sort\(/)
  assert.match(tableBlock, /rentabilite\.map/)
})

test('la colonne Coût/Marge existe et vient de r.cout / r.marge (jamais recalculée)', () => {
  const tableBlock = SRC.slice(SRC.indexOf('data-testid="rentabilite-table"'), SRC.indexOf('</table>'))
  assert.match(tableBlock, /fmtDH\(r\.cout\)/)
  assert.match(tableBlock, /fmtDH\(r\.marge\)/)
})
