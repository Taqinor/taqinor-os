// LW9 — Tests du moteur d'état PUR (blueprint D2). Exécutés en CI :
//   node --test src/features/crm/workspace/draftCore.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  reducer,
  initState,
  canonEq,
  applyFlushSuccess,
  getField,
  isDirty,
  dirtyKeys,
  isSuggested,
  toPayload,
  currentFields,
  buildCreateDefaults,
} from './draftCore.js'

// Un état d'édition minimal, avec de l'état satellite non trivial à purger.
function editState(overrides = {}) {
  const s = initState({ lead: { id: 7, nom: 'Karim', montant_estime: 30, telephone: '212612345678' }, mode: 'edit' })
  return { ...s, ...overrides }
}

test('canonEq — vide : "" ≡ null ≡ undefined', () => {
  assert.equal(canonEq('', null), true)
  assert.equal(canonEq(null, undefined), true)
  assert.equal(canonEq('', ''), true)
})

test('canonEq — numérique : "30" ≡ 30, "30" ≠ 31', () => {
  assert.equal(canonEq('30', 30), true)
  assert.equal(canonEq('30', 31), false)
  assert.equal(canonEq('30.0', 30), true)
})

test('canonEq — une vraie valeur n\'est jamais vide (0 ≠ "")', () => {
  assert.equal(canonEq(0, ''), false)
  assert.equal(canonEq('abc', 'abc'), true)
  assert.equal(canonEq('abc', 'abd'), false)
})

test('canonEq — booléens et objets (custom_data) par contenu', () => {
  assert.equal(canonEq(true, true), true)
  assert.equal(canonEq({ a: 1, b: 2 }, { b: 2, a: 1 }), true)
  assert.equal(canonEq({ a: 1 }, { a: 2 }), false)
})

test('LOAD_LEAD purge TOUT l\'état satellite (wa/note/bill/stale)', () => {
  const dirty = editState({
    draft: { nom: 'X' },
    wa: { selected: [1, 2], langue: 'darija', preview: { message: 'hi' } },
    composer: { note: 'brouillon note', file: {} },
    bill: { editing: true, hiver: '650', ete: '', error: 'boom' },
    stale: { theirs: 'Meriem', at: '2026-01-01' },
    saveState: 'error',
  })
  const next = reducer(dirty, { type: 'LOAD_LEAD', payload: { lead: { id: 9, nom: 'Y' }, mode: 'edit' } })
  assert.deepEqual(next.wa.selected, [])
  assert.equal(next.wa.preview, null)
  assert.equal(next.composer.note, '')
  assert.equal(next.composer.file, null)
  assert.equal(next.bill.editing, false)
  assert.equal(next.stale, null)
  assert.equal(next.saveState, 'idle')
  assert.deepEqual(next.draft, {})
  assert.equal(next.leadId, 9)
})

test('SET_FIELD — prune l\'égalité canonique ("" ≡ null et "30" ≡ 30)', () => {
  // server.montant_estime === 30 ; retaper "30" ne salit rien.
  let s = editState()
  s = reducer(s, { type: 'SET_FIELD', key: 'montant_estime', value: '30' })
  assert.equal(dirtyKeys(s).includes('montant_estime'), false)
  assert.equal(isDirty(s), false)
  // server.prenom === undefined (≡ vide) ; taper "" ne salit rien.
  s = reducer(s, { type: 'SET_FIELD', key: 'prenom', value: '' })
  assert.equal(dirtyKeys(s).includes('prenom'), false)
  // une vraie modification, elle, entre bien dans le draft.
  s = reducer(s, { type: 'SET_FIELD', key: 'nom', value: 'Karim B.' })
  assert.equal(getField(s, 'nom'), 'Karim B.')
  assert.equal(isDirty(s), true)
})

test('SET_FIELD — `stage` n\'entre JAMAIS dans le draft', () => {
  let s = editState()
  s = reducer(s, { type: 'SET_FIELD', key: 'stage', value: 'SIGNED' })
  assert.equal(dirtyKeys(s).includes('stage'), false)
  assert.equal(isDirty(s), false)
})

test('FLUSH success — ne « blanchit » PAS une frappe en vol', () => {
  let s = editState({ draft: { nom: 'A' } })
  s = reducer(s, { type: 'FLUSH_START', keys: ['nom'] })
  assert.equal(s.saveState, 'saving')
  assert.equal(s.inflight.nom, 'A')
  // frappe pendant que le PATCH {nom:'A'} est en vol
  s = reducer(s, { type: 'SET_FIELD', key: 'nom', value: 'AB' })
  // la réponse du PATCH précédent arrive
  s = reducer(s, { type: 'FLUSH_SUCCESS', res: { id: 7, nom: 'A' } })
  assert.equal(getField(s, 'nom'), 'AB') // frappe préservée
  assert.equal(dirtyKeys(s).includes('nom'), true)
  assert.equal(s.saveState, 'saved')
})

test('FLUSH success — sans frappe en vol, la clé est nettoyée (lit le serveur)', () => {
  let s = editState({ draft: { nom: 'A' } })
  s = reducer(s, { type: 'FLUSH_START', keys: ['nom'] })
  s = reducer(s, { type: 'FLUSH_SUCCESS', res: { id: 7, nom: 'A-canon' } })
  assert.equal(dirtyKeys(s).includes('nom'), false)
  assert.equal(getField(s, 'nom'), 'A-canon') // écho serveur
  assert.equal(isDirty(s), false)
})

test('FLUSH error — conserve le draft (rien n\'est jamais perdu)', () => {
  let s = editState({ draft: { nom: 'A' } })
  s = reducer(s, { type: 'FLUSH_START', keys: ['nom'] })
  s = reducer(s, { type: 'FLUSH_ERROR', error: 'réseau' })
  assert.equal(getField(s, 'nom'), 'A')
  assert.equal(s.saveState, 'error')
  assert.equal(s.saveError, 'réseau')
  assert.equal(s.inflight, null)
})

test('FLUSH success — réponse d\'un AUTRE leadId est ignorée (garde navigation)', () => {
  const s = editState({ leadId: 7, inflight: { nom: 'A' } })
  const next = applyFlushSuccess(s, { id: 2, nom: 'lead voisin' })
  assert.equal(next, s) // état inchangé (réponse jetée)
  assert.equal(next.server.nom, 'Karim')
})

test('SET_SERVER — écriture ponctuelle préserve le draft (étape/facture)', () => {
  let s = editState({ draft: { nom: 'edit-non-sauvé' } })
  s = reducer(s, { type: 'SET_SERVER', res: { id: 7, nom: 'Karim', stage: 'CONTACTED' } })
  assert.equal(s.server.stage, 'CONTACTED')
  assert.equal(getField(s, 'nom'), 'edit-non-sauvé') // édition préservée
  // une réponse d'un autre lead est ignorée aussi
  const s2 = reducer(s, { type: 'SET_SERVER', res: { id: 99, stage: 'COLD' } })
  assert.equal(s2.server.stage, 'CONTACTED')
})

test('toPayload — nullable + couplage été/hiver', () => {
  assert.deepEqual(toPayload({ nom: '', montant_estime: '30' }), { nom: null, montant_estime: '30' })
  const p = toPayload({ ete_differente: false, facture_ete: '420' })
  assert.equal(p.facture_ete, null) // l'été suit l'hiver quand ete_differente est faux
  assert.equal(toPayload({ perdu: true }).perdu, true) // booléens intacts
})

test('création — défauts VX93 + suggestion dérivée de l\'état', () => {
  const s = initState({ mode: 'create', currentUserId: 5, lastVille: 'Casablanca' })
  assert.equal(s.mode, 'create')
  assert.equal(getField(s, 'owner'), '5')
  assert.equal(getField(s, 'ville'), 'Casablanca')
  assert.equal(getField(s, 'canal'), 'walk_in')
  assert.equal(isSuggested(s, 'owner'), true)
  // éditer la ville la retire du « suggéré »
  const s2 = reducer(s, { type: 'SET_FIELD', key: 'ville', value: 'Rabat' })
  assert.equal(isSuggested(s2, 'ville'), false)
  // payload de création complet
  const payload = toPayload(currentFields(s))
  assert.equal(payload.stage, 'NEW')
  assert.deepEqual(payload.custom_data, {})
})

test('currentFields / buildCreateDefaults — inventaire de champs cohérent', () => {
  const d = buildCreateDefaults({ currentUserId: 1 })
  assert.equal(d.owner, '1')
  assert.equal(d.priorite, 'normale')
  const s = initState({ lead: { id: 3, nom: 'Z', ville: 'Fès' }, mode: 'edit' })
  assert.equal(currentFields(s).ville, 'Fès')
})
