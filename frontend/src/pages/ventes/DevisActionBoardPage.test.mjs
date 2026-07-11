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
// ARC54 — les routes ventes sont désormais déclarées dans le module-config
// (features/ventes/module.config.jsx), plus dans router/index.jsx inline.
const ROUTER_SRC = readFileSync(
  join(HERE, '../../features/ventes/module.config.jsx'), 'utf8')

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

test('QX29 : la route est enregistrée en ajout (module-config ARC54, pattern existant conservé)', () => {
  assert.match(ROUTER_SRC, /const DevisActionBoardPage = lazy\(\(\) => import\('\.\.\/\.\.\/pages\/ventes\/DevisActionBoardPage'\)\)/)
  assert.match(ROUTER_SRC, /path: '\/ventes\/devis\/action-requise', component: DevisActionBoardPage/)
  // Le reste des routes ventes existantes n'a pas été supprimé.
  assert.match(ROUTER_SRC, /path: '\/ventes\/devis', component: DevisList/)
  assert.match(ROUTER_SRC, /path: '\/ventes\/devis\/nouveau'/)
})
