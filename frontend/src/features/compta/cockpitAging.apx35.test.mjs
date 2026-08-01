// APX35 — Le cockpit finance parle Stripe : UN chiffre héros + aging en
// buckets colorés cliquables.
// État d'avant : `CockpitPage` était propre (post-VX115) mais PLAT — huit KPI
// de même poids, aucune hiérarchie ; et la balance âgée n'avait AUCUN
// paramètre d'URL (tranche en `useState` local), donc rien à pointer.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const cockpit = readFileSync(path.join(__dirname, 'pages', 'CockpitPage.jsx'), 'utf8')
const balance = readFileSync(
  path.join(__dirname, '..', '..', 'pages', 'reporting', 'BalanceAgeePage.jsx'), 'utf8')

test('UN chiffre héros, en échelle display et en typographie de données', () => {
  assert.match(cockpit, /data-testid="cockpit-hero"/)
  assert.match(cockpit, /num text-display font-display font-bold/)
  // Le champ héros est bien un champ DÉJÀ servi par le selector cockpit.
  assert.match(cockpit, /formatMAD\(d\.tresorerie\)/)
  // Il n'est plus dupliqué dans le bandeau de KPI secondaires.
  const stats = cockpit.slice(cockpit.indexOf('const stats = ['), cockpit.indexOf('// Top des encours'))
  assert.ok(!stats.includes("label: 'Trésorerie nette'"), 'héros dupliqué en KPI secondaire')
})

test('les QUATRE buckets d’aging existent, colorés du neutre au destructif', () => {
  const bloc = cockpit.slice(cockpit.indexOf('const agingBuckets'), cockpit.indexOf('}, [aging])'))
  for (const v of ['0_30', '31_60', '61_90', '90_plus']) {
    assert.ok(bloc.includes(`value: '${v}'`), `bucket ${v} absent`)
  }
  assert.match(bloc, /border-warning/)
  assert.match(bloc, /border-destructive/)
  // Les teintes viennent des tokens, jamais d'un hex.
  assert.doesNotMatch(bloc, /#[0-9a-fA-F]{3,8}/)
})

test('chaque bucket ouvre la balance âgée PRÉ-FILTRÉE', () => {
  assert.match(cockpit, /to=\{`\/reporting\/balance-agee\?bucket=\$\{b\.value\}`\}/)
})

test('AUCUN endpoint nouveau : l’aging vient de la balance âgée déjà exposée', () => {
  assert.match(cockpit, /ventesApi\.getBalanceAgee\(\)/)
  // Aucun appel cockpit nouveau n'a été introduit.
  assert.deepEqual(
    [...new Set(cockpit.match(/comptaApi\.\w+/g) ?? [])],
    ['comptaApi.cockpit'],
  )
})

test('la balance âgée est enfin adressable par URL (?bucket=)', () => {
  assert.match(balance, /import \{ Link, useSearchParams \} from 'react-router-dom'/)
  assert.match(balance, /searchParams\.get\('bucket'\)/)
  // La valeur d'URL est VALIDÉE contre les segments connus (jamais un filtre
  // fantôme sur une valeur inventée).
  assert.match(balance, /SEGMENTS\.some\(\(s\) => s\.value === b\) \? b : 'all'/)
  // Et le changement de segment met l'URL à jour (sans empiler d'historique).
  assert.match(balance, /\{ replace: true \}/)
})

test('la tranche 0–30 j existe côté balance âgée (sinon le lien ne résout rien)', () => {
  const segs = balance.slice(balance.indexOf('const SEGMENTS = ['), balance.indexOf(']', balance.indexOf('const SEGMENTS = [')))
  for (const [v, k] of [['0_30', 'b0_30'], ['31_60', 'b31_60'], ['61_90', 'b61_90'], ['90_plus', 'b90_plus']]) {
    assert.ok(segs.includes(`value: '${v}'`), `segment ${v} absent`)
    assert.ok(segs.includes(`key: '${k}'`), `clé ${k} absente`)
  }
})
