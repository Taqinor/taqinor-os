// COP2-W2 — images jointes à une question de l'assistant (capture d'un message de client).
//
// Réduites dans le NAVIGATEUR avant envoi : 1280 px au plus sur le grand côté, JPEG qualité ~0,8, puis base64
// SANS le préfixe `data:` (le corps de la requête est `images: [{media_type, data}]`). Les fonctions pures
// (`dimensionsReduites`, `sansPrefixeDataUrl`, `fichierImageOk`) n'ont aucune dépendance au DOM : elles sont
// testées sous node ; `reduireImage` a besoin du navigateur (Image + canvas).

export const COTE_MAX_PX = 1280
export const QUALITES_JPEG = Object.freeze([0.8, 0.6, 0.45])
// Le serveur refuse une image au-delà de 2 000 000 caractères de base64 : on s'arrête avant.
export const BASE64_MAX_CARACTERES = 1900000
export const TYPE_ENVOYE = 'image/jpeg'

/** Dimensions après réduction : le grand côté ≤ `max`, jamais d'agrandissement, entiers ≥ 1. */
export function dimensionsReduites(largeur, hauteur, max = COTE_MAX_PX) {
  const l = Number(largeur)
  const h = Number(hauteur)
  if (!Number.isFinite(l) || !Number.isFinite(h) || l <= 0 || h <= 0) return { largeur: 0, hauteur: 0 }
  const echelle = Math.min(1, max / Math.max(l, h))
  return { largeur: Math.max(1, Math.round(l * echelle)), hauteur: Math.max(1, Math.round(h * echelle)) }
}

/** `data:image/jpeg;base64,AAAA` → `AAAA` ; toute autre forme → chaîne vide. */
export function sansPrefixeDataUrl(dataUrl) {
  if (typeof dataUrl !== 'string') return ''
  const m = /^data:[^;,]+;base64,(.*)$/s.exec(dataUrl)
  return m ? m[1] : ''
}

/** Le fichier est-il une image (type MIME `image/*`) ? */
export const fichierImageOk = (fichier) => typeof fichier?.type === 'string' && fichier.type.startsWith('image/')

function chargerImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('image illisible'))
    img.src = url
  })
}

/**
 * Réduit un fichier image : `{ media_type: 'image/jpeg', data: <base64 sans préfixe>, apercu: <URL d'objet> }`.
 * `apercu` (la miniature de l'écran) est une URL d'objet du fichier d'origine : à RÉVOQUER par l'appelant.
 * Lève une `Error` française si l'image est illisible ou reste trop lourde même très compressée.
 */
export async function reduireImage(fichier) {
  const apercu = URL.createObjectURL(fichier)
  try {
    const img = await chargerImage(apercu)
    const { largeur, hauteur } = dimensionsReduites(img.naturalWidth || img.width, img.naturalHeight || img.height)
    if (!largeur) throw new Error('image illisible')
    const canvas = document.createElement('canvas')
    canvas.width = largeur
    canvas.height = hauteur
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('image illisible')
    // Un PNG transparent deviendrait noir en JPEG : fond blanc d'abord.
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, largeur, hauteur)
    ctx.drawImage(img, 0, 0, largeur, hauteur)
    for (const qualite of QUALITES_JPEG) {
      const data = sansPrefixeDataUrl(canvas.toDataURL(TYPE_ENVOYE, qualite))
      if (data && data.length <= BASE64_MAX_CARACTERES) return { media_type: TYPE_ENVOYE, data, apercu }
    }
    throw new Error('image trop lourde')
  } catch (err) {
    URL.revokeObjectURL(apercu)
    throw err
  }
}
