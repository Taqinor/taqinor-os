// AOF75 — Partie PURE de l'export SVG → PNG : résolution des custom-properties
// et calcul des dimensions bornées (node:test, aucune dépendance, aucun DOM).
// La garantie centrale testée ici : la sortie ne contient JAMAIS de `var(--…)`
// — un token non résolu sort en NOIR dans le document exporté.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  LARGEUR_EXPORT_DEFAUT,
  MAX_PIXELS_EXPORT,
  PROPRIETES_INLINE,
  contientVariableCss,
  dimensionsExport,
  resoudreVariablesCss,
  resolveurFixe,
} from './svgToPng.js'

const TOKENS = {
  '--primary': '#b8860b',
  '--border': '#e2e8f0',
  '--foreground': '#0f172a',
  '--ao-provenance-mesure': '#1d4ed8',
  '--police-plan': 'Inter, system-ui, sans-serif',
}
const resolveur = resolveurFixe(TOKENS)

/* ═══════════ Résolution des custom-properties ═══════════ */

test('resoudreVariablesCss remplace un token connu par sa valeur', () => {
  assert.equal(
    resoudreVariablesCss('fill:var(--primary)', resolveur),
    'fill:#b8860b',
  )
})

test('resoudreVariablesCss remplace TOUTES les occurrences, pas seulement la première', () => {
  const sortie = resoudreVariablesCss(
    'stroke:var(--border);fill:var(--primary);color:var(--foreground)',
    resolveur,
  )
  assert.equal(sortie, 'stroke:#e2e8f0;fill:#b8860b;color:#0f172a')
})

test('resoudreVariablesCss prend le repli écrit dans le var() quand le token est inconnu', () => {
  assert.equal(
    resoudreVariablesCss('fill:var(--inconnu, #123456)', resolveur),
    'fill:#123456',
  )
})

test('resoudreVariablesCss résout les var() IMBRIQUÉS de l’intérieur vers l’extérieur', () => {
  assert.equal(
    resoudreVariablesCss('fill:var(--inconnu, var(--primary))', resolveur),
    'fill:#b8860b',
  )
  assert.equal(
    resoudreVariablesCss('fill:var(--inconnu, var(--aussi-inconnu, #abcdef))', resolveur),
    'fill:#abcdef',
  )
})

test('resoudreVariablesCss : token inconnu SANS repli → la valeur par défaut, jamais un var()', () => {
  const sortie = resoudreVariablesCss('fill:var(--jamais-defini)', resolveur, { defaut: '#000000' })
  assert.equal(sortie, 'fill:#000000')
  assert.equal(contientVariableCss(sortie), false)
})

test('resoudreVariablesCss : une définition CYCLIQUE ne boucle pas et ne laisse aucun var()', () => {
  const cyclique = (nom) => (nom === '--a' ? 'var(--b)' : 'var(--a)')
  const sortie = resoudreVariablesCss('fill:var(--a)', cyclique, { defaut: '#000000' })
  assert.equal(contientVariableCss(sortie), false, `il reste un var() : ${sortie}`)
  assert.ok(!sortie.includes('var('))
})

test('resoudreVariablesCss tolère un token vide (chaîne blanche) et bascule sur le repli', () => {
  const vide = () => '   '
  assert.equal(resoudreVariablesCss('fill:var(--x, #fff)', vide), 'fill:#fff')
})

test('resoudreVariablesCss : entrée non textuelle → chaîne vide (jamais une exception)', () => {
  assert.equal(resoudreVariablesCss(null, resolveur), '')
  assert.equal(resoudreVariablesCss(undefined, resolveur), '')
  assert.equal(resoudreVariablesCss(42, resolveur), '')
})

/* ═══════════ La garantie du contrat : zéro var() en sortie ═══════════ */

const SVG_SERIALISE = `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="500">
  <g transform="scale(1,-1)">
    <path d="M0 0h10v5h-10z" style="fill:var(--primary);stroke:var(--border);stroke-width:1"/>
    <path d="M2 2h2v1h-2z" style="fill:var(--ao-provenance-mesure)"/>
    <rect x="0" y="0" width="4" height="2" style="fill:var(--pas-dans-la-palette)"/>
    <text style="font-family:var(--police-plan);fill:var(--foreground)">B</text>
  </g>
</svg>`

test('aucune variable CSS ne subsiste dans la sortie sérialisée (le test du contrat AOF75)', () => {
  const sortie = resoudreVariablesCss(SVG_SERIALISE, resolveur, { defaut: '#000000' })
  assert.equal(contientVariableCss(sortie), false, 'un var(--…) a survécu à l’export')
  assert.ok(!sortie.includes('var('), 'un var( a survécu à l’export')
  // Les tokens connus gardent leur VRAIE teinte (pas un repli noir générique).
  assert.ok(sortie.includes('#b8860b'))
  assert.ok(sortie.includes('#1d4ed8'))
  assert.ok(sortie.includes('Inter, system-ui, sans-serif'))
  // Le token inconnu, lui, tombe sur le défaut explicite.
  assert.ok(sortie.includes('#000000'))
})

test('contientVariableCss détecte un var() et ignore les faux positifs', () => {
  assert.equal(contientVariableCss('fill:var(--x)'), true)
  assert.equal(contientVariableCss('fill:var( --x , #fff)'), true)
  assert.equal(contientVariableCss('fill:#fff'), false)
  assert.equal(contientVariableCss('la variable est une couleur'), false)
  assert.equal(contientVariableCss(null), false)
})

test('la liste des propriétés inlinées couvre couleur, trait ET police', () => {
  for (const prop of ['fill', 'stroke', 'stroke-width', 'font-family', 'font-size', 'opacity']) {
    assert.ok(PROPRIETES_INLINE.includes(prop), `propriété non inlinée : ${prop}`)
  }
})

/* ═══════════ Dimensions d'export ═══════════ */

test('dimensionsExport : 1 000 px de large par défaut, ratio conservé', () => {
  assert.deepEqual(dimensionsExport({ largeur: 800, hauteur: 400 }), { largeur: 1000, hauteur: 500 })
  assert.equal(LARGEUR_EXPORT_DEFAUT, 1000)
})

test('dimensionsExport : largeur demandée respectée (miniature de comparateur)', () => {
  assert.deepEqual(
    dimensionsExport({ largeur: 1200, hauteur: 900 }, { largeur: 240 }),
    { largeur: 240, hauteur: 180 },
  )
})

test('dimensionsExport : taille BORNÉE — ni la largeur ni la hauteur ne dépassent le plafond', () => {
  const enorme = dimensionsExport({ largeur: 100, hauteur: 100 }, { largeur: 999999 })
  assert.equal(enorme.largeur, MAX_PIXELS_EXPORT)
  assert.equal(enorme.hauteur, MAX_PIXELS_EXPORT)

  // Vue très haute : c'est la HAUTEUR qui bute, la largeur se réduit d'autant.
  const haute = dimensionsExport({ largeur: 100, hauteur: 1000 }, { largeur: 2000 })
  assert.ok(haute.hauteur <= MAX_PIXELS_EXPORT)
  assert.ok(haute.largeur <= MAX_PIXELS_EXPORT)
  assert.ok(Math.abs(haute.hauteur / haute.largeur - 10) < 0.05, 'ratio perdu')
})

test('dimensionsExport : dimensions source absurdes → un carré de 1 000 px, jamais NaN', () => {
  for (const source of [null, { largeur: 0, hauteur: 0 }, { largeur: NaN, hauteur: 12 }]) {
    const d = dimensionsExport(source)
    assert.ok(Number.isInteger(d.largeur) && d.largeur > 0, `largeur: ${d.largeur}`)
    assert.ok(Number.isInteger(d.hauteur) && d.hauteur > 0, `hauteur: ${d.hauteur}`)
  }
})

test('dimensionsExport : une largeur nulle ou négative retombe sur au moins 1 px', () => {
  assert.ok(dimensionsExport({ largeur: 800, hauteur: 400 }, { largeur: 0 }).largeur >= 1)
  assert.ok(dimensionsExport({ largeur: 800, hauteur: 400 }, { largeur: -50 }).largeur >= 1)
})
