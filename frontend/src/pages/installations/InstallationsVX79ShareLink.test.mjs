// VX79 — Lien interne partageable pour les chantiers : /chantiers?id=<pk> ouvre
// le panneau du chantier ciblé (patron ?lead= de LeadsPage), bouton « Copier le
// lien » pointé vers l'URL INTERNE, id introuvable → EmptyState inline.
// Vérifié contre la SOURCE (pas de node_modules dans ce worktree).
//   node --test src/pages/installations/InstallationsVX79ShareLink.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'InstallationsPage.jsx'), 'utf8')

test('VX79 : ?id=<pk> ouvre le chantier ciblé (état dérivé, patron ?lead=)', () => {
  assert.match(SRC, /useSearchParams/)
  assert.match(SRC, /const wantedId = searchParams\.get\('id'\)/)
  assert.match(SRC, /const deepItem = useMemo\(/)
  // Le panneau s'ouvre sur la sélection OU le chantier du lien profond.
  assert.match(SRC, /const detailItem = selected \?\? deepItem/)
  assert.match(SRC, /<InstallationDetail installation=\{detailItem\}/)
})

test('VX79 : fermer retire le paramètre ?id de l\'URL (ne ré-ouvre pas)', () => {
  assert.match(SRC, /const clearDeepLink = \(\) =>/)
  assert.match(SRC, /next\.delete\('id'\)/)
  assert.match(SRC, /const onClose = \(\) => \{ setSelected\(null\); clearDeepLink\(\) \}/)
})

test('VX79 : « Copier le lien » pointe vers l\'URL INTERNE /chantiers?id=<pk>', () => {
  assert.match(SRC, /const copierLien = async \(it\) =>/)
  assert.match(SRC, /window\.location\.origin\}\/chantiers\?id=\$\{it\.id\}/)
  assert.match(SRC, /navigator\.clipboard\?\.writeText/)
  assert.match(SRC, /onClick=\{\(\) => copierLien\(detailItem\)\}/)
})

test('VX79 : ?id=<pk> introuvable → EmptyState inline (pas de page blanche)', () => {
  assert.match(SRC, /const deepMissing = !!wantedId && !loading && !deepItem/)
  const block = SRC.slice(
    SRC.indexOf('{deepMissing && ('),
    SRC.indexOf('{deepMissing && (') + 400)
  assert.match(block, /<EmptyState/)
  assert.match(block, /Chantier introuvable/)
})
