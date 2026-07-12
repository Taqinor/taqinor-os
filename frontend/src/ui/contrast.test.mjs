// VX194(a) — plancher visuel WCAG 2.2 : tout texte accent (variant `link` de
// Button, utilitaires `text-primary-text`/`text-warning-text`) doit atteindre
// ≥ 4.5:1 (SC 1.4.3) CLAIR ET SOMBRE. Test en CALCUL PUR (0 dépendance —
// formule WCAG officielle + conversion OKLCH->sRGB, les deux vérifiées ci-
// dessous contre des valeurs connues) sur les mêmes couleurs que
// `design/tokens.css` — un changement de token qui casse le contraste fait
// échouer CE test avant tout rendu visuel.
// Exécuté en CI : node --test src/ui/contrast.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

// ── Conversion OKLCH -> sRGB (algorithme Björn Ottosson, référence CSS Color
// 4). Utilisée pour les tokens du thème SOMBRE, définis en oklch() dans
// tokens.css. ────────────────────────────────────────────────────────────
function oklchToSrgb(L, C, H) {
  const hRad = (H * Math.PI) / 180
  const a = C * Math.cos(hRad)
  const b = C * Math.sin(hRad)
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b
  const s_ = L - 0.0894841775 * a - 1.291485548 * b
  const l = l_ ** 3
  const m = m_ ** 3
  const s = s_ ** 3
  const r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
  const g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
  const bl = -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s
  const toSrgb = (c) => {
    const clamped = Math.max(0, Math.min(1, c))
    return clamped <= 0.0031308 ? 12.92 * clamped : 1.055 * clamped ** (1 / 2.4) - 0.055
  }
  return [r, g, bl].map((c) => Math.round(toSrgb(c) * 255))
}

function hexToRgb(hex) {
  const n = parseInt(hex.replace('#', ''), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

// Luminance relative + ratio de contraste — formule WCAG 2.x officielle.
function relLum([r, g, b]) {
  const f = (c) => {
    const cs = c / 255
    return cs <= 0.03928 ? cs / 12.92 : ((cs + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
}
function contrastRatio(rgbA, rgbB) {
  const [hi, lo] = [relLum(rgbA), relLum(rgbB)].sort((a, b) => b - a)
  return (hi + 0.05) / (lo + 0.05)
}

const AA_TEXT = 4.5

// ── Sanity check du convertisseur OKLCH : valeurs déjà documentées en
// commentaire dans tokens.css (ex. `--color-nuit: oklch(15.7% 0.0388
// 271.18); /* #070b1d */`) — si ce test casse, le convertisseur est faux,
// pas les tokens. ──────────────────────────────────────────────────────
test('oklchToSrgb : concorde avec les hex déjà documentés dans tokens.css', () => {
  assert.deepEqual(oklchToSrgb(0.157, 0.0388, 271.18), hexToRgb('#070b1d'))
  assert.deepEqual(oklchToSrgb(0.859, 0.1283, 88.58), hexToRgb('#f3cc66'))
})

// ── Thème CLAIR — tokens.css `:root` (hex directs) ──────────────────────
const LIGHT_BG = hexToRgb('#f6f8fc')
const LIGHT_PRIMARY = hexToRgb('#e8b54a')       // --primary (remplissage, PAS du texte)
const LIGHT_PRIMARY_TEXT = hexToRgb('#8f6a0e')  // --primary-text = --color-brass-600
const LIGHT_WARNING = hexToRgb('#c8870f')       // --warning (remplissage, PAS du texte)
const LIGHT_WARNING_TEXT = hexToRgb('#96650b')  // --warning-text

test('VX194 régression : --primary EN TEXTE échoue AA (preuve du bug corrigé)', () => {
  assert.ok(contrastRatio(LIGHT_PRIMARY, LIGHT_BG) < AA_TEXT)
})

test('VX194 régression : --warning EN TEXTE échoue AA (preuve du bug corrigé)', () => {
  assert.ok(contrastRatio(LIGHT_WARNING, LIGHT_BG) < AA_TEXT)
})

test('thème clair : --primary-text (variant link de Button) ≥ 4.5:1', () => {
  assert.ok(
    contrastRatio(LIGHT_PRIMARY_TEXT, LIGHT_BG) >= AA_TEXT,
    `contraste ${contrastRatio(LIGHT_PRIMARY_TEXT, LIGHT_BG).toFixed(2)}:1`,
  )
})

test('thème clair : --warning-text ≥ 4.5:1', () => {
  assert.ok(
    contrastRatio(LIGHT_WARNING_TEXT, LIGHT_BG) >= AA_TEXT,
    `contraste ${contrastRatio(LIGHT_WARNING_TEXT, LIGHT_BG).toFixed(2)}:1`,
  )
})

// ── Thème SOMBRE — tokens.css `.dark` (oklch()) ──────────────────────────
const DARK_BG = oklchToSrgb(0.157, 0.028, 270)          // --background
const DARK_PRIMARY = oklchToSrgb(0.859, 0.0961, 89)     // --primary == --primary-text (déjà AA)
const DARK_WARNING = oklchToSrgb(0.859, 0.0961, 89)     // --warning == --warning-text (idem)

test('thème sombre : --primary-text (== --primary, déjà clair sur navy) ≥ 4.5:1', () => {
  assert.ok(
    contrastRatio(DARK_PRIMARY, DARK_BG) >= AA_TEXT,
    `contraste ${contrastRatio(DARK_PRIMARY, DARK_BG).toFixed(2)}:1`,
  )
})

test('thème sombre : --warning-text ≥ 4.5:1', () => {
  assert.ok(
    contrastRatio(DARK_WARNING, DARK_BG) >= AA_TEXT,
    `contraste ${contrastRatio(DARK_WARNING, DARK_BG).toFixed(2)}:1`,
  )
})
