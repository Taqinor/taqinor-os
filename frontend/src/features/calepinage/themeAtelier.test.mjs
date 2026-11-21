// ACAL430 — l'atelier (`roofbuilder.css`) suit le thème clair/sombre de l'ERP : la palette
// `.rp9-host` est reliée aux jetons (`--card`, `--foreground`, `--primary-text`…). Seuls les 3
// calques posés sur l'imagerie satellite gardent une couleur littérale. Exécuté en CI :
//   node --test src/features/calepinage/themeAtelier.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('../../styles/roofbuilder.css', import.meta.url), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '')

const LITTERAL = /rgba?\(|#[0-9a-fA-F]{3,8}\b/
const CALQUES = ['.rp9-compass', '.rp9-toit-client', '.rp9-toit-client-polygone']

/** Déclarations (selecteur, corps) de toutes les règles, y compris dans les @media. */
function regles(source) {
  const out = []
  const re = /([^{}]+)\{([^{}]*)\}/g
  let m
  while ((m = re.exec(source))) out.push({ sel: m[1].trim(), corps: m[2] })
  return out
}

test('toute déclaration de couleur littérale est dans un des 3 calques sur la carte', () => {
  const fautives = []
  for (const { sel, corps } of regles(css)) {
    if (!LITTERAL.test(corps)) continue
    const ok = sel.split(',').every((s) => CALQUES.some(
      (c) => new RegExp(`${c.replace('.', '\\.')}(?![\\w-])`).test(s),
    ))
    if (!ok) fautives.push(sel)
  }
  assert.deepEqual(fautives, [], `couleurs littérales hors calques : ${fautives.join(' | ')}`)
})

test('`.rp9-host` lit les jetons de l\'ERP', () => {
  const host = regles(css).filter((r) => r.sel === '.rp9-host')
  const corps = host.map((r) => r.corps).join('\n')
  assert.match(corps, /background:\s*var\(--rp-nuit\)/)
  assert.match(corps, /--rp-nuit:\s*var\(--card\)/)
  assert.match(corps, /border:\s*1px solid var\(--border\)/)
  assert.match(corps, /--rp-lune-soft:\s*var\(--foreground\)/)
  assert.match(corps, /--rp-lune-faint:\s*var\(--muted-foreground\)/)
  assert.match(corps, /--rp-brass-300:\s*var\(--primary-text\)/)
  assert.match(corps, /--rp-brass-400:\s*var\(--primary-text\)/)
  assert.match(corps, /--rp-alert-300:\s*var\(--destructive\)/)
  assert.match(corps, /--rp-ok-400:\s*var\(--success-text\)/)
  assert.match(corps, /--rp-ok-600:\s*var\(--success\)/)
  assert.match(corps, /--rp-azur-950:\s*var\(--primary-foreground\)/)
})

test('le markup du script partagé (text-white, bg-white/N, border-white/N) est relié au thème', () => {
  assert.match(css, /\.rp9-host \.text-white\s*\{\s*color:\s*var\(--foreground\)/)
  for (const n of [10, 15, 20, 25]) {
    assert.match(css, new RegExp(`border-white\\\\/${n}\\s*\\{[^}]*var\\(--foreground\\)`))
  }
  assert.match(css, /bg-white\\\/5\s*\{[^}]*var\(--foreground\)/)
})

test('états des cellules du plan : jetons info / success / destructive', () => {
  const cells = regles(css).filter((r) => r.sel.includes('.rp9-layout-cell')).map((r) => r.corps).join('\n')
  for (const t of ['--info', '--success', '--destructive']) assert.ok(cells.includes(`var(${t})`), t)
})

// ACAL402 (rejeu ACAL490 du 21/11) — la colonne scène du mode studio vise la RACINE réelle de
// `atelier/BuilderDom.jsx` : depuis ACAL427 elle ne porte plus `.cine-card`, et la règle
// `.rp9-studio-scene > .cine-card` (hauteur + défilement de la colonne) ne s'appliquait plus.
test('studio : la colonne scène défile sur la racine du BuilderDom (aucune règle sur .cine-card)', () => {
  const dom = readFileSync(new URL('./atelier/BuilderDom.jsx', import.meta.url), 'utf8')
  const racine = /return \(\s*<>\s*(?:\{\/\*[\s\S]*?\*\/\}\s*)?<div className="([^"]*)"/.exec(dom)
  assert.ok(racine, 'racine du BuilderDom lue')
  const studio = regles(css).filter((r) => r.sel.includes('.rp9-studio-scene >'))
  assert.ok(studio.length > 0, 'règle sur l’enfant direct de la colonne scène')
  for (const r of studio) {
    const cible = /\.rp9-studio-scene >\s*(\S+)/.exec(r.sel)[1]
    const classe = cible.startsWith('.') ? cible.slice(1) : null
    assert.ok(cible === ':first-child' || (classe && racine[1].split(/\s+/).includes(classe)),
      `« ${r.sel} » ne vise pas la racine du BuilderDom (classes : ${racine[1]})`)
    if (r.corps.includes('overflow-y')) assert.match(r.corps, /overflow-y:\s*auto/)
  }
})
