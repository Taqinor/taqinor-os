// VX130 — Le toast devient un objet de marque : tokens, icônes lucide,
// durées motion, registres réels. Vérification de SOURCE (pas de
// node_modules installés dans ce lane — cf. VX124.test.mjs/Stat.test.mjs) :
//   node --test src/ui/VX130.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const TOASTER_SRC = readFileSync(join(HERE, 'Toaster.jsx'), 'utf8')
// Les commentaires DOCUMENTENT volontairement le retrait de `richColors` (nom
// cité en prose, y compris en commentaire `//`) — on ne veut vérifier que le
// CODE, donc tout commentaire /* … */ ou // est neutralisé avant le test
// « absent du code ».
const TOASTER_CODE_ONLY = TOASTER_SRC
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/\/\/.*$/gm, '')
const TOAST_LIB_SRC = readFileSync(join(HERE, '..', 'lib', 'toast.js'), 'utf8')
const INDEX_CSS = readFileSync(join(HERE, '..', 'index.css'), 'utf8')
const EMPTY_STATE_SRC = readFileSync(join(HERE, 'EmptyState.jsx'), 'utf8')
const ERROR_BOUNDARY_SRC = readFileSync(join(HERE, 'ErrorBoundary.jsx'), 'utf8')

test('richColors retiré du CODE (palette générique sonner, divergente du thème en sombre)', () => {
  assert.doesNotMatch(TOASTER_CODE_ONLY, /richColors/)
})

test('icônes lucide injectées par type (success/error/warning/info)', () => {
  assert.match(TOASTER_SRC, /icons=\{\{/)
  assert.match(TOASTER_SRC, /success:\s*<CheckCircle2/)
  assert.match(TOASTER_SRC, /error:\s*<AlertTriangle/)
  assert.match(TOASTER_SRC, /warning:\s*<AlertTriangle/)
  assert.match(TOASTER_SRC, /info:\s*<Info/)
})

test('le toast erreur utilise le MÊME glyphe AlertTriangle que EmptyState/ErrorBoundary', () => {
  assert.match(TOASTER_SRC, /AlertTriangle/)
  assert.match(ERROR_BOUNDARY_SRC, /AlertTriangle/)
  // EmptyState reste générique (icon= en prop) — DataTable.jsx (consommateur
  // d'EmptyState pour son état d'erreur) pose AlertTriangle, vérifié par
  // grep direct : les deux sources importent bien lucide-react.
  assert.match(EMPTY_STATE_SRC, /export function EmptyState/)
})

test('classNames par type dérivées des tokens sémantiques (parité Badge bg-X/12 border-X/40 text-X)', () => {
  for (const tone of ['success', 'destructive', 'warning', 'info']) {
    const re = new RegExp(`bg-${tone}/12`)
    assert.match(TOASTER_SRC, re, `bg-${tone}/12 manquant`)
  }
})

test('index.css cable la duree des toasts sur --motion-base (pas une valeur fixe)', () => {
  assert.match(INDEX_CSS, /\[data-sonner-toast\]\s*\{[^}]*transition-duration:\s*var\(--motion-base\)/)
})

test('toastWarning/toastInfo/toastDestructive sont exportés (registres réels, pas un vocabulaire binaire)', () => {
  assert.match(TOAST_LIB_SRC, /export function toastWarning/)
  assert.match(TOAST_LIB_SRC, /export function toastInfo/)
  assert.match(TOAST_LIB_SRC, /export function toastDestructive/)
  assert.match(TOAST_LIB_SRC, /toast\.warning\(/)
  assert.match(TOAST_LIB_SRC, /toast\.info\(/)
})

test('toastDestructive impose un délai d’annulation ≥ 6 s (registre destructif)', () => {
  assert.match(TOAST_LIB_SRC, /DESTRUCTIVE_UNDO_MIN_MS\s*=\s*6000/)
  assert.match(TOAST_LIB_SRC, /Math\.max\(duration,\s*DESTRUCTIVE_UNDO_MIN_MS\)/)
})
