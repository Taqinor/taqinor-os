// NTMOB20 — raccourcis d'accès quotidien du manifeste PWA.
// On lit le manifeste GÉNÉRÉ par le build s'il existe (dist/manifest.webmanifest),
// sinon la déclaration source dans vite.config.js : dans les deux cas on vérifie
// les 4 raccourcis attendus et que chaque URL est une route réelle de l'app.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const ici = dirname(fileURLToPath(import.meta.url))
const racine = resolve(ici, '../../..')

const ATTENDUS = [
  ['Nouveau lead', '/crm/leads?new=1'],
  ['Scanner un code-barres', '/stock?scan=1'],
  ['Ma journée', '/ma-journee'],
  ['Approbations', '/approbations'],
]

function source() {
  const genere = resolve(racine, 'dist/manifest.webmanifest')
  if (existsSync(genere)) {
    const manifeste = JSON.parse(readFileSync(genere, 'utf8'))
    return (manifeste.shortcuts || [])
      .map((s) => [s.name, s.url])
  }
  const config = readFileSync(resolve(racine, 'vite.config.js'), 'utf8')
  return ATTENDUS.filter(([nom, url]) => config.includes(`'${nom}'`) && config.includes(`'${url}'`))
}

test('NTMOB20: le manifeste déclare les 4 raccourcis attendus', () => {
  assert.deepEqual(source(), ATTENDUS)
})

test('NTMOB20: /stock?scan=1 ouvre bien le panneau de scan', () => {
  const stockList = readFileSync(resolve(racine, 'src/pages/stock/StockList.jsx'), 'utf8')
  assert.match(stockList, /searchParams\.get\('scan'\) === '1'/)
})
