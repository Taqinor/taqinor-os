// Run: node --test src/features/reporting/dashboardFilters.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_GLOBAL_FILTERS, readGlobalFilters, writeGlobalFilters,
  effectiveParamsForWidget, effectiveParamsForAllWidgets, hasActiveFilters,
} from './dashboardFilters.js'

test('readGlobalFilters : layout vide/undefined renvoie les valeurs par défaut', () => {
  assert.deepEqual(readGlobalFilters(undefined), DEFAULT_GLOBAL_FILTERS)
  assert.deepEqual(readGlobalFilters(null), DEFAULT_GLOBAL_FILTERS)
  assert.deepEqual(readGlobalFilters({}), DEFAULT_GLOBAL_FILTERS)
})

test('readGlobalFilters : lit les filtres mémorisés, complète les clés manquantes', () => {
  const layout = { widgets: [], globalFilters: { canal: 'whatsapp' } }
  assert.deepEqual(readGlobalFilters(layout), { ...DEFAULT_GLOBAL_FILTERS, canal: 'whatsapp' })
})

test('writeGlobalFilters : préserve le reste du layout (widgets, disposition…)', () => {
  const layout = { widgets: [{ id: 1 }], disposition: 'grid' }
  const next = writeGlobalFilters(layout, { commercial: 'sami' })
  assert.deepEqual(next.widgets, [{ id: 1 }])
  assert.equal(next.disposition, 'grid')
  assert.equal(next.globalFilters.commercial, 'sami')
})

test('writeGlobalFilters : ne mute pas le layout original', () => {
  const layout = { widgets: [] }
  const copy = JSON.parse(JSON.stringify(layout))
  writeGlobalFilters(layout, { canal: 'x' })
  assert.deepEqual(layout, copy)
})

test('effectiveParamsForWidget : fusionne filtres globaux + params propres, le widget gagne', () => {
  const widget = { id: 1, params: { commercial: 'override' } }
  const globalFilters = { commercial: 'sami', canal: 'whatsapp' }
  assert.deepEqual(
    effectiveParamsForWidget(widget, globalFilters),
    { commercial: 'override', canal: 'whatsapp' },
  )
})

test('effectiveParamsForWidget : un widget opt-out ignore totalement les filtres globaux', () => {
  const widget = { id: 1, optOutGlobalFilters: true, params: { commercial: 'sami' } }
  const globalFilters = { canal: 'whatsapp', commercial: 'autre' }
  assert.deepEqual(effectiveParamsForWidget(widget, globalFilters), { commercial: 'sami' })
})

test('effectiveParamsForWidget : les filtres vides ne polluent pas les params', () => {
  const widget = { id: 1 }
  assert.deepEqual(effectiveParamsForWidget(widget, DEFAULT_GLOBAL_FILTERS), {})
})

test('effectiveParamsForAllWidgets : calcule les params de chaque widget, opt-out respecté', () => {
  const layout = {
    widgets: [
      { id: 'w1', params: {} },
      { id: 'w2', optOutGlobalFilters: true, params: { canal: 'sms' } },
    ],
  }
  const globalFilters = { canal: 'whatsapp', commercial: '', dateFrom: '', dateTo: '', categorieProduit: '' }
  const result = effectiveParamsForAllWidgets(layout, globalFilters)
  assert.deepEqual(result, [
    { id: 'w1', optedOut: false, params: { canal: 'whatsapp' } },
    { id: 'w2', optedOut: true, params: { canal: 'sms' } },
  ])
})

test('effectiveParamsForAllWidgets : layout sans widgets renvoie un tableau vide', () => {
  assert.deepEqual(effectiveParamsForAllWidgets({}, DEFAULT_GLOBAL_FILTERS), [])
  assert.deepEqual(effectiveParamsForAllWidgets(null, DEFAULT_GLOBAL_FILTERS), [])
})

test('hasActiveFilters : faux quand tous les filtres sont vides, vrai sinon', () => {
  assert.equal(hasActiveFilters(DEFAULT_GLOBAL_FILTERS), false)
  assert.equal(hasActiveFilters({ ...DEFAULT_GLOBAL_FILTERS, canal: 'whatsapp' }), true)
})
