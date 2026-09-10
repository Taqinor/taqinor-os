// VT10/VT11 — vérification de la transformation affine (deux triangles) au
// cœur du drapage canvas : indépendante du DOM (pas de canvas/Image ici), les
// maths seules — reformulation locale de `affineFromTriangles` (non exportée,
// interne à roofTextureWarp.js) via `boundingBox` (exporté) pour la partie
// géométrie, et une ré-implémentation fidèle pour vérifier l'algèbre.
//   node --test src/pages/crm/visites/roofTextureWarp.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { boundingBox } from './roofTextureWarp.js'

function affineFromTriangles(src, dst) {
  const [[x0, y0], [x1, y1], [x2, y2]] = src
  const [[u0, v0], [u1, v1], [u2, v2]] = dst
  const den = x0 * (y1 - y2) - x1 * (y0 - y2) + x2 * (y0 - y1)
  if (!den) return null
  const a = (u0 * (y1 - y2) - u1 * (y0 - y2) + u2 * (y0 - y1)) / den
  const b = (v0 * (y1 - y2) - v1 * (y0 - y2) + v2 * (y0 - y1)) / den
  const c = (x0 * (u1 - u2) - x1 * (u0 - u2) + x2 * (u0 - u1)) / den
  const d = (x0 * (v1 - v2) - x1 * (v0 - v2) + x2 * (v0 - v1)) / den
  const e = u0 - (a * x0 + c * y0)
  const f = v0 - (b * x0 + d * y0)
  return [a, b, c, d, e, f]
}
const applique = (m, [x, y]) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]

test('affine — une pure translation mappe chaque sommet exactement', () => {
  const src = [[0, 0], [10, 0], [10, 10]]
  const dst = [[5, 5], [15, 5], [15, 15]]
  const m = affineFromTriangles(src, dst)
  for (let i = 0; i < 3; i += 1) {
    const [xp, yp] = applique(m, src[i])
    assert.ok(Math.abs(xp - dst[i][0]) < 1e-9)
    assert.ok(Math.abs(yp - dst[i][1]) < 1e-9)
  }
})

test('affine — une rotation 90° + échelle ×2 mappe chaque sommet exactement', () => {
  const src = [[0, 0], [1, 0], [0, 1]]
  const dst = [[0, 0], [0, 2], [-2, 0]]
  const m = affineFromTriangles(src, dst)
  for (let i = 0; i < 3; i += 1) {
    const [xp, yp] = applique(m, src[i])
    assert.ok(Math.abs(xp - dst[i][0]) < 1e-9)
    assert.ok(Math.abs(yp - dst[i][1]) < 1e-9)
  }
})

test('affine — un triangle source dégénéré (points alignés) est détecté (den=0)', () => {
  const src = [[0, 0], [1, 1], [2, 2]] // alignés
  const dst = [[0, 0], [1, 0], [2, 0]]
  assert.equal(affineFromTriangles(src, dst), null)
})

test('boundingBox — englobe les 4 poignées, jamais un cadre inventé', () => {
  const box = boundingBox([[10, 20], [30, 5], [15, 40], [0, 25]])
  assert.deepEqual(box, { x: 0, y: 5, width: 30, height: 35 })
})
