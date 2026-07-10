// QX29 — « Relances du jour » : new DevisActionBoardPage mirrors
// SavActionBoardPage (4 buckets: sent-no-response/accepted-not-invoiced/
// refused-without-motif/expiring-soon), every row deep-links via ?devis= with
// tel/wa shortcuts, and the route is registered append-only. Verified against
// SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/ventes/DevisActionBoardPage.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisActionBoardPage.jsx'), 'utf8')
const API_SRC = readFileSync(join(HERE, '../../api/ventesApi.js'), 'utf8')
const ROUTER_SRC = readFileSync(join(HERE, '../../router/index.jsx'), 'utf8')

test('QX29 : les 4 buckets attendus sont déclarés', () => {
  for (const key of ['envoyes_sans_reponse', 'acceptes_non_factures', 'refuses_sans_motif', 'expirant_bientot']) {
    assert.match(SRC, new RegExp(`key: '${key}'`))
  }
})

test('QX29 : chaque ligne se lie en profondeur via ?devis=<pk> (QX12)', () => {
  assert.match(SRC, /navigate\(`\/ventes\/devis\?devis=\$\{id\}`\)/)
})

test('QX29 : raccourcis tel:/wa.me directs par ligne', () => {
  assert.match(SRC, /const telHref = /)
  assert.match(SRC, /const waHref = /)
  assert.match(SRC, /href=\{tel\}/)
  assert.match(SRC, /href=\{wa\}/)
})

test('QX29 : ventesApi expose l\'action-board (contrat backend)', () => {
  assert.match(API_SRC, /getDevisActionBoard: \(\) => api\.get\('\/ventes\/devis\/action-requise\/'\)/)
})

test('QX29 : la route est enregistrée en ajout (append-only, pattern existant conservé)', () => {
  assert.match(ROUTER_SRC, /const DevisActionBoardPage = lazy\(\(\) => import\('\.\.\/pages\/ventes\/DevisActionBoardPage'\)\)/)
  assert.match(ROUTER_SRC, /path: '\/ventes\/devis\/action-requise'/)
  // Le reste des routes ventes existantes n'a pas été supprimé.
  assert.match(ROUTER_SRC, /path: '\/ventes\/devis', loader: authLoader, element: <WithLayout><DevisList \/><\/WithLayout>/)
  assert.match(ROUTER_SRC, /path: '\/ventes\/devis\/nouveau'/)
})
