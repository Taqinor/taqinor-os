import test from 'node:test'
import assert from 'node:assert/strict'

import {
  GARANTIE_ETATS,
  garantieLabel,
  filterEquipements,
  sortEquipements,
  EMPTY_EQUIP_FILTERS,
} from './equipement.js'

test("garantieLabel reflète l'état de garantie", () => {
  assert.match(
    garantieLabel({ garantie_etat: 'sous_garantie', date_fin_garantie: '2030-01-15' }),
    /Sous garantie jusqu'au/)
  assert.match(
    garantieLabel({ garantie_etat: 'expire_bientot', garantie_jours_restants: 30, date_fin_garantie: '2026-07-13' }),
    /Expire dans 30 j/)
  assert.equal(garantieLabel({ garantie_etat: 'hors_garantie' }), 'Hors garantie')
  assert.equal(garantieLabel({ garantie_etat: 'non_renseignee' }), 'Garantie non renseignée')
  assert.equal(garantieLabel({}), 'Garantie non renseignée')
})

test('chaque état de garantie a un libellé et une couleur', () => {
  for (const k of ['sous_garantie', 'expire_bientot', 'hors_garantie', 'non_renseignee']) {
    assert.ok(GARANTIE_ETATS[k]?.label, `libellé manquant pour ${k}`)
    assert.ok(GARANTIE_ETATS[k]?.color, `couleur manquante pour ${k}`)
  }
})

test('filterEquipements : par modèle, par état de garantie, recherche', () => {
  const rows = [
    { id: 1, produit: 10, produit_nom: 'Onduleur A', produit_marque: 'Huawei', numero_serie: 'SN1', garantie_etat: 'sous_garantie' },
    { id: 2, produit: 10, produit_nom: 'Onduleur A', produit_marque: 'Huawei', numero_serie: 'SN2', garantie_etat: 'expire_bientot' },
    { id: 3, produit: 20, produit_nom: 'Panneau B', produit_marque: 'Canadian', numero_serie: 'SN3', garantie_etat: 'non_renseignee' },
  ]
  assert.deepEqual(
    filterEquipements(rows, { ...EMPTY_EQUIP_FILTERS, produit: 10 }).map(r => r.id), [1, 2])
  assert.deepEqual(
    filterEquipements(rows, { ...EMPTY_EQUIP_FILTERS, garantie: 'expire_bientot' }).map(r => r.id), [2])
  assert.deepEqual(
    filterEquipements(rows, { ...EMPTY_EQUIP_FILTERS, q: 'canadian' }).map(r => r.id), [3])
  assert.equal(filterEquipements(rows, EMPTY_EQUIP_FILTERS).length, 3)
})

test('sortEquipements : tri par date de fin de garantie (vides en fin)', () => {
  const rows = [
    { id: 1, date_fin_garantie: '2030-01-01' },
    { id: 2, date_fin_garantie: null },
    { id: 3, date_fin_garantie: '2026-06-01' },
  ]
  assert.deepEqual(
    sortEquipements(rows, 'date_fin_garantie', 'asc').map(r => r.id), [3, 1, 2])
})
