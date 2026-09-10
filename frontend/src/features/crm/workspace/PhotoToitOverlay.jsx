/* VT13 (fondateur 10/09/2026) — LA PHOTO RÉELLE DU TOIT EN CALQUE DE FOND.
   ---------------------------------------------------------------------------
   Un `<canvas>` qui drape l'image assemblée en visite terrain (VT9) sur ses 4
   coins calés (VT11), DANS le repère de dessin du contour du toit — donc
   exactement SOUS le tracé, jamais un aperçu posé à côté.

   POURQUOI UN CANVAS ET PAS UNE `<image>` SVG : draper un quadrilatère demande
   une transformation par triangles (`roofTextureWarp.js`, VT11) ; SVG ne sait
   faire qu'un affine global. On réutilise la fonction de VT11 telle quelle —
   aucune seconde implémentation du drapage dans le dépôt.

   POURQUOI `object-fit: contain` : le bitmap du canvas est dans les MÊMES
   unités que le `viewBox` du contour ; `contain` reproduit exactement le
   `preserveAspectRatio="xMidYMid meet"` du SVG posé par-dessus, donc les deux
   couches restent superposées à toute taille d'écran.

   RIEN N'EST INVENTÉ : sans charge exploitable (pas d'url, pas de 4 coins
   plausibles, image illisible), le composant rend `null` — aucun cadre vide,
   aucune image approximative. Le builder 3D vendored n'est pas touché : ce
   calque flotte AU-DESSUS de sa carte, en `pointer-events: none`. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { warpImageToQuad } from '../../../pages/crm/visites/roofTextureWarp'
import { quadPhotoToit } from './photoToit'

// Marge du viewBox du contour (`-2 -2 largeur+4 hauteur+4`, traceToit.js) :
// le bitmap du canvas la reprend pour rester aligné au pixel près.
const MARGE = 2

export default function PhotoToitOverlay({
  dessin = null, texture = null, visible = true, className = '',
}) {
  const canvasRef = useRef(null)
  // L'image chargée est mémorisée AVEC son url : c'est ce qui permet de ne
  // jamais appeler `setState` dans le corps de l'effet (react-hooks v7,
  // `set-state-in-effect`) tout en n'affichant jamais l'image d'une autre
  // visite — une url périmée ne correspond simplement plus.
  const [chargee, setChargee] = useState(null)

  const cadre = useMemo(
    () => (texture ? quadPhotoToit(dessin, texture.coins) : null),
    [dessin, texture],
  )
  const url = texture?.url ?? null
  const drapable = Boolean(cadre && url && visible)
  const image = chargee && chargee.url === url ? chargee.image : null

  useEffect(() => {
    // Aucune requête réseau spéculative : rien n'est chargé tant qu'il n'y a
    // rien à draper.
    if (!drapable) return undefined
    let vivant = true
    const img = new Image()
    // La photo est servie par le proxy Django de la MÊME origine — pas de CORS
    // à négocier, et le canvas ne devient jamais « tainted ».
    img.onload = () => { if (vivant) setChargee({ url, image: img }) }
    img.onerror = () => { if (vivant) setChargee({ url, image: null }) }
    img.src = url
    return () => { vivant = false }
  }, [drapable, url])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !cadre) return
    // Un contexte 2D indisponible (jsdom sans le paquet `canvas`, navigateur
    // exotique) n'est pas une erreur : le calque ne se dessine simplement pas.
    let ctx = null
    try {
      ctx = canvas.getContext?.('2d') ?? null
    } catch {
      ctx = null
    }
    if (!ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!image) return
    ctx.save()
    // Le viewBox du contour commence à (-2, -2) : on décale le bitmap d'autant
    // pour que les coordonnées projetées y tombent juste.
    ctx.translate(MARGE, MARGE)
    warpImageToQuad(ctx, image, cadre.quad)
    ctx.restore()
  }, [image, cadre])

  if (!drapable) return null

  return (
    <canvas
      ref={canvasRef}
      className={`lw-photo-toit ${className}`.trim()}
      data-testid="photo-toit-overlay"
      data-visite-id={texture?.visiteId ?? undefined}
      width={Math.round(cadre.largeur + MARGE * 2)}
      height={Math.round(cadre.hauteur + MARGE * 2)}
      aria-hidden="true"
    />
  )
}
