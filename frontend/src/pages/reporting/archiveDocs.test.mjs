import { test } from 'node:test'
import assert from 'node:assert/strict'
import { TYPE_LABELS, typeLabel, sortDocsDesc } from './archiveDocs.js'

// N32 — l'archive doit afficher des libellés FR pour chaque type de document
// (devis, facture, avoir, BC + post-vente) et trier du plus récent au plus
// ancien.

test('typeLabel maps known doc types to French labels', () => {
  assert.equal(typeLabel({ type: 'devis' }), 'Devis')
  assert.equal(typeLabel({ type: 'facture' }), 'Facture')
  assert.equal(typeLabel({ type: 'avoir' }), 'Avoir')
  assert.equal(typeLabel({ type: 'bon_commande' }), 'Bon de commande')
  assert.equal(typeLabel({ type: 'pv_reception' }), 'PV de réception')
  assert.equal(typeLabel({ type: 'bon_livraison' }), 'Bon de livraison')
  assert.equal(typeLabel({ type: 'dossier_remise' }), 'Dossier de remise')
  assert.equal(typeLabel({ type: 'attestation' }), 'Attestation')
})

test('typeLabel falls back to provided label then raw type', () => {
  assert.equal(typeLabel({ type: 'inconnu', label: 'Autre' }), 'Autre')
  assert.equal(typeLabel({ type: 'xyz' }), 'xyz')
})

test('all expected post-sale + sales types are covered', () => {
  for (const t of ['devis', 'facture', 'avoir', 'bon_commande',
    'pv_reception', 'bon_livraison', 'dossier_remise', 'attestation']) {
    assert.ok(TYPE_LABELS[t], `missing label for ${t}`)
  }
})

test('sortDocsDesc orders newest first, null dates last', () => {
  const out = sortDocsDesc([
    { type: 'a', date: '2026-01-01' },
    { type: 'b', date: null },
    { type: 'c', date: '2026-06-01' },
  ])
  assert.deepEqual(out.map(d => d.type), ['c', 'a', 'b'])
})

test('sortDocsDesc does not mutate the input array', () => {
  const input = [{ type: 'a', date: '2026-01-01' }, { type: 'c', date: '2026-06-01' }]
  const copy = [...input]
  sortDocsDesc(input)
  assert.deepEqual(input, copy)
})
