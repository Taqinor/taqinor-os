// ADEV69 (C-ADEV-046) — `solar.autoFillLines`, le second composeur résidentiel
// (sans appelant de production depuis CIQ126/CIQ128), est SUPPRIMÉ : D-QJR5-9
// « un seul composeur, côté serveur » (`apps/ventes/domain/composition.py`).
// Ce test importe le module RÉEL (jamais une regex sur le source) et rougit si
// l'export revient.
// Run : node --test src/features/ventes/solar.codeMortAdev69.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'

import * as solar from './solar.js'

test('autoFillLines_n_est_plus_exporte', () => {
  assert.equal('autoFillLines' in solar, false,
    'solar.js ré-exporte autoFillLines : un second composeur JS est revenu (D-QJR5-9)')
})
