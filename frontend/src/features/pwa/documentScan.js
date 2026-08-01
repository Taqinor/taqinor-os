// NTMOB13 — Scan de documents structuré vers OCR. Logique PURE (aucun DOM) de
// détection de contour SIMPLE — analyse de CONTRASTE, aucune dépendance
// externe (pas d'OpenCV.js ni équivalent) : un document papier a des bords
// nets (fort écart-type de luminance ligne/colonne, texte/traits) contre un
// fond généralement plus uniforme (table, sol). On balaie chaque bord du
// cadre vers le centre jusqu'à trouver la première ligne/colonne dont
// l'écart-type dépasse `edgeThreshold` — c'est le bord du document.
//
// `detectDocumentBounds` ne garantit RIEN : `confidence` reflète combien de
// bords ont été trouvés ET si la boîte résultante est plausible (ni
// quasi-vide, ni le cadre entier sans qu'aucun bord n'ait été détecté). En
// dessous de `MIN_CONFIDENCE`, l'appelant doit retomber sur le recadrage
// MANUEL plutôt que de faire confiance à la détection.

export const MIN_CONFIDENCE = 0.5 // ≥ 2 bords sur 4 trouvés, boîte plausible.

/** RGBA (Uint8ClampedArray, sortie de CanvasRenderingContext2D.getImageData)
 * → niveaux de gris (luminance ITU-R BT.601) à plat, un flottant par pixel. */
export function toGrayscale(rgba) {
  const n = Math.floor(rgba.length / 4)
  const gray = new Float64Array(n)
  for (let i = 0; i < n; i++) {
    const o = i * 4
    gray[i] = 0.299 * rgba[o] + 0.587 * rgba[o + 1] + 0.114 * rgba[o + 2]
  }
  return gray
}

function stdDev(values) {
  const n = values.length
  if (!n) return 0
  let mean = 0
  for (let i = 0; i < n; i++) mean += values[i]
  mean /= n
  let variance = 0
  for (let i = 0; i < n; i++) { const d = values[i] - mean; variance += d * d }
  return Math.sqrt(variance / n)
}

function rowStdDev(gray, width, y) {
  const start = y * width
  let sum = 0
  for (let x = 0; x < width; x++) sum += gray[start + x]
  const mean = sum / width
  let variance = 0
  for (let x = 0; x < width; x++) { const d = gray[start + x] - mean; variance += d * d }
  return Math.sqrt(variance / width)
}

function colStdDev(gray, width, height, x) {
  const values = new Float64Array(height)
  for (let y = 0; y < height; y++) values[y] = gray[y * width + x]
  return stdDev(values)
}

/**
 * @param {Float64Array|number[]} gray - niveaux de gris à plat (toGrayscale).
 * @param {number} width
 * @param {number} height
 * @param {{edgeThreshold?: number, marginScan?: number, sampleStride?: number}} opts
 *   `marginScan` : fraction de chaque dimension balayée depuis le bord avant
 *   d'abandonner ce bord (défaut 0.35 — un document occupe rarement moins de
 *   65 % du cadre sur une capture terrain visée). `sampleStride` : pas
 *   d'échantillonnage (2 = une ligne/colonne sur deux, perf sans perte
 *   pratique de précision).
 * @returns {{x:number, y:number, width:number, height:number, confidence:number}}
 *   Rectangle en PIXELS + confiance ∈ [0,1].
 */
export function detectDocumentBounds(gray, width, height, {
  edgeThreshold = 14, marginScan = 0.35, sampleStride = 2,
} = {}) {
  if (!width || !height || !gray || !gray.length) {
    return { x: 0, y: 0, width: 0, height: 0, confidence: 0 }
  }

  const maxTop = Math.max(1, Math.floor(height * marginScan))
  const maxLeft = Math.max(1, Math.floor(width * marginScan))

  let top = 0
  let foundTop = false
  for (let y = 0; y < maxTop; y += sampleStride) {
    if (rowStdDev(gray, width, y) >= edgeThreshold) { top = y; foundTop = true; break }
  }
  let bottom = height - 1
  let foundBottom = false
  for (let y = height - 1; y >= height - maxTop; y -= sampleStride) {
    if (rowStdDev(gray, width, y) >= edgeThreshold) { bottom = y; foundBottom = true; break }
  }
  let left = 0
  let foundLeft = false
  for (let x = 0; x < maxLeft; x += sampleStride) {
    if (colStdDev(gray, width, height, x) >= edgeThreshold) { left = x; foundLeft = true; break }
  }
  let right = width - 1
  let foundRight = false
  for (let x = width - 1; x >= width - maxLeft; x -= sampleStride) {
    if (colStdDev(gray, width, height, x) >= edgeThreshold) { right = x; foundRight = true; break }
  }

  const boxW = Math.max(0, right - left + 1)
  const boxH = Math.max(0, bottom - top + 1)
  const foundCount = [foundTop, foundBottom, foundLeft, foundRight].filter(Boolean).length
  const areaRatio = (boxW * boxH) / (width * height)
  // Une boîte quasi-vide (bruit) ou quasi-cadre-entier (rien de net détecté)
  // n'est jamais « plausible » — même avec des bords « trouvés » par accident.
  const plausible = areaRatio > 0.15 && areaRatio < 0.98
  const confidence = plausible ? foundCount / 4 : 0

  return { x: left, y: top, width: boxW, height: boxH, confidence }
}

/** Rectangle en PIXELS → insets en % de chaque bord (top/right/bottom/left),
 * la forme consommée par le panneau de recadrage manuel (sliders %). */
export function boundsToInsets(bounds, width, height) {
  if (!width || !height) return { top: 0, right: 0, bottom: 0, left: 0 }
  const right = width - (bounds.x + bounds.width)
  const bottom = height - (bounds.y + bounds.height)
  const clamp = (v) => Math.min(45, Math.max(0, v))
  return {
    top: clamp((bounds.y / height) * 100),
    left: clamp((bounds.x / width) * 100),
    right: clamp((right / width) * 100),
    bottom: clamp((bottom / height) * 100),
  }
}

/** Insets en % → rectangle en PIXELS (arrondi), jamais dégénéré (au moins
 * 1×1px) même si les insets se chevauchent par une saisie extrême. */
export function insetsToBounds(insets, width, height) {
  const left = Math.round((insets.left / 100) * width)
  const top = Math.round((insets.top / 100) * height)
  const right = Math.round(width - (insets.right / 100) * width)
  const bottom = Math.round(height - (insets.bottom / 100) * height)
  return {
    x: left,
    y: top,
    width: Math.max(1, right - left),
    height: Math.max(1, bottom - top),
  }
}
