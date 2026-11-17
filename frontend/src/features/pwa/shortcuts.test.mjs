// NTMOB20/MRY18 — raccourcis d'accès quotidien du manifeste PWA.
// On lit le manifeste GÉNÉRÉ par le build s'il existe (dist/manifest.webmanifest),
// sinon la déclaration source dans vite.config.js : dans les deux cas on vérifie
// les 5 raccourcis attendus et que chaque URL est une route réelle de l'app.
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
  // MRY18 — les notifications RELANCE_DUE (MRY17) pointent déjà vers ce
  // même lien de cockpit ; le service worker navigue vers `data.link` sans
  // changement (sw.js).
  ['Relances du jour', '/crm/cockpit'],
  // TCH120 — l'app Tâches (api.md §7) : le raccourci mène à la route d'accueil du module.
  ['Tâches', '/taches/aujourdhui'],
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

test('NTMOB20/MRY18/TCH120: le manifeste déclare les 6 raccourcis attendus', () => {
  assert.deepEqual(source(), ATTENDUS)
})

// TCH120 — liens de notification de l'app Tâches (api.md §7) : le service worker navigue vers
// `data.link` sans le réécrire ; chaque lien doit donc être une vraie route du front, avec les
// paramètres que l'écran LIT. Le comportement sur iPhone n'est pas prouvé ici.
const LIENS_TACHES = [
  ['rappel', '/taches/aujourdhui?tache=42', 'tache'],
  ['bilan du soir', '/taches/aujourdhui?ouvrir=bilan', 'ouvrir'],
  ['plan du matin / relance', '/taches/aujourdhui', null],
]

test('TCH120: les liens de notification Tâches sont des routes réelles et leurs paramètres sont lus', () => {
  const module = readFileSync(resolve(racine, 'src/features/taches/module.config.jsx'), 'utf8')
  const coquille = readFileSync(resolve(racine, 'src/features/taches/coquille/CoquilleTaches.jsx'), 'utf8')
  const page = readFileSync(resolve(racine, 'src/pages/taches/Aujourdhui.jsx'), 'utf8')
  for (const [nom, lien, param] of LIENS_TACHES) {
    const url = new URL(lien, 'https://erp.invalide')
    assert.ok(module.includes(`path: '${url.pathname}'`), `${nom} : route ${url.pathname} absente de module.config.jsx`)
    if (param) assert.ok(url.searchParams.has(param), nom)
  }
  assert.match(coquille, /params\.get\('tache'\)/, 'la fiche s\'ouvre sur ?tache=<id>')
  assert.match(page, /params\.get\('ouvrir'\) === 'bilan'/, 'le bilan s\'ouvre sur ?ouvrir=bilan')
})

test('TCH120: le clic de notification navigue vers le lien reçu (aucune réécriture)', () => {
  const sw = readFileSync(resolve(racine, 'src/sw.js'), 'utf8')
  assert.match(sw, /const link = \(event\.notification\.data && event\.notification\.data\.link\) \|\| '\/'/)
  assert.match(sw, /client\.navigate\(link\)/)
})

// TCH120 — la pastille de l'icône posée à la réception d'un push : fonction extraite du vrai sw.js.
function chargerAppliquerBadge(nav) {
  const sw = readFileSync(resolve(racine, 'src/sw.js'), 'utf8')
  const debut = sw.indexOf('function appliquerBadgeApp')
  assert.ok(debut > 0, 'appliquerBadgeApp absente de sw.js')
  const fermeture = /\r?\n\}\r?\n/.exec(sw.slice(debut))
  const fin = debut + fermeture.index + fermeture[0].length
  return new Function('self', `${sw.slice(debut, fin)}; return appliquerBadgeApp`)({ navigator: nav })
}

test('TCH120: n > 0 pose la pastille, 0 l\'efface, sans l\'API rien ne casse, un refus est absorbé', async () => {
  const appels = []
  const nav = { setAppBadge: (n) => { appels.push(['set', n]); return Promise.resolve() }, clearAppBadge: () => { appels.push(['clear']); return Promise.resolve() } }
  const appliquer = chargerAppliquerBadge(nav)
  await appliquer(4)
  await appliquer(0)
  assert.deepEqual(appels, [['set', 4], ['clear']])
  await chargerAppliquerBadge({})(3)
  await chargerAppliquerBadge({ setAppBadge: () => Promise.reject(new Error('refus')) })(3)
  await chargerAppliquerBadge({ setAppBadge: () => { throw new Error('sync') } })(3)
})

test('TCH120: le push n\'applique la pastille que si `badge` est un nombre', () => {
  const sw = readFileSync(resolve(racine, 'src/sw.js'), 'utf8')
  assert.match(sw, /typeof data\.badge === 'number' \? appliquerBadgeApp\(data\.badge\) : undefined/)
})

test('NTMOB20: /stock?scan=1 ouvre bien le panneau de scan', () => {
  const stockList = readFileSync(resolve(racine, 'src/pages/stock/StockList.jsx'), 'utf8')
  assert.match(stockList, /searchParams\.get\('scan'\) === '1'/)
})
