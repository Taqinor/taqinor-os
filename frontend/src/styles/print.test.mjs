// VX80 — Feuille de style d'impression + boutons « Imprimer ».
// Smoke source-statique (aucun jsdom/mock — évite toute collision de rôles et
// le besoin d'un mock document.createElement) : vérifie que print.css existe et
// couvre l'essentiel, qu'il est importé une fois, et qu'un bouton window.print()
// est présent sur les trois écrans.
//   node --test src/styles/print.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { lireSourcesDevisList } from '../pages/ventes/devisList/lireSources.mjs'
import { lireSourcesFactureList } from '../pages/ventes/factureList/lireSources.mjs'
import { resolveCss } from '../test/readCss.mjs'
import { memeCss } from '../../scripts/css_golden.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const PRINT_CSS = read('print.css')
const INDEX_CSS = resolveCss(join(HERE, '../index.css'))
// SPL206 — le bouton Imprimer vit dans devisList/DevisListChrome.jsx.
const DEVIS = lireSourcesDevisList()
const FACTURE = lireSourcesFactureList()
const INSTALL = read('../pages/installations/InstallationDetail.jsx')

test('print.css : tout est sous @media print (inerte à l’écran)', () => {
  assert.match(PRINT_CSS, /@media print\s*\{/)
  // Aucune règle top-level en dehors du bloc @media print et des commentaires.
  const withoutComments = PRINT_CSS.replace(/\/\*[\s\S]*?\*\//g, '')
  const firstBrace = withoutComments.indexOf('{')
  const beforeFirstRule = withoutComments.slice(0, firstBrace)
  assert.match(beforeFirstRule, /@media print\s*$/)
})

test('print.css : masque le chrome de la coquille', () => {
  for (const sel of ['.sidebar', '.header', '.bottom-tabbar', '.route-progress', 'button']) {
    assert.ok(PRINT_CSS.includes(sel), `sélecteur manquant : ${sel}`)
  }
  assert.match(PRINT_CSS, /display:\s*none\s*!important/)
})

test('print.css : noir-sur-blanc + @page 2cm + tables non tronquées', () => {
  assert.match(PRINT_CSS, /background:\s*#fff\s*!important/)
  assert.match(PRINT_CSS, /color:\s*#000\s*!important/)
  assert.match(PRINT_CSS, /@page\s*\{\s*margin:\s*2cm/)
  assert.match(PRINT_CSS, /overflow:\s*visible\s*!important/)
  assert.match(PRINT_CSS, /width:\s*auto\s*!important/)
  assert.match(PRINT_CSS, /page-break-inside:\s*avoid/)
})

test('print.css : rend le Sheet (role=dialog) statique et pleine page pour la checklist', () => {
  assert.match(PRINT_CSS, /\[role="dialog"\]\s*\{/)
  assert.match(PRINT_CSS, /position:\s*static\s*!important/)
})

test('index.css importe print.css exactement une fois', () => {
  const matches = INDEX_CSS.match(/@import\s+["'].*print\.css["']/g) || []
  assert.equal(matches.length, 1)
})

test('DevisList : bouton Imprimer → window.print()', () => {
  assert.match(DEVIS, /Printer/)
  assert.match(DEVIS, /onClick=\{\(\)\s*=>\s*window\.print\(\)\}/)
  assert.match(DEVIS, />\s*Imprimer\s*</)
})

test('FactureList : bouton Imprimer → window.print()', () => {
  assert.match(FACTURE, /Printer/)
  assert.match(FACTURE, /onClick=\{\(\)\s*=>\s*window\.print\(\)\}/)
  assert.match(FACTURE, />\s*Imprimer\s*</)
})

test('InstallationDetail : bouton Imprimer la checklist → window.print()', () => {
  assert.match(INSTALL, /Printer/)
  assert.match(INSTALL, /onClick=\{\(\)\s*=>\s*window\.print\(\)\}/)
  assert.match(INSTALL, />\s*Imprimer la checklist\s*</)
})

// ── SPL280 — golden d'index.css (lecteur `resolveCss`, `frontend/scripts/css_golden.mjs`) ──
// Capturé sur le code ACTUEL avant tout déplacement (SPL281/SPL282 passeront
// leur ref de base à `--base`) : aucune règle ne bouge, seuls les lecteurs
// passent par la résolution des `@import './styles/<dossier>/<f>.css'`.
const GOLDEN = join(HERE, '../../scripts/css_golden.mjs')

function arbre(index, styles) {
  const racine = mkdtempSync(join(tmpdir(), 'spl280-'))
  writeFileSync(join(racine, 'index.css'), index)
  for (const [rel, texte] of Object.entries(styles)) {
    mkdirSync(dirname(join(racine, 'styles', rel)), { recursive: true })
    writeFileSync(join(racine, 'styles', rel), texte)
  }
  return racine
}

const TETE = '@import "tailwindcss";\n@import \'./design/tokens.css\';\n@import \'./styles/print.css\';\n'
const MONOLITHE = TETE + '.a { color: red; }\n.b {}\n.c {}\n.z {}\n'

test('SPL280 (a) — resolveCss inline ./styles/<dossier>/<f>.css verbatim, laisse tailwind/tokens/print', () => {
  const racine = arbre(TETE + "@import './styles/x/a.css';\n@import './styles/y/c.css';\n.z {}\n",
    { 'x/a.css': '.a { color: red; }\n.b {}\n', 'y/c.css': '.c {}\n' })
  try {
    assert.equal(resolveCss(join(racine, 'index.css')), MONOLITHE)
  } finally { rmSync(racine, { recursive: true, force: true }) }
  // Sur l'index.css réel, le texte résolu ne garde AUCUN @import de sous-dossier
  // (SPL281/SPL282 : ils sont tous inlinés par resolveCss).
  assert.doesNotMatch(INDEX_CSS, /^@import\s+['"]\.\/styles\/[^/'"]+\/[^/'"]+\.css['"]/m)
})

test('SPL280 (b) — @import permutés ou octet changé dans un fichier de styles ⇒ écart', () => {
  const cas = {
    fidele: ["@import './styles/x/a.css';\n@import './styles/y/c.css';\n", '.a { color: red; }\n.b {}\n', true],
    permute: ["@import './styles/y/c.css';\n@import './styles/x/a.css';\n", '.a { color: red; }\n.b {}\n', false],
    octet: ["@import './styles/x/a.css';\n@import './styles/y/c.css';\n", '.a { color: rod; }\n.b {}\n', false],
  }
  for (const [nom, [imports, a, attendu]] of Object.entries(cas)) {
    const racine = arbre(TETE + imports + '.z {}\n', { 'x/a.css': a, 'y/c.css': '.c {}\n' })
    try {
      assert.equal(memeCss(join(racine, 'index.css'), MONOLITHE), attendu, nom)
      // CRLF→LF : seule normalisation, pour la comparaison uniquement.
      assert.equal(memeCss(join(racine, 'index.css'), MONOLITHE.replace(/\n/g, '\r\n')), attendu, nom)
    } finally { rmSync(racine, { recursive: true, force: true }) }
  }
})

test('SPL280 (c) — identité : css_golden --base HEAD sort 0 sur l\'arbre actuel', () => {
  const r = spawnSync(process.execPath, [GOLDEN, '--base', 'HEAD'], { encoding: 'utf8' })
  assert.equal(r.status, 0, r.stdout + r.stderr)
})
