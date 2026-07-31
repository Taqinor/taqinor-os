import { describe, it, expect } from 'vitest'
import {
  toGrayscale, detectDocumentBounds, boundsToInsets, insetsToBounds,
  MIN_CONFIDENCE,
} from './documentScan'

// Construit un tableau de niveaux de gris width×height, background uniforme,
// avec un « document » en damier haut-contraste (40/220) dans le rectangle
// [x0,x1)×[y0,y1) — garantit une variance ligne/colonne détectable dès qu'une
// balayage croise le rectangle, et nulle en dehors (fond uniforme).
function makeDocumentImage(width, height, background, doc) {
  const gray = new Float64Array(width * height)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const inside = doc
        && x >= doc.x0 && x < doc.x1 && y >= doc.y0 && y < doc.y1
      gray[y * width + x] = inside ? ((x + y) % 2 === 0 ? 40 : 220) : background
    }
  }
  return gray
}

describe('documentScan — NTMOB13 (détection de contour par contraste, logique pure)', () => {
  it('toGrayscale applique la luminance BT.601 sur un RGBA plat', () => {
    // Rouge pur puis vert pur (2 pixels).
    const rgba = new Uint8ClampedArray([255, 0, 0, 255, 0, 255, 0, 255])
    const gray = toGrayscale(rgba)
    expect(gray.length).toBe(2)
    expect(gray[0]).toBeCloseTo(0.299 * 255, 1)
    expect(gray[1]).toBeCloseTo(0.587 * 255, 1)
  })

  it('détecte un document net (60% du cadre) sur fond uniforme, confiance maximale', () => {
    const width = 40, height = 40
    const gray = makeDocumentImage(width, height, 200, { x0: 8, x1: 32, y0: 8, y1: 32 })
    const bounds = detectDocumentBounds(gray, width, height)
    expect(bounds.x).toBe(8)
    expect(bounds.y).toBe(8)
    expect(bounds.width).toBe(24)
    expect(bounds.height).toBe(24)
    expect(bounds.confidence).toBe(1)
    expect(bounds.confidence).toBeGreaterThanOrEqual(MIN_CONFIDENCE)
  })

  it('image entièrement uniforme (aucun bord) → confiance nulle, jamais fiable', () => {
    const width = 40, height = 40
    const gray = makeDocumentImage(width, height, 128, null)
    const bounds = detectDocumentBounds(gray, width, height)
    expect(bounds.confidence).toBe(0)
    expect(bounds.confidence).toBeLessThan(MIN_CONFIDENCE)
  })

  it('image entièrement bruitée (aucun fond distinguable) → confiance nulle (cadre entier non plausible)', () => {
    const width = 40, height = 40
    // Damier sur TOUTE l'image : chaque bord est "trouvé" dès le premier pixel,
    // la boîte résultante couvre ~100% du cadre → non plausible.
    const gray = makeDocumentImage(width, height, 200, { x0: 0, x1: width, y0: 0, y1: height })
    const bounds = detectDocumentBounds(gray, width, height)
    expect(bounds.confidence).toBe(0)
  })

  it('cadre vide (largeur/hauteur nulle) → repli sûr, jamais d’exception', () => {
    expect(detectDocumentBounds(new Float64Array(0), 0, 0)).toEqual(
      { x: 0, y: 0, width: 0, height: 0, confidence: 0 })
  })

  it('boundsToInsets / insetsToBounds font un aller-retour cohérent', () => {
    const width = 200, height = 100
    const bounds = { x: 20, y: 10, width: 160, height: 80 } // insets 10%/10%/10%/10%
    const insets = boundsToInsets(bounds, width, height)
    expect(insets.left).toBeCloseTo(10, 5)
    expect(insets.top).toBeCloseTo(10, 5)
    expect(insets.right).toBeCloseTo(10, 5)
    expect(insets.bottom).toBeCloseTo(10, 5)
    const roundTrip = insetsToBounds(insets, width, height)
    expect(roundTrip).toEqual(bounds)
  })

  it('insetsToBounds ne produit jamais un rectangle dégénéré (≥ 1×1px)', () => {
    const bounds = insetsToBounds({ top: 49, right: 49, bottom: 49, left: 49 }, 10, 10)
    expect(bounds.width).toBeGreaterThanOrEqual(1)
    expect(bounds.height).toBeGreaterThanOrEqual(1)
  })

  it('insetsToBounds à 0/0/0/0 renvoie le cadre entier (aucun recadrage)', () => {
    const bounds = insetsToBounds({ top: 0, right: 0, bottom: 0, left: 0 }, 300, 150)
    expect(bounds).toEqual({ x: 0, y: 0, width: 300, height: 150 })
  })
})
