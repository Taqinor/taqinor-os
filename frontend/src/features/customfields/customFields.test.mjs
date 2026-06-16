import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  defaultValueFor, buildCustomFieldsPayload, parseChoices, isDefinitionComplete,
} from './customFields.js'

test('defaultValueFor: boolean → false, autres → chaîne vide', () => {
  assert.equal(defaultValueFor('boolean'), false)
  assert.equal(defaultValueFor('text'), '')
  assert.equal(defaultValueFor('number'), '')
})

test('buildCustomFieldsPayload: ne garde que les clés connues', () => {
  const defs = [
    { field_key: 'a', field_type: 'text' },
    { field_key: 'b', field_type: 'number' },
  ]
  const out = buildCustomFieldsPayload(defs, { a: 'x', b: '5', ghost: 'z' })
  assert.deepEqual(out, { a: 'x', b: '5' })
  assert.equal('ghost' in out, false)
})

test('buildCustomFieldsPayload: vides → null, booléen → bool', () => {
  const defs = [
    { field_key: 'a', field_type: 'text' },
    { field_key: 'flag', field_type: 'boolean' },
  ]
  const out = buildCustomFieldsPayload(defs, { a: '', flag: undefined })
  assert.equal(out.a, null)
  assert.equal(out.flag, false)
})

test('parseChoices: trim, sans doublon ni vide, ordre préservé', () => {
  assert.deepEqual(parseChoices('A\n B \nA\n\nC'), ['A', 'B', 'C'])
  assert.deepEqual(parseChoices(''), [])
})

test('isDefinitionComplete: libellé requis', () => {
  assert.equal(isDefinitionComplete({ label: '', field_type: 'text' }), false)
  assert.equal(isDefinitionComplete({ label: 'X', field_type: 'text' }), true)
})

test('isDefinitionComplete: choice exige des options', () => {
  assert.equal(isDefinitionComplete({ label: 'X', field_type: 'choice', choices: '' }), false)
  assert.equal(isDefinitionComplete({ label: 'X', field_type: 'choice', choices: 'A\nB' }), true)
})

test('isDefinitionComplete: type inconnu rejeté', () => {
  assert.equal(isDefinitionComplete({ label: 'X', field_type: 'bogus' }), false)
})
