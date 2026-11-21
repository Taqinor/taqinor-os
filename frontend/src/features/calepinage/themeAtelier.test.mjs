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

/** Corps d'une règle -> { propriété: valeur } (comparaison de valeurs, pas de motif sur le texte). */
function declarations(corps) {
  const out = {}
  for (const d of corps.split(';')) {
    const i = d.indexOf(':')
    if (i > 0) out[d.slice(0, i).trim()] = d.slice(i + 1).trim()
  }
  return out
}
const valeursDe = (selecteur) => Object.assign(
  {}, ...regles(css).filter((r) => r.sel === selecteur).map((r) => declarations(r.corps)),
)

test("`.rp9-host` lit les jetons de l'ERP", () => {
  const host = valeursDe('.rp9-host')
  assert.equal(host.background, 'var(--rp-nuit)')
  assert.equal(host['--rp-nuit'], 'var(--card)')
  assert.equal(host.border, '1px solid var(--border)')
  assert.equal(host['--rp-lune-soft'], 'var(--foreground)')
  assert.equal(host['--rp-lune-faint'], 'var(--muted-foreground)')
  assert.equal(host['--rp-brass-300'], 'var(--primary-text)')
  assert.equal(host['--rp-brass-400'], 'var(--primary-text)')
  assert.equal(host['--rp-alert-300'], 'var(--destructive)')
  assert.equal(host['--rp-ok-400'], 'var(--success-text)')
  assert.equal(host['--rp-ok-600'], 'var(--success)')
  assert.equal(host['--rp-azur-950'], 'var(--primary-foreground)')
})

test('le markup du script partagé (text-white, bg-white/N, border-white/N) est relié au thème', () => {
  assert.equal(valeursDe('.rp9-host .text-white').color, 'var(--foreground)')
  for (const n of [10, 15, 20, 25]) {
    const v = valeursDe(`.rp9-host .border-white\\/${n}`)['border-color']
    assert.ok(String(v).includes('var(--foreground)'), `border-white/${n}`)
  }
  assert.ok(String(valeursDe('.rp9-host .bg-white\\/5').background).includes('var(--foreground)'))
})

test('états des cellules du plan : jetons info / success / destructive', () => {
  const cells = regles(css).filter((r) => r.sel.includes('.rp9-layout-cell')).map((r) => r.corps).join('\n')
  for (const t of ['--info', '--success', '--destructive']) assert.ok(cells.includes(`var(${t})`), t)
})

// ACAL402 (rejeu ACAL490 du 21/11) — la colonne scène du mode studio vise la RACINE réelle de
// `atelier/BuilderDom.jsx` : depuis ACAL427 elle ne porte plus `.cine-card`, et la règle
// `.rp9-studio-scene > .cine-card` (hauteur + défilement de la colonne) ne s'appliquait plus.
test('studio : la colonne scène défile sur son premier enfant (aucune règle sur .cine-card)', () => {
  const studio = regles(css).filter((r) => r.sel.includes('.rp9-studio-scene >'))
  assert.ok(studio.length > 0, 'règle sur l’enfant direct de la colonne scène')
  for (const r of studio) {
    assert.ok(!r.sel.includes('.cine-card'), `« ${r.sel} » vise encore .cine-card, retirée par ACAL427`)
    assert.ok(r.sel.includes('.rp9-studio-scene > :first-child'), `« ${r.sel} » ne vise pas la racine (premier enfant)`)
    const v = valeursDe(r.sel)['overflow-y']
    if (v !== undefined) assert.equal(v, 'auto')
  }
})

// ACAL402 — hauteur du studio CALÉE EN DIRECT (rejeu runner 44877345993, 1 440 × 900) : la grille commence à 266 px ;
// avec 13 rem (208 px) retranchés, la colonne scène finissait à 957 px, hors de la fenêtre (ses dernières commandes
// ne s'atteignaient pas). Le retranchement par défaut couvre au moins ces 266 px.
test('studio : la hauteur retranche au moins le haut mesuré de la grille (266 px = 16,625 rem)', () => {
  const m = /\.rp9-studio\s*\{[^}]*height:\s*calc\(100dvh - var\(--rp9-studio-haut,\s*([\d.]+)rem\)\)/.exec(css)
  assert.ok(m, 'hauteur du studio lue')
  assert.ok(Number(m[1]) * 16 >= 266, `${m[1]} rem < 266 px mesurés`)
})
