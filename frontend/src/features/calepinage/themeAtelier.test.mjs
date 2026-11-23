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
const FEUILLE_JETONS = '49-jetons-v2.css' // ACAL1800 — la seule feuille du module à couleurs littérales

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

/* Coque des maquettes (22/11) — les feuilles `styles/calepinage/5x-*.css` de la refonte (50 à 58) n'ont
   AUCUNE couleur littérale : jetons seuls, le thème sombre suit par les jetons. Les `url(data:…)` (masques
   de pictogrammes peints à `currentColor`) sont hors champ : leur tracé n'est pas une couleur affichée. */
// ACAL1800 — étendu à TOUTES les feuilles du module sauf `49-jetons-v2.css`, la seule qui porte les couleurs.
test('les feuilles du module (hors 49-jetons-v2.css) n’ont aucune couleur littérale', async () => {
  const { readdirSync } = await import('node:fs')
  const dossier = new URL('../../styles/calepinage/', import.meta.url)
  const feuilles = readdirSync(dossier).filter((f) => f.endsWith('.css') && f !== FEUILLE_JETONS).sort()
  assert.ok(feuilles.includes('50-coque-atelier.css') && feuilles.includes('56-coque-responsive.css'), feuilles.join(', '))
  assert.ok(feuilles.includes('40-choix-devis-design.css') && feuilles.includes('57-liste.css'), feuilles.join(', '))
  const fautives = []
  for (const f of feuilles) {
    const source = readFileSync(new URL(f, dossier), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/url\((["']?)data:[^)]*\1\)/g, 'url()')
    for (const { sel, corps } of regles(source)) if (LITTERAL.test(corps)) fautives.push(`${f} › ${sel}`)
  }
  assert.deepEqual(fautives, [], `couleurs littérales dans la coque : ${fautives.join(' | ')}`)
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

/* ACAL1800 — les jetons v2 (LANGAGE.md, tableau « Jetons », colonnes Clair | Sombre) sous les racines du module.
   Valeur attendue = celle du tableau (normalisée : espaces retirés, minuscules) ; `null` en sombre = même valeur. */
const RACINES = ['.cal-coque', '.cliste', '.cal-tel', '.cal-client']
const JETONS_V2 = {
  '--cal-papier': ['#f5f4f0', '#0a0f2a'],
  '--cal-surface': ['#ffffff', '#121a3f'],
  '--cal-surface-2': ['#ebe9e2', '#1a2350'],
  '--cal-flottante': ['rgba(255,255,255,0.86)', 'rgba(12,19,53,0.82)'],
  '--cal-flottante-filet': ['rgba(255,255,255,0.7)', 'rgba(255,255,255,0.1)'],
  '--cal-texte-1': ['#0c1335', '#f3f5fb'],
  '--cal-texte-2': ['#4a5072', '#a4abcb'],
  '--cal-texte-3': ['#656b8c', '#8087a9'],
  '--cal-filet': ['rgba(12,19,53,0.08)', 'rgba(255,255,255,0.08)'],
  '--cal-filet-fort': ['rgba(12,19,53,0.14)', 'rgba(255,255,255,0.16)'],
  '--cal-actif': ['#0c1335', '#e2b54a'],
  '--cal-actif-texte': ['#ffffff', '#0c1335'],
  '--cal-actif-picto': ['#e2b54a', '#0c1335'],
  '--cal-action': ['#e2b54a', null],
  '--cal-action-texte': ['#0c1335', null],
  '--cal-or-texte': ['#8a6a12', '#e2b54a'],
  '--cal-or-trait': ['#c99a2b', '#e2b54a'],
  '--cal-lien': ['#1f4fd8', '#6c86f2'],
  '--cal-ok': ['#1e7a57', '#3dbe8b'],
  '--cal-surveiller-fond': ['#fbf6e6', 'rgba(226,181,74,0.14)'],
  '--cal-surveiller-filet': ['#efdfae', 'rgba(226,181,74,0.3)'],
  '--cal-surveiller-texte': ['#5b4a12', '#f0d48a'],
  '--cal-refus': ['#c2410c', '#f26b5b'],
  '--cal-production': ['#e2b54a', null],
  '--cal-consommation': ['#1f4fd8', '#6c86f2'],
  '--cal-perte': ['#e9a48a', '#c9785e'],
  '--cal-ombre-posee': ['0 8px 24px rgba(12,19,53,0.07),0 1px 2px rgba(12,19,53,0.06)', 'differente'],
  '--cal-ombre-flottante': ['0 10px 34px rgba(12,19,53,0.16),0 1px 3px rgba(12,19,53,0.08)', 'differente'],
  '--cal-ombre-panneau': ['0 18px 48px rgba(12,19,53,0.22),0 2px 6px rgba(12,19,53,0.08)', 'differente'],
  '--cal-rayon-champ': ['8px', null],
  '--cal-rayon-bouton': ['11px', null],
  '--cal-rayon-tuile': ['12px', null],
  '--cal-rayon-pile': ['14px', null],
  '--cal-rayon-piece': ['16px', null],
  '--cal-rayon-panneau': ['20px', null],
  '--cal-rayon-carte': ['22px', null],
  '--cal-police-chiffres': ['var(--font-display)', null],
  '--cal-chiffres': ['tabular-nums', null],
}
// Une couleur se compare par sa VALEUR : la feuille des jetons l'écrit en rgb() (voir sa tête), le tableau de
// LANGAGE.md en hexadécimal — les deux sont ramenés à la même écriture avant la comparaison.
const enRgb = (v) => String(v ?? '').replace(/#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g, (_, h) => {
  const x = h.length <= 4 ? [...h].map((c) => c + c).join('') : h
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(x.slice(i, i + 2), 16))
  return x.length === 8
    ? `rgb(${r} ${g} ${b} / ${Number((parseInt(x.slice(6, 8), 16) / 255).toFixed(3))})` : `rgb(${r} ${g} ${b})`
})
const normaliser = (v) => enRgb(v).replace(/\s+/g, '').toLowerCase()
const jetons = () => regles(readFileSync(new URL(`../../styles/calepinage/${FEUILLE_JETONS}`, import.meta.url), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, ''))
const blocDe = (liste) => {
  const r = jetons().find((x) => {
    const sels = x.sel.split(',').map((s) => s.trim())
    return sels.length === liste.length && liste.every((s) => sels.includes(s))
  })
  return r ? declarations(r.corps) : null
}

test('ACAL1800 : chaque jeton v2 du tableau LANGAGE.md existe en clair sous les racines du module', () => {
  const clair = blocDe(RACINES)
  assert.ok(clair, `bloc ${RACINES.join(', ')} absent de ${FEUILLE_JETONS}`)
  for (const [nom, [attendu]] of Object.entries(JETONS_V2)) {
    assert.equal(normaliser(clair[nom]), normaliser(attendu), `${nom} (clair)`)
  }
})

test('ACAL1800 : chaque jeton dont la valeur change en sombre est redéfini sous `.dark`', () => {
  const sombre = blocDe(RACINES.map((r) => `.dark ${r}`))
  assert.ok(sombre, 'bloc `.dark <racine>` absent')
  for (const [nom, [clair, attendu]] of Object.entries(JETONS_V2)) {
    if (attendu === null) continue
    assert.ok(sombre[nom], `${nom} n’est pas redéfini en sombre`)
    if (attendu === 'differente') assert.notEqual(normaliser(sombre[nom]), normaliser(clair), `${nom} (sombre)`)
    else assert.equal(normaliser(sombre[nom]), normaliser(attendu), `${nom} (sombre)`)
  }
})

test('ACAL1800 : la feuille des jetons ne touche aucun jeton global de l’ERP (racines du module seules)', () => {
  for (const { sel, corps } of jetons()) {
    for (const s of sel.split(',').map((x) => x.trim())) {
      assert.ok(RACINES.some((r) => s === r || s === `.dark ${r}`), `sélecteur hors du module : ${s}`)
    }
    for (const nom of Object.keys(declarations(corps))) assert.ok(nom.startsWith('--cal-'), `${sel} › ${nom}`)
  }
})

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
