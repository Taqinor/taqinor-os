// Fondation CSS mobile (Groupe MB) — garde statique sur index.css, dans le même
// esprit que design/theme.test.mjs (tokens.css) et ui/overlay-stacking.test.mjs.
//
// MB1 — Coquille : le contenu ne passe JAMAIS derrière l'en-tête ni la nav
// basse sur téléphone. Architecture vérifiée au pixel (viewport 375×812) :
// l'en-tête et la .bottom-tabbar sont des frères EN FLUX de .layout-content
// dans la colonne flex .layout-main — l'en-tête réserve lui-même
// 52 px + env(safe-area-inset-top), et le scrolleur interne (.layout-content)
// est borné entre les deux barres. Ces tests verrouillent :
//   • la chaîne de hauteur bornée U2 (sans elle la garantie tombe) ;
//   • la réserve d'encoche de l'en-tête (52 px + safe-area) ;
//   • le dégagement bas MB1 (52 px de tabbar + indicateur d'accueil) pour que
//     la dernière ligne défile au-dessus des éléments ancrés au viewport ;
//   • l'ABSENCE de padding-top « dégage-en-tête » sur .layout-content : les
//     barres étant en flux, il créerait un trou mort ~66 px (régression mesurée).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Commentaires retirés AVANT analyse : les commentaires U2/MB1 citent des
// règles (`.layout-content { overflow-y:auto }`) qui piégeraient les regex.
const css = readFileSync(
  fileURLToPath(new URL('./index.css', import.meta.url)), 'utf8',
).replace(/\/\*[\s\S]*?\*\//g, '')

/** Bloc média mobile de la coquille (le premier `@media (max-width: 768px)`). */
function mobileShellBlock() {
  const start = css.indexOf('@media (max-width: 768px)')
  assert.ok(start >= 0, 'le bloc média mobile de la coquille doit exister')
  // Fin du bloc = accolade fermante appariée.
  let depth = 0
  for (let i = css.indexOf('{', start); i < css.length; i++) {
    if (css[i] === '{') depth++
    else if (css[i] === '}') {
      depth--
      if (depth === 0) return css.slice(start, i + 1)
    }
  }
  assert.fail('bloc média mobile non refermé')
}

/** Corps de la PREMIÈRE règle `sel { … }` dans `scope`, sélecteur SEUL (le
 *  sélecteur doit débuter la déclaration : début de ligne ou après `}`/`;`, sans
 *  descendant qui précède — sinon `.gs-wrap` attraperait `.header-right .gs-wrap`). */
function ruleBody(scope, sel) {
  const m = scope.match(new RegExp(`(?:^|[}\\n;])\\s*${sel.replace(/\./g, '\\.')}\\s*\\{([^}]*)\\}`, 'm'))
  return m ? m[1] : null
}

/* ── MB1 — dégagement des barres de la coquille ─────────────────────────── */

test('MB1: la chaîne de hauteur bornée U2 reste verrouillée (garantie anti-chevauchement)', () => {
  // Sans cette chaîne, .layout-content n'est plus le scrolleur interne et la
  // garantie « le contenu reste entre les barres » tombe.
  assert.match(css, /html,\s*body\s*\{[^}]*overflow-x:\s*clip/, 'html/body doivent garder overflow-x: clip (U2)')
  assert.match(ruleBody(css, '.layout-main') ?? '', /overflow:\s*hidden/, '.layout-main doit garder overflow: hidden (U2)')
  const content = ruleBody(css, '.layout-content') ?? ''
  assert.match(content, /min-height:\s*0/, '.layout-content doit garder min-height: 0 (U2)')
  assert.match(content, /overflow-y:\s*auto/, '.layout-content doit rester le scrolleur interne (U2)')
})

test('MB1: l\'en-tête réserve sa propre place (52px + encoche) — en flux, pas en recouvrement', () => {
  const header = ruleBody(css, '.header') ?? ''
  assert.match(header, /min-height:\s*52px/, '.header doit réserver 52px (base)')
  assert.match(header, /padding-top:\s*env\(safe-area-inset-top\)/, '.header doit dégager l\'encoche (U3)')
  const mobile = mobileShellBlock()
  assert.match(
    mobile,
    /\.header\s*\{[^}]*min-height:\s*calc\(52px \+ env\(safe-area-inset-top\)\)/,
    'sur mobile .header doit réserver 52px + safe-area-inset-top (U3)',
  )
})

test('MB1: .layout-content dégage la nav basse (52px + indicateur d\'accueil) sur mobile', () => {
  const mobile = mobileShellBlock()
  const content = ruleBody(mobile, '.layout-content') ?? ''
  assert.match(
    content,
    /padding-bottom:\s*calc\(52px \+ max\(0\.9rem,\s*env\(safe-area-inset-bottom\)\)\)/,
    '.layout-content (mobile) doit réserver la hauteur de la tabbar + safe-area en bas',
  )
  assert.match(content, /padding-left:\s*max\(0\.9rem,\s*env\(safe-area-inset-left\)\)/)
  assert.match(content, /padding-right:\s*max\(0\.9rem,\s*env\(safe-area-inset-right\)\)/)
})

test('MB1: pas de padding-top « dégage-en-tête » sur .layout-content (les barres sont en flux)', () => {
  const mobile = mobileShellBlock()
  const content = ruleBody(mobile, '.layout-content') ?? ''
  assert.doesNotMatch(
    content,
    /padding-top:\s*calc\([^)]*52px/,
    'un padding-top de 52px doublerait la réserve de l\'en-tête (trou mort ~66px mesuré à 375×812)',
  )
})

/* ── MB2 — pas de débordement horizontal (« grandes pages ») ────────────── */

test('MB2: le garde global anti-défilement horizontal (U2) est en place', () => {
  assert.match(css, /html,\s*body\s*\{[^}]*max-width:\s*100%;\s*overflow-x:\s*clip/, 'html/body doivent garder max-width:100% + overflow-x: clip')
})

test('MB2: .pp-pop épouse son déclencheur — min(100%, 380px), jamais max()', () => {
  const pop = ruleBody(css, '.pp-pop') ?? ''
  assert.match(pop, /width:\s*min\(100%,\s*380px\)/, '.pp-pop doit utiliser min(100%, 380px)')
  assert.doesNotMatch(css, /\.pp-pop\s*\{[^}]*width:\s*max\(/, 'max(100%, 380px) = 380px sur un téléphone de 375px (débordement)')
  // L'ancien garde-fou mobile 92vw (≈345px > carte-ligne ~326px) ne doit pas revenir.
  assert.doesNotMatch(css, /\.pp-pop\s*\{[^}]*92vw/, 'le garde-fou 92vw débordait encore de la carte-ligne mobile')
})

test('MB2: le catalogue passe en une seule colonne sous 768px', () => {
  const mobile = mobileShellBlock()
  assert.match(ruleBody(mobile, '.cat-row') ?? '', /grid-template-columns:\s*1fr\s*;/, '.cat-row doit être mono-colonne sur mobile')
  assert.match(mobile, /\.cat-row-spec,\s*\.cat-row-stock,\s*\.cat-row-prix,\s*\.cat-row-actions\s*\{[^}]*grid-column:\s*1/, 'toutes les cellules du catalogue doivent occuper la colonne unique')
})

test('MB2: les largeurs fixes héritées ont leur garde mobile', () => {
  const mobile = mobileShellBlock()
  assert.match(ruleBody(mobile, '.gen-page') ?? '', /max-width:\s*100%/, '.gen-page doit être borné à 100% sur mobile')
  // LW40 — `.lead-bill-input` (facture inline de l'ancien LeadForm) a été
  // SUPPRIMÉ avec la refonte workspace : plus de règle à garder sur mobile.
  assert.match(ruleBody(mobile, '.devis-totals') ?? '', /min-width:\s*0/, '.devis-totals (min-width 260px) doit pouvoir rétrécir sur mobile')
  assert.match(ruleBody(mobile, '.nb-panel') ?? '', /min\(320px,\s*calc\(100vw - 16px\)\)/, '.nb-panel (320px fixe) doit être borné au viewport sur mobile')
})

/* ── MB3 — adoption du barème --z-* (fin des collisions d'empilement) ────── */

test('MB3: plus AUCUN z-index en dur dans index.css (hormis l\'exception locale documentée)', () => {
  // On repart du fichier BRUT (les commentaires citent parfois « z-index:1 »).
  const raw = readFileSync(
    fileURLToPath(new URL('./index.css', import.meta.url)), 'utf8',
  ).replace(/\/\*[\s\S]*?\*\//g, '')
  const offenders = []
  const re = /z-index:\s*([^;]+);/g
  let m
  while ((m = re.exec(raw))) {
    const val = m[1].trim()
    if (val.startsWith('var(--z-')) continue
    // Seule exception tolérée : la sticky `.pp-cat` (z-index:1), locale au
    // contexte d'empilement propre de .pp-pop (ne participe pas au barème global).
    if (val === '1') continue
    offenders.push(val)
  }
  assert.deepEqual(offenders, [], `z-index en dur restants (à tokeniser) : ${offenders.join(', ')}`)
})

test('MB3: le picker produit .pp-pop est un popover (au-dessus des modales)', () => {
  assert.match(ruleBody(css, '.pp-pop') ?? '', /z-index:\s*var\(--z-popover/, '.pp-pop doit utiliser --z-popover (jamais 300 en dur, sinon sous les modales)')
  assert.doesNotMatch(css, /\.pp-pop\s*\{[^}]*z-index:\s*300/, 'l\'ancien z-index:300 ne doit plus exister')
})

test('MB3: la recherche/cloche de l\'en-tête s\'ancrent au palier --z-sticky', () => {
  assert.match(ruleBody(css, '.gs-wrap') ?? '', /z-index:\s*var\(--z-sticky/, '.gs-wrap doit s\'ancrer à --z-sticky')
  assert.match(ruleBody(css, '.nb-wrap') ?? '', /z-index:\s*var\(--z-sticky/, '.nb-wrap doit s\'ancrer à --z-sticky')
  // Leurs panneaux déroulants restent des dropdowns DANS ce contexte. (Ces
  // sélecteurs ont aussi une variante mobile SANS z-index : on cherche la
  // déclaration z-index parmi toutes les occurrences du sélecteur.)
  const zOf = (sel) => {
    const re = new RegExp(`(?:^|[}\\n;])\\s*${sel.replace(/\./g, '\\.')}\\s*\\{([^}]*)\\}`, 'gm')
    let m; const bodies = []
    while ((m = re.exec(css))) bodies.push(m[1])
    return bodies.find(b => /z-index:/.test(b)) ?? ''
  }
  assert.match(zOf('.gs-panel'), /z-index:\s*var\(--z-dropdown/, '.gs-panel = --z-dropdown')
  assert.match(zOf('.nb-panel'), /z-index:\s*var\(--z-dropdown/, '.nb-panel = --z-dropdown')
})

test('MB3: la nav basse et les modales ne se collisionnent plus (tabbar < overlay < modal)', () => {
  const mobile = mobileShellBlock()
  const tab = ruleBody(mobile, '.bottom-tabbar') ?? ''
  assert.match(tab, /z-index:\s*var\(--z-sticky/, '.bottom-tabbar doit passer à --z-sticky (n\'était plus == --z-modal)')
  assert.doesNotMatch(tab, /z-index:\s*1300/, 'la nav basse ne doit plus être à 1300 (collision modale)')
})

test('MB3: le tiroir de navigation reste au-dessus (panneau --z-popover > voile --z-modal > nav basse)', () => {
  const mobile = mobileShellBlock()
  assert.match(ruleBody(mobile, '.sidebar') ?? '', /z-index:\s*var\(--z-popover/, 'le panneau du tiroir = --z-popover')
  assert.match(ruleBody(mobile, '.drawer-overlay') ?? '', /z-index:\s*var\(--z-modal/, 'le voile du tiroir = --z-modal')
})

test('MB3: les overlays legacy conservent des replis alignés sur la vraie valeur du token', () => {
  // --z-modal vaut 1300 (tokens.css) ; aucun repli var(--z-modal, 1200) ne doit subsister.
  assert.doesNotMatch(css, /var\(--z-modal,\s*1200\)/, 'repli --z-modal désaligné (1200 au lieu de 1300)')
})
