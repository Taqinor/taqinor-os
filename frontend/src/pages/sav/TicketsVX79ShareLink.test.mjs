// VX79 — Lien interne partageable pour les tickets SAV : /sav?id=<pk> ouvre la
// fiche du ticket ciblé (patron ?lead= de LeadsPage), bouton « Copier le lien »
// pointé vers l'URL INTERNE, id introuvable → EmptyState inline.
// Vérifié contre la SOURCE (pas de node_modules dans ce worktree).
//   node --test src/pages/sav/TicketsVX79ShareLink.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'TicketsPage.jsx'), 'utf8')

test('VX79 : ?id=<pk> ouvre le ticket ciblé (état dérivé, patron ?lead=)', () => {
  assert.match(SRC, /useSearchParams/)
  assert.match(SRC, /const wantedId = searchParams\.get\('id'\)/)
  assert.match(SRC, /const deepTicket = useMemo\(/)
  assert.match(SRC, /const detailTicket = selected \?\? deepTicket/)
  assert.match(SRC, /<TicketDetail ticket=\{detailTicket\}/)
})

test('VX79 : fermer retire le paramètre ?id de l\'URL (ne ré-ouvre pas)', () => {
  assert.match(SRC, /const clearDeepLink = \(\) =>/)
  assert.match(SRC, /next\.delete\('id'\)/)
  assert.match(SRC, /const closeDetail = \(\) => \{ setSelected\(null\); clearDeepLink\(\) \}/)
  assert.match(SRC, /onClose=\{closeDetail\}/)
})

test('VX79 : « Copier le lien » pointe vers l\'URL INTERNE /sav?id=<pk>', () => {
  assert.match(SRC, /const copierLien = async \(t\) =>/)
  assert.match(SRC, /window\.location\.origin\}\/sav\?id=\$\{t\.id\}/)
  assert.match(SRC, /navigator\.clipboard\?\.writeText/)
  assert.match(SRC, /onClick=\{\(\) => copierLien\(detailTicket\)\}/)
})

test('VX79 : ?id=<pk> introuvable → EmptyState inline (pas de page blanche)', () => {
  assert.match(SRC, /const deepMissing = !!wantedId && !loading && !error && !deepTicket/)
  const block = SRC.slice(
    SRC.indexOf('{deepMissing && ('),
    SRC.indexOf('{deepMissing && (') + 400)
  assert.match(block, /<EmptyState/)
  assert.match(block, /Ticket introuvable/)
})
