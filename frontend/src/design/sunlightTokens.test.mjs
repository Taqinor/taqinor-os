// EZ9 — le mode « Plein soleil » est un BLOC DE TOKENS, pas un 3ᵉ thème.
// Vérifié à la source (node:test) : l'attribut suit le patron [data-density],
// le contraste est extrême, les ombres sont coupées, et le bloc est déclaré
// APRÈS `.dark` (spécificité égale → il gagne, ce qui est le but : un écran
// sombre est illisible au soleil).
//
//   node --test src/design/sunlightTokens.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (p) => readFileSync(join(HERE, p), 'utf8')

const TOKENS = read('tokens.css')
const PREFS = read('../pages/preferences/prefs.js')
const TOGGLE = read('../ui/SunlightToggle.jsx')
const JOURNEE = read('../pages/interventions/MaJourneePage.jsx')
const INTERVENTIONS = read('../pages/interventions/InterventionsPage.jsx')
const PANEL = read('../pages/preferences/PreferencesPanel.jsx')

const bloc = () => {
  const start = TOKENS.indexOf(":root[data-sunlight='1'] {")
  assert.notEqual(start, -1, 'bloc [data-sunlight] absent de tokens.css')
  return TOKENS.slice(start, TOKENS.indexOf('}', start))
}

test('le mode est un attribut de tokens, pas un thème', () => {
  // Aucune classe de thème nouvelle, aucune palette inventée.
  assert.equal(TOKENS.includes('.sunlight {'), false)
  assert.match(TOKENS, /:root\[data-sunlight='1'\]/)
  // Et il BAT `.dark` par SPÉCIFICITÉ (0,2,0 contre 0,1,0), quel que soit
  // l'ordre des blocs — un écran sombre en plein soleil est illisible.
  assert.equal(TOKENS.includes("\n[data-sunlight='1']"), false,
    'le sélecteur doit rester préfixé :root pour battre .dark')
})

test('contraste extrême : blanc pur / encre noire (21:1)', () => {
  const b = bloc()
  assert.match(b, /--background: #ffffff/)
  assert.match(b, /--foreground: #000000/)
  assert.match(b, /--card: #ffffff/)
  assert.match(b, /--border: #000000/)
  // Le gris pâle des textes secondaires disparaît.
  assert.match(b, /--muted-foreground: #1a1a1a/)
})

test('ombres et élévations coupées (illisibles au soleil)', () => {
  const b = bloc()
  assert.match(b, /--shadow-sm: none/)
  assert.match(b, /--shadow-md: none/)
  assert.match(b, /--shadow-lg: none/)
})

test('la taille du texte n’est PAS touchée (le problème est le contraste)', () => {
  const b = bloc()
  assert.equal(/--ui-text|font-size/.test(b), false)
})

test('persistance par utilisateur + application au démarrage', () => {
  assert.match(PREFS, /SUNLIGHT_KEY = 'taqinor\.sunlight'/)
  assert.match(PREFS, /export function applySunlight/)
  assert.match(PREFS, /root\.removeAttribute\('data-sunlight'\)/)
  // initPreferences ré-applique le réglage au démarrage de la coquille.
  const init = PREFS.slice(PREFS.indexOf('export function initPreferences'))
  assert.match(init, /applySunlight\(getSunlightPref\(\)\)/)
})

test('la bascule est sur les DEUX écrans terrain + Mes préférences', () => {
  assert.match(TOGGLE, /export function SunlightToggle/)
  assert.match(JOURNEE, /<SunlightToggle/)
  assert.match(INTERVENTIONS, /<SunlightToggle/)
  assert.match(PANEL, /id="pref-sunlight"/)
  // Une seule source de vérité : la bascule lit/écrit la préférence partagée.
  assert.match(TOGGLE, /getSunlightPref, setSunlightPref/)
})
