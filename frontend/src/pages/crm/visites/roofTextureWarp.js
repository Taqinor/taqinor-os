// VT11 — transformation perspective sur canvas : drape une image (le toit
// assemblé/choisi) sur un quadrilatère de destination (les 4 coins calés sur
// la carte, projetés en pixels écran). PUR calcul + dessin canvas, aucune
// dépendance réseau/DOM au-delà de `CanvasRenderingContext2D`/`HTMLImageElement`
// déjà fournis par l'appelant — testable en isolant les maths (VT10).
//
// Méthode standard (aucune lib) : un quad se drape en canvas en le découpant
// en DEUX triangles, chacun dessiné via une transformation AFFINE (canvas ne
// sait faire qu'affine, pas une vraie perspective — c'est l'approximation
// universellement utilisée pour ce genre d'aperçu, jamais une reconstruction
// 3D — cohérent avec l'interdiction fondateur de photogrammétrie serveur).

// Résout la matrice affine [a,b,c,d,e,f] telle que chaque point source
// [sx,sy] du triangle se retrouve en [dx,dy] du triangle destination.
function affineFromTriangles(src, dst) {
  const [[x0, y0], [x1, y1], [x2, y2]] = src
  const [[u0, v0], [u1, v1], [u2, v2]] = dst
  const den = x0 * (y1 - y2) - x1 * (y0 - y2) + x2 * (y0 - y1)
  if (!den) return null // triangle dégénéré (points alignés) — rien à dessiner
  const a = (u0 * (y1 - y2) - u1 * (y0 - y2) + u2 * (y0 - y1)) / den
  const b = (v0 * (y1 - y2) - v1 * (y0 - y2) + v2 * (y0 - y1)) / den
  const c = (x0 * (u1 - u2) - x1 * (u0 - u2) + x2 * (u0 - u1)) / den
  const d = (x0 * (v1 - v2) - x1 * (v0 - v2) + x2 * (v0 - v1)) / den
  // e/f se déduisent directement de a-d en réinjectant le premier point.
  const e = u0 - (a * x0 + c * y0)
  const f = v0 - (b * x0 + d * y0)
  return [a, b, c, d, e, f]
}

function drawWarpedTriangle(ctx, image, srcTri, dstTri) {
  const m = affineFromTriangles(srcTri, dstTri)
  if (!m) return
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(dstTri[0][0], dstTri[0][1])
  ctx.lineTo(dstTri[1][0], dstTri[1][1])
  ctx.lineTo(dstTri[2][0], dstTri[2][1])
  ctx.closePath()
  ctx.clip()
  ctx.transform(...m)
  ctx.drawImage(image, 0, 0)
  ctx.restore()
}

/**
 * Drape `image` en entier sur le quadrilatère `dstQuad` (4 points [x,y] en
 * pixels canvas, ordre coin1→coin2→coin3→coin4 — le MÊME ordre que les 4
 * poignées de la carte). `ctx` n'est PAS effacé par cette fonction (l'appelant
 * choisit quand clearRect).
 */
export function warpImageToQuad(ctx, image, dstQuad) {
  if (!image || dstQuad.length !== 4) return
  const w = image.naturalWidth || image.width
  const h = image.naturalHeight || image.height
  if (!w || !h) return
  const srcQuad = [[0, 0], [w, 0], [w, h], [0, h]]
  drawWarpedTriangle(ctx, image, [srcQuad[0], srcQuad[1], srcQuad[2]], [dstQuad[0], dstQuad[1], dstQuad[2]])
  drawWarpedTriangle(ctx, image, [srcQuad[0], srcQuad[2], srcQuad[3]], [dstQuad[0], dstQuad[2], dstQuad[3]])
}

// Boîte englobante d'un quad — sert à dimensionner/positionner le canvas
// d'aperçu par rapport aux 4 poignées projetées.
export function boundingBox(points) {
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  return {
    x: Math.min(...xs), y: Math.min(...ys),
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  }
}
