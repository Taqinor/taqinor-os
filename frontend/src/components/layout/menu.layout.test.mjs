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
// Source du composant lui-même — on retire les commentaires JS/JSX (// … et
// /* … */, dont les commentaires-accolade {/* … */}) AVANT toute analyse de
// structure, sinon un commentaire contenant « </nav> » ou « sidebar-logout »
// fausserait le contrôle d'imbrication ci-dessous.
const sidebarJsx = readFileSync(join(here, 'Sidebar.jsx'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '')

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

// ── L'INVARIANT QUI MANQUAIT (occlusion du pied) ────────────────────────────
// Le bug C1 « le menu défile » a été corrigé, mais le VRAI piège n'était pas
// testé : que la liste défilante S'ARRÊTE au-dessus du pied « Déconnexion » au
// lieu de passer dessous. Pour ça il faut une PILE verticale stricte —
//   en-tête (fixe)  +  nav (flex:1, défile)  +  pied (fixe, HORS du défilement)
// — et que le bouton de déconnexion soit un FRÈRE rendu APRÈS </nav>, jamais un
// enfant du conteneur qui défile. Si l'un de ces points saute, les derniers
// liens (Stock … Paramètres) repassent SOUS le bouton et redeviennent
// inatteignables, exactement comme sur la capture signalée. Ces quatre tests
// verrouillent cette garantie structurelle (analyse de source, pas de rendu —
// jsdom n'a pas de moteur de mise en page).

test('.sidebar est une COLONNE flex : en-tête / nav / pied s’empilent', () => {
  const base = squish(ruleBody(css, '.sidebar {'))
  assert.ok(base.includes('display:flex'),
    '.sidebar doit être display:flex (pile verticale en-tête / nav / pied)')
  assert.ok(base.includes('flex-direction:column'),
    '.sidebar doit être flex-direction:column (sinon pas de pile verticale)')
})

test('.sidebar-nav est BORNÉE (flex:1) : son bas s’arrête au-dessus du pied', () => {
  const nav = squish(ruleBody(css, '.sidebar-nav {'))
  // flex:1 (= flex:1 1 0%) force la nav à prendre EXACTEMENT la place restante
  // entre l'en-tête et le pied. Sans ça (flex:auto, ou rien) elle prend la
  // hauteur de son contenu, déborde, et le pied « Déconnexion » se retrouve par
  // dessus les derniers liens → occlusion. C'est LE bug signalé.
  assert.ok(nav.includes('flex:1') || nav.includes('flex-grow:1'),
    '.sidebar-nav doit être flex:1 (bornée à la place restante, au-dessus du pied)')
})

test('le pied Déconnexion garde son créneau (flex-shrink:0, jamais écrasé)', () => {
  const logout = squish(ruleBody(css, '.sidebar-logout {'))
  // flex-shrink:0 réserve la hauteur du pied : la nav ne peut pas s'étendre
  // par-dessus et le bouton ne peut pas être comprimé hors de l'écran.
  assert.ok(logout.includes('flex-shrink:0'),
    '.sidebar-logout doit être flex-shrink:0 (créneau de pied réservé)')
})

test('Déconnexion est un FRÈRE rendu HORS de la zone défilante (.sidebar-nav)', () => {
  const navClose = sidebarJsx.indexOf('</nav>')
  const navOpen  = sidebarJsx.indexOf('sidebar-nav')
  const logout   = sidebarJsx.indexOf('sidebar-logout')
  assert.notEqual(navOpen, -1, '<nav className="sidebar-nav"> introuvable dans Sidebar.jsx')
  assert.notEqual(navClose, -1, '</nav> introuvable dans Sidebar.jsx')
  assert.notEqual(logout, -1, '.sidebar-logout introuvable dans Sidebar.jsx')
  // Le bouton doit apparaître APRÈS la fermeture de <nav> : c'est un frère du
  // <nav>, donc HORS du conteneur qui défile. S'il était imbriqué dedans, il
  // défilerait avec la liste au lieu de rester en pied.
  assert.ok(logout > navClose,
    '.sidebar-logout doit être rendu APRÈS </nav> (frère, hors de la zone défilante)')
  const insideNav = sidebarJsx.slice(navOpen, navClose)
  assert.ok(!insideNav.includes('sidebar-logout'),
    '.sidebar-logout ne doit jamais être imbriqué dans <nav class="sidebar-nav"> (sinon il défile / recouvre les derniers liens)')
})
