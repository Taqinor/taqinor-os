// Garde-fou du menu de navigation sur iPhone (C1).
//
// Le bug signalé : sur iPhone, les DERNIERS éléments du menu (et la
// déconnexion) étaient coupés et inatteignables. Le correctif tient à quatre
// invariants CSS/HTML — si l'un saute lors d'un futur remaniement, le menu
// recoupe en bas. Ce test verrouille EXACTEMENT ces invariants (pas de rendu
// DOM : on lit la source, comme les autres tests .mjs de ce dépôt).
//
// Exécuté en CI : node --test src/components/layout/menu.layout.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
// On retire les commentaires CSS AVANT toute analyse : plusieurs règles
// décrivent l'invariant en clair dans un /* … */ (« min-height:0 indispensable »),
// ce qui ferait passer le test même si la VRAIE déclaration disparaissait.
const css = readFileSync(join(here, '..', '..', 'index.css'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '')
const html = readFileSync(join(here, '..', '..', '..', 'index.html'), 'utf8')

// Corps d'une règle CSS plate (« sélecteur { … } ») à partir d'un offset.
// Les règles visées n'imbriquent aucune accolade, donc la première « } »
// ferme bien la règle.
function ruleBody(source, selector, fromIndex = 0) {
  const selIdx = source.indexOf(selector, fromIndex)
  assert.notEqual(selIdx, -1, `règle « ${selector} » introuvable dans index.css`)
  const open = source.indexOf('{', selIdx)
  const close = source.indexOf('}', open)
  return source.slice(open + 1, close)
}

// Espaces retirés → tolère « min-height: 0 » comme « min-height:0 ».
const squish = (s) => s.replace(/\s+/g, '')

test('.sidebar-nav DÉFILE : flex enfant rétréci (min-height:0) + overflow-y', () => {
  const nav = squish(ruleBody(css, '.sidebar-nav {'))
  // Sans min-height:0 un enfant flex ne rétrécit pas sous la hauteur de son
  // contenu → overflow-y ne s'enclenche jamais et le bas du menu est coupé.
  assert.ok(nav.includes('min-height:0'),
    '.sidebar-nav doit garder « min-height: 0 » (sinon pas de défilement iPhone)')
  assert.ok(nav.includes('overflow-y:auto'),
    '.sidebar-nav doit garder « overflow-y: auto »')
})

test('.sidebar est BORNÉE au viewport (sinon la nav ne peut pas défiler)', () => {
  const base = squish(ruleBody(css, '.sidebar {'))
  assert.ok(base.includes('height:100dvh'),
    '.sidebar doit être bornée à la hauteur du viewport (height: 100dvh)')
})

test('tiroir mobile : insets iOS HAUT (encoche) ET BAS (indicateur d’accueil)', () => {
  // Le bug porte surtout sur le BAS : sans padding-bottom = safe-area-inset-bottom,
  // le dernier élément + la déconnexion passent sous l'indicateur d'accueil.
  const media = css.indexOf('@media (max-width: 768px)')
  assert.notEqual(media, -1, 'media query mobile (max-width: 768px) introuvable')
  const mobileSidebar = squish(ruleBody(css, '.sidebar {', media))
  assert.ok(mobileSidebar.includes('padding-bottom:env(safe-area-inset-bottom)'),
    'le tiroir mobile doit dégager l’indicateur d’accueil (padding-bottom: env(safe-area-inset-bottom))')
  assert.ok(mobileSidebar.includes('padding-top:env(safe-area-inset-top)'),
    'le tiroir mobile doit dégager l’encoche (padding-top: env(safe-area-inset-top))')
})

test('viewport-fit=cover présent (sinon env(safe-area-inset-*) vaut 0)', () => {
  // Sans viewport-fit=cover, les insets safe-area renvoient 0 et le
  // padding ci-dessus ne protège plus rien : régression silencieuse du bas.
  assert.ok(/viewport-fit\s*=\s*cover/.test(html),
    'index.html doit garder « viewport-fit=cover » sur la meta viewport')
})

// I36 — La barre d'onglets inférieure (mobile) doit dégager l'indicateur
// d'accueil iOS, sinon le dernier rang d'onglets passe sous le geste système.
test('barre d’onglets mobile : inset bas iOS (padding-bottom safe-area)', () => {
  const media = css.indexOf('@media (max-width: 768px)')
  assert.notEqual(media, -1, 'media query mobile (max-width: 768px) introuvable')
  const tabbar = squish(ruleBody(css, '.bottom-tabbar {', media))
  assert.ok(tabbar.includes('padding-bottom:env(safe-area-inset-bottom)'),
    '.bottom-tabbar doit dégager l’indicateur d’accueil (padding-bottom: env(safe-area-inset-bottom))')
  // Masquée sur le bureau : la règle de base hors media query doit la cacher.
  const base = squish(ruleBody(css, '.bottom-tabbar {'))
  assert.ok(base.includes('display:none'),
    '.bottom-tabbar doit être masquée sur le bureau (display:none hors media query)')
})

// I36 — Une barre de progression de navigation doit exister (feedback instantané).
test('barre de progression de navigation présente', () => {
  const bar = squish(ruleBody(css, '.route-progress {'))
  assert.ok(bar.length > 0, '.route-progress doit rester définie dans index.css')
})
