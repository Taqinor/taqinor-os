// VX80 — Feuille de style d'impression + boutons « Imprimer ».
// Smoke source-statique (aucun jsdom/mock — évite toute collision de rôles et
// le besoin d'un mock document.createElement) : vérifie que print.css existe et
// couvre l'essentiel, qu'il est importé une fois, et qu'un bouton window.print()
// est présent sur les trois écrans.
//   node --test src/styles/print.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const PRINT_CSS = read('print.css')
const INDEX_CSS = read('../index.css')
const DEVIS = read('../pages/ventes/DevisList.jsx')
const FACTURE = read('../pages/ventes/FactureList.jsx')
const INSTALL = read('../pages/installations/InstallationDetail.jsx')

test('print.css : tout est sous @media print (inerte à l’écran)', () => {
  assert.match(PRINT_CSS, /@media print\s*\{/)
  // Aucune règle top-level en dehors du bloc @media print et des commentaires.
  const withoutComments = PRINT_CSS.replace(/\/\*[\s\S]*?\*\//g, '')
  const firstBrace = withoutComments.indexOf('{')
  const beforeFirstRule = withoutComments.slice(0, firstBrace)
  assert.match(beforeFirstRule, /@media print\s*$/)
})

test('print.css : masque le chrome de la coquille', () => {
  for (const sel of ['.sidebar', '.header', '.bottom-tabbar', '.route-progress', 'button']) {
    assert.ok(PRINT_CSS.includes(sel), `sélecteur manquant : ${sel}`)
  }
  assert.match(PRINT_CSS, /display:\s*none\s*!important/)
})

test('print.css : noir-sur-blanc + @page 2cm + tables non tronquées', () => {
  assert.match(PRINT_CSS, /background:\s*#fff\s*!important/)
  assert.match(PRINT_CSS, /color:\s*#000\s*!important/)
  assert.match(PRINT_CSS, /@page\s*\{\s*margin:\s*2cm/)
  assert.match(PRINT_CSS, /overflow:\s*visible\s*!important/)
  assert.match(PRINT_CSS, /width:\s*auto\s*!important/)
  assert.match(PRINT_CSS, /page-break-inside:\s*avoid/)
})

test('print.css : rend le Sheet (role=dialog) statique et pleine page pour la checklist', () => {
  assert.match(PRINT_CSS, /\[role="dialog"\]\s*\{/)
  assert.match(PRINT_CSS, /position:\s*static\s*!important/)
})

test('index.css importe print.css exactement une fois', () => {
  const matches = INDEX_CSS.match(/@import\s+["'].*print\.css["']/g) || []
  assert.equal(matches.length, 1)
})

test('DevisList : bouton Imprimer → window.print()', () => {
  assert.match(DEVIS, /Printer/)
  assert.match(DEVIS, /onClick=\{\(\)\s*=>\s*window\.print\(\)\}/)
  assert.match(DEVIS, />\s*Imprimer\s*</)
})

test('FactureList : bouton Imprimer → window.print()', () => {
  assert.match(FACTURE, /Printer/)
  assert.match(FACTURE, /onClick=\{\(\)\s*=>\s*window\.print\(\)\}/)
  assert.match(FACTURE, />\s*Imprimer\s*</)
})

test('InstallationDetail : bouton Imprimer la checklist → window.print()', () => {
  assert.match(INSTALL, /Printer/)
  assert.match(INSTALL, /onClick=\{\(\)\s*=>\s*window\.print\(\)\}/)
  assert.match(INSTALL, />\s*Imprimer la checklist\s*</)
})
