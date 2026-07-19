// LB22 — URL partageable : module pur, testable en dur (aucune dépendance
// React, `URLSearchParams` est global en Node).
//   node --test src/pages/crm/leads/urlFilters.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { EMPTY_FILTERS } from '../../../features/crm/stages.js'
import {
  DEFAULT_VIEW,
  VALID_VIEWS,
  hasUrlFilterState,
  readFiltersFromParams,
  readViewFromParams,
  writeFiltersToParams,
} from './urlFilters.js'

test('DEFAULT_VIEW/VALID_VIEWS — kanban par défaut, les 6 vues existantes', () => {
  assert.equal(DEFAULT_VIEW, 'kanban')
  assert.deepEqual(VALID_VIEWS, [
    'kanban', 'liste', 'calendrier', 'graphique', 'carte', 'prevision',
  ])
})

test('hasUrlFilterState : faux sur une URL vide ou ne portant que lead/new/equipe/view', () => {
  assert.equal(hasUrlFilterState(new URLSearchParams('')), false)
  assert.equal(hasUrlFilterState(new URLSearchParams('lead=42')), false)
  assert.equal(hasUrlFilterState(new URLSearchParams('new=1')), false)
  assert.equal(hasUrlFilterState(new URLSearchParams('equipe=7')), false)
  assert.equal(hasUrlFilterState(new URLSearchParams('view=liste')), false)
})

test('hasUrlFilterState : vrai dès qu’UNE clé de filtre gérée est présente', () => {
  assert.equal(hasUrlFilterState(new URLSearchParams('stage=NEW')), true)
  assert.equal(hasUrlFilterState(new URLSearchParams('q=alaoui')), true)
  assert.equal(hasUrlFilterState(new URLSearchParams('mesLeads=true')), true)
})

test('readFiltersFromParams : complète les clés absentes avec EMPTY_FILTERS, jamais localStorage', () => {
  const params = new URLSearchParams('stage=SIGNED&canal=site_web')
  const filters = readFiltersFromParams(params)
  assert.equal(filters.stage, 'SIGNED')
  assert.equal(filters.canal, 'site_web')
  // Toutes les autres clés retombent au défaut EMPTY_FILTERS.
  for (const key of Object.keys(EMPTY_FILTERS)) {
    if (key === 'stage' || key === 'canal') continue
    assert.deepEqual(filters[key], EMPTY_FILTERS[key])
  }
})

test('readFiltersFromParams : coercition booléenne pour mesLeads', () => {
  assert.equal(readFiltersFromParams(new URLSearchParams('mesLeads=true')).mesLeads, true)
  assert.equal(readFiltersFromParams(new URLSearchParams('mesLeads=false')).mesLeads, false)
  assert.equal(readFiltersFromParams(new URLSearchParams('')).mesLeads, false)
})

test('readFiltersFromParams : URLSearchParams vide → EMPTY_FILTERS exact', () => {
  assert.deepEqual(readFiltersFromParams(new URLSearchParams('')), EMPTY_FILTERS)
})

test('readViewFromParams : null si absente ou invalide, la vue sinon', () => {
  assert.equal(readViewFromParams(new URLSearchParams('')), null)
  assert.equal(readViewFromParams(new URLSearchParams('view=nawak')), null)
  assert.equal(readViewFromParams(new URLSearchParams('view=liste')), 'liste')
  assert.equal(readViewFromParams(new URLSearchParams('view=prevision')), 'prevision')
})

test('writeFiltersToParams : n’écrit QUE les clés non-défaut (EMPTY_FILTERS comme référence)', () => {
  const params = writeFiltersToParams(
    new URLSearchParams(''),
    { ...EMPTY_FILTERS, stage: 'SIGNED', q: 'alaoui' },
    'kanban', // vue par défaut → jamais écrite
  )
  assert.equal(params.get('stage'), 'SIGNED')
  assert.equal(params.get('q'), 'alaoui')
  assert.equal(params.has('view'), false)
  assert.equal(params.has('canal'), false)
  assert.equal(params.has('perdus'), false) // 'avec' == défaut, jamais écrit
})

test('writeFiltersToParams : écrit `view` seulement quand elle diffère de DEFAULT_VIEW', () => {
  const params = writeFiltersToParams(new URLSearchParams(''), EMPTY_FILTERS, 'liste')
  assert.equal(params.get('view'), 'liste')
})

test('writeFiltersToParams : PRÉSERVE lead/new/equipe (et toute clé inconnue) intacts', () => {
  const existing = new URLSearchParams('lead=42&new=1&equipe=7&mystere=xyz')
  const params = writeFiltersToParams(existing, { ...EMPTY_FILTERS, stage: 'NEW' }, 'liste')
  assert.equal(params.get('lead'), '42')
  assert.equal(params.get('new'), '1')
  assert.equal(params.get('equipe'), '7')
  assert.equal(params.get('mystere'), 'xyz')
  assert.equal(params.get('stage'), 'NEW')
  assert.equal(params.get('view'), 'liste')
})

test('writeFiltersToParams : revenir au défaut EFFACE la clé (round-trip complet)', () => {
  const withFilter = writeFiltersToParams(
    new URLSearchParams(''), { ...EMPTY_FILTERS, stage: 'SIGNED' }, 'liste')
  assert.equal(withFilter.get('stage'), 'SIGNED')
  const cleared = writeFiltersToParams(withFilter, EMPTY_FILTERS, 'kanban')
  assert.equal(cleared.has('stage'), false)
  assert.equal(cleared.has('view'), false)
  assert.equal(cleared.toString(), '')
})

test('writeFiltersToParams ne mute JAMAIS le URLSearchParams reçu (fonction pure)', () => {
  const original = new URLSearchParams('lead=1')
  const before = original.toString()
  writeFiltersToParams(original, { ...EMPTY_FILTERS, stage: 'NEW' }, 'liste')
  assert.equal(original.toString(), before)
})

test('round-trip : write puis read redonne exactement les filtres+vue posés', () => {
  const filters = { ...EMPTY_FILTERS, stage: 'QUOTE_SENT', owner: 'meryem', mesLeads: true }
  const params = writeFiltersToParams(new URLSearchParams(''), filters, 'liste')
  assert.deepEqual(readFiltersFromParams(params), filters)
  assert.equal(readViewFromParams(params), 'liste')
})
