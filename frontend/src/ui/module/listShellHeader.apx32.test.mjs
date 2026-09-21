// APX32 — LE bug transverse : l'en-tête de `ListShell` était en hex NU.
// `ui/module/ListShell.jsx` importe `components/layout/PageHeader` (56 écrans
// consommateurs) dont le CSS posait `color: #0f172a` / `#64748b` SANS aucun
// override sombre : sur le fond nuit (oklch 15,7 %), titres et sous-titres
// étaient quasi invisibles. Ce test verrouille la tokenisation, la fin des
// doubles titres en compta, et les 5 poches d'hygiène de même nature.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.join(__dirname, '..', '..')
const read = (rel) => readFileSync(path.join(SRC, rel), 'utf8')
const css = read('index.css')

// Bloc CSS `pageheader-*` (I35) isolé pour l'assertion.
function block(selector) {
  const i = css.indexOf(selector + ' {')
  assert.ok(i > 0, `${selector} introuvable`)
  return css.slice(i, css.indexOf('}', i))
}

test('l’en-tête de ListShell n’est plus en hex nu (lisible en sombre)', () => {
  for (const sel of ['.pageheader-title', '.pageheader-subtitle']) {
    const b = block(sel)
    assert.doesNotMatch(b, /#[0-9a-fA-F]{3,8}/, `${sel} : couleur en dur`)
    assert.match(b, /color: var\(--(foreground|muted-foreground)\)/, `${sel} : token attendu`)
  }
})

test('ListShell sait effacer son en-tête quand la page porte déjà son titre', () => {
  const shell = read('ui/module/ListShell.jsx')
  assert.match(shell, /hideHeader = false,/)
  assert.match(shell, /title=\{hideHeader \? undefined : title\}/)
})

test('5 pages réelles n’empilent pas DEUX titres (PageHeader + ListShell)', () => {
  // SOLMVP40 (21/09/2026) a sorti `features/compta/pages/` vers
  // frontend/parked/ : les 5 pages d'origine de ce test n'existent plus.
  // `hideHeader` lui-même n'a plus aucun consommateur KEPT (grep vérifié :
  // seul `ui/module/ListShell.jsx`, qui déclare le prop, le mentionne encore)
  // — le réutiliser serait une tautologie. Le même bug de fond (deux titres
  // empilés) reste vérifiable sur des pages KEPT réelles via l'invariant
  // qu'elles respectent déjà : quand un <PageHeader> porte le titre de page,
  // aucune <ListShell> de contenu ne doit en porter un second ; à l'inverse,
  // quand la <ListShell> EST le titre de page, aucun <PageHeader> concurrent.
  const avecPageHeader = [
    'pages/installations/SuiviGpsPage.jsx',
    'features/installations/ParametrageKits.jsx',
    'features/installations/SuiviImport.jsx',
  ]
  for (const f of avecPageHeader) {
    const src = read(f)
    assert.match(src, /<PageHeader/, `${f} : PageHeader attendu`)
    const shells = src.match(/<ListShell\b[^>]*>/g) || []
    assert.ok(shells.length > 0, `${f} : aucune ListShell`)
    shells.forEach((tag, i) => {
      assert.doesNotMatch(tag, /\btitle=/, `${f} : ListShell #${i + 1} empile un second titre`)
    })
  }

  const titreSurListShell = [
    'pages/tiers/TiersPage.jsx',
    'features/ged/advanced/CoffresPage.jsx',
  ]
  for (const f of titreSurListShell) {
    const src = read(f)
    assert.doesNotMatch(src, /<PageHeader/, `${f} : PageHeader concurrent de la ListShell`)
    const shells = src.match(/<ListShell\b[^>]*>/g) || []
    assert.ok(shells.length > 0, `${f} : aucune ListShell`)
    assert.match(shells[0], /\btitle=/, `${f} : la ListShell devrait porter le titre de page`)
  }
})

test('(a) la carte n’a plus de couleur de repli figée', () => {
  const src = read('pages/CartePage.jsx')
  assert.doesNotMatch(src, /COLOR\[p\.type\] \|\| '#/)
  assert.match(src, /COLOR\[p\.type\] \|\| 'var\(--muted-foreground\)'/)
})

test('(b) Calendrier et Carte rendent les mêmes états vide/chargement', () => {
  const carte = read('pages/CartePage.jsx')
  const cal = read('pages/CalendarPage.jsx')
  for (const src of [carte, cal]) {
    assert.match(src, /<EmptyState/, 'EmptyState attendu des deux côtés')
    assert.match(src, /page-loading"><Spinner \/>/, 'Spinner attendu des deux côtés')
  }
  assert.doesNotMatch(cal, /className="cp-empty"/)
})

test('(c) la balance âgée n’a plus de marge en style inline', () => {
  const src = read('pages/reporting/BalanceAgeePage.jsx')
  assert.doesNotMatch(src, /style=\{\{ marginBottom/)
  assert.match(src, /className="page-header mb-5"/)
})

test('(d) ApprobationPage n’a plus un seul style inline en px', () => {
  const src = read('features/ged/advanced/ApprobationPage.jsx')
  assert.doesNotMatch(src, /style=\{\{/)
})

test('(e) le 4ᵉ idiome d’en-tête de la GED a disparu', () => {
  for (const f of ['features/ged/GedNavigator.jsx', 'features/ged/NumeriserPage.jsx']) {
    const src = read(f)
    assert.match(src, /import \{ PageHeader \} from '\.\.\/\.\.\/ui\/PageHeader'/, f)
    assert.match(src, /<PageHeader/, f)
    assert.doesNotMatch(src, /<h1 className="text-xl font-semibold">/, f)
  }
})
