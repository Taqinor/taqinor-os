// APXTMO — L'aperçu devis « Aperçu indisponible » (19/08/2026, prod).
// Cause mesurée : le rendu premium /proposal prend ~26 s À FROID sur le
// serveur (mesure curl : 26,3 s puis 0,4 s une fois le cache moteur chaud) ;
// le timeout GLOBAL axios (20 s, VX55) avortait donc CHAQUE premier aperçu
// → nginx 499 → repli « Vérifiez votre connexion » alors que le réseau va
// bien. Le correctif donne aux octets PDF un budget dédié (90 s) SANS toucher
// au timeout global de 20 s (VX55 reste la règle pour tout le reste), et le
// panneau annule le rendu en vol quand il devient inutile (changement de
// format / fermeture) pour ne pas empiler des rendus de ~26 s sur les
// workers gunicorn. Vérifié contre le SOURCE (pas de node_modules ici).
//   node --test src/api/ventesApi.pdfTimeout.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const VENTES_API_SRC = readFileSync(join(HERE, 'ventesApi.js'), 'utf8')
const LDP_SRC = readFileSync(
  join(HERE, '../pages/crm/leads/LeadDevisPanel.jsx'), 'utf8')

test('APXTMO : getProposalPdf porte un timeout dédié ≥ 60 s (rendu à froid ~26 s mesuré)', () => {
  const start = VENTES_API_SRC.indexOf('getProposalPdf:')
  assert.notEqual(start, -1, 'getProposalPdf introuvable')
  const block = VENTES_API_SRC.slice(start, start + 400)
  const m = block.match(/timeout:\s*(\d+)/)
  assert.ok(m, 'getProposalPdf ne porte aucun timeout dédié — le global 20 s avorte le rendu à froid (~26 s)')
  assert.ok(Number(m[1]) >= 60000, `timeout ${m[1]} ms trop court pour un rendu à froid de ~26 s`)
})

test('APXTMO : getProposalPdf accepte un config (signal d\'annulation) transmis à axios', () => {
  const start = VENTES_API_SRC.indexOf('getProposalPdf:')
  const block = VENTES_API_SRC.slice(start, start + 400)
  assert.match(block, /config\s*=\s*\{\}/)
  assert.match(block, /\.\.\.config/)
})

test('APXTMO : l\'effet d\'aperçu du panneau lead ANNULE le rendu en vol au cleanup', () => {
  // Un AbortController est créé dans l'effet et transmis à l'appel…
  const ctrlIdx = LDP_SRC.indexOf('new AbortController()')
  assert.notEqual(ctrlIdx, -1, 'aucun AbortController dans LeadDevisPanel')
  const effectBlock = LDP_SRC.slice(ctrlIdx, ctrlIdx + 1600)
  assert.match(effectBlock,
    /getProposalPdf\([\s\S]{0,160}?\{ signal: controller\.signal \}/,
    'le fetch d\'aperçu ne transmet pas le signal d\'annulation')
  // …et le cleanup de l'effet l'avorte réellement.
  assert.match(effectBlock, /controller\.abort\(\)/,
    'le cleanup de l\'effet n\'avorte pas le rendu en vol')
})
