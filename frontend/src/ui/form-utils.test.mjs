import test from 'node:test'
import assert from 'node:assert/strict'
import {
  isEmptyValue, runValidation, hasErrors, errorSummary, shallowEqualValues, isDirty,
  required, minLength, email, numberInRange, atLeastField,
} from './form-utils.js'

test('isEmptyValue : chaînes/null/tableaux', () => {
  assert.equal(isEmptyValue(''), true)
  assert.equal(isEmptyValue('  '), true)
  assert.equal(isEmptyValue(null), true)
  assert.equal(isEmptyValue(undefined), true)
  assert.equal(isEmptyValue([]), true)
  assert.equal(isEmptyValue('x'), false)
  assert.equal(isEmptyValue(0), false) // 0 n'est pas vide
  assert.equal(isEmptyValue(['a']), false)
})

test('validateurs : required / minLength / email / numberInRange', () => {
  assert.equal(required()(''), 'Ce champ est obligatoire.')
  assert.equal(required()('ok'), null)
  assert.equal(minLength(3)('ab'), 'Au moins 3 caractères.')
  assert.equal(minLength(3)('abc'), null)
  assert.equal(minLength(3)(''), null) // vide → laissé à required
  assert.equal(email()('bad'), 'Adresse e-mail invalide.')
  assert.equal(email()('a@b.co'), null)
  assert.equal(email()(''), null)
  assert.equal(numberInRange(1, 10)('0'), 'Minimum 1.')
  assert.equal(numberInRange(1, 10)('11'), 'Maximum 10.')
  assert.equal(numberInRange(1, 10)('5'), null)
  assert.equal(numberInRange(1, 10)('5,5'), null) // virgule décimale tolérée
  assert.equal(numberInRange(1, 10)('abc'), 'Nombre invalide.')
})

test('runValidation : 1ère erreur par champ, ignore les champs OK', () => {
  const rules = {
    nom: [required('Nom requis.')],
    email: [required('Email requis.'), email()],
  }
  const errs = runValidation({ nom: '', email: 'bad' }, rules)
  assert.equal(errs.nom, 'Nom requis.')
  assert.equal(errs.email, 'Adresse e-mail invalide.') // required passe, email échoue
  assert.equal(hasErrors(errs), true)

  const ok = runValidation({ nom: 'Reda', email: 'r@x.co' }, rules)
  assert.deepEqual(ok, {})
  assert.equal(hasErrors(ok), false)
})

test('validation croisée : atLeastField (période début ≤ fin)', () => {
  const rules = { fin: [atLeastField('debut', 'La fin doit suivre le début.')] }
  assert.equal(runValidation({ debut: 5, fin: 3 }, rules).fin, 'La fin doit suivre le début.')
  assert.deepEqual(runValidation({ debut: 5, fin: 9 }, rules), {})
  assert.deepEqual(runValidation({ debut: '', fin: 9 }, rules), {}) // début vide → pas d'erreur croisée
})

test('errorSummary : ordonné par fieldOrder puis apparition', () => {
  const errors = { email: 'E', nom: 'N', tel: 'T' }
  const summary = errorSummary(errors, ['nom', 'email'])
  assert.deepEqual(summary.map((e) => e.field), ['nom', 'email', 'tel'])
  assert.equal(summary[0].message, 'N')
  assert.deepEqual(errorSummary(null), [])
  assert.deepEqual(errorSummary({}), [])
})

test('shallowEqualValues / isDirty', () => {
  assert.equal(shallowEqualValues({ a: 1, b: 'x' }, { b: 'x', a: 1 }), true) // ordre ignoré
  assert.equal(shallowEqualValues({ a: 1 }, { a: 2 }), false)
  assert.equal(shallowEqualValues({ a: 1 }, { a: 1, b: 2 }), false)
  assert.equal(shallowEqualValues({ tags: ['a', 'b'] }, { tags: ['a', 'b'] }), true)
  assert.equal(shallowEqualValues({ tags: ['a', 'b'] }, { tags: ['a', 'c'] }), false)

  const initial = { nom: 'Reda', tags: ['solaire'] }
  assert.equal(isDirty(initial, { nom: 'Reda', tags: ['solaire'] }), false)
  assert.equal(isDirty(initial, { nom: 'Reda K.', tags: ['solaire'] }), true)
  assert.equal(isDirty(initial, { nom: 'Reda', tags: ['solaire', 'pompage'] }), true)
})
