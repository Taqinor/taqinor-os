/* ACAL529 — carte → photo : les modules posés PROJETÉS sur la photo de site calée.
   Le calage `[lat, lng]` (ordre NO, NE, SE, SO) pose les 4 coins de l'image sur 4 points
   géographiques ; l'homographie entre ces 4 points et les 4 coins de l'image donne le pixel de
   n'importe quel point (toit SUPPOSÉ plan). Aucune écriture : rendu à la demande. */

/** Résout A·x = b (Gauss avec pivot partiel), A carrée. */
function resoudre(A, b) {
  const n = b.length
  const M = A.map((l, i) => [...l, b[i]])
  for (let c = 0; c < n; c += 1) {
    let p = c
    for (let r = c + 1; r < n; r += 1) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r
    ;[M[c], M[p]] = [M[p], M[c]]
    for (let r = 0; r < n; r += 1) {
      if (r === c) continue
      const f = M[r][c] / M[c][c]
      for (let k = c; k <= n; k += 1) M[r][k] -= f * M[c][k]
    }
  }
  return M.map((l, i) => l[n] / l[i])
}

/** `(lng, lat) → [px, py]` : l'homographie des 4 coins de calage vers les 4 coins d'une image largeur × hauteur. */
export function versPixelsPhoto(calage, largeur, hauteur) {
  const centre = calage.reduce((s, [lat, lng]) => [s[0] + lat / 4, s[1] + lng / 4], [0, 0])
  const echelle = Math.cos((centre[0] * Math.PI) / 180)
  const plan = (lng, lat) => [(lng - centre[1]) * echelle, lat - centre[0]]
  const cibles = [[0, 0], [largeur, 0], [largeur, hauteur], [0, hauteur]]
  const A = []
  const b = []
  calage.forEach(([lat, lng], i) => {
    const [x, y] = plan(lng, lat)
    const [u, v] = cibles[i]
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y])
    b.push(u, v)
  })
  const h = resoudre(A, b)
  return (lng, lat) => {
    const [x, y] = plan(lng, lat)
    const w = h[6] * x + h[7] * y + 1
    return [(h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w]
  }
}

/** Dessine l'image puis chaque module (`pans[].quads`, lng/lat) sur le canvas, à la taille native de l'image. */
export function dessinerSurPhoto(canvas, image, calage, pans) {
  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight
  const ctx = canvas.getContext('2d')
  ctx.drawImage(image, 0, 0)
  const px = versPixelsPhoto(calage, canvas.width, canvas.height)
  ctx.lineWidth = Math.max(1, canvas.width / 600)
  ctx.strokeStyle = '#ffffff'
  ctx.fillStyle = 'rgba(30, 90, 200, 0.45)'
  for (const pan of pans) {
    for (const quad of pan.quads) {
      ctx.beginPath()
      quad.forEach(([lng, lat], i) => {
        const [x, y] = px(lng, lat)
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
      })
      ctx.closePath()
      ctx.fill()
      ctx.stroke()
    }
  }
}
