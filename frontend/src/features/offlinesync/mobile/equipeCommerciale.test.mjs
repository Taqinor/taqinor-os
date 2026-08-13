// NTMOB26 — classement des relances en retard par commercial (logique pure).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classementParCommercial } from './equipeCommerciale.js'

test('NTMOB26: groupe par commercial et trie du plus chargé au moins', () => {
  const classement = classementParCommercial([
    { id: 1, owner: 11, owner_nom: 'Sara' },
    { id: 2, owner: 12, owner_nom: 'Younes' },
    { id: 3, owner: 12, owner_nom: 'Younes' },
  ])
  assert.deepEqual(classement.map((c) => [c.nom, c.leads.length]),
    [['Younes', 2], ['Sara', 1]])
})

test('NTMOB26: un lead sans propriétaire est regroupé sans en inventer un', () => {
  const classement = classementParCommercial([{ id: 4 }])
  assert.equal(classement.length, 1)
  assert.equal(classement[0].nom, 'Non attribué')
})

test('NTMOB26: liste vide', () => {
  assert.deepEqual(classementParCommercial(), [])
  assert.deepEqual(classementParCommercial([]), [])
})
