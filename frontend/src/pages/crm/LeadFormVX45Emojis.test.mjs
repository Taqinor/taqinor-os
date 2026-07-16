// VX45 — La voix TAQINOR : microcopie FR premium + fin des emojis-icônes.
// Les emojis fonctionnels 💡🏠⚡📝 de LeadForm.jsx sont remplacés par leurs
// équivalents lucide (Lightbulb/Home/Zap/FileText) : le rendu emoji varie par
// OS et casse le système d'icônes. Verified against SOURCE (no node_modules
// in this worktree/lane).
//   node --test src/pages/crm/LeadFormVX45Emojis.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')

test('VX45 : Lightbulb importé et utilisé à la place de 💡 (facture)', () => {
  assert.match(SRC, /Lightbulb/)
  assert.match(SRC, /<Lightbulb className="lead-subbar-icon"/)
})

test('VX45 : Home rendu devant « Concevoir la toiture » à la place de 🏠', () => {
  assert.match(SRC, /<Home aria-hidden="true" size=\{14\} \/> Concevoir la toiture/)
})

test('VX45 : Zap rendu devant « Devis automatique » à la place de ⚡', () => {
  assert.match(SRC, /<Zap aria-hidden="true" size=\{14\} \/> Devis automatique/)
})

test('VX45 : FileText rendu devant « Devis modifiable » à la place de 📝', () => {
  assert.match(SRC, /<FileText aria-hidden="true" size=\{14\} \/> Devis modifiable/)
})

test('VX45 : aucun des emojis fonctionnels ciblés ne reste dans le code exécutable', () => {
  const codeLines = SRC.split('\n').filter((l) => !l.trim().startsWith('//'))
  const code = codeLines.join('\n')
  // 💡🏠📝 ne doivent plus apparaître du tout (⚡ reste légitime dans des
  // commentaires de code référençant l'ancien comportement — non testé ici).
  for (const emoji of ['💡', '🏠', '📝']) {
    assert.ok(!code.includes(emoji), `emoji ${emoji} encore présent dans le code`)
  }
})
