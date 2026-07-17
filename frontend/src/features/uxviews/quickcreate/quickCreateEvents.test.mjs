import test from 'node:test'
import assert from 'node:assert/strict'

import {
  QUICK_CREATE_TYPES, isQuickCreateType, openQuickCreate, QUICK_CREATE_EVENT, filterQuickCreateTypes,
} from './quickCreateEvents.js'

test('QUICK_CREATE_TYPES liste les 4 types à modal (jamais "devis" — écran dédié)', () => {
  const ids = QUICK_CREATE_TYPES.map((t) => t.id)
  assert.deepEqual(ids, ['lead', 'client', 'ticket', 'produit'])
  assert.ok(!ids.includes('devis'))
})

test('isQuickCreateType', () => {
  assert.equal(isQuickCreateType('lead'), true)
  assert.equal(isQuickCreateType('devis'), false)
  assert.equal(isQuickCreateType('bogus'), false)
})

test('filterQuickCreateTypes: requête vide → les 4 types', () => {
  assert.equal(filterQuickCreateTypes('').length, 4)
  assert.equal(filterQuickCreateTypes().length, 4)
})

test('filterQuickCreateTypes: filtre insensible à la casse par libellé', () => {
  const r = filterQuickCreateTypes('TICKET')
  assert.deepEqual(r.map((t) => t.id), ['ticket'])
})

test('openQuickCreate sans window (SSR) ne lève jamais', () => {
  assert.doesNotThrow(() => openQuickCreate('lead'))
})

test('openQuickCreate émet un CustomEvent avec detail.type', () => {
  let captured = null
  globalThis.window = {
    dispatchEvent: (evt) => { captured = evt },
  }
  globalThis.CustomEvent = class CustomEvent {
    constructor(type, opts) { this.type = type; this.detail = opts?.detail }
  }
  openQuickCreate('ticket')
  assert.equal(captured.type, QUICK_CREATE_EVENT)
  assert.deepEqual(captured.detail, { type: 'ticket' })
  delete globalThis.window
  delete globalThis.CustomEvent
})
