// APX29 — la tournée n'est plus rendue en double, et la carte est aux DEUX
// endroits. Verrouillé à la source (node:test) :
//   node --test src/features/installations/TourneeStopsDedup.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (p) => readFileSync(join(HERE, p), 'utf8')

const PARTAGE = read('TourneeStops.jsx')
const PLANIF = read('../../pages/installations/PlanificationPage.jsx')
const JOURNEE = read('../../pages/interventions/MaJourneePage.jsx')
const MAPVIEW = read('../../components/MapView.jsx')
const API = read('../../api/installationsApi.js')

test('les DEUX écrans montent le composant de tournée partagé', () => {
  for (const [nom, src] of [['PlanificationPage', PLANIF], ['MaJourneePage', JOURNEE]]) {
    assert.match(src, /import TourneeStops from '.*TourneeStops'/, `${nom} n'importe pas le partagé`)
    assert.match(src, /<TourneeStops/, `${nom} ne monte pas le partagé`)
  }
})

test('la liste numérotée de la planification n’est plus dupliquée', () => {
  // L'ancien rendu (arrêt numéroté + lien Itinéraire) vivait DANS la page.
  const tournee = PLANIF.slice(PLANIF.indexOf('function MaTourneeTab'),
    PLANIF.indexOf('// ── FG299/300/301'))
  assert.equal(tournee.includes('itineraire_url'), false,
    'la planification rend encore son propre lien Itinéraire')
  assert.match(tournee, /<TourneeStops stops=\{data\.stops\}/)
})

test('zéro endpoint nouveau : la tournée vient de getMaTournee, déjà appelé', () => {
  assert.match(PLANIF, /installationsApi\.getMaTournee\(date\)/)
  assert.match(JOURNEE, /getMaTournee\(today\)/)
  // `config` optionnel (cache de lecture NTMOB27) : toujours le MEME
  // endpoint, ce que ce test verifie reellement.
  assert.match(API, /getMaTournee: \(date(?:, config)?\) =>/)
  // Le composant partagé n'appelle AUCUNE API : il reçoit les arrêts en props
  // (la seule occurrence du nom est le commentaire d'en-tête).
  assert.equal(/^\s*import .*installationsApi/m.test(PARTAGE), false)
  assert.equal(/installationsApi\.\w+\(/.test(PARTAGE), false)
})

test('les arrêts sans GPS ne sont jamais posés à une position inventée', () => {
  assert.match(PARTAGE, /const aGps = \(s\) => s\?\.gps_lat != null && s\?\.gps_lng != null/)
  assert.match(PARTAGE, /\.filter\(\(\{ stop \}\) => aGps\(stop\)\)/)
})

test('MapView gagne le tracé + la pastille numérotée, de façon ADDITIVE', () => {
  // Sans `path` ni `badge`, le rendu reste celui d'avant (cercle plein).
  assert.match(MAPVIEW, /path = null,/)
  assert.match(MAPVIEW, /badge == null\s*\n?\s*\?\s*'<circle cx="13" cy="13" r="5" fill="#ffffff"\/>'/)
  assert.match(MAPVIEW, /L\.polyline\(trace, \{/)
  // Aucun service de routage (aucune clé, aucun appel réseau nouveau).
  assert.equal(/fetch\(|axios/.test(MAPVIEW), false)
})
