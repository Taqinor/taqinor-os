// XGED12 — Helpers PURS (sans React) pour l'écran « Numériser » (capture
// mobile photo → PDF multi-pages). Le recadrage/rotation se fait CÔTÉ CLIENT
// via un `<canvas>` (aucune dépendance npm) — cette fonction transforme un
// `Blob` image en un nouveau `Blob` pivoté par un multiple de 90°, prêt à être
// envoyé au serveur qui assemble le PDF (Pillow, `apps/ged`).
//
// Testable sans DOM réel de navigateur : les tests fournissent un `canvasFactory`
// (jsdom ne supporte pas `getContext('2d')` nativement) — en production,
// `rotateImageBlob` utilise `document.createElement('canvas')` par défaut.

// Dimensions (largeur, hauteur) résultantes d'une rotation de `degrees`
// (multiple de 90, positif ou négatif) appliquée à une image `w`×`h`. Une
// rotation impaire (90/270) permute largeur et hauteur ; une rotation paire
// (0/180) les conserve. Fonction pure, utilisée pour dimensionner le canvas
// AVANT de dessiner.
export function rotatedDims(w, h, degrees) {
  const norm = ((Math.round(degrees / 90) * 90) % 360 + 360) % 360
  return norm === 90 || norm === 270 ? { width: h, height: w } : { width: w, height: h }
}

// Normalise un angle quelconque à l'un des 4 crans supportés (0/90/180/270).
export function normalizeRotation(degrees) {
  return ((Math.round(degrees / 90) * 90) % 360 + 360) % 360
}

// Ordre de dessin canvas (translate + rotate) pour chaque cran, en repartant
// du coin (0,0) du canvas DÉJÀ dimensionné par `rotatedDims`. Fonction pure —
// renvoie les paramètres de la transformation, ne touche à aucun canvas réel
// (permet de la tester sans DOM).
export function rotationTransform(norm, w, h) {
  switch (norm) {
    case 90: return { translateX: h, translateY: 0, angleRad: Math.PI / 2 }
    case 180: return { translateX: w, translateY: h, angleRad: Math.PI }
    case 270: return { translateX: 0, translateY: w, angleRad: (3 * Math.PI) / 2 }
    default: return { translateX: 0, translateY: 0, angleRad: 0 }
  }
}

// Pivote un `Blob` image d'un multiple de 90° via un canvas hors-écran, renvoie
// une Promise<Blob> JPEG. `degrees` : 0/90/180/270 (ou tout multiple — normalisé).
// Utilise `document`/`Image`/`URL` du navigateur — appelée uniquement côté
// client (jamais côté serveur, qui assemble le PDF final avec Pillow).
export function rotateImageBlob(blob, degrees, { quality = 0.9 } = {}) {
  const norm = normalizeRotation(degrees)
  if (norm === 0) return Promise.resolve(blob)
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob)
    const img = new Image()
    img.onload = () => {
      try {
        const { width, height } = rotatedDims(img.width, img.height, norm)
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        const { translateX, translateY, angleRad } = rotationTransform(
          norm, img.width, img.height)
        ctx.translate(translateX, translateY)
        ctx.rotate(angleRad)
        ctx.drawImage(img, 0, 0)
        canvas.toBlob(
          (out) => { URL.revokeObjectURL(url); resolve(out) },
          'image/jpeg', quality)
      } catch (err) {
        URL.revokeObjectURL(url)
        reject(err)
      }
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('image illisible')) }
    img.src = url
  })
}

// État pur d'une page capturée : construit l'entrée de liste affichée par
// l'écran « Numériser » (aperçu + rotation courante). `id` doit être stable
// (fourni par l'appelant, ex. incrément) — jamais recalculé depuis l'index
// (permet la suppression sans décalage des clés React).
export function makeCapturedPage(id, file) {
  return { id, file, rotation: 0 }
}

// Fait tourner la rotation ENREGISTRÉE d'une page de +90° (boucle 0→360).
// Fonction pure sur la liste de pages ; ne touche à aucun Blob — la rotation
// réelle du Blob (via `rotateImageBlob`) n'est appliquée qu'à la validation
// (avant upload), pour éviter de re-encoder à chaque clic.
export function rotatePageInList(pages, id) {
  return pages.map((p) => (p.id === id
    ? { ...p, rotation: normalizeRotation(p.rotation + 90) }
    : p))
}

export function removePageFromList(pages, id) {
  return pages.filter((p) => p.id !== id)
}
