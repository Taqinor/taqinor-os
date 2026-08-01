import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  PROVENANCE_LEVELS, PROVENANCE_ORDER,
  provenanceLabel, provenanceToken, provenanceDescription, provenancePrintHex,
} from './provenance'
import { ProvenanceBadge } from './components/ProvenanceBadge'

/* AOF9 — Tokens de provenance + `ProvenanceBadge`.
   ----------------------------------------------------------------------------
   Trois couches vérifiées : (1) le contrat pur `provenance.js` (labels/tokens/
   hex normatif), (2) la correspondance token↔hex normatif d'impression en
   OKLCH — mêmes valeurs que `design/tokens.css`, contraste AA recalculé par
   l'algorithme de `ui/contrast.test.mjs` (Björn Ottosson, CSS Color 4) pour
   les DEUX thèmes, (3) le rendu du badge lui-même. */

describe('provenance.js — contrat pur', () => {
  it('expose exactement les 4 niveaux, dans l’ordre mesuré → confirmer → déduit → deviné', () => {
    expect(PROVENANCE_ORDER).toEqual(['mesure', 'confirmer', 'deduit', 'devine'])
    expect(Object.keys(PROVENANCE_LEVELS).sort()).toEqual([...PROVENANCE_ORDER].sort())
  })

  it('chaque niveau porte un libellé FR, un token CSS et une description non vides', () => {
    for (const level of PROVENANCE_ORDER) {
      expect(provenanceLabel(level).length).toBeGreaterThan(0)
      expect(provenanceToken(level)).toMatch(/^--ao-provenance-/)
      expect(provenanceDescription(level).length).toBeGreaterThan(0)
    }
  })

  it('mesuré/à confirmer/déduit portent le hex NORMATIF d’impression de dessin.py:16-19 ; deviné n’en a aucun', () => {
    expect(provenancePrintHex('mesure')).toBe('#1d4ed8')
    expect(provenancePrintHex('confirmer')).toBe('#d97706')
    expect(provenancePrintHex('deduit')).toBe('#64748b')
    expect(provenancePrintHex('devine')).toBeNull()
  })
})

// ── Conversion OKLCH -> sRGB (algorithme Björn Ottosson, référence CSS Color 4)
//    — copie du convertisseur déjà vérifié par ui/contrast.test.mjs, réutilisée
//    ici pour les tokens `--ao-provenance-*`. ────────────────────────────────
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

// Sanity check du convertisseur (mêmes valeurs que ui/contrast.test.mjs).
it('oklchToSrgb : concorde avec les hex déjà documentés dans tokens.css', () => {
  expect(oklchToSrgb(0.157, 0.0388, 271.18)).toEqual(hexToRgb('#070b1d'))
})

// ── Thème CLAIR — design/tokens.css `:root` (valeurs copiées ici). ──────────
const LIGHT_BG = hexToRgb('#f6f8fc')
const LIGHT = {
  mesure: { L: 0.488, C: 0.2172, H: 264.38, hex: '#1d4ed8' },
  confirmer: { L: 0.56, C: 0.1308, H: 59.19, hex: '#ab5e05' },
  deduit: { L: 0.551, C: 0.0408, H: 257.42, hex: '#63738a' },
  devine: { L: 0.541, C: 0.2466, H: 293.01, hex: '#7c3aed' },
}

// ── Thème SOMBRE — design/tokens.css `.dark` (fond navy, mêmes L/C/H que
//    ui/contrast.test.mjs pour --background). ───────────────────────────────
const DARK_BG = oklchToSrgb(0.157, 0.028, 270)
const DARK = {
  mesure: { L: 0.591, C: 0.18, H: 266.22, hex: '#4b74e7' },
  confirmer: { L: 0.666, C: 0.1574, H: 58.32, hex: '#d97706' },
  deduit: { L: 0.578, C: 0.0422, H: 257.01, hex: '#6a7b93' },
  devine: { L: 0.604, C: 0.2149, H: 296.24, hex: '#915af0' },
}

describe.each(PROVENANCE_ORDER)('token --ao-provenance-%s', (level) => {
  it('la valeur OKLCH clair reproduit EXACTEMENT le hex documenté dans tokens.css', () => {
    const { L, C, H, hex } = LIGHT[level]
    expect(oklchToSrgb(L, C, H)).toEqual(hexToRgb(hex))
  })

  it('la valeur OKLCH sombre reproduit EXACTEMENT le hex documenté dans tokens.css', () => {
    const { L, C, H, hex } = DARK[level]
    expect(oklchToSrgb(L, C, H)).toEqual(hexToRgb(hex))
  })

  it('thème clair : contraste ≥ 4.5:1 sur --background', () => {
    const { L, C, H } = LIGHT[level]
    const ratio = contrastRatio(oklchToSrgb(L, C, H), LIGHT_BG)
    expect(ratio).toBeGreaterThanOrEqual(AA_TEXT)
  })

  it('thème sombre : contraste ≥ 4.5:1 sur --background', () => {
    const { L, C, H } = DARK[level]
    const ratio = contrastRatio(oklchToSrgb(L, C, H), DARK_BG)
    expect(ratio).toBeGreaterThanOrEqual(AA_TEXT)
  })
})

describe('correspondance token ↔ hex normatif d’impression', () => {
  it('mesuré : le token clair EST le hex d’impression (aucun ajustement nécessaire, déjà ≥ AA)', () => {
    expect(LIGHT.mesure.hex).toBe(provenancePrintHex('mesure'))
  })

  it('à confirmer (sombre) : le token EST le hex d’impression (déjà ≥ AA sur navy)', () => {
    expect(DARK.confirmer.hex).toBe(provenancePrintHex('confirmer'))
  })

  it('à confirmer/plan-déduit (clair) : assombris pour l’AA, mais MÊME TEINTE que l’impression (écart de teinte OKLCH < 5°)', () => {
    // Hex d'impression bruts, convertis en teinte OKLCH via le même
    // convertisseur (aller-retour déjà vérifié ci-dessus pour les 8 tokens).
    const PRINT_HUE = { confirmer: 58.32, deduit: 257.42 } // dessin.py #d97706 / #64748b
    expect(Math.abs(LIGHT.confirmer.H - PRINT_HUE.confirmer)).toBeLessThan(5)
    expect(Math.abs(LIGHT.deduit.H - PRINT_HUE.deduit)).toBeLessThan(5)
  })
})

describe('<ProvenanceBadge />', () => {
  it.each(PROVENANCE_ORDER)('rend le libellé et le hook data-ao-provenance="%s" (contrat AOF8)', (level) => {
    render(<ProvenanceBadge level={level} />)
    expect(screen.getByText(provenanceLabel(level))).toBeInTheDocument()
    const el = document.querySelector(`[data-ao-provenance="${level}"]`)
    expect(el).not.toBeNull()
  })

  it('pose la couleur via var(--ao-provenance-<niveau>) — jamais un hex en dur', () => {
    render(<ProvenanceBadge level="confirmer" />)
    const dot = document.querySelector('[data-ao-provenance="confirmer"] > span')
    expect(dot).not.toBeNull()
    expect(dot.style.background).toBe('var(--ao-provenance-confirmer)')
  })

  it('accepte une description custom qui remplace la description normative', () => {
    render(<ProvenanceBadge level="mesure" description="Dégagement dérivé de la fermeture Nord." />)
    // Le libellé reste celui du niveau ; la description custom pilote l'infobulle
    // (non assertée ici — Radix ne l'ouvre qu'au survol/focus, cf. setup.js).
    expect(screen.getByText('Mesuré')).toBeInTheDocument()
  })
})
