// VX158(b) — le jargon fiscal (FEC, liasse, IS…) se traduit : une phrase
// grise par bouton d'export, visible sans clic. Test SOURCE (le fichier
// importe tout un module useComptaList/ListShell — pas de rendu ici).
//   node --test src/features/compta/pages/FiscalitePage.vx158.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'FiscalitePage.jsx'), 'utf8')

test('VX158(b) : chaque export EXPORTS porte un champ help non vide', () => {
  const exportsBlock = SRC.match(/const EXPORTS = \[([\s\S]*?)\n\]/)[1]
  const helpMatches = [...exportsBlock.matchAll(/help: '([^']+)'/g)]
  const keyMatches = [...exportsBlock.matchAll(/key: '([^']+)'/g)]
  assert.equal(helpMatches.length, keyMatches.length,
    'chaque entrée EXPORTS doit porter une phrase help')
  for (const [, help] of helpMatches) {
    assert.ok(help.trim().length > 0)
  }
})

test('VX158(b) : la phrase help est rendue sous chaque bouton, sans clic ni tooltip', () => {
  assert.match(SRC, /\{exp\.help\}/)
  // Pas de tooltip/hover requis : la phrase est un <p> statique, pas un title=.
  assert.doesNotMatch(SRC, /title=\{exp\.help\}/)
})
