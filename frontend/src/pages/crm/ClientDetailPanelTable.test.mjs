// VX152 — Fin des moteurs de table parallèles : la fiche client fabriquait un
// TROISIÈME moteur `DocTable` maison pour Devis/Factures/Chantiers. Elle rejoint
// le primitif `Table` partagé (reporting) — plus aucune <table> HTML écrite à la
// main dans ClientDetailPanel. Vérification de SOURCE (pas de node_modules
// installés dans ce lane — cf. RolesManagementDataTable.test.mjs) :
//   node --test src/pages/crm/ClientDetailPanelTable.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ClientDetailPanel.jsx'), 'utf8')

test('la fiche client utilise le primitif Table partagé, plus de <table> HTML maison', () => {
  assert.match(SRC, /import \{ Table \} from '\.\.\/reporting\/Table'/)
  assert.match(SRC, /<Table\b/)
  // DoD : grep "<table" (minuscule) = 0 dans ClientDetailPanel.jsx.
  assert.doesNotMatch(SRC, /<table/)
})
