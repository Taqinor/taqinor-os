import { warpImageToQuad, boundingBox } from '../roofTextureWarp'

/* Aperçu DRAPÉ PARTAGÉ des deux écrans de calage (photo de site, calage du toit
   de la visite) : les 4 poignées CARTE sont projetées en pixels écran, le canvas
   est calé sur leur boîte englobante et l'image y est déformée sur le
   quadrilatère. Ne fait rien tant que le canvas, la carte, l'image chargée ou
   les 4 poignées manquent. */
export function dessinerApercuDrape({ canvas, map, image, markers, opacite }) {
  if (!canvas || !map || !image?.complete) return
  const points = markers.map((m) => {
    const p = map.latLngToContainerPoint(m.getLatLng())
    return [p.x, p.y]
  })
  if (points.length !== 4) return
  const box = boundingBox(points)
  canvas.width = Math.max(1, Math.round(box.width))
  canvas.height = Math.max(1, Math.round(box.height))
  canvas.style.left = `${box.x}px`
  canvas.style.top = `${box.y}px`
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const decale = points.map(([x, y]) => [x - box.x, y - box.y])
  ctx.globalAlpha = opacite
  warpImageToQuad(ctx, image, decale)
}
