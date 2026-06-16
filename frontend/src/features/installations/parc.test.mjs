import test from 'node:test'
import assert from 'node:assert/strict'

import {
  KWC_BANDS, EMPTY_PARC_FILTERS,
  buildParcParams, osmLink, geolocated, formatKwc,
} from './parc.js'

test('buildParcParams : filtres vides → objet vide', () => {
  assert.deepEqual(buildParcParams(EMPTY_PARC_FILTERS), {})
})

test('buildParcParams : recherche / ville / marque / type / année', () => {
  const params = buildParcParams({
    ...EMPTY_PARC_FILTERS, q: ' CHT ', ville: 'Casa', marque: 'Longi',
    type_installation: 'residentiel', annee: '2026',
  })
  assert.deepEqual(params, {
    search: 'CHT', ville: 'Casa', marque: 'Longi',
    type_installation: 'residentiel', annee: '2026',
  })
})

test('buildParcParams : bande kWc → kwc_min / kwc_max (bornes vides omises)', () => {
  assert.deepEqual(buildParcParams({ ...EMPTY_PARC_FILTERS, band: '3-9' }),
    { kwc_min: '3', kwc_max: '9' })
  // borne basse seule
  assert.deepEqual(buildParcParams({ ...EMPTY_PARC_FILTERS, band: '36+' }),
    { kwc_min: '36' })
  // borne haute seule
  assert.deepEqual(buildParcParams({ ...EMPTY_PARC_FILTERS, band: '0-3' }),
    { kwc_max: '3' })
})

test('KWC_BANDS : option « toutes » neutre + bandes ordonnées', () => {
  assert.equal(KWC_BANDS[0].value, '')
  assert.deepEqual(buildParcParams({ ...EMPTY_PARC_FILTERS, band: '' }), {})
})

test('osmLink : URL OpenStreetMap centrée sur le point (carte légère)', () => {
  const url = osmLink(33.5, -7.6)
  assert.ok(url.startsWith('https://www.openstreetmap.org/'))
  assert.ok(url.includes('mlat=33.5'))
  assert.ok(url.includes('mlon=-7.6'))
})

test('geolocated : ne garde que les systèmes avec GPS', () => {
  const rows = [
    { id: 1, gps_lat: 33.5, gps_lng: -7.6 },
    { id: 2, gps_lat: null, gps_lng: -7.6 },
    { id: 3, gps_lat: 31.6, gps_lng: null },
    { id: 4, gps_lat: 30.4, gps_lng: -9.6 },
  ]
  assert.deepEqual(geolocated(rows).map((r) => r.id), [1, 4])
  assert.deepEqual(geolocated(undefined), [])
})

test('formatKwc : nombre formaté, vide → tiret', () => {
  assert.equal(formatKwc(null), '—')
  assert.equal(formatKwc(''), '—')
  assert.ok(formatKwc(7.2).includes('kWc'))
})
