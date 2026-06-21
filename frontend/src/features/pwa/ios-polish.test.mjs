// M157 — Finitions PWA iOS : vérifie que les balises/styles de « polish » natif
// iOS restent présents dans index.html. Pas de rendu DOM : on lit la source,
// comme les autres tests .mjs de ce dépôt (menu.layout.test.mjs).
//
// Exécuté en CI : node --test src/features/pwa/ios-polish.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
// index.html est à la racine de frontend/ : src/features/pwa → ../../../index.html
const html = readFileSync(join(here, '..', '..', '..', 'index.html'), 'utf8')

test('viewport-fit=cover (sinon env(safe-area-inset-*) vaut 0 sur iPhone)', () => {
  assert.ok(/viewport-fit\s*=\s*cover/.test(html),
    'la meta viewport doit garder « viewport-fit=cover »')
})

test('barre d’état iOS : statut translucide en mode plein écran', () => {
  assert.ok(
    /<meta\s+name="apple-mobile-web-app-status-bar-style"\s+content="black-translucent"/.test(html),
    'apple-mobile-web-app-status-bar-style="black-translucent" doit être présent')
})

test('mode « app installée » iOS activé (capable)', () => {
  assert.ok(/<meta\s+name="apple-mobile-web-app-capable"\s+content="yes"/.test(html),
    'apple-mobile-web-app-capable="yes" doit être présent')
})

test('couleur de barre (theme-color) déclarée comme repli avant hydratation', () => {
  // theme-color est ensuite mis à jour dynamiquement selon le thème résolu par
  // src/design/theme.js ; cette balise statique sert de valeur initiale.
  assert.ok(/<meta\s+name="theme-color"\s+content="#0f172a"/.test(html),
    'une meta theme-color statique doit rester comme valeur initiale')
})

test('écrans de démarrage iOS (apple-touch-startup-image) câblés', () => {
  const splash = html.match(/rel="apple-touch-startup-image"/g) || []
  assert.ok(splash.length >= 4,
    `au moins 4 liens apple-touch-startup-image attendus, ${splash.length} trouvé(s)`)
})

test('défilement standalone : overscroll-behavior:contain + inertie iOS', () => {
  // Sans espaces pour tolérer le formatage.
  const squished = html.replace(/\s+/g, '')
  assert.ok(squished.includes('overscroll-behavior:contain'),
    'index.html doit fixer overscroll-behavior: contain (anti rubber-band / pull-to-refresh)')
  assert.ok(squished.includes('-webkit-overflow-scrolling:touch'),
    'index.html doit fixer -webkit-overflow-scrolling: touch (défilement inertiel iOS)')
})
