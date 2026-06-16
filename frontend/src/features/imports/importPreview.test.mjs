import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  statusLabel, summarize, canConfirm, IMPORT_TARGETS,
} from './importPreview.js'

test('IMPORT_TARGETS couvre leads/clients/produits', () => {
  const keys = IMPORT_TARGETS.map(t => t.target).sort()
  assert.deepEqual(keys, ['client', 'lead', 'produit'])
})

test('statusLabel : libellés FR', () => {
  assert.equal(statusLabel('create'), 'À créer')
  assert.equal(statusLabel('duplicate'), 'Doublon (ignoré)')
  assert.equal(statusLabel('error'), 'Erreur')
  assert.equal(statusLabel('inconnu'), 'inconnu')
})

test('summarize : résumé incluant colonnes non reconnues', () => {
  const s = summarize({
    total_rows: 5, will_create: 3, will_skip: 2,
    unmapped_columns: ['X', 'Y'],
  })
  assert.match(s, /5 ligne/)
  assert.match(s, /3 à créer/)
  assert.match(s, /2 ignorée/)
  assert.match(s, /2 colonne/)
})

test('summarize : null → chaîne vide', () => {
  assert.equal(summarize(null), '')
})

test('canConfirm : vrai seulement si des lignes sont créables', () => {
  assert.equal(canConfirm({ will_create: 2 }), true)
  assert.equal(canConfirm({ will_create: 0 }), false)
  assert.equal(canConfirm(null), false)
})
