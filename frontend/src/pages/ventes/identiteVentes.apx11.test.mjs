// APX11 — L'identité Ventes atteint ses écrans de flux.
// Vérification STRUCTURELLE (node --test, sans jsdom) : avant APX11, `brass`
// (l'accent du module déclaré dans `features/ventes/module.config.jsx`)
// n'apparaissait que dans le générateur ; les 5 écrans de flux utilisaient le
// vieux `<div className="page-header"><h2>`, sans icône ni accent. Ce test
// verrouille les 3 acquis :
//   1. plus AUCUN en-tête legacy dans pages/ventes/ ;
//   2. les écrans de flux passent par l'en-tête unique `ui/PageHeader` (VX28) ;
//   3. l'accent vient de la source UNIQUE `features/ventes/accent.js`, jamais
//      d'une couleur en dur (donc lisible clair ET sombre).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const read = (f) => readFileSync(path.join(__dirname, f), 'utf8')

// Les 5 écrans de FLUX nommés par la tâche + les 4 autres pages du dossier :
// la clause « zéro en-tête legacy dans pages/ventes/ » vaut pour tout le dossier.
const FLUX = [
  'DevisList.jsx', 'DevisGenerator.jsx', 'FactureList.jsx',
  'RelancesPage.jsx', 'BonCommandeList.jsx',
]

test('plus aucun en-tête legacy dans pages/ventes/', () => {
  const offenders = []
  for (const f of readdirSync(__dirname)) {
    if (!f.endsWith('.jsx') || f.includes('.test.')) continue
    if (/className="page-header/.test(read(f))) offenders.push(f)
  }
  assert.deepEqual(offenders, [], `en-tête legacy encore présent : ${offenders.join(', ')}`)
})

test('les 5 écrans de flux rendent l’en-tête unique ui/PageHeader (VX28)', () => {
  for (const f of FLUX) {
    const src = read(f)
    assert.match(src, /import \{ PageHeader \} from '\.\.\/\.\.\/ui\/PageHeader'/, `${f} : import manquant`)
    assert.match(src, /<PageHeader\b/, `${f} : PageHeader non rendu`)
  }
})

test('l’accent Ventes vient de la source unique, jamais d’une couleur en dur', () => {
  const accent = read('../../features/ventes/accent.js')
  // La teinte est une VARIABLE de thème (--module-accent-brass), donc elle
  // suit clair/sombre — le patron déjà utilisé par Sidebar/Header/HomeMenu.
  assert.match(accent, /'--module-accent':\s*'var\(--module-accent-brass\)'/)
  for (const f of FLUX) {
    const src = read(f)
    assert.match(src, /VENTES_ACCENT_STYLE/, `${f} : accent de module absent`)
    // Aucun hex posé à la main dans le style de l'en-tête.
    assert.doesNotMatch(src, /'--module-accent':\s*'#/, `${f} : couleur en dur`)
  }
})

test('l’icône du module accompagne le titre sur les 5 écrans de flux', () => {
  for (const f of FLUX) {
    assert.match(read(f), /<PageHeader[\s\S]{0,400}?icon=\{/, `${f} : icône absente`)
  }
})
