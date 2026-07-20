// VX45 — boutons ⚡ Express / 🔀 Doublons de LeadsPage.jsx remplacés par
// Zap/GitMerge lucide. Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageVX45Emojis.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('VX45 : Zap et GitMerge importés depuis lucide-react', () => {
  assert.match(SRC, /import \{ Upload, Download, X, Plus, MoreHorizontal, Zap, GitMerge \} from 'lucide-react'/)
})

test('VX45 : l\'item Express rend Zap au lieu de ⚡ (LB43 : Express vit dans le menu ⋯)', () => {
  assert.match(SRC, /<Zap aria-hidden="true" \/> Express/)
})

test('VX45 : l\'item de menu Doublons rend GitMerge au lieu de 🔀', () => {
  assert.match(SRC, /<GitMerge aria-hidden="true" \/> Doublons/)
})

test('VX45 : aucun emoji ⚡/🔀 littéral ne reste dans le code exécutable', () => {
  const codeLines = SRC.split('\n').filter((l) => !l.trim().startsWith('//'))
  const code = codeLines.join('\n')
  for (const emoji of ['⚡', '🔀']) {
    assert.ok(!code.includes(emoji), `emoji ${emoji} encore présent`)
  }
})
