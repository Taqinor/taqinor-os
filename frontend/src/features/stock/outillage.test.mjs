// F1 — Tests des helpers Outillage (équipement durable).
// Run with: node --test src/features/stock/outillage.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  emplacementLabel, statutMeta, filterOutillage,
} from './outillage.js'

test('emplacementLabel : libellés FR + repli', () => {
  assert.equal(emplacementLabel('depot'), 'Dépôt')
  assert.equal(emplacementLabel('camionnette'), 'Camionnette')
  assert.equal(emplacementLabel('en_intervention'), 'En intervention')
  assert.equal(emplacementLabel('inconnu'), 'inconnu')
  assert.equal(emplacementLabel(undefined), '—')
})

test('statutMeta : couleur + libellé connus, repli neutre', () => {
  assert.equal(statutMeta('disponible').label, 'Disponible')
  assert.equal(statutMeta('en_reparation').label, 'En réparation')
  assert.equal(statutMeta('perdu').color, '#b91c1c')
  assert.equal(statutMeta('zzz').color, '#64748b')
})

test('filterOutillage : filtre par emplacement + statut + recherche', () => {
  const list = [
    { nom: 'Perceuse', categorie: 'Électroportatif', asset_tag: 'T1', numero_serie: '', emplacement: 'depot', statut: 'disponible' },
    { nom: 'Échelle', categorie: 'Accès', asset_tag: 'T2', numero_serie: 'SN9', emplacement: 'camionnette', statut: 'en_reparation' },
  ]
  assert.deepEqual(filterOutillage(list, { emplacement: 'depot' }).map(o => o.nom), ['Perceuse'])
  assert.deepEqual(filterOutillage(list, { statut: 'en_reparation' }).map(o => o.nom), ['Échelle'])
  assert.deepEqual(filterOutillage(list, { search: 'perce' }).map(o => o.nom), ['Perceuse'])
  assert.deepEqual(filterOutillage(list, { search: 'SN9' }).map(o => o.nom), ['Échelle'])
  assert.equal(filterOutillage(list, { search: 'zzz' }).length, 0)
  assert.equal(filterOutillage(null).length, 0)
})
