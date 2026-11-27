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
const RACINES = ['.cal-coque', '.cliste', '.cal-tel', '.cal-client', '.cal-reglages'] // ACAL1985 : Démarrage rapide lit le bouton doré v2
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

/* ACAL1941 — la pile de police des TITRES commence par Archivo (la pile globale --font-display commence par « Noto
   Sans Arabic », NTI18N7) ; les titres de la coque, du téléphone et de la vue client la lisent. Mutant : Noto en tête. */
test('ACAL1941 : le jeton de police des titres commence par Archivo ; coque, téléphone et vue client le lisent', () => {
  const pile = blocDe(RACINES)?.['--cal-police-titre'] ?? ''
  // `pile` est la VALEUR du jeton lue par l'analyseur de feuille (blocDe), pas un motif sur le texte du source
  assert.ok(pile.startsWith("'Archivo'"), `--cal-police-titre : ${pile}`)
  assert.ok(pile.includes("'Noto Sans Arabic'"), 'l’arabe reste servi par Noto, en repli')
  const feuille = (f) => regles(readFileSync(new URL(`../../styles/calepinage/${f}`, import.meta.url), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, ''))
  const titres = {
    '50-coque-atelier.css': ['.cal-coque .cal-projet-titre', '.cal-coque .cal-panneau-etape-titre', '.cal-coque .cal-rail-etape'],
    '58-telephone.css': ['.cal-tel-projet-titre', '.cal-tel-h', '.cal-client-puce-titre'],
  }
  for (const [f, selecteurs] of Object.entries(titres)) {
    const regs = feuille(f)
    for (const s of selecteurs) {
      const familles = regs.filter((r) => r.sel === s).map((r) => declarations(r.corps)['font-family']).filter(Boolean)
      assert.deepEqual(familles, ['var(--cal-police-titre)'], `${f} › ${s}`)
    }
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

// ACAL1985 (rejeu T3-VAGUEC du 23/11) — en Guidé à Documents, « Générer le devis » mesurait 163 × 52, rayon 10, ancienne
// teinte : la classe `.cal-bouton-or-grand` était posée, mais une règle de `55-etape-documents.css`
// (`.cdoc-devis [data-testid=…] button`, plus spécifique que `.cal-coque .cal-bouton-or`) lui redonnait le fond
// `--primary`, le rayon 10 et la graisse 600. Aucune feuille du module ne redessine le bouton de `BoutonDevis` :
// fond, rayon, graisse et hauteur viennent des jetons du bouton d'étape.
test('ACAL1985 : aucune règle ne redessine le bouton de BoutonDevis par-dessus le bouton doré v2', async () => {
  const { readdirSync } = await import('node:fs')
  const dossier = new URL('../../styles/calepinage/', import.meta.url)
  const PROPRIETES = ['background', 'background-color', 'border-radius', 'font-weight', 'font-size', 'min-height', 'height']
  const fautives = []
  for (const f of readdirSync(dossier).filter((x) => x.endsWith('.css')).sort()) {
    const source = readFileSync(new URL(f, dossier), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
    for (const { sel, corps } of regles(source)) {
      const cibles = sel.split(',').map((s) => s.trim()).filter((s) => {
        const i = s.indexOf('cal-bouton-devis')
        return i >= 0 && s.slice(i).split(/[\s>]+/).some((morceau) => morceau.startsWith('button'))
      })
      if (!cibles.length) continue
      const posees = Object.keys(declarations(corps)).filter((p) => PROPRIETES.includes(p))
      if (posees.length) fautives.push(`${f} › ${cibles.join(', ')} { ${posees.join(', ')} }`)
    }
  }
  assert.deepEqual(fautives, [], `bouton de BoutonDevis redessiné : ${fautives.join(' | ')}`)
})

// ACAL1942 — un seul aplat doré par écran, réservé à l'action suivante (K8). « Localiser » (Toit sans contour, à côté de
// « Poser les panneaux ») et « Recalculer » (Expert > Pertes, résultat frais : plus d'action suivante) passent au gabarit
// contour (surface + filet), sans fond d'or. Mutant : remettre `background: var(--cal-action)` / `var(--primary)` ⇒ échec.
test('ACAL1942 : « Localiser » et « Recalculer » sont des boutons à contour, jamais un aplat doré', () => {
  const feuille = (f) => regles(readFileSync(new URL(`../../styles/calepinage/${f}`, import.meta.url), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, ''))
  const OR = /var\(--(cal-action|primary|cal-production|cal-or[\w-]*)\)|brass/
  const cibles = [
    ['50-coque-atelier.css', (s) => s.includes('#rp9-search') && s.includes("button[type='submit']")],
    ['54-etape-resultats.css', (s) => s.includes('calx48-lancer-bouton') && s.includes("data-etat='frais'")],
  ]
  for (const [f, vise] of cibles) {
    const regs = feuille(f).filter((r) => r.sel.split(',').some((s) => vise(s) && !s.includes(':hover')))
    assert.ok(regs.length > 0, `${f} : aucune règle ne vise le bouton secondaire`)
    const d = Object.assign({}, ...regs.map((r) => declarations(r.corps)))
    assert.equal(d.background, 'var(--cal-surface)', `${f} : fond`)
    assert.ok(!OR.test(d.background), `${f} : fond doré`)
    assert.ok(/var\(--cal-filet-fort\)/.test(d.border ?? ''), `${f} : filet`)
  }
})

// ACAL1978 — « Montrer au client » à 1440 × 900 : la mise en page grand écran existe (58-telephone.css, @media ≥ 1024 px) —
// pied « Retour à l'atelier / Envoyer le lien » posé en haut à droite, sans barre ; la carte de production flotte. Le libellé
// vient de `PiedClient` (VueClient.test.jsx). Ce cas fige la règle : sans elle la vue client redevient la colonne du téléphone.
test('ACAL1978 : au bureau (≥ 1024 px) le pied de la vue client est posé en haut à droite, sans barre', () => {
  const source = readFileSync(new URL('../../styles/calepinage/58-telephone.css', import.meta.url), 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
  const debut = source.indexOf('@media (min-width: 1024px)')
  assert.ok(debut >= 0, 'bloc @media (min-width: 1024px) absent')
  const bloc = source.slice(debut, source.indexOf('\n}\n', debut))
  const regle = regles(bloc).find((r) => /\.cal-tel-pied\s*$/.test(r.sel))
  assert.ok(regle, 'aucune règle .cal-tel-pied dans le bloc grand écran')
  const d = declarations(regle.corps)
  assert.equal(d.position, 'absolute')
  assert.equal(d.top, '28px')
  assert.equal(d.right, '28px')
  assert.equal(d.background, 'transparent')
})
