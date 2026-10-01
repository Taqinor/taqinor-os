// QJR654 — les libellés de statut DEVIS vivent dans UNE table
// (`devisStatuts.js`), importée par les huit écrans qui la recopiaient ; elle
// ne porte aucune clé du funnel STAGES.py (règles #2 et #4).
// Exécuté en CI : node --test src/features/ventes/devisStatutsUnique.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import * as devisStatuts from './devisStatuts.js'
import { DEVIS_BOARD_COLUMNS } from './devisBoard.js'
import { PIPELINE_STAGES } from '../crm/stages.js'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const ECRANS = [
  'features/crm/workspace/DevisTab.jsx',
  'features/crm/workspace/IdentityRail.jsx',
  'pages/ventes/DevisList.jsx',
  'features/ventes/devisBoard.js',
  'pages/crm/leads/SigneDialog.jsx',
  'pages/Dashboard.jsx',
  'pages/stock/ProduitDetail.jsx',
  'pages/visites/VisiteClientDevisPanel.jsx',
]

test('aucun des huit écrans ne recopie la table des libellés', () => {
  for (const rel of ECRANS) {
    const source = readFileSync(join(SRC, rel), 'utf-8')
    assert.doesNotMatch(source, /envoye:\s*'Envoyé'/, rel)
    assert.doesNotMatch(source, /accepte:\s*'Accepté'/, rel)
  }
})

test('la table unique : cinq statuts ordonnés, libellés, filtres', () => {
  assert.deepEqual(devisStatuts.DEVIS_STATUTS,
    ['brouillon', 'envoye', 'accepte', 'refuse', 'expire'])
  assert.equal(devisStatuts.STATUT_DEVIS_LABELS.envoye, 'Envoyé')
  assert.equal(devisStatuts.libelleStatutDevis('accepte'), 'Accepté')
  assert.equal(devisStatuts.libelleStatutDevis('inconnu'), 'inconnu')
  assert.deepEqual(devisStatuts.STATUT_DEVIS_FILTRES.map(f => f.value),
    ['tous', ...devisStatuts.DEVIS_STATUTS])
  assert.deepEqual(DEVIS_BOARD_COLUMNS.map(c => c.label),
    devisStatuts.DEVIS_STATUTS.map(s => devisStatuts.STATUT_DEVIS_LABELS[s]))
})

test('devisStatuts.js n’exporte aucune clé de STAGES.py (règle #2)', () => {
  const stages = new Set(PIPELINE_STAGES.map(s => (typeof s === 'string' ? s : s.key)))
  const valeurs = [
    ...devisStatuts.DEVIS_STATUTS,
    ...Object.keys(devisStatuts.STATUT_DEVIS_LABELS),
    ...Object.keys(devisStatuts),
  ]
  for (const v of valeurs) assert.equal(stages.has(v), false, v)
})
