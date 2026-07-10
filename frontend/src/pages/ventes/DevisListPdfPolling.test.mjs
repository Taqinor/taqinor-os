// QX21fe — PDF polling: past 30 s (15 fast attempts × 2 s), DevisList must NOT
// give up — it shows a resumable "toujours en cours" state and keeps polling
// (slower), and never dispatches a second genererPdfDevis for the same click.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/ventes/DevisListPdfPolling.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')

const genererUnPdfBody = SRC.slice(
  SRC.indexOf('const genererUnPdf = async'),
  SRC.indexOf('const handleGenererPdf = async'))

test('QX21 : un seul dispatch(genererPdfDevis) par appel — jamais de job Celery dupliqué', () => {
  const dispatchCalls = genererUnPdfBody.match(/dispatch\(genererPdfDevis\(/g) ?? []
  assert.equal(dispatchCalls.length, 1)
})

test('QX21 : passé 15 tentatives rapides (30 s), le polling ne s\'arrête plus — il ralentit', () => {
  assert.match(genererUnPdfBody, /FAST_ATTEMPTS = 15/)
  assert.match(genererUnPdfBody, /const slow = attempts >= FAST_ATTEMPTS/)
  // L'ancien comportement `if (attempts++ > 15) { ...; return }` (abandon) ne
  // doit plus exister : aucun `return` prématuré qui coupe le polling.
  assert.doesNotMatch(genererUnPdfBody, /attempts\+\+ > 15/)
  assert.match(genererUnPdfBody, /setTimeout\(poll, slow \? 10000 : 2000\)/)
})

test('QX21 : l\'état « toujours en cours » est posé et lu par la ligne du tableau', () => {
  assert.match(SRC, /const \[pdfSlowPoll, setPdfSlowPoll\] = useState\(\{\}\)/)
  assert.match(genererUnPdfBody, /setPdfSlowPoll\(prev => \(\{ \.\.\.prev, \[d\.id\]: true \}\)\)/)
  // Se réinitialise proprement une fois le fichier prêt.
  assert.match(genererUnPdfBody, /setPdfSlowPoll\(prev => \(\{ \.\.\.prev, \[d\.id\]: false \}\)\)/)
  assert.match(SRC, /const isSlowPolling = !!pdfSlowPoll\[d\.id\]/)
  assert.match(SRC, /PDF toujours en cours/)
})
